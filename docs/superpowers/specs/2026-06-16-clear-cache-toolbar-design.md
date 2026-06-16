# 设计文档：清空缓存移到工具栏

**日期**: 2026-06-16

## 目标

将"工具"菜单中"清空缩略图缓存"操作从下拉菜单移动到工具栏，并删除"工具"菜单的下拉框，使其与"文件"、"帮助"菜单行为一致（下拉框为空，仅通过 `aboutToShow` 切换工具栏内容）。

## 背景

当前菜单栏有三个菜单：文件、工具、帮助。文件菜单和帮助菜单的下拉框都是空的，它们的 Action 仅显示在工具栏中。但工具菜单在三项 Action 之外额外做了 `addAction()`，导致点击时弹出下拉框，与另外两个菜单行为不一致。

## Before / After

```
Before: 点击"工具" → 弹出下拉框 [批量重命名] [全量解压] [清空缩略图缓存]
After:  点击"工具" → 不弹出下拉框，工具栏显示三个按钮 [批量重命名] [全量解压] [清空缩略图缓存]
```

## 改动

**文件**: `gdm/gui/main_window.py`

### 1. 删除工具菜单的子 Action

在 `_init_menubar()` 方法中，删除工具菜单的三行 `tool_menu.addAction()` 调用：

```python
tool_menu.addAction(rename_action)
tool_menu.addAction(extract_action)
tool_menu.addAction(clear_cache_act)
```

`aboutToShow` 信号连接保持不变。

由于工具菜单不再有子 Action，Qt 不会弹出下拉框。

### 2. 将"清空缩略图缓存"加入工具栏

在 `_init_menubar()` 方法的 `_toolbar_actions` 字典中，`"工具"` 项增加 `clear_cache_act`：

```python
# 原来
"工具": [rename_action, extract_action],
# 改为
"工具": [rename_action, extract_action, clear_cache_act],
```

## 测试

**文件**: `tests/test_main_window.py`

### 1. 修改现有测试

`TestToolbarUpdate.test_toolbar_updates_on_menu_about_to_show` 的 `expected_texts` 新增"清空缩略图缓存"：

```python
# 原来
expected_texts = ["批量重命名", "全量解压"]
# 改为
expected_texts = ["批量重命名", "全量解压", "清空缩略图缓存"]
```

### 2. 新增回归测试

在 `TestToolbarUpdate` 类中增加测试用例，验证"工具"菜单的 `actions()` 为空：

```python
def test_tool_menu_has_no_children(self, main_window):
    """工具菜单不应包含下拉子项。"""
    menu_bar = main_window.menuBar()
    tool_menu = None
    for action in menu_bar.actions():
        if action.text() == "工具":
            tool_menu = action.menu()
            break
    assert tool_menu is not None
    assert len(tool_menu.actions()) == 0
```

## 影响范围

- 修改文件: `gdm/gui/main_window.py`、`tests/test_main_window.py`
- 无功能删除，仅 UX 调整
- "清空缩略图缓存"功能逻辑完全不变
- 不影响菜单栏其他部分
