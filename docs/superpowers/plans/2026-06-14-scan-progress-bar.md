# 扫描进度条 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在缩略图区域显示扫描进度条，将扫描移至后台线程避免 UI 冻结。

**Architecture:** 新增 `scan_with_progress()` 双阶段函数（先统计总数→再逐张提取）；ThumbnailView 新增进度界面（QProgressBar + QLabel）；MainWindow 使用 ScanWorker(QObject) + QThread 后台执行，三处扫描入口统一改用异步进度模式。

**Tech Stack:** Python, PySide6, pytest

---

### Task 1: scanner.py — 新增 `scan_with_progress()`

**Files:**
- Modify: `gdm/core/scanner.py`

- [ ] **Step 1: 在 `scan()` 后新增 `scan_with_progress()`**

在 `D:\UGit\game-dev-manager\gdm\core\scanner.py`，在现有的 `scan()` 函数之后添加：

```python
from typing import Callable, List, Optional


def scan_with_progress(
    directory: str,
    recursive: bool = True,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> List[SpriteInfo]:
    """带进度回调的扫描函数，先快速统计总数，再逐张提取元数据。

    Args:
        directory: 要扫描的目录路径
        recursive: 是否递归扫描子目录
        progress_callback: 进度回调，参数为 (已处理数, 总数)

    Returns:
        包含所有图片元数据的 SpriteInfo 列表。
    """
    path = Path(directory)
    if not path.is_dir():
        return []

    pattern = "**/*" if recursive else "*"

    # 阶段1：收集所有图片路径（仅检查扩展名，不读取内容）
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

需要在文件顶部 `typing` import 行添加缺失的类型。如果已有 `from typing import List`，改为：

```python
from typing import Callable, List, Optional
```

- [ ] **Step 2: 运行现有测试确认无回归**

```bash
cd D:/UGit/game-dev-manager && python -m pytest tests/test_scanner.py -v
```

预期输出：9 passed（全部通过）。

- [ ] **Step 3: 提交**

```bash
cd D:/UGit/game-dev-manager
git add gdm/core/scanner.py
git commit -m "feat: 新增 scan_with_progress() 带进度回调的扫描函数

双阶段扫描：先统计图片总数（仅扩展名），再逐张提取 PIL 元数据，
每处理一张通过回调报告 (已处理数, 总数)。

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: thumbnail_view.py — 新增扫描进度界面

**Files:**
- Modify: `gdm/gui/thumbnail_view.py`

- [ ] **Step 1: 在 `__init__` 中创建进度控件**

在 `ThumbnailView.__init__()` 的 `self._init_ui()` 调用之后，新增进度控件的初始化：

找到 `_pending_workers: Dict[str, ThumbnailLoadWorker] = {}` 之后，添加：

```python
        # 扫描进度界面（扫描时显示，完成后隐藏）
        self._progress_widget = QWidget()
        self._progress_widget.setVisible(False)
        progress_layout = QVBoxLayout(self._progress_widget)
        progress_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._progress_label = QLabel("正在扫描图片资源...")
        self._progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._progress_label.setStyleSheet("font-size: 16px; color: #666;")

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedWidth(400)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 6px;
                text-align: center;
                height: 24px;
            }
            QProgressBar::chunk {
                background-color: #0078d4;
                border-radius: 5px;
            }
        """)

        self._progress_detail = QLabel("")
        self._progress_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._progress_detail.setStyleSheet("font-size: 12px; color: #999;")

        progress_layout.addStretch()
        progress_layout.addWidget(self._progress_label)
        progress_layout.addSpacing(16)
        progress_layout.addWidget(self._progress_bar, 0, Qt.AlignmentFlag.AlignCenter)
        progress_layout.addSpacing(8)
        progress_layout.addWidget(self._progress_detail)
        progress_layout.addStretch()

        layout.addWidget(self._progress_widget)  # 添加到 ThumbnailView 的布局中
```

同时在文件顶部的 import 中新增所需控件。现有 import：

```python
from PySide6.QtWidgets import (
    QAbstractItemView,
    QListWidget,
    QListWidgetItem,
    QStyledItemDelegate,
    QWidget,
    QVBoxLayout,
    QStyle,
)
```

改为：

```python
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QStyledItemDelegate,
    QWidget,
    QVBoxLayout,
    QStyle,
)
```

注：`Qt` 已经包含在 `from PySide6.QtCore import ...` 中，无需新增。

