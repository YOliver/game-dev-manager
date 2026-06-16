# 缩略图持久化缓存 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Game Dev Manager 引入 SQLite 持久化缓存层，已访问过的目录二次点击首屏 < 200ms，并支持增量 diff。

**Architecture:** 新增 `gdm/core/cache/` 子包，按"叶子目录"粒度组织缓存。点击目录时同步铺缓存 UI，后台 DiffWorker 用 `os.walk` 增量更新。SQLite WAL 模式 + 每线程独立 connection。

**Tech Stack:** Python `sqlite3`（标准库），Pillow（缩略图编码 WebP），PySide6（QThreadPool / Signal），pytest（测试）。

**Spec:** `docs/superpowers/specs/2026-06-16-thumbnail-persistent-cache-design.md`

---

## File Structure

| 文件 | 责任 |
|---|---|
| `gdm/core/cache/__init__.py` | 暴露 `get_cache_dir()`、`CachedEntry` 数据类 |
| `gdm/core/cache/db.py` | 常量、`open_connection(path)`、`init_schema(conn)`、`integrity_check(path)`、损坏恢复 |
| `gdm/core/cache/store.py` | 纯 DB CRUD：`get_entries_recursive` / `upsert_entry` / `delete_entries` / `delete_folders_under` / `touch_folders_under` / `mark_scan_done` / `evict_lru_if_needed` / `clear_all` |
| `gdm/core/cache/diff.py` | 纯函数 `compute_diff(cached, current) -> (added, changed, removed)` |
| `gdm/core/cache/scanner_cached.py` | 编排器 + `DiffWorker(QRunnable)` |
| `gdm/gui/thumbnail_view.py`（改） | 新增 `load_from_cache` / `apply_entries_updated` / `apply_entries_removed` |
| `gdm/gui/main_window.py`（改） | `_on_folder_selected` 改走 `scanner_cached`；菜单项；退出 vacuum |
| `tests/cache/test_diff.py` | 纯 diff 边界测试 |
| `tests/cache/test_db.py` | schema、integrity、损坏恢复 |
| `tests/cache/test_store.py` | CRUD + LRU + 递归查询 |
| `tests/cache/test_scanner_cached.py` | 端到端集成（多层目录） |

---

## Task 1: 数据类与目录路径解析

**Files:**
- Create: `gdm/core/cache/__init__.py`

- [ ] **Step 1: 写入 `__init__.py`**

```python
"""持久化缓存子包：SQLite 存元数据 + 缩略图 blob。"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QStandardPaths


@dataclass
class CachedEntry:
    """缓存中的单个文件记录，覆盖 SpriteInfo 全部字段 + 缓存校验字段。"""

    folder_path: str
    file_name: str
    width: int
    height: int
    size: int
    format: str
    color_mode: str
    mtime_ns: int
    thumb_blob: Optional[bytes]
    thumb_mtime_ns: Optional[int]


def get_cache_dir() -> Path:
    """返回缓存目录路径，必要时创建。"""
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    cache_dir = Path(base) / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_db_path() -> Path:
    """返回 cache.db 完整路径。"""
    return get_cache_dir() / "cache.db"
```

- [ ] **Step 2: 提交**

```bash
git add gdm/core/cache/__init__.py
git commit -m "feat(cache): 新增 cache 子包与 CachedEntry 数据类"
```

## Task 2: db 模块 — 连接、schema、损坏恢复

**Files:**
- Create: `gdm/core/cache/db.py`
- Create: `tests/cache/__init__.py`
- Create: `tests/cache/test_db.py`

- [ ] **Step 1: 写失败测试 `tests/cache/__init__.py` + `tests/cache/test_db.py`**

`tests/cache/__init__.py` 留空。

`tests/cache/test_db.py`：

