# 缩略图持久化缓存设计文档

## 概述

为 Game Dev Manager 引入**持久化缩略图缓存系统**，解决"每次点击目录都要重新扫描和导入图片"的性能问题。
通过 SQLite 集中存储元数据 + 缩略图 blob，配合"立即出缓存 + 后台增量 diff"策略，
使得已访问过的目录在二次点击时**首屏 < 200ms**，并自动检测增删改的图片做增量更新。

## 背景

### 当前行为

每次用户点击左侧树中的目录，都会触发完整的 `scan_with_progress()` 流程：

1. 列出目录所有图片文件（按扩展名过滤）
2. 对每张图调用 Pillow 读取元数据（width / height / format）
3. 把 sprite 列表交给 `ThumbnailView`，逐张异步生成 128×128 缩略图

现有缓存仅有一层：`ThumbnailView._thumbnails`（500 张内存 LRU，按 mtime 校验），
**仅在同一会话内对同一目录二次访问时命中**。重启 App 后全部丢失，
切换到不同目录时上一个目录的缩略图也会被新内容挤掉。

### 性能瓶颈

| 阶段 | 现状 | 上千张图的耗时 |
|---|---|---|
| 文件列表扫描 | 每次完整 `os.scandir` | ~50ms |
| 元数据读取 | 每张图 Pillow 打开文件 | 数秒～十几秒 |
| 缩略图生成 | 每张图 Pillow 缩放 + 编码 | 数秒～几十秒 |

**核心问题**：缓存层只覆盖了"图片解码"（CPU），没有覆盖"文件 I/O + 元数据读取"，
也没有跨会话持久化。

## 目标

- 已访问过的目录**首屏出现 < 200ms**（亚秒级）
- 跨 App 重启依然有效
- 上千张图里只改了少数几张时，**只重做变化的部分**
- 缓存数据**集中存放**，不污染用户素材目录
- 缓存损坏 / 失败时**自动降级**为现行的"每次重扫"模式，不阻断使用

## 非目标

- 不做手动指定缓存目录的功能
- 不做缓存内容的可视化管理界面（仅一个"清空缓存"菜单项）
- 不做目录重命名/移动后的缓存自动迁移（自然 LRU 过期）
- 不做并行的缩略图生成（首版串行；如实测过慢再加，作为后续优化）
- **不优化"首次访问新目录"的速度**：本次需求只解决"重复访问已扫过的目录"的问题。
  首次访问仍走 DiffWorker 串行处理，与现状耗时相当（但 UI 不再阻塞主线程）。
  并行化首次扫描作为后续独立优化跟踪

## 架构

### 模块结构

新增 `gdm/core/cache/` 子包，承担所有持久化缓存职责：

```
gdm/core/cache/
├── __init__.py           # 对外 API：get_cache() 单例
├── db.py                 # SQLite 连接管理、schema 初始化、损坏恢复、常量
├── store.py              # 业务层 CRUD + LRU 淘汰：纯 DB 操作，不涉及扫描/UI
├── diff.py               # 纯函数 diff(cached, current) -> (added, changed, removed)
└── scanner_cached.py     # 编排器：load_folder_cached()，对接 UI
```

**职责切分**（每个模块一个清晰目的）：

| 模块 | 职责 | 不做的事 |
|---|---|---|
| `db` | 只懂 SQLite，不懂业务 | 不知道何为 sprite |
| `store` | 实体 CRUD + LRU + 递归查询 | 不知道扫描，不知道 UI |
| `diff` | 纯函数比对（按 (folder_path, file_name) 复合键） | 不碰 DB，不碰文件系统外的状态 |
| `scanner_cached` | 编排：取递归缓存 → `os.walk` 列文件 → diff → 增量更新 → 通知 UI | 不直接操作 SQL |

### 递归扫描的缓存语义

