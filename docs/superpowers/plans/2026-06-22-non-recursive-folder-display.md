# 目录显示非递归化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 点击任意目录时只显示当前目录的直接图片，不再递归展示子目录的图片。

**Architecture:** 为 `store.get_entries`、`snapshot_folder`、`process_diff_sync`、`update_folder_counts` 添加 `recursive` 参数（默认 `False`），入口调用方显式传入 `recursive=False`。改动集中在 3 个源文件 + 2 个测试文件。

**Tech Stack:** Python 3, SQLite, PySide6

---

### Task 1: `store.py` — `get_entries_recursive` 重命名为 `get_entries`，加 `recursive` 参数

**Files:**
- Modify: `gdm/core/cache/store.py:87-113`

- [ ] **Step 1: 修改函数签名和内部逻辑**

```python
def get_entries(
    conn: sqlite3.Connection, root: str, *, recursive: bool = False
) -> List[CachedEntry]:
    """返回 root 下的缓存条目。

    Args:
        conn: 数据库连接
        root: 目录路径（已规范化）
        recursive: True 时递归包含所有子目录；False 时仅当前目录

    Returns:
        CachedEntry 列表
    """
    if recursive:
        prefix = root + "/%"
        rows = conn.execute(
            """
            SELECT folder_path, file_name, mtime_ns, size,
                   width, height, format, color_mode,
                   thumb_blob, thumb_mtime_ns
            FROM entries
            WHERE folder_path = ? OR folder_path LIKE ?
            """,
            (root, prefix),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT folder_path, file_name, mtime_ns, size,
                   width, height, format, color_mode,
                   thumb_blob, thumb_mtime_ns
            FROM entries
            WHERE folder_path = ?
            """,
            (root,),
        ).fetchall()
    return [
        CachedEntry(
            folder_path=r[0], file_name=r[1], mtime_ns=r[2], size=r[3],
            width=r[4] if r[4] is not None else 0,
            height=r[5] if r[5] is not None else 0,
            format=r[6] or "UNKNOWN",
            color_mode=r[7] or "UNKNOWN",
            thumb_blob=r[8],
            thumb_mtime_ns=r[9],
        )
        for r in rows
    ]
```

- [ ] **Step 2: 运行现有测试确认函数改名后功能不变**

```bash
python -m pytest tests/cache/test_store.py::TestRecursiveQuery::test_returns_root_and_descendants -v
```

Expected: FAIL (函数名 `get_entries_recursive` 已不存在)

---

### Task 2: 更新 `get_entries` 的所有调用方

**Files:**
- Modify: `gdm/core/cache/scanner_cached.py:132`
- Modify: `gdm/gui/main_window.py:308`
- Modify: `tests/cache/test_store.py` (多处)
- Modify: `tests/cache/test_scanner_cached.py` (多处)

- [ ] **Step 1: 更新 `scanner_cached.py` 中的 import 和调用**

在 `scanner_cached.py:132`，`process_diff_sync` 函数内：

```python
# 旧
cached = store.get_entries_recursive(conn, norm_root)
# 新
cached = store.get_entries(conn, norm_root, recursive=True)
```

> 注：`process_diff_sync` 尚未加 `recursive` 参数，此处先硬编码 `recursive=True` 保持兼容，Task 4 会改为参数透传。

- [ ] **Step 2: 更新 `main_window.py` 中的调用**

在 `main_window.py:308`：

```python
# 旧
entries = cache_store.get_entries_recursive(conn, norm)
# 新
entries = cache_store.get_entries(conn, norm, recursive=False)
```

- [ ] **Step 3: 更新测试文件 `test_store.py` 中的所有调用**

将以下文件中的 `store.get_entries_recursive(...)` 全部替换为 `store.get_entries(..., recursive=True)`：

- 第 31 行
- 第 40 行
- 第 53 行
- 第 63 行
- 第 73 行
- 第 82 行

- [ ] **Step 4: 更新测试文件 `test_scanner_cached.py` 中的所有 `store.get_entries_recursive` 调用**

将以下文件中的 `store.get_entries_recursive(...)` 全部替换为 `store.get_entries(..., recursive=True)`：

- 第 80 行
- 第 96 行
- 第 102 行
- 第 127 行
- 第 147 行
- 第 163 行
- 第 174 行

- [ ] **Step 5: 运行全部缓存测试确认兼容**

```bash
python -m pytest tests/cache/ -v
```

Expected: ALL PASS

---

### Task 3: `store.py` — `update_folder_counts` 加 `recursive` 参数

**Files:**
- Modify: `gdm/core/cache/store.py:218-231`

- [ ] **Step 1: 修改函数签名和逻辑**

