---
name: Fix Foreign Key Race Condition Design
description: 修复 scanner_cached.py 中 process_diff_sync 的 FOREIGN KEY constraint failed 并发竞态条件
type: design
---

# 修复 FOREIGN KEY 并发竞态条件

## 背景

用户点击大目录扫描时，`process_diff_sync()` 间歇性抛出 `sqlite3.IntegrityError: FOREIGN KEY constraint failed`。

在上次"跳过隐藏文件"改动后频发，因为大量仅有 `._xxx.png` 的目录不再被处理，其 `last_access_at` 不更新，更易被 `evict_lru_if_needed` 淘汰。

## 根因

`store.py` 中 `upsert_folder()` 和 `upsert_entry()` 各自有 `conn.commit()`（`store.py:26`、`store.py:85`），意味着文件夹创建和条目插入在**两个独立事务**中完成。

### 竞态条件

```
Worker A（处理文件 X，位于目录 D）:
  upsert_folder(D)     ──conn.commit()──  D 出现在 folders 表                ✓
  _read_metadata_and_thumb(full_path)     <── Pillow I/O，耗时较长
  upsert_entry(D, X)   ──conn.commit()──  FOREIGN KEY 约束失败！！！         ✗
                                          因为 Worker B 在此期间删除了 D

Worker B（另一个 DiffWorker，正在执行 evict_lru_if_needed）:
  evict_lru_if_needed() ──conn.commit()──  删除 folders 表中的 D（它因
                                           last_access_at 未更新而成为最旧行）
```

### 为什么之前不明显

跳过隐藏文件之前，每个包含图片的目录都会更新 `last_access_at`，不易被 LRU 淘汰。改动后，仅有隐藏文件的目录不再更新 `last_access_at`，在并发场景下极易被其他 Worker 淘汰。

## 方案

将 `upsert_folder` + `upsert_entry` 合并到**同一事务**中。如果文件夹不存在，SQLite 会立即报错并回滚整个事务；如果存在，两次操作在同一个原子操作中完成，不会被其他连接打断。

具体做法：
1. 从 `store.py` 的 `upsert_folder()`、`upsert_entry()`、`delete_entries()` 中移除 `conn.commit()`
2. 在 `scanner_cached.py` 的 `process_diff_sync()` 中添加显式 `conn.commit()`

---

## 改动点

### 1. `gdm/core/cache/store.py`：移除三个函数的自提交

#### `upsert_folder()`（第 14-26 行）

```python
# 修改前
def upsert_folder(conn, folder_path, now):
    conn.execute(...)
    conn.commit()          # ← 删除这行

# 修改后
def upsert_folder(conn, folder_path, now):
    """插入或刷新 folders 行。调用方负责 commit。"""
    conn.execute(...)
    # 提交由调用方负责
```

#### `upsert_entry()`（第 60-85 行）

```python
# 修改前
def upsert_entry(conn, e):
    conn.execute(...)
    conn.commit()          # ← 删除这行

# 修改后
def upsert_entry(conn, e):
    """插入或刷新 entries 行。调用方负责 commit。"""
    conn.execute(...)
    # 提交由调用方负责
```

#### `delete_entries()`（第 117-124 行）

```python
# 修改前
def delete_entries(conn, keys):
    conn.executemany(...)
    conn.commit()          # ← 删除这行

# 修改后
def delete_entries(conn, keys):
    """删除 entries 行。调用方负责 commit。"""
    conn.executemany(...)
    # 提交由调用方负责
```

> `mark_scan_done()` 和 `evict_lru_if_needed()` 保留自提交，它们在其他上下文中独立使用，且不参与该竞态条件。

### 2. `gdm/core/cache/scanner_cached.py`：在 `process_diff_sync()` 中添加显式提交

#### 删除 removed 条目后提交（约第 136-139 行）

```python
# 修改后
if removed:
    store.delete_entries(conn, removed)
    conn.commit()                         # ← 新增
    if on_removed:
        on_removed(list(removed))
```

#### 每批条目后提交（约第 164 行）

```python
# 修改后
if len(batch) >= db.BATCH_EMIT_SIZE:
    conn.commit()                         # ← 新增
    if on_batch_updated:
        on_batch_updated(list(batch))
    batch.clear()
```

#### 最后一批条目后提交（约第 169 行）

```python
# 修改后
if batch:
    conn.commit()                         # ← 新增
    if on_batch_updated:
        on_batch_updated(list(batch))
```

> `mark_scan_done()` 和 `evict_lru_if_needed()` 保留自提交，在批次处理循环之后不需要额外 commit。

### 3. 测试更新

受影响的测试文件：
- `tests/cache/test_store.py`（如有）：验证移除自提交后单个函数行为不变
- `tests/cache/test_scanner_cached.py`：现有测试应全部通过，因为 `process_diff_sync` 现在负责提交

---

## 影响范围

| 文件 | 改动 | 影响 |
|------|------|------|
| `gdm/core/cache/store.py` | 从 3 个函数中移除 `conn.commit()`：`upsert_folder`、`upsert_entry`、`delete_entries` | 调用方必须负责提交 |
| `gdm/core/cache/scanner_cached.py` | 在 `process_diff_sync()` 中添加 3 处 `conn.commit()` | 保证 `upsert_folder` + `upsert_entry` 在同一事务中 |
| `tests/cache/test_scanner_cached.py` | 无测试改动；确认现有测试 100% 通过 | 回归验证 |

## 事务边界对比

```
修改前：
  upsert_folder(D) ──commit──  [窗口：Worker B 可以删除 D]
  _read_metadata_and_thumb()    <── 在此窗口内，D 可能被删除
  upsert_entry(D, X) ──commit── ** FK 约束失败！

修改后：
  upsert_folder(D) ─┐
  _read_metadata_and_thumb()  ├── 同一事务，无法打断
  upsert_entry(D, X) ─┘
  conn.commit()                ** 原子成功或回滚
```