- [ ] **Step 2: 新增 `show_progress()` 和 `update_progress()` 方法**

在 `ThumbnailView` 类中，`resizeEvent` 之后（或类中合适位置），新增：

```python
    def show_progress(self) -> None:
        """隐藏缩略图网格，显示扫描进度界面。"""
        self._list_widget.setVisible(False)
        self._progress_widget.setVisible(True)
        self._progress_bar.setValue(0)
        self._progress_detail.setText("")

    def update_progress(self, current: int, total: int) -> None:
        """更新扫描进度条和详情文字。

        Args:
            current: 已处理的图片数量
            total: 图片总数
        """
        if total > 0:
            pct = int(current / total * 100)
            self._progress_bar.setValue(pct)
            self._progress_detail.setText(f"已完成: {current} / {total} 张")
```

- [ ] **Step 3: 修改 `load()` 方法 — 扫描完成后隐藏进度、显示网格**

在现有的 `load()` 方法中，在开头添加：

```python
    def load(self, sprites: List[SpriteInfo]) -> None:
        """加载精灵图列表到网格视图。"""
        # 扫描完成，从进度界面切换回缩略图网格
        self._progress_widget.setVisible(False)
        self._list_widget.setVisible(True)

        self._sprites = list(sprites)
        # ... 后续代码不变
```

- [ ] **Step 4: 运行测试**

```bash
cd D:/UGit/game-dev-manager && python -m pytest tests/test_thumbnail_view.py -v
```

预期输出：6 passed。

- [ ] **Step 5: 提交**

```bash
cd D:/UGit/game-dev-manager
git add gdm/gui/thumbnail_view.py
git commit -m "feat: 缩略图视图新增扫描进度界面

添加 QProgressBar + QLabel 进度显示，show_progress() 切换
到进度界面，update_progress() 实时更新进度，load() 自动
恢复缩略图网格。

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: main_window.py — 后台扫描协调

**Files:**
- Modify: `gdm/gui/main_window.py`

- [ ] **Step 1: 添加 ScanWorker 类和后台扫描方法**

在 `gdm/gui/main_window.py` 中：

**更新 import：**

```python
from PySide6.QtCore import QObject, Qt, QThread, Slot, Signal
```

将原有的 `from PySide6.QtCore import Slot` 改为如上。

**在 `MainWindow` 类之前添加 ScanWorker：**

```python
class ScanWorker(QObject):
    """后台扫描工作器，在 QThread 中运行。"""
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

- [ ] **Step 2: 在 MainWindow 中添加 `_start_scan()` 公共方法**

```python
    def _start_scan(self, folder: str, on_finished) -> None:
        """启动后台扫描线程。

        Args:
            folder: 要扫描的文件夹路径
            on_finished: 扫描完成回调，接收 List[SpriteInfo] 参数
        """
        # 取消之前的扫描（如果仍在运行）
        if hasattr(self, '_scan_thread') and self._scan_thread is not None:
            self._scan_thread.quit()
            self._scan_thread.wait()

        self._scan_thread = QThread()
        self._scan_worker = ScanWorker(folder)
        self._scan_worker.moveToThread(self._scan_thread)
        self._scan_thread.started.connect(self._scan_worker.run)
        self._scan_worker.progress.connect(self.thumbnail_view.update_progress)
        self._scan_worker.finished.connect(lambda sprites: on_finished(sprites))
        self._scan_worker.finished.connect(self._scan_thread.quit)
        self._scan_worker.finished.connect(self._scan_worker.deleteLater)
        self._scan_thread.finished.connect(self._scan_thread.deleteLater)
        self._scan_thread.start()
```

- [ ] **Step 3: 修改 `_set_workspace()` 使用后台扫描**

将当前代码：

```python
    def _set_workspace(self, folder: str) -> None:
        """设置工作区根目录，扫描并加载精灵图。"""
        self._project = Project(root_path=folder)
        self.project_panel.set_root(folder)

        try:
            sprites = scan(folder, recursive=True)
        except Exception as e:
            logger.warning(f"扫描文件夹失败: {folder}, 错误: {e}")
            sprites = []

        self._current_sprites = sprites
        self.thumbnail_view.load(sprites)

        # 保存 last_folder 到全局配置
        try:
            save_config({"last_folder": folder})
        except Exception as e:
            logger.warning(f"保存配置失败: {e}")

        # 保存项目文件
        try:
            self._save_project()
        except Exception as e:
            logger.warning(f"保存项目失败: {e}")
```

