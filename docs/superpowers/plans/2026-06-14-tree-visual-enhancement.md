# 目录树视觉优化 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复目录树选中项文字看不清的问题，并将包含图片的目录名显示为绿色。

**架构:** stylesheet 修复选中态对比度；新增 `_build_img_dirs()` 方法提前扫描全量图片，构建"有图片的目录集合"，在填充树时据此上色。所有改动集中在 `gdm/gui/project_panel.py`。

**Tech Stack:** Python, PySide6, pytest

---

### Task 1: 添加选中态样式 + 含图片目录标绿

**Files:**
- Modify: `gdm/gui/project_panel.py` (全部改动)

- [ ] **Step 1: 更新 import 语句**

在 `D:\UGit\game-dev-manager\gdm\gui\project_panel.py` 顶部，将：

```python
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem
from PySide6.QtCore import Signal
from pathlib import Path
```

改为：

```python
import os

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem
from PySide6.QtCore import Signal
from pathlib import Path

from gdm.core.scanner import scan
```

- [ ] **Step 2: 在 `__init__` 中新增 `_img_dirs` 属性**

在 `__init__` 中新增一个空集合，用于存储包含图片的目录路径：

```python
    def __init__(self):
        super().__init__()
        self.root_path: str = ""
        self._img_dirs: set[str] = set()  # 包含图片的目录路径集合
        self._init_ui()
```

- [ ] **Step 3: stylesheet 中添加选中态样式**

在 `_init_ui()` 中，在现有 stylesheet 的 `}` 之后、`""")` 之前插入 `:selected` 和 `:selected:active` 规则：

```python
        self.tree.setStyleSheet("""
            QTreeWidget {
                font-size: 11px;
            }
            QTreeWidget::item {
                padding: 1px 0px;
                margin: 0px;
                border: none;
            }
            QTreeWidget::item:selected {
                background-color: #0078d4;
                color: white;
            }
            QTreeWidget::item:selected:active {
                background-color: #0078d4;
                color: white;
            }
            QTreeWidget::branch {
                margin: 0px;
                padding: 0px;
            }
        """)
```

- [ ] **Step 4: 新增 `_build_img_dirs()` 方法**

在 `_on_item_clicked` 方法之前，新增：

```python
    def _build_img_dirs(self, root_path: str) -> set[str]:
        """扫描 root_path 下所有图片，返回包含图片的目录及其所有父目录的集合。"""
        img_dirs: set[str] = set()
        sprites = scan(root_path, recursive=True)
        for sprite in sprites:
            dir_path = os.path.dirname(sprite.file_path)
            # 添加该目录及其所有父目录
            while dir_path and dir_path != root_path:
                img_dirs.add(dir_path)
                dir_path = os.path.dirname(dir_path)
            if dir_path == root_path or dir_path == "":
                img_dirs.add(root_path)
        return img_dirs
```

- [ ] **Step 5: 修改 `set_root()` — 构建 `_img_dirs` 集合**

将当前的：

```python
    def set_root(self, path: str):
        """设置工作区根目录，构建文件夹树。"""
        self.root_path = path
        self.tree.clear()
        root_item = QTreeWidgetItem(self.tree, [Path(path).name])
        root_item.setData(0, 42, path)  # 存储完整路径
        self._populate_tree(root_item, path)
        self.tree.expandItem(root_item)
```

改为：

```python
    def set_root(self, path: str):
        """设置工作区根目录，构建文件夹树。"""
        self.root_path = path
        self._img_dirs = self._build_img_dirs(path)  # 扫描含图片的目录
        self.tree.clear()
        root_item = QTreeWidgetItem(self.tree, [Path(path).name])
        root_item.setData(0, 42, path)  # 存储完整路径
        # 根节点也标绿
        if path in self._img_dirs:
            root_item.setForeground(0, QColor("#22c55e"))
        self._populate_tree(root_item, path)
        self.tree.expandItem(root_item)
```

- [ ] **Step 6: 修改 `_populate_tree()` — 目录标绿**

在 `_populate_tree` 中，在每个 `child` 创建后添加标绿判断：

将：

```python
    def _populate_tree(self, parent_item: QTreeWidgetItem, parent_path: str):
        """递归填充子目录。"""
        try:
            for entry in sorted(Path(parent_path).iterdir()):
                if entry.is_dir() and not entry.name.startswith("."):
                    child = QTreeWidgetItem(parent_item, [entry.name])
                    child.setData(0, 42, str(entry))
                    self._populate_tree(child, str(entry))
        except PermissionError:
            pass
```

改为：

```python
    def _populate_tree(self, parent_item: QTreeWidgetItem, parent_path: str):
        """递归填充子目录。"""
        try:
            for entry in sorted(Path(parent_path).iterdir()):
                if entry.is_dir() and not entry.name.startswith("."):
                    child = QTreeWidgetItem(parent_item, [entry.name])
                    child.setData(0, 42, str(entry))
                    # 如果该目录包含图片，标绿色
                    if str(entry) in self._img_dirs:
                        child.setForeground(0, QColor("#22c55e"))
                    self._populate_tree(child, str(entry))
        except PermissionError:
            pass
```

- [ ] **Step 7: 运行测试确认无回归**

```bash
cd D:/UGit/game-dev-manager && python -m pytest tests/ -v
```

预期输出：62 passed, 1 skipped（与改动前一致）。

- [ ] **Step 8: 提交修改**

```bash
cd D:/UGit/game-dev-manager
git add gdm/gui/project_panel.py
git commit -m "feat: 优化目录树视觉体验

1) 添加选中态样式（#0078d4 蓝底白字），解决文字与背景混淆
2) 含图片的目录名显示为绿色（#22c55e），递归检测后代目录

Co-Authored-By: Claude <noreply@anthropic.com>"
```