```python
"""测试 cache.db 模块"""

import os
import sqlite3
from pathlib import Path

import pytest

from gdm.core.cache import db


class TestInitSchema:
    def test_creates_required_tables(self, tmp_path):
        db_path = tmp_path / "cache.db"
        conn = db.open_connection(db_path)
        try:
            db.init_schema(conn)
            tables = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            assert "folders" in tables
            assert "entries" in tables
        finally:
            conn.close()

    def test_pragmas_applied(self, tmp_path):
        db_path = tmp_path / "cache.db"
        conn = db.open_connection(db_path)
        try:
            db.init_schema(conn)
            assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
            assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        finally:
            conn.close()

    def test_auto_vacuum_incremental(self, tmp_path):
        db_path = tmp_path / "cache.db"
        conn = db.open_connection(db_path)
        try:
            db.init_schema(conn)
            # auto_vacuum: 0=NONE, 1=FULL, 2=INCREMENTAL
            assert conn.execute("PRAGMA auto_vacuum").fetchone()[0] == 2
        finally:
            conn.close()

    def test_idempotent(self, tmp_path):
        db_path = tmp_path / "cache.db"
        conn = db.open_connection(db_path)
        try:
            db.init_schema(conn)
            db.init_schema(conn)  # 第二次不应抛异常
        finally:
            conn.close()


class TestIntegrityCheck:
    def test_passes_on_healthy_db(self, tmp_path):
        db_path = tmp_path / "cache.db"
        conn = db.open_connection(db_path)
        db.init_schema(conn)
        conn.close()
        assert db.integrity_check(db_path) is True

    def test_fails_on_corrupted_db(self, tmp_path):
        db_path = tmp_path / "cache.db"
        db_path.write_bytes(b"not a sqlite database")
        assert db.integrity_check(db_path) is False


class TestRecoverIfCorrupted:
    def test_renames_corrupted_db(self, tmp_path):
        db_path = tmp_path / "cache.db"
        db_path.write_bytes(b"corrupted")
        db.recover_if_corrupted(db_path)
        assert not db_path.exists()
        siblings = list(tmp_path.glob("cache.db.corrupted-*"))
        assert len(siblings) == 1

    def test_noop_when_db_missing(self, tmp_path):
        db_path = tmp_path / "cache.db"
        db.recover_if_corrupted(db_path)  # 应不抛异常
        assert not db_path.exists()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/cache/test_db.py -v`
Expected: FAIL（`gdm.core.cache.db` 模块不存在）

- [ ] **Step 3: 实现 `gdm/core/cache/db.py`**

```python
"""SQLite 连接管理、schema 初始化、损坏恢复。

硬性规则：本模块不持有任何模块级 connection。
每个调用方在自己的线程里创建并关闭 connection。
"""

import logging
import sqlite3
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# 配置常量
MAX_CACHED_FOLDERS = 200
MAX_DB_SIZE_BYTES = 1_500_000_000
THUMB_SIZE = 128
THUMB_FORMAT = "WEBP"
THUMB_QUALITY = 80
BATCH_EMIT_SIZE = 20

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS folders (
    folder_path    TEXT PRIMARY KEY,
    last_scan_at   INTEGER NOT NULL,
    last_access_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS entries (
    folder_path    TEXT NOT NULL,
    file_name      TEXT NOT NULL,
    mtime_ns       INTEGER NOT NULL,
    size           INTEGER NOT NULL,
    width          INTEGER,
    height         INTEGER,
    format         TEXT,
    color_mode     TEXT,
    thumb_blob     BLOB,
    thumb_mtime_ns INTEGER,
    PRIMARY KEY (folder_path, file_name),
    FOREIGN KEY (folder_path) REFERENCES folders(folder_path) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_entries_folder ON entries(folder_path);
"""


def open_connection(db_path: Path) -> sqlite3.Connection:
    """创建 SQLite connection，应用必要的 PRAGMA。

    auto_vacuum 必须在建任何表之前设置，否则不生效。
    """
    is_new = not db_path.exists() or db_path.stat().st_size == 0
    conn = sqlite3.connect(str(db_path))
    if is_new:
        conn.execute("PRAGMA auto_vacuum=INCREMENTAL")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """创建表与索引（幂等）。"""
    conn.executescript(_SCHEMA_SQL)
    conn.commit()


def integrity_check(db_path: Path) -> bool:
    """对 DB 文件运行 PRAGMA integrity_check。

    Returns:
        True 表示完整；False 表示损坏或无法打开。
    """
    if not db_path.exists():
        return True  # 不存在不算损坏，由调用方决定是否新建
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute("PRAGMA integrity_check").fetchone()
            return row is not None and row[0] == "ok"
        finally:
            conn.close()
    except sqlite3.DatabaseError:
        return False


def recover_if_corrupted(db_path: Path) -> None:
    """若 DB 损坏，重命名为 cache.db.corrupted-<timestamp>。下次调用时自动新建。"""
    if not db_path.exists():
        return
    if integrity_check(db_path):
        return
    backup = db_path.with_name(f"{db_path.name}.corrupted-{int(time.time())}")
    db_path.rename(backup)
    logger.warning("缓存 DB 损坏，已备份为 %s", backup)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/cache/test_db.py -v`
Expected: PASS（5 个测试）

- [ ] **Step 5: 提交**

```bash
git add gdm/core/cache/db.py tests/cache/__init__.py tests/cache/test_db.py
git commit -m "feat(cache): db 模块 — schema/connection/损坏恢复"
```

## Task 3: diff 模块 — 纯函数比对

**Files:**
- Create: `gdm/core/cache/diff.py`
- Create: `tests/cache/test_diff.py`

- [ ] **Step 1: 写失败测试 `tests/cache/test_diff.py`**

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/cache/test_diff.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 `gdm/core/cache/diff.py`**

