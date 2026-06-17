# 缩略图按文件名前缀分组筛选 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在缩略图区域顶部新增 QComboBox 下拉筛选栏，按文件名前缀分组查看图片。

**Architecture:** 通过正则 `^(.*)_\d+` 从文件名提取分组前缀，构建 QComboBox 选项，选中分组后对 QListWidgetItem 做 hidden/visible 切换实现过滤。ComboBox 在扫描期间隐藏。

**Tech Stack:** PySide6 QComboBox, Python re

---

### Task 1: 新增前缀提取和过滤方法

**Files:**
- Modify: `gdm/gui/thumbnail_view.py`

- [ ] **Step 1: 添加 import**

在文件顶部添加 `import re` 和 `QComboBox`：

```python
import os
import re
```

```python
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
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

- [ ] **Step 2: 新增 `_extract_prefix()` 静态方法**

在 `_update_count()` 方法之后、`_relayout()` 之前插入：

```python
    @staticmethod
    def _extract_prefix(file_name: str) -> str:
        """从文件名提取分组前缀。

        匹配最后一个 '_数字' 之前的部分，无匹配返回 '其他'。
        """
        stem = os.path.splitext(file_name)[0]
        m = re.match(r"^(.*)_\d+", stem)
        return m.group(1) if m else "其他"
```

- [ ] **Step 3: 提交**

```bash
git add gdm/gui/thumbnail_view.py
git commit -m "feat: 新增前缀提取静态方法"
```

---

### Task 2: 新增 ComboBox 和构建/过滤方法

**Files:**
- Modify: `gdm/gui/thumbnail_view.py`

- [ ] **Step 1: 在 `_init_ui()` 中新增 ComboBox**

在 `_list_widget` 添加到布局后（`self._main_layout.addWidget(self._list_widget)` 之后），插入筛选栏：

```python
        self._main_layout.addWidget(self._list_widget)

        # 分组筛选栏
        self._prefix_combo = QComboBox()
        self._prefix_combo.addItem("全部")
        self._prefix_combo.currentTextChanged.connect(self._on_group_changed)
        self._main_layout.addWidget(self._prefix_combo)
```

- [ ] **Step 2: 新增 `_build_groups()` 方法**

在 `_extract_prefix()` 之后插入：

```python
    def _build_groups(self) -> None:
        """从当前精灵图列表提取分组并填充下拉框。"""
        groups = sorted(set(
            self._extract_prefix(s.file_name) for s in self._sprites
        ))
        current = self._prefix_combo.currentText()
        self._prefix_combo.blockSignals(True)
        self._prefix_combo.clear()
        self._prefix_combo.addItem("全部")
        self._prefix_combo.addItems(groups)
        if current in groups or current == "全部":
            self._prefix_combo.setCurrentText(current)
        else:
            self._prefix_combo.setCurrentText("全部")
        self._prefix_combo.blockSignals(False)
        self._apply_filter()
```

- [ ] **Step 3: 新增 `_apply_filter()` 和 `_on_group_changed()`**

在 `_build_groups()` 之后插入：

```python
    def _apply_filter(self) -> None:
        """根据当前选中的分组隐藏/显示列表项。"""
        group = self._prefix_combo.currentText()
        for sprite in self._sprites:
            item = self._items.get(sprite.file_path)
            if item is None:
                continue
            if group == "全部":
                item.setHidden(False)
            else:
                item.setHidden(self._extract_prefix(sprite.file_name) != group)

    def _on_group_changed(self, _text: str) -> None:
        """分组切换回调。"""
        self._apply_filter()
```

- [ ] **Step 4: 提交**

```bash
git add gdm/gui/thumbnail_view.py
git commit -m "feat: 新增分组筛选 ComboBox 和过滤逻辑"
```

---

### Task 3: 接入数据加载流程和可见性控制

**Files:**
- Modify: `gdm/gui/thumbnail_view.py`

- [ ] **Step 1: 在 `show_progress()` 中隐藏 ComboBox**

在 `show_progress()` 方法末尾（`_count_label.setVisible(False)` 之后）追加：

```python
        self._prefix_combo.setVisible(False)
```

- [ ] **Step 2: 在 `load()` 中恢复 ComboBox 并构建分组**

在 `load()` 中，`_count_label.setVisible(True)` 之后追加：

```python
        self._prefix_combo.setVisible(True)
```

在 `self._update_count()` 之后追加：

```python
        self._build_groups()
```

- [ ] **Step 3: 在 `load_from_cache()` 中恢复 ComboBox 并构建分组**

在 `load_from_cache()` 中，`_count_label.setVisible(True)` 之后追加：

```python
        self._prefix_combo.setVisible(True)
```

在 `self._update_count()` 之后追加：

```python
        self._build_groups()
```

- [ ] **Step 4: 提交**

```bash
git add gdm/gui/thumbnail_view.py
git commit -m "feat: 接入分组筛选到数据加载流程"
```

---

### Task 4: 编写测试

**Files:**
- Modify: `tests/test_thumbnail_view.py`

- [ ] **Step 1: 编写前缀提取测试**

```python
class TestExtractPrefix:
    """测试 _extract_prefix() 前缀提取。"""

    def test_extract_with_number_suffix(self):
        from gdm.gui.thumbnail_view import ThumbnailView
        assert ThumbnailView._extract_prefix("character_idle_001.png") == "character_idle"
        assert ThumbnailView._extract_prefix("enemy_boss_02.png") == "enemy_boss"
        assert ThumbnailView._extract_prefix("sprite_1.png") == "sprite"

    def test_extract_no_number_returns_other(self):
        from gdm.gui.thumbnail_view import ThumbnailView
        assert ThumbnailView._extract_prefix("icon.png") == "其他"
        assert ThumbnailView._extract_prefix("UI_button.png") == "其他"
        assert ThumbnailView._extract_prefix("bg.png") == "其他"

    def test_extract_multi_underscore(self):
        from gdm.gui.thumbnail_view import ThumbnailView
        assert ThumbnailView._extract_prefix("player_run_left_001.png") == "player_run_left"
```

- [ ] **Step 2: 运行测试**

```bash
pytest tests/test_thumbnail_view.py -v
```

预期：全部 PASS

- [ ] **Step 3: 提交**

```bash
git add tests/test_thumbnail_view.py
git commit -m "test: 新增前缀提取测试"
```
