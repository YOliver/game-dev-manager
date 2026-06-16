"""测试纯函数 compute_diff()"""

from gdm.core.cache import CachedEntry
from gdm.core.cache.diff import compute_diff, FileSnapshot


def _entry(folder, name, mtime=1000, size=100):
    return CachedEntry(
        folder_path=folder, file_name=name,
        width=10, height=10, size=size, format="PNG", color_mode="RGB",
        mtime_ns=mtime, thumb_blob=None, thumb_mtime_ns=None,
    )


def _snap(folder, name, mtime=1000, size=100):
    return FileSnapshot(folder_path=folder, file_name=name, mtime_ns=mtime, size=size)


class TestComputeDiff:
    def test_all_empty(self):
        added, changed, removed = compute_diff([], [])
        assert added == [] and changed == [] and removed == []

    def test_only_added(self):
        cached = []
        current = [_snap("d", "a.png"), _snap("d", "b.png")]
        added, changed, removed = compute_diff(cached, current)
        assert added == current
        assert changed == [] and removed == []

    def test_only_removed(self):
        cached = [_entry("d", "a.png")]
        current = []
        added, changed, removed = compute_diff(cached, current)
        assert added == [] and changed == []
        assert removed == [("d", "a.png")]

    def test_changed_by_mtime(self):
        cached = [_entry("d", "a.png", mtime=1000, size=100)]
        current = [_snap("d", "a.png", mtime=2000, size=100)]
        added, changed, removed = compute_diff(cached, current)
        assert added == [] and removed == []
        assert changed == current

    def test_changed_by_size_same_mtime(self):
        cached = [_entry("d", "a.png", mtime=1000, size=100)]
        current = [_snap("d", "a.png", mtime=1000, size=200)]
        added, changed, removed = compute_diff(cached, current)
        assert changed == current

    def test_unchanged_when_mtime_and_size_match(self):
        cached = [_entry("d", "a.png", mtime=1000, size=100)]
        current = [_snap("d", "a.png", mtime=1000, size=100)]
        added, changed, removed = compute_diff(cached, current)
        assert added == [] and changed == [] and removed == []

    def test_same_filename_in_different_folders_not_confused(self):
        """同名文件在不同子目录中不应误判为同一项。"""
        cached = [_entry("d/sub1", "x.png"), _entry("d/sub2", "x.png")]
        # 删除 sub1/x.png，新增 sub3/x.png
        current = [_snap("d/sub2", "x.png"), _snap("d/sub3", "x.png")]
        added, changed, removed = compute_diff(cached, current)
        assert removed == [("d/sub1", "x.png")]
        assert len(added) == 1 and added[0].folder_path == "d/sub3"
        assert changed == []

    def test_multi_folder_mixed_operations(self):
        cached = [
            _entry("d/a", "1.png"),
            _entry("d/a", "2.png", mtime=1000),
            _entry("d/b", "3.png"),
        ]
        current = [
            _snap("d/a", "1.png"),                   # unchanged
            _snap("d/a", "2.png", mtime=9999),       # changed
            _snap("d/b", "4.png"),                   # added (3.png removed)
        ]
        added, changed, removed = compute_diff(cached, current)
        assert [s.file_name for s in added] == ["4.png"]
        assert [s.file_name for s in changed] == ["2.png"]
        assert removed == [("d/b", "3.png")]