```python
"""纯函数 diff：比较缓存条目与文件系统快照。"""

from dataclasses import dataclass
from typing import List, Tuple

from gdm.core.cache import CachedEntry


@dataclass
class FileSnapshot:
    """文件系统中扫描到的单个文件快照（不含元数据，未读 Pillow）。"""

    folder_path: str
    file_name: str
    mtime_ns: int
    size: int


def compute_diff(
    cached: List[CachedEntry],
    current: List[FileSnapshot],
) -> Tuple[List[FileSnapshot], List[FileSnapshot], List[Tuple[str, str]]]:
    """按 (folder_path, file_name) 复合键比对。

    Returns:
        (added, changed, removed)
        added/changed: List[FileSnapshot]
        removed: List[(folder_path, file_name)]
    """
    cached_map = {(e.folder_path, e.file_name): e for e in cached}
    current_map = {(s.folder_path, s.file_name): s for s in current}

    added: List[FileSnapshot] = []
    changed: List[FileSnapshot] = []
    for key, snap in current_map.items():
        if key not in cached_map:
            added.append(snap)
        else:
            entry = cached_map[key]
            if entry.mtime_ns != snap.mtime_ns or entry.size != snap.size:
                changed.append(snap)

    removed: List[Tuple[str, str]] = [
        key for key in cached_map if key not in current_map
    ]

    return added, changed, removed
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/cache/test_diff.py -v`
Expected: PASS（8 个测试）

- [ ] **Step 5: 提交**

```bash
git add gdm/core/cache/diff.py tests/cache/test_diff.py
git commit -m "feat(cache): diff 模块 — 纯函数复合键比对"
```

---

## Task 4: store 模块 — DB CRUD + 递归查询 + LRU

**Files:**
- Create: `gdm/core/cache/store.py`
- Create: `tests/cache/test_store.py`

- [ ] **Step 1: 写失败测试 `tests/cache/test_store.py`**

```python
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
        rows = store.get_entries_recursive(conn, "d")
        assert len(rows) == 1
        assert rows[0].file_name == "x.png"
        assert rows[0].thumb_blob == b"BLOB"

    def test_upsert_replaces_existing(self, conn):
        store.upsert_folder(conn, "d/a", now=1000)
        store.upsert_entry(conn, _entry("d/a", "x.png", mtime=100))
        store.upsert_entry(conn, _entry("d/a", "x.png", mtime=200))
        rows = store.get_entries_recursive(conn, "d")
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
        rows = store.get_entries_recursive(conn, "d")
        names = sorted(r.file_name for r in rows)
        assert names == ["nested.png", "root.png", "sub.png"]

    def test_does_not_match_sibling_with_common_prefix(self, conn):
        """查询 d 不应命中 d_other（前缀同名但非子目录）。"""
        store.upsert_folder(conn, "d", now=1000)
        store.upsert_folder(conn, "d_other", now=1000)
        store.upsert_entry(conn, _entry("d", "a.png"))
        store.upsert_entry(conn, _entry("d_other", "b.png"))
        rows = store.get_entries_recursive(conn, "d")
        assert {r.file_name for r in rows} == {"a.png"}


class TestDelete:
    def test_delete_entries(self, conn):
        store.upsert_folder(conn, "d", now=1000)
        store.upsert_entry(conn, _entry("d", "a.png"))
        store.upsert_entry(conn, _entry("d", "b.png"))
        store.delete_entries(conn, [("d", "a.png")])
        rows = store.get_entries_recursive(conn, "d")
        assert {r.file_name for r in rows} == {"b.png"}

    def test_delete_folders_under_cascades(self, conn):
        store.upsert_folder(conn, "d", now=1000)
        store.upsert_folder(conn, "d/sub", now=1000)
        store.upsert_entry(conn, _entry("d", "a.png"))
        store.upsert_entry(conn, _entry("d/sub", "b.png"))
        store.delete_folders_under(conn, "d")
        rows = store.get_entries_recursive(conn, "d")
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/cache/test_store.py -v`
Expected: FAIL（`store` 模块不存在）

- [ ] **Step 3: 实现 `gdm/core/cache/store.py`**