```python
def update_folder_counts(
    conn: sqlite3.Connection, root: str, *, recursive: bool = False
) -> None:
    """统计 root 下各目录的 entry 数量并更新 folders.entry_count。

    Args:
        conn: 数据库连接
        root: 目录路径（已规范化）
        recursive: True 时递归统计子目录；False 时仅统计当前目录
    """
    _ensure_ancestor_folders(conn, root)
    if recursive:
        conn.execute("""
            UPDATE folders
            SET entry_count = (
                SELECT COUNT(*)
                FROM entries
                WHERE entries.folder_path = folders.folder_path
                   OR entries.folder_path LIKE (folders.folder_path || '/%')
            )
            WHERE folder_path = ? OR folder_path LIKE ?
        """, (root, root + "/%"))
    else:
        conn.execute("""
            UPDATE folders
            SET entry_count = (
                SELECT COUNT(*)
                FROM entries
                WHERE entries.folder_path = folders.folder_path
            )
            WHERE folder_path = ?
        """, (root,))
    conn.commit()
```

- [ ] **Step 2: 更新调用方 `scanner_cached.py:186`**

```python
# 旧
store.update_folder_counts(conn, norm_root)
# 新
store.update_folder_counts(conn, norm_root, recursive=True)
```

> 注：同样先硬编码 `recursive=True` 保持兼容，Task 4 会改为参数透传。

- [ ] **Step 3: 更新测试 `test_store.py` 中的调用**

将 `test_store.py` 中 `store.update_folder_counts(conn, "d")` 替换为 `store.update_folder_counts(conn, "d", recursive=True)`：

- 第 140 行
- 第 154 行
- 第 167 行
- 第 181 行

- [ ] **Step 4: 运行全部缓存测试**

```bash
python -m pytest tests/cache/ -v
```

Expected: ALL PASS

---

### Task 4: `scanner_cached.py` — `snapshot_folder` 加 `recursive` 参数

**Files:**
- Modify: `gdm/core/cache/scanner_cached.py:47-73`

- [ ] **Step 1: 修改函数签名和逻辑**

```python
def snapshot_folder(root: str, *, recursive: bool = False) -> List[FileSnapshot]:
    """列出 root 下的图片文件快照。

    Args:
        root: 目录路径
        recursive: True 时递归遍历子目录；False 时仅当前目录

    Returns:
        FileSnapshot 列表
    """
    out: List[FileSnapshot] = []
    if not os.path.isdir(root):
        return out

    if recursive:
        for sub_dir, _dirs, files in os.walk(root):
            for fname in files:
                if fname.startswith("."):
                    continue
                ext = os.path.splitext(fname)[1].lower()
                if ext not in SUPPORTED_EXTENSIONS:
                    continue
                full = os.path.join(sub_dir, fname)
                try:
                    st = os.stat(full)
                except OSError:
                    continue
                out.append(FileSnapshot(
                    folder_path=normalize_folder(sub_dir),
                    file_name=fname,
                    mtime_ns=st.st_mtime_ns,
                    size=st.st_size,
                ))
    else:
        try:
            entries = os.listdir(root)
        except OSError:
            return out
        for fname in entries:
            if fname.startswith("."):
                continue
            full = os.path.join(root, fname)
            if not os.path.isfile(full):
                continue
            ext = os.path.splitext(fname)[1].lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue
            try:
                st = os.stat(full)
            except OSError:
                continue
            out.append(FileSnapshot(
                folder_path=normalize_folder(root),
                file_name=fname,
                mtime_ns=st.st_mtime_ns,
                size=st.st_size,
            ))
    return out
```

- [ ] **Step 2: 更新测试 `test_scanner_cached.py` 中的所有调用**

将 `snapshot_folder(str(tmp_path))` 替换为 `snapshot_folder(str(tmp_path), recursive=True)`：

- 第 36 行
- 第 43 行
- 第 55 行
- 第 64 行

第 47 行的 `snapshot_folder(str(tmp_path / "nonexistent"))` — 该测试不涉及递归，保持不传参即可。

- [ ] **Step 3: 在 `process_diff_sync` 中更新 `snapshot_folder` 调用**

`scanner_cached.py:133`：

```python
# 旧
current = snapshot_folder(root)
# 新
current = snapshot_folder(root, recursive=True)
```

- [ ] **Step 4: 运行缓存测试**

```bash
python -m pytest tests/cache/ -v
```

Expected: ALL PASS

---

### Task 5: `scanner_cached.py` — `process_diff_sync` 和 `DiffWorker` 加 `recursive` 参数透传

**Files:**
- Modify: `gdm/core/cache/scanner_cached.py:113-237`

- [ ] **Step 1: `process_diff_sync` 签名和内部调用**

```python
def process_diff_sync(
    conn: sqlite3.Connection,
    root: str,
    cancelled: Optional[threading.Event] = None,
    on_removed=None,
    on_batch_updated=None,
    *,
    recursive: bool = False,
) -> None:
```

更新内部调用：

```python
# 第 132 行 (约为)
cached = store.get_entries(conn, norm_root, recursive=recursive)

# 第 133 行 (约为)
current = snapshot_folder(root, recursive=recursive)

# 第 179-180 行 all_folders 逻辑
if recursive:
    all_folders = (
        touched_folders
        | {snap.folder_path for snap in current}
        | {norm_root}
    )
else:
    all_folders = {norm_root}

# 第 186 行 (约为)
store.update_folder_counts(conn, norm_root, recursive=recursive)
```

