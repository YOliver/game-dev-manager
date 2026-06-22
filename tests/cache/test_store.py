"""测试 cache.store：DB CRUD + 递归查询 + LRU。"""

import pytest

from gdm.core.cache import CachedEntry
from gdm.core.cache import db, store


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "cache.db"
    c = db.open_connection(db_path)
    db.init_schema(c)
    yield c
    c.close()


def _entry(folder, name, mtime=100, size=1000, thumb=None):
    return CachedEntry(
        folder_path=folder, file_name=name,
        width=32, height=32, size=size, format="PNG", color_mode="RGBA",
        mtime_ns=mtime, thumb_blob=thumb,
        thumb_mtime_ns=mtime if thumb else None,
    )


class TestUpsert:
    def test_upsert_then_get(self, conn):
        store.upsert_folder(conn, "d/a", now=1000)
        store.upsert_entry(conn, _entry("d/a", "x.png", thumb=b"BLOB"))
        rows = store.get_entries(conn, "d", recursive=True)
        assert len(rows) == 1
        assert rows[0].file_name == "x.png"
        assert rows[0].thumb_blob == b"BLOB"

    def test_upsert_replaces_existing(self, conn):
        store.upsert_folder(conn, "d/a", now=1000)
        store.upsert_entry(conn, _entry("d/a", "x.png", mtime=100))
        store.upsert_entry(conn, _entry("d/a", "x.png", mtime=200))
        rows = store.get_entries(conn, "d", recursive=True)
        assert len(rows) == 1
        assert rows[0].mtime_ns == 200


class TestRecursiveQuery:
    def test_returns_root_and_descendants(self, conn):
        store.upsert_folder(conn, "d", now=1000)
        store.upsert_folder(conn, "d/sub", now=1000)
        store.upsert_folder(conn, "d/sub/nested", now=1000)
        store.upsert_entry(conn, _entry("d", "root.png"))
        store.upsert_entry(conn, _entry("d/sub", "sub.png"))
        store.upsert_entry(conn, _entry("d/sub/nested", "nested.png"))
        rows = store.get_entries(conn, "d", recursive=True)
        names = sorted(r.file_name for r in rows)
        assert names == ["nested.png", "root.png", "sub.png"]

    def test_does_not_match_sibling_with_common_prefix(self, conn):
        """查询 d 不应命中 d_other（前缀同名但非子目录）。"""
        store.upsert_folder(conn, "d", now=1000)
        store.upsert_folder(conn, "d_other", now=1000)
        store.upsert_entry(conn, _entry("d", "a.png"))
        store.upsert_entry(conn, _entry("d_other", "b.png"))
        rows = store.get_entries(conn, "d", recursive=True)
        assert {r.file_name for r in rows} == {"a.png"}


class TestDelete:
    def test_delete_entries(self, conn):
        store.upsert_folder(conn, "d", now=1000)
        store.upsert_entry(conn, _entry("d", "a.png"))
        store.upsert_entry(conn, _entry("d", "b.png"))
        store.delete_entries(conn, [("d", "a.png")])
        rows = store.get_entries(conn, "d", recursive=True)
        assert {r.file_name for r in rows} == {"b.png"}

    def test_delete_folders_under_cascades(self, conn):
        store.upsert_folder(conn, "d", now=1000)
        store.upsert_folder(conn, "d/sub", now=1000)
        store.upsert_entry(conn, _entry("d", "a.png"))
        store.upsert_entry(conn, _entry("d/sub", "b.png"))
        store.delete_folders_under(conn, "d")
        rows = store.get_entries(conn, "d", recursive=True)
        assert rows == []


class TestTouch:
    def test_touch_folders_under_updates_access_time(self, conn):
        store.upsert_folder(conn, "d", now=1000)
        store.upsert_folder(conn, "d/sub", now=1000)
        store.touch_folders_under(conn, "d", now=2000)
        rows = list(conn.execute(
            "SELECT folder_path, last_access_at FROM folders ORDER BY folder_path"
        ))
        assert rows == [("d", 2000), ("d/sub", 2000)]


class TestEvictLRU:
    def test_evicts_oldest_when_over_limit(self, conn, monkeypatch):
        monkeypatch.setattr(db, "MAX_CACHED_FOLDERS", 3)
        for i, t in enumerate([100, 200, 300, 400]):
            store.upsert_folder(conn, f"d{i}", now=t)
        store.evict_lru_if_needed(conn)
        remaining = sorted(
            row[0] for row in conn.execute("SELECT folder_path FROM folders")
        )
        # 最老的 d0 (last_access_at=100) 被淘汰
        assert remaining == ["d1", "d2", "d3"]

    def test_cascade_removes_entries(self, conn, monkeypatch):
        monkeypatch.setattr(db, "MAX_CACHED_FOLDERS", 1)
        store.upsert_folder(conn, "d0", now=100)
        store.upsert_folder(conn, "d1", now=200)
        store.upsert_entry(conn, _entry("d0", "x.png"))
        store.upsert_entry(conn, _entry("d1", "y.png"))
        store.evict_lru_if_needed(conn)
        rows = list(conn.execute("SELECT file_name FROM entries"))
        assert rows == [("y.png",)]


