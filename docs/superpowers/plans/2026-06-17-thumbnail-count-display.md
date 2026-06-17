# 缩略图区域显示图片总数 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在缩略图视图底部新增右对齐灰色数字标签，实时显示当前目录图片总数。

**Architecture:** 在 `ThumbnailView` 中新增一个 `QLabel`，通过对 `_sprites` 列表的 `len()` 取值驱动文本更新，在四个数据变更方法中调用 `_update_count()` 保持同步，扫描期间隐藏。

**Tech Stack:** PySide6 QLabel

---

### Task 1: 新增计数标签和更新方法

**Files:**
- Modify: `gdm/gui/thumbnail_view.py`

- [ ] **Step 1: 在 `__init__()` 中新增 `_count_label`**

在 `self._main_layout.addWidget(self._progress_widget)` **之前**插入：

```python
# 图片计数标签
self._count_label = QLabel("0")
self._count_label.setAlignment(Qt.AlignmentFlag.AlignRight)
self._count_label.setStyleSheet(
    "color: #999; font-size: 11px; padding: 2px 8px;"
)
self._main_layout.addWidget(self._count_label)
```

- [ ] **Step 2: 新增 `_update_count()` 方法**

在 `_init_ui()` 之后、`_relayout()` 之前添加：

```python
def _update_count(self) -> None:
    """更新图片计数显示。"""
    self._count_label.setText(str(len(self._sprites)))
```

- [ ] **Step 3: 提交**

```bash
git add gdm/gui/thumbnail_view.py
git commit -m "feat: 新增缩略图计数标签和更新方法"
```

---

### Task 2: 在数据变更点调用计数更新

**Files:**
- Modify: `gdm/gui/thumbnail_view.py`

- [ ] **Step 1: 在 `load()` 末尾加入计数更新和可见性恢复**

在 `load()` 方法中，`self._progress_widget.setVisible(False)` 下方追加 `_count_label` 可见性恢复，方法末尾调用 `_update_count()`：

```python
# load() 中
self._progress_widget.setVisible(False)
self._list_widget.setVisible(True)
self._count_label.setVisible(True)    # ← 新增
```

在方法末尾 `self._relayout()` 之后添加：

```python
self._update_count()    # ← 新增
```

- [ ] **Step 2: 在 `load_from_cache()` 末尾加入计数更新和可见性恢复**

在 `load_from_cache()` 中，`self._list_widget.setVisible(True)` 下方追加：

```python
self._count_label.setVisible(True)    # ← 新增
```

在方法末尾 `self._relayout()` 之后添加：

```python
self._update_count()    # ← 新增
```

- [ ] **Step 3: 在 `show_progress()` 中隐藏计数标签**

在 `show_progress()` 方法末尾追加：

```python
self._count_label.setVisible(False)    # ← 新增
```

- [ ] **Step 4: 在 `apply_entries_updated()` 末尾加入计数更新**

在方法末尾追加：

```python
self._update_count()    # ← 新增
```

- [ ] **Step 5: 在 `apply_entries_removed()` 末尾加入计数更新**

在方法末尾 `self._thumbnails.pop(full_path, None)` 之后、方法结束前追加：

```python
self._update_count()    # ← 新增
```

- [ ] **Step 6: 提交**

```bash
git add gdm/gui/thumbnail_view.py
git commit -m "feat: 在数据变更点接入计数更新逻辑"
```

---

### Task 3: 编写测试

**Files:**
- Modify: `tests/test_thumbnail_view.py`（如不存在则创建）

- [ ] **Step 1: 创建测试 fixtures**

如果 `tests/test_thumbnail_view.py` 不存在，先写入 fixtures：

```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from gdm.gui.thumbnail_view import ThumbnailView
from gdm.core.models import SpriteInfo


@pytest.fixture
def thumbnail_view(qtbot):
    view = ThumbnailView()
    qtbot.addWidget(view)
    return view


@pytest.fixture
def sample_sprites():
    return [
        SpriteInfo(
            file_path=f"/test/sprite_{i:03d}.png",
            file_name=f"sprite_{i:03d}.png",
            width=64, height=64,
            file_size=1024, format="PNG", color_mode="RGBA",
        )
        for i in range(5)
    ]
```

- [ ] **Step 2: 编写初始状态测试**

```python
def test_count_label_initial(thumbnail_view):
    """初始状态计数应为 0。"""
    assert thumbnail_view._count_label.text() == "0"
```

- [ ] **Step 3: 编写加载后计数测试**

```python
def test_count_label_after_load(thumbnail_view, sample_sprites):
    """加载精灵图后计数应正确。"""
    thumbnail_view.load(sample_sprites)
    assert thumbnail_view._count_label.text() == str(len(sample_sprites))
```

- [ ] **Step 4: 编写删除后计数测试**

```python
def test_count_label_after_remove(thumbnail_view, sample_sprites):
    """删除项后计数应减少。"""
    thumbnail_view.load(sample_sprites)
    keys = [
        (os.path.dirname(s.file_path), s.file_name)
        for s in sample_sprites[:2]
    ]
    thumbnail_view.apply_entries_removed(keys)
    assert thumbnail_view._count_label.text() == str(len(sample_sprites) - 2)
```

- [ ] **Step 5: 运行测试验证**

```bash
pytest tests/test_thumbnail_view.py -v
```

预期：全部 PASS

- [ ] **Step 6: 提交**

```bash
git add tests/test_thumbnail_view.py
git commit -m "test: 新增缩略图计数标签测试"
```
