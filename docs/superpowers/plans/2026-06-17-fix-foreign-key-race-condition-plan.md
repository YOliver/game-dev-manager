# Fix Foreign Key Race Condition — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `upsert_folder` + `upsert_entry` 合并到同一 SQLite 事务中，消除并发 `DiffWorker` 间的 FOREIGN KEY constraint failed 竞态条件。

**Architecture:** 从 `store.py` 的 `upsert_folder()`、`upsert_entry()`、`delete_entries()` 中移除 `conn.commit()`，改为在 `process_diff_sync()` 中显式提交。`mark_scan_done()` 和 `evict_lru_if_needed()` 保留自提交。

**Tech Stack:** Python 3.10+, sqlite3, Pillow, pytest

---

### Task 1: 移除 `store.py` 中三个函数的自提交

**Files:**
- Modify: `gdm/core/cache/store.py:26,85,124`（删除 `conn.commit()`）

- [ ] **Step 1: 修改 `upsert_folder()`（第 26 行）**

删除 `conn.commit()`，更新 docstring。

```python
# 修改前（第 14-26 行）
def upsert_folder(conn: sqlite3.Connection, folder_path: str, now: int) -> None:
    """插入或刷新 folders 行。"""
    conn.execute(
        """
        INSERT INTO folders(folder_path, last_scan_at, last_access_at)
        VALUES (?, ?, ?)
        ON CONFLICT(folder_path) DO UPDATE SET
            last_scan_at = excluded.last_scan_at,
            last_access_at = excluded.last_access_at
        """,
        (folder_path, now, now),
    )
    conn.commit()

# 修改后
def upsert_folder(conn: sqlite3.Connection, folder_path: str, now: int) -> None:
    """插入或刷新 folders 行。调用方负责 commit。"""
    conn.execute(
        """
        INSERT INTO folders(folder_path, last_scan_at, last_access_at)
        VALUES (?, ?, ?)
        ON CONFLICT(folder_path) DO UPDATE SET
            last_scan_at = excluded.last_scan_at,
            last_access_at = excluded.last_access_at
        """,
        (folder_path, now, now),
    )
```

- [ ] **Step 2: 修改 `upsert_entry()`（第 85 行）**

删除 `conn.commit()`，更新 docstring。

```python
# 修改前（第 60-85 行）
def upsert_entry(conn: sqlite3.Connection, e: CachedEntry) -> None:
    conn.execute(
        """
        INSERT INTO entries(
            folder_path, file_name, mtime_ns, size,
            width, height, format, color_mode,
            thumb_blob, thumb_mtime_ns
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(folder_path, file_name) DO UPDATE SET
            mtime_ns = excluded.mtime_ns,
            size = excluded.size,
            width = excluded.width,
            height = excluded.height,
            format = excluded.format,
            color_mode = excluded.color_mode,
            thumb_blob = excluded.thumb_blob,
            thumb_mtime_ns = excluded.thumb_mtime_ns
        """,
        (
            e.folder_path, e.file_name, e.mtime_ns, e.size,
            e.width, e.height, e.format, e.color_mode,
            e.thumb_blob, e.thumb_mtime_ns,
        ),
    )
    conn.commit()

# 修改后
def upsert_entry(conn: sqlite3.Connection, e: CachedEntry) -> None:
    """插入或刷新 entries 行。调用方负责 commit。"""
    conn.execute(
        """
        INSERT INTO entries(
            folder_path, file_name, mtime_ns, size,
            width, height, format, color_mode,
            thumb_blob, thumb_mtime_ns
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(folder_path, file_name) DO UPDATE SET
            mtime_ns = excluded.mtime_ns,
            size = excluded.size,
            width = excluded.width,
            height = excluded.height,
            format = excluded.format,
            color_mode = excluded.color_mode,
            thumb_blob = excluded.thumb_blob,
            thumb_mtime_ns = excluded.thumb_mtime_ns
        """,
        (
            e.folder_path, e.file_name, e.mtime_ns, e.size,
            e.width, e.height, e.format, e.color_mode,
            e.thumb_blob, e.thumb_mtime_ns,
        ),
    )
```

