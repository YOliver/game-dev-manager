# entry_count 递归计数实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `folders.entry_count` 从"本目录直接文件数"改为"本目录及其所有子目录的文件总数（递归）"，简化 UI 查询。

**Architecture:** 改 `store.py` 中 `update_folder_counts()` 的 SQL 为递归统计 + 新增 `_ensure_ancestor_folders()` 补中间目录行；简化 `thumbnail_view.py` 中 `_update_count()` 的查询为单行读取；更新 `test_store.py` 断言。

**Tech Stack:** Python, sqlite3

---

## 文件改动清单

| 文件 | 改动类型 |
|---|---|
| `gdm/core/cache/store.py` | 修改 `update_folder_counts()` SQL + 新增 `_ensure_ancestor_folders()` + `_norm_path_parent()` + 新增 `Optional` 导入 |
| `gdm/gui/thumbnail_view.py` | 简化 `_update_count()` SQL 查询 |
| `tests/cache/test_store.py` | 更新递归计数断言 + 新增祖先目录补行测试 |

---

### Task 1: 新增 `_norm_path_parent()` 和 `_ensure_ancestor_folders()`

**Files:**
- Modify: `gdm/core/cache/store.py`

- [ ] **Step 1: 更新 typing 导入**

在 `store.py` 顶部，将 `from typing import Iterable, List, Tuple` 改为：

```python
from typing import Iterable, List, Optional, Tuple
```

- [ ] **Step 2: 在 `update_folder_counts` 上方添加 `_norm_path_parent()`**

在 `store.py` 第 168 行（`update_folder_counts` 函数之前）插入：

```python
def _norm_path_parent(path: str) -> Optional[str]:
    """返回标准化路径的父目录，根目录返回 None。

    >>> _norm_path_parent("d/sub")
    'd'
    >>> _norm_path_parent("d")
    None
    """
    idx = path.rfind("/")
    if idx <= 0:
        return None
    return path[:idx]


def _ensure_ancestor_folders(conn: sqlite3.Connection, root: str) -> None:
    """为 root 下所有叶子目录的缺失祖先目录补充 folders 行。"""
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
            parent = _norm_path_parent(path)
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

- [ ] **Step 3: 运行已有测试确认无回归**

```bash
pytest tests/cache/test_store.py -v
```

预期：所有已有测试仍通过。

- [ ] **Step 4: 提交**

```bash
git add gdm/core/cache/store.py
git commit -m "feat: 新增 _ensure_ancestor_folders 和 _norm_path_parent"
```

---

### Task 2: 修改 `update_folder_counts()` 为递归计数

**Files:**
- Modify: `gdm/core/cache/store.py`

- [ ] **Step 1: 修改 `update_folder_counts()` 的 SQL 并调用 `_ensure_ancestor_folders`**

将 `store.py` 中现有的 `update_folder_counts()` 函数（第 169-180 行）替换为：

```python
def update_folder_counts(conn: sqlite3.Connection, root: str) -> None:
    """统计 root 下各目录的递归 entry 数量并更新 folders.entry_count。"""
    _ensure_ancestor_folders(conn, root)
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

- [ ] **Step 2: 更新测试断言为递归计数值**

修改 `tests/cache/test_store.py` 中 `test_counts_root_and_subdirs`（第 148 行）的断言：

```python
# 旧：非递归
# assert rows == {"d": 2, "d/sub": 1, "d/sub/nested": 1}
# 新：递归（d 含子目录，d/sub 含嵌套子目录）
assert rows == {"d": 4, "d/sub": 2, "d/sub/nested": 1}
```

- [ ] **Step 3: 运行测试验证新的递归计数逻辑**

```bash
pytest tests/cache/test_store.py::TestUpdateFolderCounts -v
```

预期：全部通过。

- [ ] **Step 4: 提交**

```bash
git add gdm/core/cache/store.py tests/cache/test_store.py
git commit -m "feat: entry_count 改为递归计数"
```

---

### Task 3: 新增中间祖先目录补行测试

**Files:**
- Modify: `tests/cache/test_store.py`

- [ ] **Step 1: 在 `TestUpdateFolderCounts` 类末尾添加测试方法**

在 `tests/cache/test_store.py` 中 `test_unrelated_folder_not_affected` 之后（第 172 行之后）添加：

```python
    def test_ancestor_folders_created(self, conn):
        """中间祖先目录没有直接文件时，_ensure_ancestor_folders 自动补行。"""
        # 只创建最深层的叶子目录
        store.upsert_folder(conn, "d/sub/deep", now=1000)
        store.upsert_entry(conn, _entry("d/sub/deep", "x.png"))
        conn.commit()

        store.update_folder_counts(conn, "d")

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
```

- [ ] **Step 2: 运行新测试**

```bash
pytest tests/cache/test_store.py::TestUpdateFolderCounts::test_ancestor_folders_created -v
```

预期：PASS。

- [ ] **Step 3: 确认全部 store 测试通过**

```bash
pytest tests/cache/test_store.py -v
```

预期：全部通过。

- [ ] **Step 4: 提交**

```bash
git add tests/cache/test_store.py
git commit -m "test: 新增祖先目录补行测试"
```

---

### Task 4: 简化 UI 中的 `_update_count()` 查询

**Files:**
- Modify: `gdm/gui/thumbnail_view.py`

- [ ] **Step 1: 简化 `_update_count()` 的 SQL 查询**

将 `thumbnail_view.py` 第 351-354 行的查询改为单行读取：

```python
# 旧代码（351-354行）：
#         row = conn.execute(
#             "SELECT COALESCE(SUM(entry_count), 0) FROM folders "
#             "WHERE folder_path = ? OR folder_path LIKE ?",
#             (norm, norm + "/%"),
#         ).fetchone()

# 新代码：
        row = conn.execute(
            "SELECT entry_count FROM folders WHERE folder_path = ?",
            (norm,),
        ).fetchone()
```

即 `_update_count()` 完整代码变为：

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

- [ ] **Step 2: 运行 thumbnail_view 测试**

```bash
pytest tests/test_thumbnail_view.py -v
```

预期：全部通过（`_update_count` 读 DB 为空时 count 为 0，行为不变）。

- [ ] **Step 3: 提交**

```bash
git add gdm/gui/thumbnail_view.py
git commit -m "feat: UI 计数查询简化为单行读取"
```

---

### Task 5: 全量回归测试

- [ ] **Step 1: 运行全部测试**

```bash
pytest tests/ -v
```

预期：全部通过。