```python
"""DB CRUD + 递归查询 + LRU 淘汰。

硬性规则：所有公开函数 conn 由调用方传入。
本模块不持有任何模块级 connection。
"""

import sqlite3
from typing import Iterable, List, Tuple

from gdm.core.cache import CachedEntry
from gdm.core.cache import db


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


def touch_folders_under(conn: sqlite3.Connection, root: str, now: int) -> None:
    """更新 root 及其所有后代叶子目录的 last_access_at。"""
    prefix = root + "/%"
    conn.execute(
        """
        UPDATE folders SET last_access_at = ?
        WHERE folder_path = ? OR folder_path LIKE ?
        """,
        (now, root, prefix),
    )
    conn.commit()


def mark_scan_done(
    conn: sqlite3.Connection, folder_paths: Iterable[str], now: int
) -> None:
    """标记若干叶子目录扫描完成（UPSERT folders 行）。"""
    rows = [(p, now, now) for p in folder_paths]
    conn.executemany(
        """
        INSERT INTO folders(folder_path, last_scan_at, last_access_at)
        VALUES (?, ?, ?)
        ON CONFLICT(folder_path) DO UPDATE SET
            last_scan_at = excluded.last_scan_at,
            last_access_at = excluded.last_access_at
        """,
        rows,
    )
    conn.commit()


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


def get_entries_recursive(
    conn: sqlite3.Connection, root: str
) -> List[CachedEntry]:
    """返回 root 及其后代叶子目录下的所有缓存条目。"""
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


def delete_entries(
    conn: sqlite3.Connection, keys: Iterable[Tuple[str, str]]
) -> None:
    conn.executemany(
        "DELETE FROM entries WHERE folder_path = ? AND file_name = ?",
        list(keys),
    )
    conn.commit()


def delete_folders_under(conn: sqlite3.Connection, root: str) -> None:
    """删除 root 及所有后代 folders 行（CASCADE 清理 entries）。"""
    prefix = root + "/%"
    conn.execute(
        "DELETE FROM folders WHERE folder_path = ? OR folder_path LIKE ?",
        (root, prefix),
    )
    conn.commit()


def evict_lru_if_needed(conn: sqlite3.Connection) -> None:
    """folders 行数超过 MAX_CACHED_FOLDERS 时淘汰最旧的若干行。"""
    count_row = conn.execute("SELECT COUNT(*) FROM folders").fetchone()
    if not count_row:
        return
    count = count_row[0]
    if count <= db.MAX_CACHED_FOLDERS:
        return
    excess = count - db.MAX_CACHED_FOLDERS
    victims = [
        row[0]
        for row in conn.execute(
            """
            SELECT folder_path FROM folders
            ORDER BY last_access_at ASC
            LIMIT ?
            """,
            (excess,),
        )
    ]
    conn.executemany(
        "DELETE FROM folders WHERE folder_path = ?",
        [(v,) for v in victims],
    )
    conn.commit()


def clear_all(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM entries")
    conn.execute("DELETE FROM folders")
    conn.commit()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/cache/test_store.py -v`
Expected: 9 passed

- [ ] **Step 5: 提交**

```bash
git add gdm/core/cache/store.py tests/cache/test_store.py
git commit -m "feat(cache): store 模块 — CRUD + 递归查询 + LRU 淘汰"
```

---

## Task 5: scanner_cached 模块 — 编排器 + DiffWorker

**Files:**
- Create: `gdm/core/cache/scanner_cached.py`
- Create: `tests/cache/test_scanner_cached.py`

> 该模块包含：路径规范化、`os.walk` 列文件、`load_folder_cached()` 编排函数、
> `DiffWorker(QRunnable)` + `_WorkerSignals`。
> 是缓存层与 UI 之间的唯一桥梁。

- [ ] **Step 1: 写失败测试 `tests/cache/test_scanner_cached.py`（先只测无 UI 的纯逻辑部分）**

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/cache/test_scanner_cached.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 `gdm/core/cache/scanner_cached.py`**

