# 递归扫描图片设计文档

## 概述

将 Game Dev Manager 默认的文件夹扫描方式从非递归改为递归，
使得用户选中一个文件夹后，自动显示该目录下**所有子目录**中的图片文件，
无需逐个点击子目录来查看。

## 背景

当前行为：用户打开一个文件夹（或点击左侧树中的目录），
`scan()` 函数以 `recursive=False` 调用，仅显示选中目录的直接子文件。
用户需要手动点击左侧树中的各个子目录，才能浏览其内的图片。

期望行为：选中文件夹后，自动递归扫描所有后代目录，一次性展示全部图片。

## 改动范围

仅修改 `gdm/gui/main_window.py` 中 3 处调用 `scan()` 的位置，
将 `recursive=False` 改为 `recursive=True`：

| 调用位置 | 方法 | 行号（当前代码） |
|----------|------|------------------|
| 设置工作区 | `_set_workspace()` | 第 118 行 |
| 启动恢复 | `_try_restore_project()` | 第 168 行 |
| 左侧树点击 | `_on_folder_selected()` | 第 183 行 |

## 不需要修改的文件

- `gdm/core/scanner.py` — 已支持 `recursive` 参数
- `gdm/gui/thumbnail_view.py` — 异步加载机制对图片数量不敏感
- `gdm/gui/project_panel.py` — 无需改动
- `tests/` — 如测试递归扫描场景则补充用例（可选）

## 影响分析

| 方面 | 评估 |
|------|------|
| 性能 | 递归扫描更多文件，但 ThumbnailView 已有异步加载 + QThreadPool，不阻塞 UI |
| 左侧树 | 点击子目录也递归显示其后代图片（行为一致） |
| 重命名刷新 | `_on_renamed()` 调用 `_on_folder_selected()`，同样走递归路径 |
| 用户体验 | 一次点击即可查看整个项目所有图片，无需逐层浏览 |
| 大型项目 | 数千张图片时网格会很长，但现有滚动机制自适应 |


## 实现步骤

1. 将 `_set_workspace()` 中的 `recursive=False` 改为 `recursive=True`
2. 将 `_try_restore_project()` 中的 `recursive=False` 改为 `recursive=True`
3. 将 `_on_folder_selected()` 中的 `recursive=False` 改为 `recursive=True`
4. 运行测试确认无回归
5. 手动验证递归扫描效果

## 验证标准

- 打开包含多层子目录的文件夹，能看到所有子目录中的图片
- 左侧树点击任意子目录，同样显示其全部后代目录的图片
- 启动自动恢复上次工作区时，也使用递归扫描
- 重命名后刷新视图，文件列表一致
