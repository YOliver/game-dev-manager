# GDM — 精灵图管理工具设计文档

**项目名称：** gdm（Game Dev Manager）
**版本：** v1（精灵图管理）
**日期：** 2026-06-12
**状态：** 待审阅

---

## 1. 概述

gdm 是一款面向游戏开发者的资源管理桌面应用，v1 阶段实现**精灵图管理**功能，支持：

- 浏览文件夹中的图片资源（支持递归扫描）
- 以缩略图网格 + 侧边详情面板的形式展示
- 实时显示每张图片的像素尺寸、文件大小、格式等信息
- 批量重命名（多种模式）
- 工作区/项目状态保存与恢复

技术选型：Python + PySide6（GUI）+ Pillow（图片元数据）。

---

## 2. 功能规格

### 2.1 文件夹浏览与工作区

- 用户通过菜单或快捷键打开一个文件夹
- 支持递归扫描子目录（可勾选开关）
- 扫描结果以文件夹树形式展示在左侧面板
- 点击文件夹树中的节点，中间区域显示该文件夹下的图片缩略图
- 工作区状态（根目录路径）保存到 `.gdm.json`，下次启动自动恢复
- v1 不保存文件夹展开状态，启动时文件夹树默认全部折叠

### 2.2 缩略图网格视图（主区域）

- 网格形式展示图片缩略图，每张图下方显示文件名
- 支持 Ctrl / Shift 多选
- 缩略图异步加载，避免界面卡顿
- 选中图片后，发出 `selection_changed` 信号，由主窗口转发至详情面板

### 2.3 侧边详情面板（右侧）

- 显示当前选中图片的：
  - 预览图（较大尺寸）
  - 文件名
  - 像素尺寸（宽 × 高）
  - 文件大小（自动换算为 KB / MB）
  - 图片格式（PNG / JPG / WebP 等）
  - 色彩模式（RGB / RGBA / 灰度等，来自 Pillow）
  - 完整文件路径
- 选中多张图片时，显示汇总信息：
  - 共 N 张图片
  - 总文件大小
  - 各图片尺寸分布（可选）

### 2.4 批量重命名

通过菜单「工具 → 批量重命名」打开配置弹窗，支持以下模式：

| 模式 | 说明 | 示例 |
|---|---|---|
| 前缀 + 序号 | 统一前缀，自动编号 | `sprite_001.png` |
| 查找替换 | 查找文件名中的字符串并替换 | `old_*.png` → `new_*.png` |
| 正则替换 | 支持正则表达式匹配替换 | `(.*)_copy\.png` → `$1.png` |
| 添加后缀 | 在扩展名前插入文字 | `hero.png` → `hero_small.png` |

- 弹窗中实时预览重命名前后对照
- 确认后执行，执行完成后自动刷新视图

---

## 3. 架构设计

采用**分层架构**（方案 B），核心逻辑层与 GUI 层完全分离。

### 3.1 目录结构

```
gdm/
├── core/                  # 核心逻辑层（无 GUI 依赖）
│   ├── __init__.py
│   ├── models.py          # 数据模型：SpriteInfo, Project, RenameRule
│   ├── scanner.py         # 文件夹扫描，过滤图片文件
│   ├── metadata.py        # 提取图片元数据（Pillow）
│   ├── renamer.py         # 批量重命名引擎
│   └── project.py         # 工作区状态保存/加载
├── gui/                   # GUI 层（PySide6）
│   ├── __init__.py
│   ├── main_window.py     # 主窗口，布局与信号协调
│   ├── thumbnail_view.py  # 缩略图网格视图
│   ├── detail_panel.py    # 侧边详情面板
│   ├── rename_dialog.py   # 批量重命名配置弹窗
│   └── project_panel.py  # 工作区文件夹树面板
├── utils/
│   ├── __init__.py
│   └── helpers.py         # 通用工具函数
├── main.py                # 入口文件
└── requirements.txt       # 依赖声明
```

### 3.2 核心模块职责

#### `core/models.py`

纯数据结构，无外部依赖：