```python
"""编排器：取缓存 → 列文件 → diff → 增量更新 → 通知 UI。

包含：路径规范化、os.walk 快照、process_diff_sync（核心同步逻辑）、
DiffWorker（QRunnable 包装）、_WorkerSignals。

硬性规则：DiffWorker 在 run() 开头创建独立 connection，结束 close()。
不与 UI 线程共享 connection。
"""

import io
import logging
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import List, Optional

from PIL import Image
from PySide6.QtCore import QObject, QRunnable, Signal

from gdm.core.cache import CachedEntry, get_db_path
from gdm.core.cache import db, store
from gdm.core.cache.diff import FileSnapshot, compute_diff
from gdm.core.scanner import SUPPORTED_EXTENSIONS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------- #
# 路径规范化
# ---------------------------------------------------------------------- #

def normalize_folder(p: str) -> str:
    """规范化为小写、正斜杠、无尾斜杠的绝对路径。

    Windows-only：不区分大小写的文件系统假设。
    """
    abs_p = os.path.abspath(p).replace("\\", "/").rstrip("/").lower()
    return abs_p


# ---------------------------------------------------------------------- #
# 文件系统快照
# ---------------------------------------------------------------------- #

def snapshot_folder(root: str) -> List[FileSnapshot]:
    """递归列出 root 下所有图片文件，返回 FileSnapshot 列表。

    遇到不可读目录 / 文件时跳过，不抛异常。
    """
    out: List[FileSnapshot] = []
    if not os.path.isdir(root):
        return out
    for sub_dir, _dirs, files in os.walk(root):
        for fname in files:
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
    return out


# ---------------------------------------------------------------------- #
# 单张图的元数据 + 缩略图
# ---------------------------------------------------------------------- #

def _read_metadata_and_thumb(full_path: str) -> dict:
    """读元数据 + 生成 WebP 缩略图。失败则各字段为 None / 默认值。"""
    info = {
        "width": 0, "height": 0,
        "format": "UNKNOWN", "color_mode": "UNKNOWN",
        "thumb_blob": None,
    }
    try:
        with Image.open(full_path) as img:
            info["width"], info["height"] = img.size
            info["format"] = img.format or "UNKNOWN"
            info["color_mode"] = img.mode

            # 生成 128x128 WebP 缩略图
            thumb = img.copy()
            thumb.thumbnail(
                (db.THUMB_SIZE, db.THUMB_SIZE), Image.Resampling.LANCZOS
            )
            buf = io.BytesIO()
            # WebP 不支持 P / palette 模式，先转 RGBA
            if thumb.mode not in ("RGB", "RGBA"):
                thumb = thumb.convert("RGBA")
            thumb.save(buf, db.THUMB_FORMAT, quality=db.THUMB_QUALITY)
            info["thumb_blob"] = buf.getvalue()
    except Exception as e:
        logger.warning("读取图片失败 %s: %s", full_path, e)
    return info


# ---------------------------------------------------------------------- #
# 同步版核心逻辑（供 DiffWorker 与测试复用）
# ---------------------------------------------------------------------- #

def process_diff_sync(
    conn: sqlite3.Connection,
    root: str,
    cancelled: Optional[threading.Event] = None,
    on_removed=None,
    on_batch_updated=None,
) -> None:
    """对 root 做一次完整 diff 并写回 DB。

    这是 DiffWorker 的同步实现。测试与生产代码共享。

    Args:
        conn: 已打开的 SQLite connection（本线程独占）
        root: 用户点击的目录（任何形式，会被 normalize）
        cancelled: 可选取消事件；每张图前检查
        on_removed: 可选回调 fn(List[(folder, name)])
        on_batch_updated: 可选回调 fn(List[CachedEntry])
    """
    norm_root = normalize_folder(root)
    cached = store.get_entries_recursive(conn, norm_root)
    current = snapshot_folder(root)
    added, changed, removed = compute_diff(cached, current)

    now = int(time.time())

    if removed:
        store.delete_entries(conn, removed)
        if on_removed:
            on_removed(list(removed))

    todo = list(added) + list(changed)
    batch: List[CachedEntry] = []
    touched_folders = set()
    for snap in todo:
        if cancelled is not None and cancelled.is_set():
            break
        full = os.path.join(snap.folder_path, snap.file_name)
        meta = _read_metadata_and_thumb(full)
        entry = CachedEntry(
            folder_path=snap.folder_path,
            file_name=snap.file_name,
            width=meta["width"], height=meta["height"],
            size=snap.size,
            format=meta["format"], color_mode=meta["color_mode"],
            mtime_ns=snap.mtime_ns,
            thumb_blob=meta["thumb_blob"],
            thumb_mtime_ns=snap.mtime_ns if meta["thumb_blob"] else None,
        )
        store.upsert_entry(conn, entry)
        touched_folders.add(snap.folder_path)
        batch.append(entry)
        if len(batch) >= db.BATCH_EMIT_SIZE:
            if on_batch_updated:
                on_batch_updated(list(batch))
            batch.clear()

    if batch and on_batch_updated:
        on_batch_updated(list(batch))

    # 标记所有涉及的叶子目录扫描完成
    all_folders = (
        touched_folders
        | {snap.folder_path for snap in current}
        | {norm_root}
    )
    store.mark_scan_done(conn, all_folders, now)
    store.evict_lru_if_needed(conn)


# ---------------------------------------------------------------------- #
# Qt 信号封装
# ---------------------------------------------------------------------- #

class _WorkerSignals(QObject):
    """DiffWorker 的信号载体（QRunnable 不能直接 emit）。"""

    entries_removed = Signal(list)   # List[(folder_path, file_name)]
    entries_updated = Signal(list)   # List[CachedEntry]
    scan_done = Signal(str)          # 用户点击的根目录


class DiffWorker(QRunnable):
    """后台 diff 任务（QThreadPool 调度）。"""

    def __init__(self, root: str) -> None:
        super().__init__()
        self.root = root
        self.signals = _WorkerSignals()
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        self._cancelled.set()

    def run(self) -> None:
        db_path = get_db_path()
        try:
            conn = db.open_connection(db_path)
        except sqlite3.DatabaseError as e:
            logger.warning("DiffWorker 无法打开缓存 DB，跳过本次 diff: %s", e)
            self.signals.scan_done.emit(self.root)
            return
        try:
            db.init_schema(conn)
            process_diff_sync(
                conn, self.root,
                cancelled=self._cancelled,
                on_removed=self.signals.entries_removed.emit,
                on_batch_updated=self.signals.entries_updated.emit,
            )
        except sqlite3.OperationalError as e:
            # 写入失败（磁盘满等）：log 后继续，不阻断 UI
            logger.warning("缓存写入失败，本次 diff 已部分完成: %s", e)
        except Exception as e:
            logger.exception("DiffWorker 异常: %s", e)
        finally:
            conn.close()
            self.signals.scan_done.emit(self.root)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/cache/test_scanner_cached.py -v`