**前提**：当前 `scanner.scan_with_progress` 默认 `recursive=True`，
`MainWindow._on_folder_selected` 调用链全部走递归扫描。
用户点击目录 D 时显示的是 D **及其所有后代目录**的图片。

**缓存组织方式**：按"叶子目录"粒度存储，**不**按"被点击的目录"存储。

- 每个 `entries` 行的 `folder_path` 是该图片**直接所在的目录**（不是被点击的根）
- 用户点击 D → 查询 `WHERE folder_path = D OR folder_path LIKE 'D/%'` 的所有条目
- 子目录新增/修改文件 → 只影响该子目录的缓存行，不波及兄弟目录
- LRU 淘汰也按叶子目录粒度（`folders` 表每行就是一个叶子目录）

**为什么选这个方案**：

- 用户从 D 进、从 D 的子目录 D/sub 进时，**复用同一份缓存**，不重复存储
- 修改 D/sub/x.png 只导致 D/sub 这一行缓存失效，D 下其他子目录无需 diff
- LRU 粒度更细，常用子目录不会因偶尔点根目录导致整体被挤出

**对 diff 流程的影响**：

DiffWorker 在收到根目录 D 后，需要：
1. 用 `os.walk(D)` 列出**所有后代叶子目录** + 每个目录下的图片文件名
2. 用 `SELECT folder_path, file_name, ... FROM entries WHERE folder_path = D OR folder_path LIKE ?` 拿到所有相关缓存
3. 按 `(folder_path, file_name)` 复合键做 diff，得到 added / changed / removed
4. removed 也需要带 folder_path（同名文件可能存在于不同子目录）

**`folder_path` 规范化**：
- Windows 平台：`os.path.abspath` + `replace('\\', '/')` + `lower()`
- 当前项目仅 Windows，跨平台支持是非目标

### 缓存目录路径

使用 `QStandardPaths.AppDataLocation` 解析平台特定的应用数据目录。

- Windows: `%APPDATA%/game-dev-manager/cache/cache.db`
- macOS: `~/Library/Application Support/game-dev-manager/cache/cache.db`
- Linux: `~/.local/share/game-dev-manager/cache/cache.db`

### 与现有代码的关系

| 现有文件 | 改动 |
|---|---|
| `gdm/core/scanner.py` | 保留。`scan_with_progress` 仍作为"无缓存模式"的降级路径 |
| `gdm/core/metadata.py` | 不动。被 `scanner_cached` 调用 |
| `gdm/gui/thumbnail_view.py` | 新增 `load_from_cache(entries)` 入口；新增信号处理槽接增量更新；保留内存 LRU 作为二级缓存 |
| `gdm/gui/main_window.py` | `_on_folder_selected` 改为调用 `scanner_cached.load_folder_cached`，进度面板逻辑保留为首次访问时的降级路径 |

## 数据库 Schema

```sql
-- 目录登记表
CREATE TABLE folders (
    folder_path    TEXT PRIMARY KEY,    -- 规范化绝对路径（小写、正斜杠）
    last_scan_at   INTEGER NOT NULL,    -- Unix 秒，最近一次完成 diff 的时间
    last_access_at INTEGER NOT NULL     -- Unix 秒，最近一次被点击访问的时间，用于 LRU
);

-- 文件条目表
CREATE TABLE entries (
    folder_path    TEXT NOT NULL,        -- 图片直接所在的目录（非用户点击的根目录）
    file_name      TEXT NOT NULL,        -- 仅文件名，不含路径
    mtime_ns       INTEGER NOT NULL,     -- os.stat().st_mtime_ns，纳秒精度
    size           INTEGER NOT NULL,     -- 字节
    width          INTEGER,              -- 可空：读取失败时为 NULL
    height         INTEGER,
    format         TEXT,                 -- 'PNG' / 'JPEG' / 'WEBP' ...
    color_mode     TEXT,                 -- 'RGB' / 'RGBA' / 'P' ...，对应 SpriteInfo.color_mode
    thumb_blob     BLOB,                 -- 128×128 WebP 编码的缩略图，可空
    thumb_mtime_ns INTEGER,              -- 缩略图基于哪个版本生成的；与 mtime_ns 不一致即失效
    PRIMARY KEY (folder_path, file_name),
    FOREIGN KEY (folder_path) REFERENCES folders(folder_path) ON DELETE CASCADE
);

-- 用于按叶子目录精确查询
CREATE INDEX idx_entries_folder ON entries(folder_path);
-- 用于递归查询：WHERE folder_path LIKE 'D/%'
-- SQLite 会用前缀索引扫描，不需要单独建
```

