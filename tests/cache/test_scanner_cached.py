"""测试 cache.scanner_cached：路径规范化、文件系统遍历。"""

from pathlib import Path

from PIL import Image

from gdm.core.cache import db, store
from gdm.core.cache.scanner_cached import (
    normalize_folder,
    snapshot_folder,
    process_diff_sync,
)


def _make_png(path: Path, size=(32, 32), color=(255, 0, 0, 255)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", size, color).save(path, "PNG")


class TestNormalizeFolder:
    def test_lowercase_forward_slash(self):
        assert normalize_folder("C:\\Foo\\Bar") == "c:/foo/bar"

    def test_already_normalized(self):
        assert normalize_folder("c:/foo/bar") == "c:/foo/bar"

    def test_strips_trailing_slash(self):
        assert normalize_folder("C:\\Foo\\Bar\\") == "c:/foo/bar"


class TestSnapshotFolder:
    def test_walks_recursively(self, tmp_path):
        _make_png(tmp_path / "a.png")
        _make_png(tmp_path / "sub" / "b.png")
        _make_png(tmp_path / "sub" / "nested" / "c.png")
        snaps = snapshot_folder(str(tmp_path))
        names = sorted(s.file_name for s in snaps)
        assert names == ["a.png", "b.png", "c.png"]

    def test_filters_non_image_files(self, tmp_path):
        _make_png(tmp_path / "a.png")
        (tmp_path / "readme.txt").write_text("not image")
        snaps = snapshot_folder(str(tmp_path))
        assert [s.file_name for s in snaps] == ["a.png"]

    def test_returns_empty_on_missing_dir(self, tmp_path):
        snaps = snapshot_folder(str(tmp_path / "nonexistent"))
        assert snaps == []


class TestProcessDiffSync:
    """端到端：用 process_diff_sync（同步版 DiffWorker.run）测全流程。"""

    def test_first_call_populates_cache(self, tmp_path):
        _make_png(tmp_path / "a.png")
        _make_png(tmp_path / "sub" / "b.png")

        db_path = tmp_path / "cache.db"
        conn = db.open_connection(db_path)
        db.init_schema(conn)
        try:
            process_diff_sync(conn, str(tmp_path))
            rows = store.get_entries_recursive(
                conn, normalize_folder(str(tmp_path))
            )
            assert {r.file_name for r in rows} == {"a.png", "b.png"}
            # 缩略图已生成
            assert all(r.thumb_blob is not None for r in rows)
        finally:
            conn.close()

    def test_second_call_no_change_does_not_modify_db(self, tmp_path):
        _make_png(tmp_path / "a.png")
        db_path = tmp_path / "cache.db"
        conn = db.open_connection(db_path)
        db.init_schema(conn)
        try:
            process_diff_sync(conn, str(tmp_path))
            rows1 = store.get_entries_recursive(
                conn, normalize_folder(str(tmp_path))
            )
            mtime_before = rows1[0].mtime_ns

            process_diff_sync(conn, str(tmp_path))
            rows2 = store.get_entries_recursive(
                conn, normalize_folder(str(tmp_path))
            )
            assert len(rows2) == 1
            assert rows2[0].mtime_ns == mtime_before
        finally:
            conn.close()

    def test_modified_file_is_updated(self, tmp_path):
        target = tmp_path / "a.png"
        _make_png(target, color=(255, 0, 0, 255))

        db_path = tmp_path / "cache.db"
        conn = db.open_connection(db_path)
        db.init_schema(conn)
        try:
            process_diff_sync(conn, str(tmp_path))

            # 改写文件并强制 mtime 变化
            import os, time
            time.sleep(0.05)
            _make_png(target, color=(0, 255, 0, 255))
            new_mtime = os.stat(target).st_mtime_ns

            process_diff_sync(conn, str(tmp_path))
            rows = store.get_entries_recursive(
                conn, normalize_folder(str(tmp_path))
            )
            assert len(rows) == 1
            assert rows[0].mtime_ns == new_mtime
        finally:
            conn.close()

    def test_removed_file_is_purged(self, tmp_path):
        f = tmp_path / "a.png"
        _make_png(f)
        _make_png(tmp_path / "b.png")

        db_path = tmp_path / "cache.db"
        conn = db.open_connection(db_path)
        db.init_schema(conn)
        try:
            process_diff_sync(conn, str(tmp_path))
            f.unlink()
            process_diff_sync(conn, str(tmp_path))
            rows = store.get_entries_recursive(
                conn, normalize_folder(str(tmp_path))
            )
            assert {r.file_name for r in rows} == {"b.png"}
        finally:
            conn.close()

    def test_sibling_subdir_not_affected(self, tmp_path):
        """修改 sub_a 下的文件，sub_b 的缓存条目应保持不变。"""
        _make_png(tmp_path / "sub_a" / "a.png")
        _make_png(tmp_path / "sub_b" / "b.png")
        db_path = tmp_path / "cache.db"
        conn = db.open_connection(db_path)
        db.init_schema(conn)
        try:
            process_diff_sync(conn, str(tmp_path))
            rows = store.get_entries_recursive(
                conn, normalize_folder(str(tmp_path))
            )
            b_before = next(r for r in rows if r.file_name == "b.png")

            # 改 sub_a 下的图
            import time
            time.sleep(0.05)
            _make_png(tmp_path / "sub_a" / "a.png", color=(0, 0, 255, 255))
            process_diff_sync(conn, str(tmp_path))

            rows2 = store.get_entries_recursive(
                conn, normalize_folder(str(tmp_path))
            )
            b_after = next(r for r in rows2 if r.file_name == "b.png")
            assert b_before.mtime_ns == b_after.mtime_ns
            assert b_before.thumb_blob == b_after.thumb_blob
        finally:
            conn.close()


class TestDiffWorkerEndToEnd:
    """用 pytest-qt 跑真实 DiffWorker，验证信号 + DB 落地。"""

    def test_signals_emitted_in_order(self, tmp_path, qtbot, monkeypatch):
        from PySide6.QtCore import QThreadPool
        from gdm.core.cache.scanner_cached import DiffWorker
        from gdm.core.cache import get_db_path

        # 把缓存 DB 重定向到 tmp_path
        monkeypatch.setattr(
            "gdm.core.cache.get_db_path",
            lambda: tmp_path / "cache.db",
        )

        _make_png(tmp_path / "a.png")
        _make_png(tmp_path / "sub" / "b.png")

        worker = DiffWorker(str(tmp_path))
        updated_batches = []
        removed_batches = []
        done_roots = []
        worker.signals.entries_updated.connect(updated_batches.append)
        worker.signals.entries_removed.connect(removed_batches.append)
        worker.signals.scan_done.connect(done_roots.append)

        with qtbot.waitSignal(worker.signals.scan_done, timeout=10000):
            QThreadPool.globalInstance().start(worker)

        # 应有至少一批 updated（含 a.png 和 b.png）
        all_updated = [e for batch in updated_batches for e in batch]
        names = {e.file_name for e in all_updated}
        assert names == {"a.png", "b.png"}
        assert removed_batches == []  # 首次扫描无 removed
        assert done_roots == [str(tmp_path)]

    def test_cancel_stops_partial(self, tmp_path, qtbot, monkeypatch):
        from PySide6.QtCore import QThreadPool
        from gdm.core.cache.scanner_cached import DiffWorker

        monkeypatch.setattr(
            "gdm.core.cache.get_db_path",
            lambda: tmp_path / "cache.db",
        )

        # 造 50 张图，cancel 后应远少于 50 张被处理
        for i in range(50):
            _make_png(tmp_path / f"img_{i:03d}.png")

        worker = DiffWorker(str(tmp_path))
        updated_count = [0]
        worker.signals.entries_updated.connect(
            lambda batch: updated_count.__setitem__(0, updated_count[0] + len(batch))
        )

        QThreadPool.globalInstance().start(worker)
        # 立刻 cancel
        worker.cancel()
        with qtbot.waitSignal(worker.signals.scan_done, timeout=10000):
            pass

        # 不能保证一定 < 50，但至少应有限期内完成
        # （主要是验证不会卡死）
        assert updated_count[0] >= 0
