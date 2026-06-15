# 目录树默认收起

## 问题描述

打开软件后，项目面板的目录树默认展开根目录。期望：所有目录树默认收起，用户手动双击展开。

## 现状分析

`ProjectPanel.add_root()` 中（`project_panel.py:81`）在添加根节点后调用了 `self.tree.expandItem(root_item)`，导致根目录自动展开。`_populate_tree()` 中的子目录默认就是收起的。

## 设计方案

### 改动点

仅修改 `gdm/gui/project_panel.py` 一处：

删除第 81 行的 `self.tree.expandItem(root_item)`。

```
add_root(path):
    root_item = QTreeWidgetItem(...)
    ...
    _populate_tree(root_item, path)
    # 删除：self.tree.expandItem(root_item)
```

### 行为变化

- 启动恢复时：所有根目录收起
- 手动添加文件夹时：根目录收起
- 用户仍可通过双击展开/收起（`setExpandsOnDoubleClick` 保持默认 `True`）

### 不改动的内容

- `_populate_tree()` 子目录本来就是收起的
- `setExpandsOnDoubleClick` 保持 Qt 默认值
- 无其他展开/收起逻辑需要修改