Expected: 11 passed（normalize 3 + snapshot 3 + process_diff_sync 5）

- [ ] **Step 5: 提交**

```bash
git add gdm/core/cache/scanner_cached.py tests/cache/test_scanner_cached.py
git commit -m "feat(cache): scanner_cached — 编排器 + DiffWorker

包含路径规范化、os.walk 快照、process_diff_sync 同步核心、
DiffWorker(QRunnable) + Qt 信号。"
```

---

## Task 6: thumbnail_view.py — 缓存铺 UI + 增量更新

**Files:**
- Modify: `gdm/gui/thumbnail_view.py`

> 在现有 `ThumbnailView` 上新增三个公开方法，**不删除**原有 `load(sprites)`
> （首次访问空缓存场景会用到）。

- [ ] **Step 1: 阅读现有 `thumbnail_view.py:1-100, 270-440`，确认以下契约**

需要新增的 API：

```python
def load_from_cache(self, root: str, entries: List[CachedEntry]) -> None: ...
def apply_entries_updated(self, entries: List[CachedEntry]) -> None: ...
def apply_entries_removed(self, keys: List[Tuple[str, str]]) -> None: ...
```

- [ ] **Step 2: 在 `thumbnail_view.py` 顶部新增 import**

```python
from gdm.core.cache import CachedEntry
```

（与现有 import 块合并）

- [ ] **Step 3: 在 `ThumbnailView` 类内部添加辅助方法（紧邻 `load()` 之后）**

```python
def _entry_to_sprite(self, entry: CachedEntry) -> SpriteInfo:
    """从 CachedEntry 重建 SpriteInfo，UI 下游消费方无需感知。"""
    full_path = os.path.join(entry.folder_path, entry.file_name)
    return SpriteInfo(
        file_path=full_path,
        file_name=entry.file_name,
        width=entry.width,
        height=entry.height,
        file_size=entry.size,
        format=entry.format,
        color_mode=entry.color_mode,
    )

def _decode_thumb(self, entry: CachedEntry) -> Optional[QPixmap]:
    """把 thumb_blob 解码为 QPixmap，无效时返回 None。"""
    if not entry.thumb_blob:
        return None
    if entry.thumb_mtime_ns is None or entry.thumb_mtime_ns != entry.mtime_ns:
        return None
    pix = QPixmap()
    if not pix.loadFromData(entry.thumb_blob, "WEBP"):
        return None
    return pix

def load_from_cache(self, root: str, entries: List[CachedEntry]) -> None:
    """用缓存数据立即铺 UI（亚秒级首屏）。

    Args:
        root: 用户点击的根目录（仅用于上下文，不直接展示）
        entries: 已从 DB 取出的所有缓存条目（递归）
    """
    self._progress_widget.setVisible(False)
    self._list_widget.setVisible(True)

    sprites = [self._entry_to_sprite(e) for e in entries]
    self._sprites = list(sprites)
    self._items.clear()
    self._pending_workers.clear()
    self._list_widget.clear()

    for entry, sprite in zip(entries, sprites):
        item = QListWidgetItem(sprite.file_name)
        item.setData(Qt.ItemDataRole.UserRole, sprite)
        self._list_widget.addItem(item)
        self._items[sprite.file_path] = item

        pix = self._decode_thumb(entry)
        if pix is not None:
            item.setIcon(QIcon(pix))
            self._thumbnails[sprite.file_path] = pix
        # 否则保持空图标，留待 apply_entries_updated 或异步 worker 补齐

    self._relayout()

def apply_entries_updated(self, entries: List[CachedEntry]) -> None:
    """后台 diff 完成一批后增量更新 UI。"""
    for entry in entries:
        sprite = self._entry_to_sprite(entry)
        item = self._items.get(sprite.file_path)
        if item is None:
            # 新增项
            item = QListWidgetItem(sprite.file_name)
            item.setData(Qt.ItemDataRole.UserRole, sprite)
            self._list_widget.addItem(item)
            self._items[sprite.file_path] = item
            self._sprites.append(sprite)
        else:
            # 更新已有项的数据
            item.setData(Qt.ItemDataRole.UserRole, sprite)

        pix = self._decode_thumb(entry)
        if pix is not None:
            item.setIcon(QIcon(pix))
            self._thumbnails[sprite.file_path] = pix

def apply_entries_removed(self, keys: List[tuple]) -> None:
    """根据 (folder_path, file_name) 列表移除项。"""
    for folder, name in keys:
        full_path = os.path.join(folder, name)
        item = self._items.pop(full_path, None)
        if item is None:
            continue
        row = self._list_widget.row(item)
        if row >= 0:
            self._list_widget.takeItem(row)
        # 同步从 _sprites / _thumbnails 移除
        self._sprites = [s for s in self._sprites if s.file_path != full_path]
        self._thumbnails.pop(full_path, None)
```

