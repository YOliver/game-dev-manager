# 移除菜单下拉列表

## 问题描述

功能栏已展示所有子功能项，菜单栏的下拉列表成为冗余交互。期望：点击菜单标题只切换功能栏，不再弹出下拉列表。

## 设计方案

### 架构

菜单栏保留三个标题（文件/工具/帮助）及原生样式，但不再添加子项。点击标题只触发 `aboutToShow` 信号切换功能栏，无下拉出现。

```
┌──────────────────────────────────────────────┐
│  文件    工具    帮助          ← 菜单栏标题（保留样式，无下拉）  │
├──────────────────────────────────────────────┤
│  [打开文件夹] [保存工作区] [退出] ← 功能栏（一切功能在此）   │
└──────────────────────────────────────────────┘
```

### 实现方式

#### 1. Action 创建与菜单分离

将原本通过 `menu.addAction()` 创建的 Action 改为独立创建，存入字典：

```python
# 文件菜单的 Action（独立创建，不加入菜单）
open_action = QAction("打开文件夹", self)
open_action.triggered.connect(self._open_folder)

save_action = QAction("保存工作区", self)
save_action.triggered.connect(self._save_project)

exit_action = QAction("退出", self)
exit_action.triggered.connect(self.close)

# 存入字典，供功能栏使用
self._toolbar_actions = {
    "文件": [open_action, save_action, exit_action],
    "工具": [rename_action],
    "帮助": [manual_action, welcome_action, about_action],
}
```

#### 2. _update_toolbar 改为接受菜单名称

```python
def _update_toolbar(self, menu_name: str) -> None:
    """根据菜单名称更新功能栏内容。"""
    self.toolbar.clear()
    for action in self._toolbar_actions.get(menu_name, []):
        self.toolbar.addAction(action)
```

#### 3. aboutToShow 传菜单名称

```python
file_menu.aboutToShow.connect(lambda: self._update_toolbar("文件"))
tool_menu.aboutToShow.connect(lambda: self._update_toolbar("工具"))
help_menu.aboutToShow.connect(lambda: self._update_toolbar("帮助"))
```

默认显示：

```python
self._update_toolbar("文件")
```

### 需新增/修改的导入

```python
from PySide6.QtGui import QAction, QCloseEvent
```

### 改动范围

仅修改 `gdm/gui/main_window.py`：

| 区域 | 改动 |
|------|------|
| 导入 | `from PySide6.QtGui import QAction` |
| `_init_menubar()` | Action 与菜单分离，存入 `self._toolbar_actions` |
| `_update_toolbar()` | 签名改为 `(menu_name: str)`，从字典取 Action |

### 不影响的内容

- 所有回调函数不变
- 功能栏按钮行为不变
- `aboutToShow` 信号仍正常触发

### 注意事项

- 菜单标题仍可被点击（触发 `aboutToShow`），但由于没有子项，Qt 不会弹出下拉
- `self._toolbar_actions` 是 `dict[str, list[QAction]]`，在 `_init_menubar()` 中赋值