```python
@dataclass
class SpriteInfo:
    file_path: str           # 完整路径
    file_name: str           # 文件名（含扩展名）
    width: int               # 像素宽度
    height: int              # 像素高度
    file_size: int           # 文件大小（字节）
    format: str              # 图片格式（PNG/JPEG/WebP...）
    color_mode: str          # 色彩模式（RGB/RGBA/P...）

@dataclass
class Project:
    root_path: str          # 工作区根目录
    # v1 仅保存根目录路径，后续版本可扩展其他字段。

class RenameMode(Enum):
    PREFIX_NUMBER = "前缀+序号"
    FIND_REPLACE = "查找替换"
    REGEX = "正则替换"
    ADD_SUFFIX = "添加后缀"

@dataclass
class RenameRule:
    mode: RenameMode
    prefix: Optional[str] = None      # 前缀+序号模式用
    start_index: int = 1              # 序号起始值
    padding: int = 3                 # 序号补零位数
    find_text: Optional[str] = None   # 查找替换模式用
    replace_text: Optional[str] = None
    regex_pattern: Optional[str] = None  # 正则模式用
    regex_replacement: Optional[str] = None
    suffix: Optional[str] = None      # 添加后缀模式用
```

#### `core/scanner.py`

- 职责：遍历目录、过滤图片文件扩展名。**不负责读取文件内容。**
- 输入：文件夹路径、是否递归
- 扫描图片文件（扩展名：`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.bmp`）
- 对每个文件调用 `metadata.extract()` 获取 `SpriteInfo`
- 输出：`List[SpriteInfo]`

#### `core/metadata.py`

- 职责：打开文件并提取元数据。**不负责发现或遍历文件。**
- `extract(file_path: str) -> SpriteInfo`：用 Pillow 打开图片，读取尺寸和色彩模式，结合 `os.path.getsize` 获取文件大小
- 读取失败时返回部分信息（文件大小可读，图片信息标注为未知）

#### `core/renamer.py`

- `preview(files: List[SpriteInfo], rule: RenameRule) -> List[Tuple[str, str]]`：返回（原路径, 新路径）对照表，不实际写入
- `execute(files: List[SpriteInfo], rule: RenameRule) -> Tuple[int, List[str]]`：执行重命名，**原地更新**传入的 `SpriteInfo` 对象的 `file_path` 和 `file_name` 字段，返回（成功数量, 旧路径列表）
- 执行前检查目标文件名是否已存在，避免覆盖
- `main_window` 根据返回的旧路径列表调用 `thumbnail_view.update_cache_keys()` 更新缩略图缓存 key，并刷新受影响的缩略图项，不做全量重新扫描

#### `core/project.py`

- `save(project: Project, path: str) -> None`：将工作区状态写入 `.gdm.json`
- `load(path: str) -> Optional[Project]`：读取 `.gdm.json` 恢复工作区
- `.gdm.json` 放在工作区根目录下

---

### 3.3 GUI 模块职责

#### `gui/main_window.py`

- 主窗口类，采用 QMainWindow
- 布局：左侧 `project_panel`，中间 `thumbnail_view`，右侧 `detail_panel`
- 菜单栏：文件（打开文件夹、保存工作区、退出）、工具（批量重命名）
- 信号协调：
  - 连接 `thumbnail_view.selection_changed` → `detail_panel.update()`
  - 连接 `project_panel.folder_selected` → `thumbnail_view.load()`
  - 菜单「批量重命名」→ 打开 `rename_dialog`
- 启动时可检测并恢复上一次的工作区。如果 `.gdm.json` 不存在，或其中记录的根目录已不存在，静默跳过，不报错，启动空工作区（用户可手动重新打开文件夹）

#### `gui/thumbnail_view.py`

- 继承 `QWidget`，内部使用 `QListWidget`（Icon Mode）或 `QGraphicsView` 实现网格
- 接收 `List[SpriteInfo]`，为每个 `SpriteInfo` 生成缩略图
- 缩略图使用 `QRunnable` + `QThreadPool` 异步加载，避免阻塞 UI。每张图片生成一个 worker 任务，线程池统一管理，无需手动管理 `QThread` 生命周期。
- **缩略图内存缓存**：使用 `dict[str, QPixmap]`（key 为文件完整路径），已缓存的缩略图不重复生成。切换文件夹时缓存保留，仅在文件发生变化（路径相同但 mtime 变化）时重新生成。**缓存失效检查通过 `os.path.getmtime()` 直接获取文件修改时间，不依赖 `SpriteInfo` 字段。**
- 发出信号：`selection_changed(sprite_info: SpriteInfo)`
- 支持拖选、Ctrl/Shift 多选

#### `gui/detail_panel.py`