改为：

```python
    def _set_workspace(self, folder: str) -> None:
        """设置工作区根目录，后台扫描并加载精灵图。"""
        self._project = Project(root_path=folder)
        self.project_panel.set_root(folder)

        # 显示进度界面
        self.thumbnail_view.show_progress()

        # 启动后台扫描
        self._start_scan(folder, on_finished=self._on_workspace_scan_finished)

    def _on_workspace_scan_finished(self, sprites) -> None:
        """_set_workspace 扫描完成回调。"""
        self._current_sprites = sprites
        self.thumbnail_view.load(sprites)

        # 保存 last_folder 到全局配置
        folder = self._project.root_path
        try:
            save_config({"last_folder": folder})
        except Exception as e:
            logger.warning(f"保存配置失败: {e}")

        # 保存项目文件
        try:
            self._save_project()
        except Exception as e:
            logger.warning(f"保存项目失败: {e}")
```

- [ ] **Step 4: 修改 `_try_restore_project()` 使用后台扫描**

将当前代码：

```python
    def _try_restore_project(self) -> None:
        """启动时尝试恢复上一次的工作区。"""
        config = load_config()
        if config is None:
            return

        last_folder = config.get("last_folder")
        if last_folder is None:
            return

        if not os.path.isdir(last_folder):
            return

        # 恢复 UI 状态（跳过再次保存，避免覆盖）
        self._project = Project(root_path=last_folder)
        self.project_panel.set_root(last_folder)

        try:
            sprites = scan(last_folder, recursive=True)
        except Exception as e:
            logger.warning(f"扫描文件夹失败: {last_folder}, 错误: {e}")
            sprites = []

        self._current_sprites = sprites
        self.thumbnail_view.load(sprites)
```

改为：

```python
    def _try_restore_project(self) -> None:
        """启动时尝试恢复上一次的工作区。"""
        config = load_config()
        if config is None:
            return

        last_folder = config.get("last_folder")
        if last_folder is None:
            return

        if not os.path.isdir(last_folder):
            return

        # 恢复 UI 状态（跳过再次保存，避免覆盖）
        self._project = Project(root_path=last_folder)
        self.project_panel.set_root(last_folder)

        # 显示进度界面
        self.thumbnail_view.show_progress()

        # 启动后台扫描
        self._start_scan(last_folder, on_finished=self._on_restore_scan_finished)

    def _on_restore_scan_finished(self, sprites) -> None:
        """_try_restore_project 扫描完成回调（不保存配置）。"""
        self._current_sprites = sprites
        self.thumbnail_view.load(sprites)
```

- [ ] **Step 5: 修改 `_on_folder_selected()` 使用后台扫描**

将当前代码：

```python
    def _on_folder_selected(self, folder_path: str) -> None:
        """左侧面板选中文件夹回调，加载该文件夹的精灵图到缩略图视图。"""
        try:
            sprites = scan(folder_path, recursive=True)
        except Exception as e:
            logger.warning(f"扫描文件夹失败: {folder_path}, 错误: {e}")
            sprites = []
        self._current_sprites = sprites
        self.thumbnail_view.load(sprites)
```

改为：

```python
    def _on_folder_selected(self, folder_path: str) -> None:
        """左侧面板选中文件夹回调，后台扫描并加载精灵图。"""
        self.thumbnail_view.show_progress()
        self._start_scan(folder_path, on_finished=self._on_tree_scan_finished)

    def _on_tree_scan_finished(self, sprites) -> None:
        """左侧树点击扫描完成回调（不保存配置）。"""
        self._current_sprites = sprites
        self.thumbnail_view.load(sprites)
```

- [ ] **Step 6: 运行全部测试**

```bash
cd D:/UGit/game-dev-manager && python -m pytest tests/ -v
```

预期输出：62 passed, 1 skipped（与改动前一致，因为现有测试未覆盖 UI 线程部分）。

- [ ] **Step 7: 提交**

```bash
cd D:/UGit/game-dev-manager
git add gdm/gui/main_window.py
git commit -m "feat: 后台扫描 + 进度条协调

新增 ScanWorker(QObject) 运行在 QThread 中执行扫描，
_start_scan() 公共方法封装线程生命周期管理，
三处扫描入口（打开文件夹、启动恢复、左侧树点击）统一
改用后台扫描，缩略图区域实时显示进度。

Co-Authored-By: Claude <noreply@anthropic.com>"
```
