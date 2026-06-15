# 记住所有已打开根目录

## 问题描述

用户在项目面板中添加了多个目录，关闭软件后重启，只剩一个目录被恢复。期望：重启后恢复所有关闭前已打开的有效目录。

## 当前状态分析

**已有基础设施：**

- `_save_root_paths()` — 已实现，遍历项目面板中所有顶级条目，将路径列表写入全局配置 `root_paths` 字段
- `_try_restore_project()` — 已实现，启动时从全局配置读取 `root_paths`，恢复所有有效目录
- `save_config()` / `load_config()` — 全局配置的读写能力完好

**当前调用链（问题所在）：**

```
_save_root_paths()  ← 仅 _on_root_removed() 调用
                    ← 没有在添加目录时调用
                    ← 没有在关闭窗口时调用
```

**已有 bug：** `_try_restore_project()` 第 245 行使用了可能不存在的变量 `last_folder`，当从 `root_paths` 恢复时该变量未定义。

## 设计方案

### 改动点

仅需修改 `gdm/gui/main_window.py` 四处：

#### 1. 添加目录时保存

在 `_set_workspace()` 中，`add_root()` 后调用 `_save_root_paths()`。

```
_set_workspace(folder):
    project = Project(root_path=folder)
    project_panel.add_root(folder)
    _save_root_paths()        ← 新增
    # ... 扫描逻辑不变
```

#### 2. 关闭窗口时保存

重写 `closeEvent()`，先保存再关闭：

```
closeEvent(event):
    _save_root_paths()
    super().closeEvent(event)
```

#### 3. 修复已有 bug

`_try_restore_project()` 末尾（第 242-245 行）存在两个问题：

- `_on_folder_selected()` 已在第 239 行触发扫描，第 242-245 行导致**重复扫描**
- 第 245 行引用变量 `last_folder`，当从 `root_paths` 恢复时该变量未定义，导致 `NameError`

修复方案：删除第 242-245 行（冗余的进度条显示 + buggy 的扫描调用）。

`_on_folder_selected()` → `_on_tree_scan_finished` 和原来的 `_on_restore_scan_finished` 功能完全一致（设置 sprites + 加载缩略图），不需要额外的回调路径。

同时删除不再被调用的 `_on_restore_scan_finished()` 方法。

### 恢复时的行为

- `_try_restore_project()` 中已有 `os.path.isdir(path)` 检查，不存在的目录**静默跳过**
- 不恢复展开/选中状态，仅恢复顶级条目列表
- 选中并展开第一个目录

### 会影响到的现有测试

| 测试用例 | 位置 | 影响 |
|----------|------|------|
| `TestSetWorkspaceSavesConfig` | `test_main_window.py:99` | 需新增断言：验证 `root_paths` 字段被正确写入 |
| `TestTryRestoreProjectLoadsConfig` | `test_main_window.py:123` | 不受影响（已有 `last_folder` → `root_paths` 兼容路径） |

### 不改动的内容

- `Project` 模型保持单 `root_path` 字段不变（多根目录信息由全局配置承载即可）
- `ProjectPanel` 无需修改
- `_try_restore_project()` 恢复逻辑无需修改（已正确处理）
- 全局配置文件结构无需变更