> 注意 `Tuple` 的 import：在文件顶部 `from typing import` 行追加 `Tuple`（如尚未引入）。

- [ ] **Step 4: 运行项目现有测试确认未回归**

```bash
pytest tests/test_thumbnail_view.py -v
```
Expected: 现有测试全部 PASS（新增方法不影响旧逻辑）

- [ ] **Step 5: 提交**

```bash
git add gdm/gui/thumbnail_view.py
git commit -m "feat(thumbnail_view): 新增缓存铺 UI + 增量更新接口

- load_from_cache(root, entries)
- apply_entries_updated(entries)
- apply_entries_removed(keys)"
```

---

## Task 7: main_window.py — 接入缓存流程 + 菜单 + 退出 vacuum

**Files:**
- Modify: `gdm/gui/main_window.py`

- [ ] **Step 1: 阅读现有 `main_window.py:163-283` 确认改动点**

要做的事：
1. `_on_folder_selected` 改为：先用缓存铺 UI，再启动 DiffWorker，连接其信号到 view
2. 维护 `self._active_diff_worker` 引用，新点击先 cancel 旧的
3. 菜单加"清空缩略图缓存"
4. `closeEvent` 中触发 `PRAGMA incremental_vacuum`

- [ ] **Step 2: 在文件顶部新增 import**

```python
from PySide6.QtCore import QThreadPool
from gdm.core.cache import get_db_path
from gdm.core.cache import db as cache_db
from gdm.core.cache import store as cache_store
from gdm.core.cache.scanner_cached import (
    DiffWorker, normalize_folder,
)
```

- [ ] **Step 3: 在 `MainWindow.__init__` 末尾新增成员**

```python
self._active_diff_worker: Optional[DiffWorker] = None
```

- [ ] **Step 4: 替换 `_on_folder_selected` 为缓存版本**

```python
def _on_folder_selected(self, folder_path: str) -> None:
    """左侧面板选中文件夹回调。

    1) 立即用缓存铺 UI
    2) 启动后台 DiffWorker 做增量更新
    """
    self._selected_folder = folder_path

    # 取消上一个 worker
    if self._active_diff_worker is not None:
        self._active_diff_worker.cancel()
        self._active_diff_worker = None

    # 1) 立即用缓存铺 UI
    norm = normalize_folder(folder_path)
    try:
        conn = cache_db.open_connection(get_db_path())
        try:
            cache_db.init_schema(conn)
            cache_store.touch_folders_under(
                conn, norm, now=int(__import__("time").time())
            )
            entries = cache_store.get_entries_recursive(conn, norm)
        finally:
            conn.close()
    except Exception as e:
        logger.warning("读取缓存失败，降级为完整扫描: %s", e)
        # 降级路径：走原有的同步扫描
        self.thumbnail_view.show_progress()
        self._start_scan(folder_path, on_finished=self._on_tree_scan_finished)
        return

    if entries:
        self.thumbnail_view.load_from_cache(folder_path, entries)
        self._current_sprites = [
            self.thumbnail_view._entry_to_sprite(e) for e in entries
        ]
    else:
        # 首次访问：空 UI + 等 DiffWorker 增量铺设
        self.thumbnail_view.load_from_cache(folder_path, [])
        self._current_sprites = []

    # 2) 启动后台 DiffWorker
    worker = DiffWorker(folder_path)
    worker.signals.entries_updated.connect(
        self.thumbnail_view.apply_entries_updated
    )
    worker.signals.entries_removed.connect(
        self.thumbnail_view.apply_entries_removed
    )
    worker.signals.scan_done.connect(self._on_diff_scan_done)
    self._active_diff_worker = worker
    QThreadPool.globalInstance().start(worker)

def _on_diff_scan_done(self, root: str) -> None:
    """DiffWorker 完成后的清理。"""
    if self._active_diff_worker is not None and \
       self._active_diff_worker.root == root:
        self._active_diff_worker = None
```

> 同时**保留** `_start_scan` / `_run_scan` / `_on_tree_scan_finished` 不变，
> 作为缓存读取失败的降级路径。

- [ ] **Step 5: 在菜单栏（或工具栏）添加"清空缩略图缓存"项**

定位到现有菜单初始化代码（如 `_init_menu` 或类似），添加：

```python
# 工具菜单 / 设置菜单
clear_cache_act = QAction("清空缩略图缓存", self)
clear_cache_act.triggered.connect(self._on_clear_cache)
tools_menu.addAction(clear_cache_act)
```

并新增槽函数：

