# 文件夹树紧凑布局优化设计

## 概述

优化左侧项目面板的 QTreeWidget 文件夹树，使其外观更紧凑、更美观。

## 当前问题

- QTreeWidget 的默认缩进（20px）过大，嵌套子目录时浪费水平空间
- 列标题 "文件夹" 占据一整行高度，在只显示目录名的场景下无实际价值
- 项间距和面板边距默认偏大，导致文件夹树信息密度低
- 左侧面板被不必要地撑宽

## 改动方案

仅修改 `gdm/gui/project_panel.py` 中 `_init_ui()` 方法。

### 具体改动

| 项 | 改动前 | 改动后 |
|------|--------|--------|
| 面板边距 | 默认 (11px 左右) | `0, 0, 0, 0` |
| 列标题 | 显示 "文件夹" | 隐藏 (`setHeaderHidden(True)`) |
| 缩进 | 20px (默认) | 10px |
| 字号 | 默认 | 11px |
| item 内边距 | 默认 | `1px 0px` |

### stylesheet

```css
QTreeWidget {
    font-size: 11px;
}
QTreeWidget::item {
    padding: 1px 0px;
    margin: 0px;
    border: none;
}
QTreeWidget::branch {
    margin: 0px;
    padding: 0px;
}
```

### 不变的部分

- 功能逻辑：`set_root()`、`_populate_tree()`、`_on_item_clicked()` 不变
- 信号：`folder_selected` 不变
- 主窗口布局比例（stretch 1:3:1）不变

## 验证标准

- 隐藏标题栏后根节点名清晰可辨
- 缩进减小后嵌套目录不拥挤
- 点击切换文件夹功能正常
- 所有测试通过
