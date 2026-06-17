# DB 持久化目录图片计数 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `folders` 表增加 `entry_count` 字段，扫描完成时批量写入，UI 计数改为 DB 查询，解决计数跳动和二次打开立显问题。

**Architecture:** Schema 加列 → 增量幂等迁移 → `process_diff_sync` 末尾批量写入计数 → `_update_count` 改为 DB SUM 查询 → main_window 在切换目录和扫描完成时触发更新。

**Tech Stack:** SQLite ALTER TABLE, SQL SUM/LIKE

---

### Task 1: Schema 变更 + 迁移 + 存储方法

**Files:**
- Modify: `gdm/core/cache/db.py`
- Modify: `gdm/core/cache/store.py`

- [ ] **Step 1: `_SCHEMA_SQL` 中 `folders` 表新增 `entry_count` 列**

```sql
CREATE TABLE IF NOT EXISTS folders (
    folder_path    TEXT PRIMARY KEY,
    last_scan_at   INTEGER NOT NULL,
    last_access_at INTEGER NOT NULL,
    entry_count    INTEGER NOT NULL DEFAULT 0
);
```

- [ ] **Step 2: `init_schema()` 中加入幂等迁移**

```python
def init_schema(conn: sqlite3.Connection) -> None:
    """创建表与索引（幂等）。"""
    conn.executescript(_SCHEMA_SQL)
    # 幂等迁移：旧 DB 无 entry_count 列时新增
    try:
        conn.execute("ALTER TABLE folders ADD COLUMN entry_count INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass  # 列已存在
    conn.commit()
```

- [ ] **Step 3: `store.py` 新增 `update_folder_counts()`**

在文件末尾追加：

```python
def update_folder_counts(conn: sqlite3.Connection, root: str) -> None:
    """统计 root 下各目录的 entry 数量并更新 folders.entry_count。"""
    conn.execute("""
        UPDATE folders
        SET entry_count = (
            SELECT COUNT(*)
            FROM entries
            WHERE entries.folder_path = folders.folder_path
        )
        WHERE folder_path = ? OR folder_path LIKE ?
    """, (root, root + "/%"))
    conn.commit()
```

- [ ] **Step 4: 提交**

```bash
git add gdm/core/cache/db.py gdm/core/cache/store.py
git commit -m "feat: folders 表新增 entry_count 列及迁移脚本"
```

---

### Task 2: 扫描完成时写入计数

**Files:**
- Modify: `gdm/core/cache/scanner_cached.py`

- [ ] **Step 1: 在 `process_diff_sync()` 末尾调用计数写入**

在 `store.evict_lru_if_needed(conn)` 之后、函数结束之前追加：

```python
    store.evict_lru_if_needed(conn)
    store.update_folder_counts(conn, norm_root)
```

- [ ] **Step 2: 提交**

```bash
git add gdm/core/cache/scanner_cached.py
git commit -m "feat: 扫描完成后写入各目录 entry_count"
```

---

### Task 3: UI 层改为 DB 读取计数

**Files:**
- Modify: `gdm/gui/thumbnail_view.py`

- [ ] **Step 1: 删除增量过程中的计数更新**

删掉 `apply_entries_updated()` 末尾的 `self._update_count()` 一行。

- [ ] **Step 2: 新增 `set_current_folder()`**

在 `_update_count()` 方法上方新增：

```python
    def set_current_folder(self, folder: str) -> None:
        """记录当前选中的目录路径，供 _update_count() 查询 DB。"""
        self._current_folder = folder
```

- [ ] **Step 3: 重写 `_update_count()`**

将当前的 `_update_count()` 方法替换为：