- 继承 `QWidget`
- 接收 `SpriteInfo`（单张）或 `List[SpriteInfo]`（多张）
- 更新界面：预览图、各项元数据、汇总信息
- 仅读取 `SpriteInfo` 字段，不调用任何核心模块

#### `gui/rename_dialog.py`

- 继承 `QDialog`
- 下拉框选择重命名模式，根据模式动态显示参数输入区
- 预览区域显示重命名前后对照
- 确认后调用 `core.renamer.execute()`，根据返回结果精确更新：`SpriteInfo` 对象已被原地修改
- 完成后发出 `renamed(old_paths: List[str], sprites: List[SpriteInfo])` 信号，**由 `main_window` 负责**：
  - 从 `sprites` 中提取 `sprite.file_path` 组装为 `new_paths`
  - 调用 `thumbnail_view.update_cache_keys(old_paths, new_paths)` 更新缩略图缓存 key
  - 刷新受影响的缩略图项（不重新扫描文件夹）

#### `gui/project_panel.py`

- 继承 `QWidget`，使用 `QTreeWidget` 或 `QFileSystemModel` 显示文件夹树
- 仅显示当前工作区根目录下的文件夹结构（不显示文件）
- 发出信号：`folder_selected(dir_path: str)`

---

## 4. 依赖关系

### 设计原则

- **核心层不依赖 GUI 层**
- **GUI 组件之间不直接通信**，全部通过 `main_window` 信号-槽中转
- **GUI 组件只依赖 `core/models`，不依赖其他核心模块**（除 `rename_dialog` 外）

### 依赖图

```
【核心层 — 无 GUI 依赖】

core/models.py        ← 无依赖
core/metadata.py      ← Pillow（第三方）
core/scanner.py       ← core/models, core/metadata
core/renamer.py       ← core/models
core/project.py        ← core/models, json（标准库）

【GUI 层】

gui/main_window.py    ← 全部 core/* 和全部 gui/*（协调者）
gui/thumbnail_view.py ← core/models（接收 SpriteInfo 列表）
gui/detail_panel.py   ← core/models（接收 SpriteInfo）
gui/project_panel.py  ← 无核心层依赖（接收目录路径字符串）
gui/rename_dialog.py  ← core/models, core/renamer（modal 对话框）
```

### 数据流示例

**用户选中图片 → 详情面板更新：**

```
thumbnail_view.selection_changed.emit(sprite_info)
        ↓（信号）
main_window（槽函数）
        ↓
detail_panel.update(sprite_info)
```

**用户执行批量重命名：**

```
main_window 菜单触发
        ↓
rename_dialog.exec()  ← 内部调用 core.renamer.preview() 做预览
        ↓ 用户确认
rename_dialog 调用 core.renamer.execute()
        → 原地更新 SpriteInfo 的 file_path / file_name
        → 返回 (成功数量, 旧路径列表)
        ↓
rename_dialog.renamed.emit(old_paths, sprites)
        ↓
main_window 收到 renamed 信号
        ↓
main_window 调用 thumbnail_view.update_cache_keys(old_paths, new_paths)
        ↓ 完成
main_window 刷新受影响的缩略图项（不重新扫描文件夹）
```

---

## 5. 关键技术决策

| 决策 | 选择 | 理由 |
|---|---|---|
| GUI 框架 | PySide6 | 功能强大，LGPL 许可，适合商业项目 |
| 图片元数据 | Pillow | Python 生态标准图片处理库，轻量可靠 |
| 缩略图加载 | QRunnable + QThreadPool | 异步加载，线程池统一管理，无需手动管理 QThread 生命周期 |
| 项目状态存储 | `.gdm.json`（JSON） | 人类可读，易于调试和版本控制 |
| Python 版本 | 3.10+ | 支持 `dataclass`、类型注解，`match` 语法 |

---

## 6. 不在 v1 范围内的功能

以下功能明确不纳入 v1，留待后续版本：

- 音频、字体、纹理等其他资源类型管理
- 图片编辑（裁剪、缩放、格式转换）
- 拖拽导入图片
- 多工作区切换
- CLI 前端
- 插件系统
- 文件变化自动监听与刷新

---

## 7. 后续步骤

设计文档审阅通过后：

1. 调用 `writing-plans` skill 制定实现计划
2. 按模块顺序实现：先核心层，后 GUI 层
3. 每完成一个模块做基础验证

---

*文档版本：v1.1 — 已批准*
