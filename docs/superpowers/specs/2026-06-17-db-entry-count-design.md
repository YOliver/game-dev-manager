# 设计文档：DB 持久化目录图片计数

**日期**: 2026-06-17

## 目标

解决两个问题：
1. 扫描过程中计数跳动（数字慢慢攀升而非一次到位）
2. 二次打开时无法秒显图片总数

方案：在 `folders` 表增加 `entry_count` 字段，扫描完成时写入，UI 计数从 DB 直接读取。

## 背景

当前计数通过 `len(self._sprites)` 实现，`_sprites` 在 `apply_entries_updated`（增量推送）过程中不断变化。且 `_sprites` 是内存数据，程序关闭后消失，二次打开必须等扫描完成才能知道总数。

## Before / After

```
Before: 扫描中数字跳动；重启后计数为 0 直到扫描完成
After:  扫描完成后持久化计数；重启后立显上次的总数
```

## Schema 变更

**文件**: `gdm/core/cache/db.py`

`folders` 表新增 `entry_count` 列：

```sql
CREATE TABLE IF NOT EXISTS folders (
    folder_path    TEXT PRIMARY KEY,
    last_scan_at   INTEGER NOT NULL,
    last_access_at INTEGER NOT NULL,
    entry_count    INTEGER NOT NULL DEFAULT 0
);
```

由于已有数据使用 `CREATE TABLE IF NOT EXISTS`，存量 DB 需通过迁移脚本新增列。在 `init_schema()` 中加入幂等迁移：

```python
def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA_SQL)
    # 幂等迁移：旧 DB 无 entry_count 列时新增
    try:
        conn.execute("ALTER TABLE folders ADD COLUMN entry_count INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass  # 列已存在
    conn.commit()
```

## 新增存储方法

**文件**: `gdm/core/cache/store.py`

新增 `update_folder_counts()`，统计指定 root 下所有叶子目录的 entries 数量并写入 `folders.entry_count`：

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

## 写入时机

**文件**: `gdm/core/cache/scanner_cached.py`

在 `process_diff_sync()` 末尾，`store.evict_lru_if_needed(conn)` 之后追加：

```python
    store.update_folder_counts(conn, norm_root)
```

只在 DiffWorker 完全扫描完成时写入，不在增量过程中写入，保证计数是最终值。

## UI 读取

**文件**: `gdm/gui/thumbnail_view.py`

### 1. 删除增量过程中的计数更新

删掉 `apply_entries_updated()` 末尾的 `self._update_count()`。

### 2. 新增 `set_current_folder()` 方法

ThumbnailView 本身不持有目录信息，由 main_window 在切换目录时传入：

```python
def set_current_folder(self, folder: str) -> None:
    """记录当前选中的目录路径，供 _update_count() 查询 DB。"""
    self._current_folder = folder
```

### 3. 重写 `_update_count()` 为从 DB 读取

无参数，直接使用 `self._current_folder` 查询：

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

### 4. `load()` / `load_from_cache()` 中的旧调用保持不变

不再从内存 `_sprites` 取计数，改为从 DB 读。由于 `set_current_folder()` 已在调用前由 main_window 设置，`_update_count()` 可正常查询。无需修改这两个方法的调用代码。

### 5. MainWindow 触发计数更新

**文件**: `gdm/gui/main_window.py`

在 `_on_folder_selected()` 中，加载数据前设置当前目录：

```python
def _on_folder_selected(self, folder_path: str) -> None:
    self._selected_folder = folder_path
    self.thumbnail_view.set_current_folder(folder_path)  # 新增
    # ... 原有逻辑 ...
```

在 `_on_diff_scan_done()` 末尾，扫描完成后刷新计数：

```python
def _on_diff_scan_done(self, root: str) -> None:
    # ... 原有清理逻辑 ...
    self.thumbnail_view._update_count()  # 新增
```

## 影响范围

- `gdm/core/cache/db.py` — schema 新增列 + 迁移
- `gdm/core/cache/store.py` — 新增 `update_folder_counts()`
- `gdm/core/cache/scanner_cached.py` — `process_diff_sync` 末尾调计数写入
- `gdm/gui/thumbnail_view.py` — `_update_count` 改为 DB 查询；删掉 `apply_entries_updated` 中的计数调用；新增 `set_current_folder`
- `gdm/gui/main_window.py` — `_on_diff_scan_done` 触发计数更新；`_on_folder_selected` 传入目录

存量 DB 兼容：`ALTER TABLE ... ADD COLUMN` 幂等执行，旧数据自动初始化为 0。