```python
    def _update_count(self) -> None:
        """从 DB 读取当前目录的图片总数并更新标签。"""
        if not getattr(self, "_current_folder", None):
            return
        from gdm.core.cache.db import open_connection, get_db_path
        from gdm.core.cache.scanner_cached import normalize_folder
        try:
            conn = open_connection(get_db_path())
            try:
                norm = normalize_folder(self._current_folder)
                row = conn.execute(
                    "SELECT COALESCE(SUM(entry_count), 0) FROM folders "
                    "WHERE folder_path = ? OR folder_path LIKE ?",
                    (norm, norm + "/%"),
                ).fetchone()
                self._count_label.setText(str(row[0]) if row else "0")
            finally:
                conn.close()
        except sqlite3.DatabaseError:
            pass
```

- [ ] **Step 4: 提交**

```bash
git add gdm/gui/thumbnail_view.py
git commit -m "feat: 缩略图计数改为 DB 聚合查询"
```

---

### Task 4: MainWindow 接入目录传递和计数刷新

**Files:**
- Modify: `gdm/gui/main_window.py`

- [ ] **Step 1: `_on_folder_selected()` 中设置目录**

在 `self._selected_folder = folder_path` 之后追加：

```python
        self.thumbnail_view.set_current_folder(folder_path)
```

- [ ] **Step 2: `_on_diff_scan_done()` 末尾刷新计数**

在方法末尾（`self._active_diff_worker = None` 之后）追加：

```python
        self.thumbnail_view._update_count()
```

- [ ] **Step 3: 提交**

```bash
git add gdm/gui/main_window.py
git commit -m "feat: MainWindow 接入目录传递和扫描完成计数刷新"
```

---

### Task 5: 编写测试

**Files:**
- Modify: `tests/test_cache.py`（如不存在则参考现有 `tests/test_extractor.py` 结构创建）

- [ ] **Step 1: 编写 `update_folder_counts` 测试**

```python
import os
import sqlite3
import tempfile
from gdm.core.cache import db, store, CachedEntry


def test_update_folder_counts():
    """update_folder_counts 应正确统计各目录 entry 数量。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = sqlite3.connect(db_path)
        try:
            db.init_schema(conn)

            # 创建 folder 和 entries
            root = "/test/root"
            sub = "/test/root/sub"
            store.upsert_folder(conn, root, 1000)
            store.upsert_folder(conn, sub, 1000)

            # 插入 3 条 entries（root 下 2 条，sub 下 1 条）
            for i in range(2):
                store.upsert_entry(conn, CachedEntry(
                    folder_path=root, file_name=f"a{i}.png",
                    width=64, height=64, size=100,
                    format="PNG", color_mode="RGBA",
                    mtime_ns=1000 + i, thumb_blob=None, thumb_mtime_ns=None,
                ))
            store.upsert_entry(conn, CachedEntry(
                folder_path=sub, file_name="b.png",
                width=64, height=64, size=100,
                format="PNG", color_mode="RGBA",
                mtime_ns=2000, thumb_blob=None, thumb_mtime_ns=None,
            ))
            conn.commit()

            # 写入计数
            store.update_folder_counts(conn, root)

            # 验证
            row = conn.execute(
                "SELECT folder_path, entry_count FROM folders "
                "WHERE folder_path = ? OR folder_path LIKE ? "
                "ORDER BY folder_path",
                (root, root + "/%"),
            ).fetchall()

            assert len(row) == 2
            counts = {r[0]: r[1] for r in row}
            assert counts[root] == 2
            assert counts[sub] == 1

            # 根目录 SUM 应为 3
            total = conn.execute(
                "SELECT COALESCE(SUM(entry_count), 0) FROM folders "
                "WHERE folder_path = ? OR folder_path LIKE ?",
                (root, root + "/%"),
            ).fetchone()[0]
            assert total == 3
        finally:
            conn.close()
```

- [ ] **Step 2: 运行测试**

```bash
pytest tests/test_cache.py -v
```

- [ ] **Step 3: 提交**

```bash
git add tests/test_cache.py
git commit -m "test: 新增 entry_count 读写测试"
```