- [ ] **Step 2: `DiffWorker` 加 `recursive` 属性并透传**

```python
class DiffWorker(QRunnable):
    """后台 diff 任务（QThreadPool 调度）。"""

    def __init__(self, root: str, *, recursive: bool = False) -> None:
        super().__init__()
        self.root = root
        self.signals = _WorkerSignals()
        self._cancelled = threading.Event()
        self.recursive = recursive

    def cancel(self) -> None:
        self._cancelled.set()

    def run(self) -> None:
        # ... (前面不变)
        try:
            db.init_schema(conn)
            process_diff_sync(
                conn, self.root,
                cancelled=self._cancelled,
                on_removed=self.signals.entries_removed.emit,
                on_batch_updated=self.signals.entries_updated.emit,
                recursive=self.recursive,
            )
        # ... (后面不变)
```

- [ ] **Step 3: 更新 `main_window.py` 中的 `DiffWorker` 调用**

`main_window.py:329`：

```python
# 旧
worker = DiffWorker(folder_path)
# 新
worker = DiffWorker(folder_path, recursive=False)
```

- [ ] **Step 4: 运行全部缓存测试**

```bash
python -m pytest tests/cache/ -v
```

Expected: ALL PASS

---

### Task 6: `main_window.py` — 同步扫描路径改为非递归

**Files:**
- Modify: `gdm/gui/main_window.py:202`

- [ ] **Step 1: `_run_scan` 中 `scan_with_progress` 调用**

```python
# 旧
sprites = scan_with_progress(folder, recursive=True,
                             progress_callback=progress_callback)
# 新
sprites = scan_with_progress(folder, recursive=False,
                             progress_callback=progress_callback)
```

- [ ] **Step 2: 验证无语法错误**

```bash
python -c "from gdm.gui.main_window import MainWindow; print('OK')"
```

Expected: OK (无 ImportError / SyntaxError)

---

### Task 7: 新增非递归模式测试

**Files:**
- Modify: `tests/cache/test_store.py`
- Modify: `tests/cache/test_scanner_cached.py`

- [ ] **Step 1: 在 `test_store.py` 末尾新增 `TestNonRecursiveQuery` 类**

```python
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
        assert count == 1  # 只有 a.png，不包含子目录的 b.png
```

- [ ] **Step 2: 在 `test_scanner_cached.py` 新增 `TestSnapshotFolderNonRecursive` 类**

```python
class TestSnapshotFolderNonRecursive:
    def test_only_current_dir(self, tmp_path):
        _make_png(tmp_path / "a.png")
        _make_png(tmp_path / "sub" / "b.png")
        snaps = snapshot_folder(str(tmp_path), recursive=False)
        names = sorted(s.file_name for s in snaps)
        assert names == ["a.png"]

    def test_all_folder_paths_are_root(self, tmp_path):
        _make_png(tmp_path / "a.png")
        _make_png(tmp_path / "sub" / "b.png")
        snaps = snapshot_folder(str(tmp_path), recursive=False)
        norm_root = normalize_folder(str(tmp_path))
        for s in snaps:
            assert s.folder_path == norm_root
```

- [ ] **Step 3: 在 `test_scanner_cached.py` 新增 `TestProcessDiffSyncNonRecursive` 类**

```python
class TestProcessDiffSyncNonRecursive:
    def test_only_current_dir_stored(self, tmp_path):
        _make_png(tmp_path / "a.png")
        _make_png(tmp_path / "sub" / "b.png")
        db_path = tmp_path / "cache.db"
        conn = db.open_connection(db_path)
        db.init_schema(conn)
        try:
            process_diff_sync(conn, str(tmp_path), recursive=False)
            rows = store.get_entries(conn, normalize_folder(str(tmp_path)), recursive=False)
            assert {r.file_name for r in rows} == {"a.png"}
        finally:
            conn.close()
```

- [ ] **Step 4: 运行全部缓存测试**

```bash
python -m pytest tests/cache/ -v
```

Expected: ALL PASS (包括新增测试)

---

### Task 8: 全量测试 + 提交

- [ ] **Step 1: 运行全部测试**

```bash
python -m pytest tests/ -v
```

Expected: ALL PASS

- [ ] **Step 2: 确认无 lint 错误**

```bash
python -m py_compile gdm/core/cache/store.py gdm/core/cache/scanner_cached.py gdm/gui/main_window.py
```

Expected: 无输出（编译成功）

- [ ] **Step 3: 提交**

```bash
git add gdm/core/cache/store.py gdm/core/cache/scanner_cached.py gdm/gui/main_window.py tests/cache/test_store.py tests/cache/test_scanner_cached.py
git commit -m "feat: 目录显示改为非递归，仅展示当前目录的直接图片

- get_entries_recursive 重命名为 get_entries，新增 recursive 参数
- snapshot_folder / process_diff_sync / update_folder_counts 新增 recursive 参数
- 入口调用点统一传 recursive=False
- 新增非递归模式的测试覆盖"
```
