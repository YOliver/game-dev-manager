# 图片扫描进度条设计

## 概述

在扫描大量图片时，在缩略图区域显示扫描进度条，避免用户面对无响应的界面无所适从。

## 当前问题

- `scanner.scan()` 在**主线程**同步执行，逐张调用 `extract()`（PIL 读取元数据），大量图片时 UI 完全冻结
- 用户无法得知扫描进度，也无法判断程序是否卡死

## 方案

扫描放到后台线程，缩略图区域在扫描时显示进度条，完成后自动切换回网格。

## 改动详情

### 1. `gdm/core/scanner.py` — 新增 `scan_with_progress()`

新增一个支持进度回调的扫描函数，分两阶段执行：

- **阶段 1（快速统计）**：遍历目录树，仅检查文件扩展名，收集所有图片路径
- **阶段 2（逐张提取）**：对收集到的每张图片调用 `extract()`，每处理一张通过回调报告进度

```python
from typing import Callable, List, Optional

def scan_with_progress(
    directory: str,
    recursive: bool = True,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> List[SpriteInfo]:
    """带进度回调的扫描函数。

    先快速统计总数，再逐张提取元数据。

    Args:
        directory: 要扫描的目录路径
        recursive: 是否递归扫描子目录
        progress_callback: 进度回调，参数为 (已处理数, 总数)
    """
    path = Path(directory)
    if not path.is_dir():
        return []

    pattern = "**/*" if recursive else "*"

    # 阶段1：收集所有图片路径
    image_paths: list[str] = []
    for file_path in path.glob(pattern):
        if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
            image_paths.append(str(file_path))

    total = len(image_paths)

    # 阶段2：逐张提取元数据
    sprites: List[SpriteInfo] = []
    for i, fp in enumerate(image_paths):
        sprites.append(extract(fp))
        if progress_callback:
            progress_callback(i + 1, total)

    return sprites
```

**兼容性：** 原 `scan()` 函数保持不变。

### 2. `gdm/gui/thumbnail_view.py` — 新增进度界面

在 `ThumbnailView` 中添加一个 `QWidget` 用作扫描进度界面，与缩略图网格交替显示。

- 新增控件：`QProgressBar` + `QLabel`（显示文字 "正在扫描图片... 45/1200"）
- 新增方法：`show_progress()` — 隐藏网格，显示进度条
- 新增方法：`update_progress(current, total)` — 更新进度条和百分比文字
- 现有 `load()` — 隐藏进度界面，显示网格（不变）

```
┌──────────────────────────────┐
│                              │
│   ⏳ 正在扫描图片资源...     │
│   ┌──────────────────────┐   │
│   │ ████████████░░░░░ 65% │   │
│   └──────────────────────┘   │
│   已完成: 800 / 1200 张     │
│                              │
└──────────────────────────────┘
```

### 3. `gdm/gui/main_window.py` — 后台扫描协调

使用 `QThread` + 工作对象在后台执行扫描。

```python
from PySide6.QtCore import QObject, QThread, Signal
```

**ScanWorker（可移动到线程的 QObject）：**

```python
class ScanWorker(QObject):
    progress = Signal(int, int)  # current, total
    finished = Signal(object)    # List[SpriteInfo]

    def __init__(self, folder: str, recursive: bool = True):
        super().__init__()
        self._folder = folder
        self._recursive = recursive

    def run(self):
        """在工作线程中执行扫描。"""
        from gdm.core.scanner import scan_with_progress
        sprites = scan_with_progress(
            self._folder,
            self._recursive,
            progress_callback=lambda c, t: self.progress.emit(c, t),
        )
        self.finished.emit(sprites)
```

**主窗口协调：**

```python
def _set_workspace(self, folder: str) -> None:
    self._project = Project(root_path=folder)
    self.project_panel.set_root(folder)

    # 显示进度界面
    self.thumbnail_view.show_progress()

    # 启动后台扫描
    self._scan_thread = QThread()
    self._scan_worker = ScanWorker(folder)
    self._scan_worker.moveToThread(self._scan_thread)
    self._scan_thread.started.connect(self._scan_worker.run)
    self._scan_worker.progress.connect(self.thumbnail_view.update_progress)
    self._scan_worker.finished.connect(self._on_scan_finished)
    self._scan_worker.finished.connect(self._scan_thread.quit)
    self._scan_worker.finished.connect(self._scan_worker.deleteLater)
    self._scan_thread.finished.connect(self._scan_thread.deleteLater)
    self._scan_thread.start()

def _on_scan_finished(self, sprites: List[SpriteInfo]) -> None:
    """后台扫描完成回调。"""
    self._current_sprites = sprites
    self.thumbnail_view.load(sprites)

    # 保存配置
    try:
        save_config({"last_folder": self._project.root_path})
    except Exception as e:
        logger.warning(f"保存配置失败: {e}")
```

### 三处扫描入口统一改用后台扫描

各入口扫描完成后的行为不同，需使用不同的完成回调：

| 入口 | 完成后行为 |
|------|-----------|
| `_set_workspace()` | `load(sprites)` + 保存配置 + 保存项目文件 |
| `_try_restore_project()` | `load(sprites)`（不保存，启动恢复） |
| `_on_folder_selected()` | `load(sprites)`（不保存） |

可抽取公共的线程启动逻辑为 `_start_scan(folder, on_finished)` 方法，三个入口各自传入不同的 `on_finished` 回调。

## 验证标准

- 扫描大量图片时界面不冻结
- 缩略图区域显示实时进度（进度条百分比 + 数字）
- 扫描完成后自动切换为缩略图网格
- 进度条显示平滑，不卡顿
- 三个入口（打开文件夹、启动恢复、左侧树点击）都支持进度条
- 所有测试通过
