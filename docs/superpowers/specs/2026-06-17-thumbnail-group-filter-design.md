# 设计文档：缩略图按文件名前缀分组筛选

**日期**: 2026-06-17

## 目标

在缩略图区域顶部新增下拉筛选栏，允许用户按文件名前缀分组查看图片，解决大量图片扁平堆叠难以浏览的问题。

## 背景

当前缩略图是一个扁平网格，目录下所有图片不分来源地混在一起。在典型的游戏素材目录中，图片通常按命名规范组织（如 `character_idle_001.png`、`character_run_001.png`、`enemy_boss_001.png`），用户希望按前缀分组浏览。

## Before / After

```
Before: 网格平铺所有图片，无法分类
After:  网格顶部有 QComboBox 下拉框，选择分组后只显示该组图片
```

## 前缀提取规则

- 对每个文件名（不含扩展名），匹配 `^(.*)_\d+` 模式
- 取第一个捕获组作为分组名
- 无匹配的文件归入 `其他`

| 文件名 | 分组名 |
|--------|--------|
| `character_idle_001.png` | `character_idle` |
| `enemy_boss_02.png` | `enemy_boss` |
| `UI_button.png` | `其他` |
| `icon.png` | `其他` |

## 改动

**文件**: `gdm/gui/thumbnail_view.py`

### 1. 新增 `_extract_prefix()` 静态方法

```python
import re

@staticmethod
def _extract_prefix(file_name: str) -> str:
    """从文件名提取分组前缀。

    匹配最后一个 '_数字' 之前的部分，无匹配返回 '其他'。
    示例：
        character_idle_001.png → character_idle
        icon.png → 其他
    """
    stem = os.path.splitext(file_name)[0]
    m = re.match(r"^(.*)_\d+", stem)
    return m.group(1) if m else "其他"
```

### 2. 在 `_init_ui()` 中新增 ComboBox

确保文件顶部已导入 `QComboBox`。在 `_list_widget` 上方插入筛选栏：

```python
# 分组筛选栏
self._prefix_combo = QComboBox()
self._prefix_combo.addItem("全部")
self._prefix_combo.currentTextChanged.connect(self._on_group_changed)
self._main_layout.addWidget(self._prefix_combo)
```

### 3. 新增 `_build_groups()` 方法

扫描当前 `_sprites` 中所有文件名，提取分组去重排序后填充 ComboBox，保留当前选中项：

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

### 4. 新增 `_apply_filter()` 和 `_on_group_changed()`

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

### 5. 在数据加载完成后调用 `_build_groups()`

在 `load()` 和 `load_from_cache()` 方法末尾（`_update_count()` 之后）追加：

```python
self._build_groups()
```

### 6. 扫描期间隐藏 ComboBox

在 `show_progress()` 末尾追加：

```python
self._prefix_combo.setVisible(False)
```

在 `load()` 和 `load_from_cache()` 的可见性恢复处追加：

```python
self._prefix_combo.setVisible(True)
```

## 注意事项

- `_items` 的 key 是 `file_path`，过滤时通过 `sprite.file_path` 从 `_items` 查找 item，而非依赖 `zip`（Dict 顺序不可靠）

## 影响范围

- 修改文件: `gdm/gui/thumbnail_view.py`
- 需要在文件顶部 import 中新增 `QComboBox`
- 新增约 50 行代码
- 不改变现有数据流和信号
- ComboBox 在扫描期间隐藏（`show_progress`），加载完成后恢复显示
- 由于 `_build_groups()` 只在 `load()` / `load_from_cache()` 末尾调用，增量更新后分组列表不会自动刷新