- [ ] **Step 3: 修改 `delete_entries()`（第 124 行）**

删除 `conn.commit()`，更新 docstring。

```python
# 修改前（第 117-124 行）
def delete_entries(
    conn: sqlite3.Connection, keys: Iterable[Tuple[str, str]]
) -> None:
    conn.executemany(
        "DELETE FROM entries WHERE folder_path = ? AND file_name = ?",
        list(keys),
    )
    conn.commit()

# 修改后
def delete_entries(
    conn: sqlite3.Connection, keys: Iterable[Tuple[str, str]]
) -> None:
    """删除 entries 行。调用方负责 commit。"""
    conn.executemany(
        "DELETE FROM entries WHERE folder_path = ? AND file_name = ?",
        list(keys),
    )
```

- [ ] **Step 4: Commit**

```bash
git add gdm/core/cache/store.py
git commit -m "refactor(store): remove conn.commit() from upsert_folder/upsert_entry/delete_entries"
```

---

### Task 2: `process_diff_sync()` 添加显式 `conn.commit()`

**Files:**
- Modify: `gdm/core/cache/scanner_cached.py`（在 `process_diff_sync` 添加 3 处 `conn.commit()`）

- [ ] **Step 1: 在删除 removed 条目后添加 commit（约第 138-141 行）**

```python
# 修改前
if removed:
    store.delete_entries(conn, removed)
    if on_removed:
        on_removed(list(removed))

# 修改后
if removed:
    store.delete_entries(conn, removed)
    conn.commit()                         # ← 新增：提交删除操作
    if on_removed:
        on_removed(list(removed))
```

- [ ] **Step 2: 在每批条目后添加 commit（约第 166-169 行）**

```python
# 修改前
if len(batch) >= db.BATCH_EMIT_SIZE:
    if on_batch_updated:
        on_batch_updated(list(batch))
    batch.clear()

# 修改后
if len(batch) >= db.BATCH_EMIT_SIZE:
    conn.commit()                         # ← 新增：提交 upsert_folder + upsert_entry 批次
    if on_batch_updated:
        on_batch_updated(list(batch))
    batch.clear()
```

- [ ] **Step 3: 在最后一批条目后添加 commit（约第 171-172 行）**

```python
# 修改前
if batch and on_batch_updated:
    on_batch_updated(list(batch))

# 修改后
if batch:
    conn.commit()                         # ← 新增：提交最后一批
    if on_batch_updated:
        on_batch_updated(list(batch))
```

- [ ] **Step 4: Commit**

```bash
git add gdm/core/cache/scanner_cached.py
git commit -m "fix(cache): group upsert_folder + upsert_entry in same transaction in process_diff_sync"
```

---

### Task 3: 回归测试验证

**Files:**
- Test: `tests/cache/test_store.py`
- Test: `tests/cache/test_scanner_cached.py`
- Test: `tests/test_scanner.py`

- [ ] **Step 1: 运行缓存相关测试**

Run: `cd G:/UGit/game-dev-manager && python -m pytest tests/cache/test_store.py tests/cache/test_scanner_cached.py -v`
Expected: 24 passed

- [ ] **Step 2: 运行扫描器测试**

Run: `cd G:/UGit/game-dev-manager && python -m pytest tests/test_scanner.py -v`
Expected: 11 passed

- [ ] **Step 3: 运行全量测试**

Run: `cd G:/UGit/game-dev-manager && python -m pytest tests/ -v`
Expected: 145 passed

- [ ] **Step 4: Git 状态确认**

Run: `cd G:/UGit/game-dev-manager && git log --oneline -3`
Expected: 看到两个新 commit（refactor + fix）

---

### Self-Review Checklist

- [x] **Spec coverage:** 设计文档所有改动点已覆盖 — store.py 3 个函数移除 commit（Task 1）+ scanner_cached.py 3 处添加 commit（Task 2）+ 回归测试（Task 3）
- [x] **Placeholder scan:** 无 TBD/TODO/placeholder
- [x] **Type consistency:** `conn` 类型一致，`db.BATCH_EMIT_SIZE` 引用正确