### Schema 设计要点

1. **缩略图编码用 WebP**（`THUMB_FORMAT="WEBP"`, `THUMB_QUALITY=80`）：
   128×128 WebP 约 2-5KB，PNG 约 8-20KB。上千张图差距明显。Pillow 原生支持。

2. **`mtime_ns` 而非 `mtime`**：Windows NTFS 提供 100ns 精度，
   纳秒整数对比比浮点更可靠，避免文件系统精度差异引发的伪命中。

3. **`thumb_mtime_ns` 单独存**：源文件 mtime 变化后，元数据可能已重读、
   缩略图还没来得及重做。读取时若 `thumb_mtime_ns != mtime_ns` 即视为缩略图失效，
   UI 显示占位图、等待后台重做。

4. **`format` / `color_mode` 字段**：完整覆盖 `SpriteInfo` 的全部字段，
   保证从缓存重建的 SpriteInfo 与 `metadata.extract()` 的输出语义一致，
   `detail_panel` 等下游组件无需关心数据来源。

5. **不存全路径**：仅 `folder_path + file_name`。DB 体积小。
   完整路径在 UI 层按需拼接：`os.path.join(folder_path, file_name)`

6. **连接初始化 PRAGMA**：
   - `journal_mode=WAL` — 读写并发好（UI 线程读、后台 diff 线程写）
   - `synchronous=NORMAL` — 缓存数据丢一点能接受，换性能
   - `foreign_keys=ON` — 让 CASCADE 生效
   - `auto_vacuum=INCREMENTAL` — 仅在**首次创建** DB 时设置（建库前执行）；
     允许后续用 `PRAGMA incremental_vacuum(N)` 按页回收空间

## 核心流程

### 点击目录后发生什么

