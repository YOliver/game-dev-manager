# 设计文档：`entry_count` 存储递归文件数

**日期**: 2026-06-18

## 目标

`folders.entry_count` 从"本目录直接文件数"改为"本目录及其所有子目录的文件总数（递归）"。UI 读取时无需再 `SUM` 聚合子目录，直接单行查询即可。

## 现状

```
当前语义：entry_count = 本目录直接文件数（非递归）
UI 查询：  SELECT SUM(entry_count) FROM folders WHERE LIKE 'root/%'
         ↑ 每次 UI 刷新都要 SUM 聚合
```

## 目标语义

```
优化后：   entry_count = 本目录 + 所有子孙目录的文件总数（递归）
UI 查询：  SELECT entry_count FROM folders WHERE folder_path = 'root'
         ↑ 单行读取，无需聚合
```

### 示例

目录结构：`d/` 有 2 个文件，`d/sub/` 有 1 个文件

| `folder_path` | 当前 entry_count | 优化后 entry_count |
|---|---|---|
| `d` | 2 | 3 |
| `d/sub` | 1 | 1 |

## 改动范围

### 1. `gdm/core/cache/store.py` — `update_folder_counts()`

SQL 从精确匹配改为递归匹配：

```python
def update_folder_counts(conn: sqlite3.Connection, root: str) -> None:
    """统计 root 下各目录的递归 entry 数量并更新 folders.entry_count。"""
    # 1) 确保所有祖先目录都有 folders 行（见下文 §2）
    _ensure_ancestor_folders(conn, root)

    # 2) 对 root 下所有目录，计算递归文件数
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
    conn.commit()
```

关键变化：
- 子查询增加 `OR entries.folder_path LIKE (folders.folder_path || '/%')` 匹配子孙目录
- 新增 `_ensure_ancestor_folders()` 处理中间目录问题（见 §2）

### 2. 中间目录补行 — `_ensure_ancestor_folders()`

**问题**：`folders` 表只有叶子目录（实际包含文件的目录）的行，不含中间祖先目录。例如 `d/a/b/` 有文件，但 `d/` 和 `d/a/` 可能没有直接文件，`folders` 里就缺少这两行。用户选择 `d/` 时，`_update_count()` 查不到对应行。

**解决**：在 `update_folder_counts()` 开头，遍历 root 下所有叶子目录的路径，为缺失的祖先目录插入 `folders` 行。

```python
def _ensure_ancestor_folders(conn: sqlite3.Connection, root: str) -> None:
    """为 root 下所有文件夹路径的缺失祖先目录补充 folders 行。"""
    norm_root = root.rstrip("/")

    # 收集 root 下所有已有 folder_path
    existing = {
        r[0] for r in conn.execute(
            "SELECT folder_path FROM folders WHERE folder_path = ? OR folder_path LIKE ?",
            (norm_root, norm_root + "/%"),
        ).fetchall()
    }

    # 计算所有需要存在的祖先路径
    ancestors = set()
    for path in existing:
        while True:
            parent = norm_path_parent(path)
            if parent is None or parent in ancestors or parent in existing:
                break
            if not parent.startswith(norm_root):
                break
            ancestors.add(parent)
            path = parent

    if not ancestors:
        return

    # 批量插入缺失的祖先行
    conn.executemany(
        "INSERT OR IGNORE INTO folders (folder_path, last_scan_at, last_access_at) VALUES (?, 0, 0)",
        [(a,) for a in sorted(ancestors)],
    )
    conn.commit()
```

其中 `norm_path_parent` 是一个简单的路径父目录提取：

```python
def _norm_path_parent(path: str) -> Optional[str]:
    """返回标准化路径的父目录，根目录返回 None。"""
    idx = path.rfind("/")
    if idx <= 0:
        return None
    return path[:idx]
```

**插入行的约束处理**：
- `last_scan_at = 0`：该目录没有直接文件，不参与扫描时间判断
- `last_access_at = 0`：不影响 LRU 淘汰
- `entry_count` 由后续 `UPDATE` 写入

### 3. `gdm/gui/thumbnail_view.py` — `_update_count()` 简化

```python
def _update_count(self) -> None:
    """从 DB 读取当前目录的图片总数并更新标签。"""
    if not getattr(self, "_current_folder", None):
        return
    from gdm.core.cache.db import open_connection
    from gdm.core.cache import get_db_path
    from gdm.core.cache.scanner_cached import normalize_folder
    try:
        conn = open_connection(get_db_path())
        try:
            norm = normalize_folder(self._current_folder)
            row = conn.execute(
                "SELECT entry_count FROM folders WHERE folder_path = ?",
                (norm,),
            ).fetchone()
            self._count_label.setText(str(row[0]) if row else "0")
        finally:
            conn.close()
    except sqlite3.DatabaseError:
        pass
```

变化：
- `SELECT COALESCE(SUM(entry_count), 0) FROM folders WHERE ... LIKE` → `SELECT entry_count FROM folders WHERE folder_path = ?`
- 不再需要 SUM 聚合和 LIKE 子目录匹配

### 4. `gdm/gui/main_window.py` — `_on_diff_scan_done()` 保持不变

已调用 `thumbnail_view._update_count()`，无需修改。

## 测试更新

### `tests/cache/test_store.py`

更新 `test_update_folder_counts` 和 `test_update_folder_counts_only_affected_root` 的断言，使其符合新的递归计数逻辑：

```python
# 原断言：entry_count 非递归
assert rows == {"d": 2, "d/sub": 1, "d/sub/nested": 1}
# 新断言：entry_count 递归
assert rows == {"d": 4, "d/sub": 2, "d/sub/nested": 1}
```

### `tests/test_thumbnail_view.py`

`_update_count` 改用单行查询后，需确保测试中的 `set_current_folder` + `_update_count` 交互逻辑仍然通过。测试逻辑本身无需变化（DB 为空时读不到行，count 仍为 0）。

## 边界情况

| 场景 | 处理方式 |
|---|---|
| 用户选择叶子目录 | `entry_count` = 该目录文件的递归数（恰好等于直接文件数） |
| 用户选择中间祖先目录 | `_ensure_ancestor_folders` 补行后，`entry_count` 正确包含所有子孙文件 |
| 用户选择没有任何文件的空目录 | `folders` 无行，`_update_count` 返回 "0" |
| 文件删除后子目录变空 | 下次扫描 `update_folder_counts` 重新计算，自动正确 |

## 影响范围总结

| 文件 | 改动类型 |
|---|---|
| `gdm/core/cache/store.py` | `update_folder_counts()` 改 SQL + 新增 `_ensure_ancestor_folders()` + `_norm_path_parent()` |
| `gdm/gui/thumbnail_view.py` | `_update_count()` 简化 SQL 查询 |
| `tests/cache/test_store.py` | 更新递归计数断言 |
