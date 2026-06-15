# 功能栏（Toolbar）

## 问题描述

目前所有功能藏在菜单栏的二级菜单中，用户需要点击菜单才能看到可用操作。期望：菜单栏下方增加一个功能栏，展示当前选中菜单的子功能项，用户可直接点击按钮执行操作。

## 现状分析

菜单栏结构：

| 顶级菜单 | 子项 |
|----------|------|
| 文件 | 打开文件夹、保存工作区、退出 |
| 工具 | 批量重命名 |
| 帮助 | 使用手册、欢迎、软件信息 |

每个子项对应一个 `QAction`，已绑定 `triggered` 信号到对应回调函数。

## 设计方案

### 架构

在菜单栏下方添加一个 `QToolBar`，通过监听顶级菜单的 `aboutToShow` 信号动态切换显示内容。

```
┌──────────────────────────────────────────────┐
│  文件    工具    帮助                          │ ← 菜单栏（不变）
├──────────────────────────────────────────────┤
│  [打开文件夹] [保存工作区] [退出]              │ ← 功能栏（新增）
├──────────────────────────────────────────────┤
│  项目面板 │ 缩略图视图 │ 详情面板               │ ← 主窗格（不变）
└──────────────────────────────────────────────┘
```

### 交互流程

1. **启动时**：默认显示"文件"菜单的子项
2. **点击"工具"菜单**：功能栏切换为 [批量重命名]
3. **点击"帮助"菜单**：功能栏切换为 [使用手册] [欢迎] [软件信息]
4. **点击按钮**：执行与菜单项相同的功能（复用同一 QAction）

### 实现方式

在 `_init_ui()` 中添加 QToolBar，在 `_init_menubar()` 中连接 `aboutToShow` 信号：

```python
# _init_ui() 中添加
self.toolbar = QToolBar("功能栏")
self.toolbar.setMovable(False)
self.addToolBar(Qt.TopToolBarArea, self.toolbar)

# _init_menubar() 中为每个顶级菜单连接 aboutToShow
file_menu.aboutToShow.connect(lambda: self._update_toolbar(file_menu))
tool_menu.aboutToShow.connect(lambda: self._update_toolbar(tool_menu))
help_menu.aboutToShow.connect(lambda: self._update_toolbar(help_menu))

# 默认显示"文件"菜单内容
self._update_toolbar(file_menu)

# 新增方法
def _update_toolbar(self, menu):
    self.toolbar.clear()
    for action in menu.actions():
        if action.isSeparator():
            continue
        self.toolbar.addAction(action)
```

### 设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 组件类型 | `QToolBar` + `QAction` | Qt 原生，自动创建 `QToolButton`，继承 action 文本和信号 |
| 分隔线 | 忽略 | 功能栏无需视觉分隔 |
| 按钮样式 | 纯文本 | 简洁，无需设计图标 |
| 默认显示 | "文件"菜单内容 | 启动即可用核心功能 |
| 可移动 | 否（`setMovable(False)`） | 保持固定位置 |

### 改动范围

仅修改 `gdm/gui/main_window.py`：
- 文件顶部新增 `from PySide6.QtWidgets import QToolBar`
- `_init_ui()` — 添加 `QToolBar`
- `_init_menubar()` — 连接 `aboutToShow` 信号，设置默认内容
- 新增 `_update_toolbar()` 方法

### 注意事项

- 点击菜单时，下拉菜单会短暂遮挡功能栏。用户关闭下拉菜单后，功能栏保留显示该菜单功能项，这是预期行为。
- 功能栏按钮使用 `addAction(action)` 创建，自动继承对应菜单项的文本和 `triggered` 信号，无需手动绑定回调。

### 不改动的内容

- 菜单栏结构和回调保持不变
- 其他 UI 组件不变