```
用户点击目录 D
   │
   ▼
[UI 线程] MainWindow._on_folder_selected(D)
   │
   ├─① 取消上一个未完成的 DiffWorker（如果有）
   │     旧 worker 收到 cancel 后会停在下一张图前；已写入 DB 的部分保留
   │
   ├─② store.touch_folders_under(D)
   │     更新 D 及其所有后代叶子目录的 last_access_at
   │     （新叶子目录的 folders 行延后到 mark_scan_done 时插入）
   │
   ├─③ cached = store.get_entries_recursive(D)
   │     SELECT folder_path, file_name, width, height, color_mode,
   │            mtime_ns, size, format, thumb_blob, thumb_mtime_ns
   │     FROM entries
   │     WHERE folder_path = ? OR folder_path LIKE ?
   │     参数: (D, D + '/%')
   │
   ├─④ 立即铺 UI（亚秒级首屏）
   │     thumbnail_view.load_from_cache(cached)
   │     入参 cached 是 List[CachedEntry]，CachedEntry 含 SpriteInfo 全部字段：
   │     folder_path / file_name / width / height / size / format / color_mode
   │     + 缓存校验字段：mtime_ns / thumb_blob / thumb_mtime_ns
   │     UI 用 os.path.join(folder_path, file_name) 拼出 SpriteInfo.file_path
   │     - 元数据有效  → 显示文件名/尺寸
   │     - thumb_blob 非空且 thumb_mtime_ns == mtime_ns
   │       → QPixmap.loadFromData(blob, "WEBP") 解码后显示
   │       同时写入内存 LRU（_thumbnails），后续滚动复用
   │     - thumb 无效 → 显示占位图，等待后台补齐
   │
   └─⑤ 启动后台 DiffWorker（QThreadPool，单实例）
         │
         ▼
[后台线程] DiffWorker.run(D, cached)
   │
   ├─⑥ current = []
   │     for sub_dir, _, files in os.walk(D):
   │         for f in files:
   │             if ext(f) in SUPPORTED_EXTENSIONS:
   │                 current.append((normalize(sub_dir), f, mtime_ns, size))
   │     按扩展名过滤；记录每张图所在的"叶子目录"
   │
   ├─⑦ added, changed, removed = diff.compute(cached, current)
   │     按 (folder_path, file_name) 复合键比对
   │     added:   current 有 cached 没有
   │     changed: 同复合键但 mtime_ns 或 size 不同
   │     removed: cached 有 current 没有（带 folder_path，避免同名跨目录误删）
   │
   ├─⑧ 三者皆空 → emit scan_done(D)，结束
   │
   ├─⑨ store.delete_entries(removed)
   │     removed: List[(folder_path, file_name)]
   │     emit entries_removed(removed) → UI 移除对应项
   │
   ├─⑩ 对 added + changed 的每张图：
   │     a) metadata.extract() → width/height/format
   │     b) Pillow 生成 128×128 WebP → thumb_blob
   │     c) store.upsert_entry(...)
   │     d) 累积进 batch（每 20 张一批）
   │     e) emit entries_updated(batch) → UI 替换/追加
   │     f) 每张前检查 self._cancelled.is_set()，True 则中断
   │
   └─⑪ store.mark_scan_done(D 及所有涉及的叶子目录)
        → UPSERT folders 行，更新 last_scan_at
        store.evict_lru_if_needed() → 按 folders 表中 last_access_at 淘汰
        emit scan_done(D)
```

### 关键约束

1. **取消机制**：`DiffWorker._cancelled` 是 `threading.Event`，
   UI 线程在切目录时 `set()`。worker 在每张图处理前 `is_set()` 检查。
   已写入的部分保留，下次访问该目录时正好是部分缓存。

2. **DB 写在后台线程**：UI 线程只读、后台线程读写。
   每个线程持独立 connection（详见"并发模型"章节的硬性规则）。

3. **首次访问目录的退化路径**：步骤 ④ UI 是空列表，步骤 ⑩ 走增量分批 emit。
   总耗时与现状相当（仍串行读 metadata + 生成缩略图），但 UI 不再阻塞主线程
   （现状是 `processEvents` 伪后台），切其他目录可即时响应。
   **下次再点就秒开**——这才是本次需求的核心收益。

4. **跨目录的内存 LRU 保留**：`thumbnail_view._thumbnails`（500 张）继续使用，
   作为"DB blob → QPixmap 解码"的二级缓存，避免反复解码 WebP。

## 缓存淘汰与维护

### 淘汰策略

1. **按叶子目录 LRU**（主策略）：
   - 上限：`MAX_CACHED_FOLDERS = 200`（注意：粒度是叶子目录，不是用户点击的根）
   - 触发：每次 `mark_scan_done` 后
   - 实现：`SELECT folder_path FROM folders ORDER BY last_access_at ASC LIMIT (count - 200)`，
     `DELETE FROM folders WHERE folder_path IN (...)`，CASCADE 自动清理 entries
   - 容量估算：200 叶子目录 × 平均 100 张/叶子目录 × 4KB/张 ≈ **80MB**
     （单个素材库被点一次，会登记其下所有叶子目录；200 上限可覆盖 ~10 个中等素材库）

2. **按 DB 总大小硬上限**（兜底）：
   - 上限：`MAX_DB_SIZE_BYTES = 1_500_000_000`（1.5GB）
   - 触发：App 启动时检查 `os.path.getsize(cache.db)`
   - 超额则继续按 LRU 删目录直到达标