class TestClearAll:
    def test_clear_all_empties_both_tables(self, conn):
        store.upsert_folder(conn, "d", now=1000)
        store.upsert_entry(conn, _entry("d", "a.png"))
        store.clear_all(conn)
        assert list(conn.execute("SELECT * FROM folders")) == []
        assert list(conn.execute("SELECT * FROM entries")) == []


class TestUpdateFolderCounts:
    def test_counts_root_and_subdirs(self, conn):
        store.upsert_folder(conn, "d", now=1000)
        store.upsert_folder(conn, "d/sub", now=1000)
        store.upsert_folder(conn, "d/sub/nested", now=1000)
        store.upsert_entry(conn, _entry("d", "a.png"))
        store.upsert_entry(conn, _entry("d", "b.png"))
        store.upsert_entry(conn, _entry("d/sub", "c.png"))
        store.upsert_entry(conn, _entry("d/sub/nested", "d.png"))
        conn.commit()

        store.update_folder_counts(conn, "d", recursive=True)

        rows = {
            r[0]: r[1]
            for r in conn.execute(
                "SELECT folder_path, entry_count FROM folders"
            ).fetchall()
        }
        assert rows == {"d": 4, "d/sub": 2, "d/sub/nested": 1}

    def test_zero_count_when_no_entries(self, conn):
        store.upsert_folder(conn, "d", now=1000)
        conn.commit()

        store.update_folder_counts(conn, "d", recursive=True)

        (count,) = conn.execute(
            "SELECT entry_count FROM folders WHERE folder_path = ?", ("d",)
        ).fetchone()
        assert count == 0

    def test_unrelated_folder_not_affected(self, conn):
        store.upsert_folder(conn, "d", now=1000)
        store.upsert_folder(conn, "other", now=1000)
        store.upsert_entry(conn, _entry("d", "a.png"))
        conn.commit()

        store.update_folder_counts(conn, "d", recursive=True)

        (other_count,) = conn.execute(
            "SELECT entry_count FROM folders WHERE folder_path = ?", ("other",)
        ).fetchone()
        assert other_count == 0  # other 不受影响

    def test_ancestor_folders_created(self, conn):
        """中间祖先目录没有直接文件时，_ensure_ancestor_folders 自动补行。"""
        # 只创建最深层的叶子目录
        store.upsert_folder(conn, "d/sub/deep", now=1000)
        store.upsert_entry(conn, _entry("d/sub/deep", "x.png"))
        conn.commit()

        store.update_folder_counts(conn, "d", recursive=True)

        # d 和 d/sub 应被自动补行
        rows = {
            r[0]: r[1]
            for r in conn.execute(
                "SELECT folder_path, entry_count FROM folders ORDER BY folder_path"
            ).fetchall()
        }
        assert rows == {
            "d": 1,
            "d/sub": 1,
            "d/sub/deep": 1,
        }


class TestNonRecursiveQuery:
    def test_only_current_folder(self, conn):
        store.upsert_folder(conn, "d", now=1000)
        store.upsert_folder(conn, "d/sub", now=1000)
        store.upsert_entry(conn, _entry("d", "root.png"))
        store.upsert_entry(conn, _entry("d/sub", "sub.png"))
        rows = store.get_entries(conn, "d", recursive=False)
        names = {r.file_name for r in rows}
        assert names == {"root.png"}

    def test_empty_when_no_direct_files(self, conn):
        store.upsert_folder(conn, "d", now=1000)
        store.upsert_folder(conn, "d/sub", now=1000)
        store.upsert_entry(conn, _entry("d/sub", "sub.png"))
        rows = store.get_entries(conn, "d", recursive=False)
        assert rows == []


class TestUpdateFolderCountsNonRecursive:
    def test_only_current_folder_count(self, conn):
        store.upsert_folder(conn, "d", now=1000)
        store.upsert_folder(conn, "d/sub", now=1000)
        store.upsert_entry(conn, _entry("d", "a.png"))
        store.upsert_entry(conn, _entry("d/sub", "b.png"))
        conn.commit()
        store.update_folder_counts(conn, "d", recursive=False)
        (count,) = conn.execute(
            "SELECT entry_count FROM folders WHERE folder_path = ?", ("d",)
        ).fetchone()
        assert count == 1  # 仅 a.png，不包含 b.png
