# 多根目录支持功能设计

> **Date:** 2026-06-15
> **Status:** Approved
> **Goal:** 支持在项目面板中显示和管理多个根目录，类似 VS Code 的资源管理器

## 背景

当前 GDM 的项目面板（`ProjectPanel`）只支持单一根目录。用户每次打开文件夹都会替换当前工作区，无法同时管理多个项目或文件夹。

用户希望：
- 打开文件夹后，默认记录并追加到左侧面板
- 所有打开过的目录都作为根目录显示在最左侧
- 右键选中根目录可主动删除
- 软件扫描选中根目录的图片

## 设计决策

### 1. 实现方案

**决定**：方案 A — 直接扩展 `ProjectPanel`，支持多个 QTreeWidget 顶级项

**理由**：
- 改动最小，复用现有组件
- 保持树形结构直观性
- 右键菜单容易实现（判断是否为顶级项即可）

### 2. 打开文件夹行为

**决定**：改为追加模式，保留现有根目录

**理由**：
- 用户明确选择方案 1（追加模式）
- 符合"所有打开过的目录都显示"的预期

### 3. 扫描触发方式

**决定**：点击根目录即触发该根目录下的全量递归扫描

**理由**：
- 用户明确选择方案 1（点击根目录即扫描）
- 提升操作效率，不需要先展开再点击子文件夹

## 架构与组件

### 组件变化

| 组件 | 变化 |
|------|------|
| `ProjectPanel` | 新增 `add_root()`、`remove_root()`、右键菜单 |
| `MainWindow` | "打开文件夹"改为调用 `add_root()` |
| `config.py` / `models.py` | `save_config()` 支持 `root_paths` 列表 |

### 类设计

**ProjectPanel 新增方法**：

```python
def add_root(self, path: str) -> None:
    """追加一个根目录到树中。
    
    - 检测路径是否存在，不存在则提示
    - 检查是否已存在，避免重复
    - 构建子树并追加为顶级项
    """

def remove_root(self, path: str) -> None:
    """从树中移除指定根目录。
    
    - 查找对应的顶级项并移除
    - 不修改配置文件（由调用方负责持久化）
    """
```

## 数据流与用户交互

### 1. 打开文件夹（追加模式）

```
用户点击"打开文件夹"
  → MainWindow._open_folder()
  → 调用 project_panel.add_root(folder)
  → 追加顶级项到树中
  → 保存到 config.root_paths
```

### 2. 点击根目录触发全量扫描

```
用户点击某个根目录（顶级项）
  → ProjectPanel 发出 folder_selected 信号，路径为该根目录路径
  → MainWindow._on_folder_selected(folder_path)
  → 调用 _start_scan(folder, recursive=True)
  → 扫描该根目录下所有图片
```

### 3. 右键菜单移除根目录

```
用户右键点击某个顶级根目录
  → 弹出菜单："从工作区移除"
  → 点击后调用 project_panel.remove_root(path)
  → 从树中移除该顶级项
  → 从 config.root_paths 中移除
```

### 4. 启动时恢复

```
MainWindow._try_restore_project()
  → 读取 config.root_paths（列表）
  → 遍历调用 project_panel.add_root(path)
  → 所有根目录自动构建子树
```

## 数据持久化

### 配置文件格式

`config.json` 新增 `root_paths` 字段：

```json
{
  "last_folder": "G:/UGit/game-dev-manager",
  "root_paths": [
    "G:/UGit/game-dev-manager",
    "D:/Projects/another-game",
    "C:/Work/test-assets"
  ]
}
```

- `last_folder` 保留，用于兼容旧版本
- `root_paths` 为新字段，为空时不报错

### load_config / save_config 变化

```python
# load_config() 新增返回 root_paths
def load_config() -> dict:
    """返回包含 root_paths (list) 的配置字典。"""
    ...

# save_config() 新增保存 root_paths
def save_config(config: dict) -> bool:
    """接受包含 root_paths (list) 的配置字典。"""
    ...
```

## 边界处理

| 场景 | 处理方式 |
|------|---------|
| 根目录已被删除/移动 | `add_root()` 时检测路径是否存在，不存在则跳过并提示 |
| 重复添加同一根目录 | `add_root()` 先检查是否已存在，避免重复顶级项 |
| 移除唯一剩下的根目录 | 允许移除，面板显示为空，中间缩略图区域清空 |
| 配置文件损坏/无 root_paths 字段 | `load_config()` 返回空列表，不报错 |
| 右键非顶级项（子文件夹） | 不显示"移除"菜单，只触发扫描 |

## 实施计划

### Task 1: 扩展 ProjectPanel 支持多根目录

**Files:**
- Modify: `gdm/gui/project_panel.py`
- Modify: `gdm/gui/main_window.py`

- [ ] **Step 1: 修改 ProjectPanel，新增 add_root() 和 remove_root()**

在 `project_panel.py` 中：
- 将 `set_root()` 重命名为 `add_root()`，改为追加顶级项
- 新增 `remove_root(path)` 方法
- 新增 `_is_top_level_item(item)` 辅助方法
- 新增右键菜单（`contextMenuEvent`）

- [ ] **Step 2: 修改 MainWindow._open_folder()，改为调用 add_root()**

在 `main_window.py` 中：
- 将 `self._set_workspace(folder)` 改为 `self.project_panel.add_root(folder)`
- 保存 `root_paths` 到配置

- [ ] **Step 3: 修改 MainWindow._try_restore_project()，恢复多根目录**

在 `main_window.py` 中：
- 读取 `config.get("root_paths", [])`
- 遍历调用 `project_panel.add_root(path)`

- [ ] **Step 4: 更新 config.py，支持 root_paths**

在 `config.py` 中：
- `save_config()` 接受并保存 `root_paths` 列表
- `load_config()` 返回时包含 `root_paths` 字段

- [ ] **Step 5: 运行测试确认无回归**

```bash
cd G:/UGit/game-dev-manager && python -m pytest tests/ -v
```

预期输出：所有测试通过

- [ ] **Step 6: 提交修改**

```bash
cd G:/UGit/game-dev-manager
git add gdm/gui/project_panel.py gdm/gui/main_window.py gdm/core/config.py
git commit -m "feat: 支持多根目录，打开文件夹改为追加模式

- ProjectPanel 新增 add_root()/remove_root()，支持多个顶级项
- 点击根目录即触发该根目录下的全量递归扫描
- 右键菜单支持从工作区移除根目录
- 配置文件新增 root_paths 字段，启动时自动恢复

Co-Authored-By: Claude <noreply@anthropic.com>"
```

## 影响分析

### 用户体验
- ✅ 可同时管理多个项目/工作区
- ✅ 快速切换不同项目的文件夹
- ✅ 保留所有打开过的目录记录
- ⚠️ 旧版本只支持单一根目录，升级后自动迁移（last_folder → root_paths[0]）

### 技术风险
- ✅ 风险低：主要改动集中在 ProjectPanel
- ✅ QTreeWidget 原生支持多个顶级项
- ⚠️ 需注意右键菜单只对顶级项显示移除选项

### 向后兼容
- ✅ `last_folder` 字段保留，旧配置可正常加载
- ✅ `root_paths` 为空或不存时不报错

---

**审批记录**：
- ✅ 用户确认使用方案 A（扩展 ProjectPanel）
- ✅ 用户确认打开文件夹为追加模式
- ✅ 用户确认点击根目录即触发全量扫描
- ✅ 用户确认所有设计章节（架构、数据流、持久化）