3. **VACUUM**：
   - DELETE 不会立即释放空间
   - App 退出时执行 `PRAGMA incremental_vacuum`（异步，不阻塞退出）

### 手动清理入口

- 设置/工具菜单新增 "**清空缩略图缓存**" → `store.clear_all()` + `VACUUM`
- 缩略图视图右键菜单新增 "**重新扫描此目录**" → `store.delete_folders_under(D)` 后立即触发完整扫描

### 配置常量

写在 `gdm/core/cache/db.py`，不暴露给用户：

```python
MAX_CACHED_FOLDERS = 200
MAX_DB_SIZE_BYTES = 1_500_000_000
THUMB_SIZE = 128
THUMB_FORMAT = "WEBP"
THUMB_QUALITY = 80
BATCH_EMIT_SIZE = 20
```

## 错误处理

| 场景 | 处理 |
|---|---|
| Pillow 读某张图失败 | entries 记录里 width/height/format 写 NULL，thumb_blob 写 NULL，**不抛异常**。UI 显示占位图。下次 mtime 变了再重试 |
| 缩略图生成失败 | 元数据照常 upsert，thumb_blob 留 NULL。UI 显示占位图，不阻塞其他图 |
| `os.walk` 时根目录被删 | 捕获 `FileNotFoundError` → `store.delete_folders_under(D)` → emit `folder_gone(D)` |
| `os.walk` 中途某个子目录消失 | `os.walk` 静默跳过；下一次 diff 时该子目录的条目自然进入 `removed` |
| DB 写入失败（磁盘满 / 权限） | 捕获 `sqlite3.OperationalError` → log warning，**降级为无缓存模式**（流程退化为现有 `scan_with_progress`）。不弹窗骚扰用户 |
| DB 损坏 | 启动时 `PRAGMA integrity_check`，失败则改名为 `cache.db.corrupted-<ts>`，新建空库，记 warning |
| 用户在 diff 跑到一半时退出 App | 后台线程收到 cancel 信号，已写入 entries 保留 |
| 目录被外部重命名/移动 | 等同于"老目录消失 + 新目录首访"，老目录的缓存按 LRU 自然过期，**不做自动迁移** |

## 并发模型

### 硬性规则：SQLite connection 不跨线程共享

Python `sqlite3` 模块默认拒绝跨线程使用同一 connection。即使设置
`check_same_thread=False`，跨线程共享仍然容易出 race。本设计的硬性规则：

- **每个线程独立创建自己的 connection**，使用完毕**当场关闭**
- `get_cache()` 单例**只持有配置和路径**，不持有 connection
- `store` 模块的每个公开方法签名是 `def xxx(conn, ...)`，由调用方传入 connection
- 错误用法（必须在 code review 时拒绝）：模块级全局 connection、`get_cache()` 返回 connection

### 线程职责

- **UI 线程**：仅在需要查询缓存时 `with sqlite3.connect(...)` 创建短生命 connection。
  典型场景是 `_on_folder_selected` 调用 `get_entries_recursive`，毫秒级释放
- **DiffWorker（QThreadPool）**：`run()` 开头创建 connection，结束 `close()`。
  整个 diff + upsert 过程共用这一个 connection
- **App 退出时的 VACUUM**：在专门的清理线程里做，独立 connection

### 串行化

- **同一时刻只允许一个 DiffWorker** 在跑
- 新点击触发时，先 `_active_worker._cancelled.set()`，再启动新 worker
- 旧 worker 收到 cancel 后在下一张图前停止，已写入 DB 的部分保留
- **WAL 模式**保证：旧 worker 还没退出时，新 worker / UI 线程的读不会被阻塞

### 缩略图生成串行（在 DiffWorker 内）

- Pillow GIL 释放在 IO 段，CPU 并行收益有限
- 上千张图首次扫描的并行化作为后续优化（参见"非目标"）

