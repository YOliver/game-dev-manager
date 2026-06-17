# 设计文档：缩略图区域显示图片总数

**日期**: 2026-06-17

## 目标

在缩略图视图底部显示当前目录中的图片总数，纯数字，右对齐灰色小字。

## 背景

目前缩略图区域仅在扫描时通过进度条临时显示 `已完成: X / Y 张`，扫描完成后该信息消失。用户在浏览精灵图时无法直观了解当前目录下共有多少张图片，只能通过选中多张后在右侧详情面板看到汇总数量。

## Before / After

```
Before: 缩略图网格占满整个区域，底部无任何信息
After:  缩略图网格下方显示右对齐灰色数字，如 "42"
        无图片时显示 "0"
```

## 改动

**文件**: `gdm/gui/thumbnail_view.py`

### 1. 在 `__init__()` 中新增计数标签

在 `self._main_layout.addWidget(self._progress_widget)` 之前插入计数标签，使其位于网格与进度界面之间：

```python
# 图片计数标签
self._count_label = QLabel("0")
self._count_label.setAlignment(Qt.AlignmentFlag.AlignRight)
self._count_label.setStyleSheet(
    "color: #999; font-size: 11px; padding: 2px 8px;"
)
self._main_layout.addWidget(self._count_label)
```

### 2. 新增 `_update_count()` 方法

```python
def _update_count(self) -> None:
    """更新图片计数显示。"""
    self._count_label.setText(str(len(self._sprites)))
```

### 3. 在 `show_progress()` / `load()` / `load_from_cache()` 中控制可见性

扫描期间隐藏计数标签，加载完成后恢复显示：

```python
# show_progress() 中追加
self._count_label.setVisible(False)

# load() 的进度切换处追加
self._count_label.setVisible(True)

# load_from_cache() 的进度切换处追加
self._count_label.setVisible(True)
```

### 4. 在数据变更点调用 `_update_count()`

在以下四个方法末尾加入 `self._update_count()`：

- `load()` — 全新加载精灵图列表
- `load_from_cache()` — 从缓存加载
- `apply_entries_updated()` — 增量新增/更新
- `apply_entries_removed()` — 删除项

以上方法已经在操作中正确维护 `self._sprites` 列表，直接取 `len(self._sprites)` 即可得到准确数量。

## 测试

**文件**: `tests/test_thumbnail_view.py`（如已存在则追加，否则新建）

```python
def test_count_label_initial(self, thumbnail_view):
    """初始状态计数应为 0。"""
    assert thumbnail_view._count_label.text() == "0"

def test_count_label_after_load(self, thumbnail_view, sample_sprites):
    """加载精灵图后计数应正确。"""
    thumbnail_view.load(sample_sprites)
    assert thumbnail_view._count_label.text() == str(len(sample_sprites))

def test_count_label_after_remove(self, thumbnail_view, sample_sprites):
    """删除项后计数应减少。"""
    thumbnail_view.load(sample_sprites)
    to_remove = [(s.file_path, s.file_name) for s in sample_sprites[:2]]
    keys = [(s.file_path, s.file_name) for s in sample_sprites[:2]]
    thumbnail_view.apply_entries_removed(keys)
    assert thumbnail_view._count_label.text() == str(len(sample_sprites) - 2)
```

## 影响范围

- 修改文件: `gdm/gui/thumbnail_view.py`
- 新增约 10 行代码
- 不改变任何现有数据流或信号
- 标签在扫描进度界面显示时不可见（与 `_list_widget` 一起隐藏），符合预期
