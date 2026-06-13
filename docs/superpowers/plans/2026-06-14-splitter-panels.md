# 可拖动面板分隔条 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将主窗口三个面板的固定比例布局替换为 QSplitter，支持鼠标拖动分隔条自由调整宽度。

**架构:** 保留 QHBoxLayout 作为边距容器，内部嵌入 QSplitter。QSplitter 原生提供可拖动分隔条，无需额外事件处理。

**Tech Stack:** Python, PySide6, pytest

---

### Task 1: 替换布局为 QSplitter

**Files:**
- Modify: `gdm/gui/main_window.py:10-16` (import)
- Modify: `gdm/gui/main_window.py:44-69` (`_init_ui()`)

- [ ] **Step 1: 更新 import 语句**

在 `gdm/gui/main_window.py` 中，将：

```python
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QWidget,
)
from PySide6.QtCore import Slot
```

改为：

```python
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QSplitter,
    QWidget,
)
from PySide6.QtCore import Qt, Slot
```

- [ ] **Step 2: 修改 `_init_ui()` 方法**

将当前的：

```python
    def _init_ui(self) -> None:
        """初始化 UI 组件与布局。"""
        self.setWindowTitle("Game Dev Manager")
        self.setMinimumSize(1000, 600)

        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        # 左侧：项目面板
        self.project_panel = ProjectPanel()
        self.project_panel.folder_selected.connect(self._on_folder_selected)
        main_layout.addWidget(self.project_panel, 1)

        # 中间：缩略图视图
        self.thumbnail_view = ThumbnailView()
        self.thumbnail_view.selection_changed.connect(self._on_selection_changed)
        main_layout.addWidget(self.thumbnail_view, 3)

        # 右侧：详情面板
        self.detail_panel = DetailPanel()
        main_layout.addWidget(self.detail_panel, 1)

        # 菜单栏
        self._init_menubar()
```

改为：

```python
    def _init_ui(self) -> None:
        """初始化 UI 组件与布局。"""
        self.setWindowTitle("Game Dev Manager")
        self.setMinimumSize(1000, 600)

        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 使用 QSplitter 实现可拖动分隔条
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(4)

        # 左侧：项目面板
        self.project_panel = ProjectPanel()
        self.project_panel.folder_selected.connect(self._on_folder_selected)
        splitter.addWidget(self.project_panel)

        # 中间：缩略图视图
        self.thumbnail_view = ThumbnailView()
        self.thumbnail_view.selection_changed.connect(self._on_selection_changed)
        splitter.addWidget(self.thumbnail_view)

        # 右侧：详情面板
        self.detail_panel = DetailPanel()
        splitter.addWidget(self.detail_panel)

        # 设置初始大小比例 左侧:中间:右侧 = 200:600:200
        splitter.setSizes([200, 600, 200])

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.addWidget(splitter)

        # 菜单栏
        self._init_menubar()
```

- [ ] **Step 3: 运行测试确认无回归**

```bash
cd D:/UGit/game-dev-manager && python -m pytest tests/ -v
```

预期输出：62 passed, 1 skipped（与改动前一致）。

- [ ] **Step 4: 提交修改**

```bash
cd D:/UGit/game-dev-manager
git add gdm/gui/main_window.py
git commit -m "feat: 用 QSplitter 替换固定布局，支持拖动调整面板宽度

三个面板之间添加可拖动的分隔条，用户可通过鼠标拖拽
自由调整左侧文件夹树、中间缩略图、右侧详情面板的宽度。

Co-Authored-By: Claude <noreply@anthropic.com>"
```