### 取消信号

`threading.Event`，UI 线程 `set()`，worker 每张图前 `is_set()` 检查

## 测试策略

测试用 `pytest`，跟项目现有 Python 习惯一致。

`tests/cache/`：

| 测试文件 | 覆盖内容 |
|---|---|
| `test_diff.py` | 纯函数 diff 的全部边界：空缓存、空目录、added/changed/removed 各种组合、相同 mtime 不同 size、相同 size 不同 mtime、**多叶子目录复合键 diff**、**同名文件跨子目录不误判** |
| `test_store.py` | 用 `:memory:` SQLite 做 CRUD、`touch_folders_under`、`get_entries_recursive`（前缀 LIKE 查询正确性）、`evict_lru_if_needed`、size 上限测试 |
| `test_db.py` | schema 初始化、`auto_vacuum=INCREMENTAL` 设置、`integrity_check` 失败时的损坏库恢复 |
| `test_scanner_cached.py` | 集成：用 `tmp_path` 造**多层嵌套**图片目录（几张小 PNG 散落在子目录），跑两次 `load_folder_cached`，断言第二次走缓存、修改后能正确增量更新、子目录修改不影响兄弟目录 |

**不写的测试**：

- UI 信号顺序（PySide6 信号测试成本高、价值低，靠手测）
- 性能数字（环境相关，靠手测 + 日志计时）

## 性能验收基准

手测项，作为完成标准：

| 场景 | 目标 |
|---|---|
| 1000 张 PNG（平均 2MB/张）目录的**第二次访问**首屏出现 | < 200ms |
| 同一目录无变化时的 diff 完成时间 | < 500ms |
| 修改其中 5 张图后再访问的增量更新完成时间 | < 2s |
| DB 命中场景下目录切换帧时间 | < 16ms（无可感知卡顿） |

## 改动范围汇总

### 新增文件

- `gdm/core/cache/__init__.py`
- `gdm/core/cache/db.py`
- `gdm/core/cache/store.py`
- `gdm/core/cache/diff.py`
- `gdm/core/cache/scanner_cached.py`
- `tests/cache/test_diff.py`
- `tests/cache/test_store.py`
- `tests/cache/test_db.py`
- `tests/cache/test_scanner_cached.py`

### 修改文件

- `gdm/gui/main_window.py` — `_on_folder_selected` 改走 `load_folder_cached`；
  添加"清空缩略图缓存"菜单项；退出时触发 `incremental_vacuum`
- `gdm/gui/thumbnail_view.py` — 新增 `load_from_cache(entries)`；
  新增 `entries_updated` / `entries_removed` 槽；
  右键菜单加"重新扫描此目录"

### 不改动

- `gdm/core/scanner.py`（保留为降级路径）
- `gdm/core/metadata.py`
- `gdm/gui/project_panel.py`

## 风险与权衡

| 风险 | 缓解 |
|---|---|
| SQLite 在大量并发写下性能下降 | 严格限制为单 worker，且 WAL 模式 |
| 用户磁盘满导致 DB 写入失败 | 自动降级到无缓存模式，不阻断使用 |
| 1000+ 行的 SELECT 反序列化 thumb_blob 慢 | 实测若 > 100ms 则改为分页加载（先出元数据，blob 按需懒加载） |
| 200 目录上限不够某些重度用户 | 当前是写死常量；如有反馈再升级为可配置 |
| Pillow 读取损坏图片崩溃整个 worker | 每张图单独 try/except，单个失败不影响整体 |
| `LIKE 'D/%'` 在 200 叶子目录下查询过慢 | 主键 (folder_path, file_name) 已覆盖前缀扫描；实测若 > 100ms 再加 `idx_entries_folder_prefix` |
| 同名文件分布在多个子目录中导致 diff 误判 | diff 用复合键 `(folder_path, file_name)`，专门测试覆盖该场景 |