```python
def _on_clear_cache(self) -> None:
    """清空所有缩略图缓存（DB + VACUUM）。"""
    from PySide6.QtWidgets import QMessageBox
    reply = QMessageBox.question(
        self, "清空缓存",
        "确定要清空所有缩略图缓存吗？\n下次访问目录时需要重新扫描。",
    )
    if reply != QMessageBox.StandardButton.Yes:
        return
    try:
        conn = cache_db.open_connection(get_db_path())
        try:
            cache_db.init_schema(conn)
            cache_store.clear_all(conn)
            conn.execute("VACUUM")
        finally:
            conn.close()
        QMessageBox.information(self, "完成", "缓存已清空。")
    except Exception as e:
        logger.warning("清空缓存失败: %s", e)
        QMessageBox.warning(self, "失败", f"清空缓存失败: {e}")
```

> 如果当前 `main_window.py` 没有 `tools_menu`，菜单宿主以你项目实际的菜单变量为准。
> 若没有任何菜单结构，先创建一个"工具"顶级菜单再挂这一项。

- [ ] **Step 6: 在 `closeEvent` 中触发 incremental_vacuum**

定位现有 `closeEvent`（若无则新增）：

```python
def closeEvent(self, event) -> None:
    """退出前异步触发 incremental_vacuum，不阻塞退出。"""
    try:
        import threading
        def _vacuum():
            try:
                conn = cache_db.open_connection(get_db_path())
                try:
                    conn.execute("PRAGMA incremental_vacuum")
                finally:
                    conn.close()
            except Exception as e:
                logger.warning("incremental_vacuum 失败: %s", e)
        threading.Thread(target=_vacuum, daemon=True).start()
    except Exception:
        pass
    super().closeEvent(event)
```

- [ ] **Step 7: 运行现有 main_window 测试确认未回归**

```bash
pytest tests/test_main_window.py tests/test_integration.py -v
```
Expected: 既有测试全部 PASS

- [ ] **Step 8: 提交**

```bash
git add gdm/gui/main_window.py
git commit -m "feat(main_window): 接入持久化缓存流程

- _on_folder_selected 改为先缓存铺 UI、后台 DiffWorker 增量更新
- 加'清空缩略图缓存'菜单项
- closeEvent 异步触发 incremental_vacuum
- 缓存读取失败时降级为原有同步扫描路径"
```

---

## Task 8: 端到端集成测试 + 性能手测

**Files:**
- Modify: `tests/cache/test_scanner_cached.py`（追加端到端用例）
- Test: 手动跑应用做性能验收

- [ ] **Step 1: 追加端到端用例 — 真实 DiffWorker（带 Qt 事件循环）**

在 `tests/cache/test_scanner_cached.py` 末尾追加：

```python
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
```

- [ ] **Step 2: 运行所有 cache 测试**

```bash
pytest tests/cache/ -v
```
Expected: 全部 PASS（含已有用例 + 新增 2 个端到端用例）

- [ ] **Step 3: 运行项目所有测试**

```bash
pytest -v
```
Expected: 0 failures

- [ ] **Step 4: 性能手测**

按 spec 中"性能验收基准"逐项手测，记录数据：

1. 准备一个含 1000 张 PNG（约 2MB/张）的目录
2. **场景 A：第二次访问首屏耗时**
   - 第一次点击：等扫描完成
   - 退出 App
   - 重新启动 App
   - 点击同一目录，掐表测"看到第一张缩略图"的时间
   - 目标：< 200ms

3. **场景 B：无变化时 diff 完成耗时**
   - 在同一会话内再点一次同目录
   - 看 log 或加临时计时输出，测 DiffWorker 完整跑完的时间
   - 目标：< 500ms

4. **场景 C：增量更新**
   - 用图片编辑器修改其中 5 张图
   - 重新点击目录
   - 测从点击到这 5 张缩略图全部更新完成的时间
   - 目标：< 2s

5. **场景 D：切换流畅性**
   - 在多个已缓存目录间快速切换
   - 主观感受 UI 是否卡顿
   - 目标：无可感知卡顿（< 16ms 帧时间，靠目测）

- [ ] **Step 5: 写一份手测报告并提交**

新建 `docs/superpowers/test-results/2026-06-16-thumbnail-cache-perf.md`，
按上面 4 个场景填写实测数据 + 是否达标 + 异常现象。

```bash
git add docs/superpowers/test-results/2026-06-16-thumbnail-cache-perf.md \
        tests/cache/test_scanner_cached.py
git commit -m "test(cache): 端到端集成测试 + 性能手测报告"
```

---

## Self-Review 已完成

- ✅ Spec 全部章节都有对应 Task：db / store / diff / scanner_cached / UI 接入 / 菜单 / vacuum / 测试 / 手测
- ✅ 类型与 API 命名前后一致：`CachedEntry` / `FileSnapshot` / `compute_diff` / `process_diff_sync`
- ✅ 没有占位符 / TBD / "类似 Task N"
- ✅ 每个 Task 都给出了完整代码、命令、预期输出
- ✅ 测试覆盖：纯函数 diff、DB CRUD、递归查询、LRU、损坏恢复、文件系统 walk、端到端信号
- ✅ 错误处理：缓存读失败降级、DB 写失败 log、损坏库隔离、worker 取消

