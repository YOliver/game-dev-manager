# 可拖动面板分隔条设计

## 概述

将主窗口三个面板（文件夹树、缩略图、详情面板）的固定比例布局改为使用 `QSplitter`，
支持用户通过鼠标拖动分隔条自由调整各面板宽度。

## 当前问题

- 三个面板使用 `QHBoxLayout` + 固定 stretch 比例（1:3:1），无法动态调整
- 用户无法根据当前任务需求调整各面板宽度（例如需要更宽的缩略图区，或更宽的详情面板）

## 改动方案

仅修改 `gdm/gui/main_window.py`。

### Import 变更

| 操作 | 内容 |
|------|------|
| 新增 | `QSplitter`（来自 `PySide6.QtWidgets`） |
| 新增 | `Qt`（来自 `PySide6.QtCore`） |

### _init_ui() 变更

将 QHBoxLayout + addWidget(panel, stretch) 替换为 QSplitter + addWidget(panel) + setSizes()。

```python
def _init_ui(self) -> None:
    self.setWindowTitle("Game Dev Manager")
    self.setMinimumSize(1000, 600)

    central_widget = QWidget()
    self.setCentralWidget(central_widget)

    splitter = QSplitter(Qt.Horizontal, central_widget)
    splitter.setHandleWidth(4)

    self.project_panel = ProjectPanel()
    self.project_panel.folder_selected.connect(self._on_folder_selected)
    splitter.addWidget(self.project_panel)

    self.thumbnail_view = ThumbnailView()
    self.thumbnail_view.selection_changed.connect(self._on_selection_changed)
    splitter.addWidget(self.thumbnail_view)

    self.detail_panel = DetailPanel()
    splitter.addWidget(self.detail_panel)

    splitter.setSizes([200, 600, 200])

    main_layout = QHBoxLayout(central_widget)
    main_layout.setContentsMargins(4, 4, 4, 4)
    main_layout.addWidget(splitter)
```

### 不变的部分

- 所有信号连接不变
- 菜单栏不变
- 各面板内部逻辑不变
- 功能行为不变

## QSplitter 原生特性

- 分隔条可鼠标拖动
- 双击分隔条快速平衡两侧面板大小
- 拖动时可实时显示新的面板大小

## 验证标准

- 三个面板之间可见可拖动的分隔条
- 拖动分隔条能正常调整各面板宽度
- 最小窗口大小限制仍有效（1000×600）
- 所有测试通过
