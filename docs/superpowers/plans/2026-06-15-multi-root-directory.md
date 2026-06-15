# 多根目录支持功能实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 扩展 ProjectPanel 支持多个顶级根目录，打开文件夹改为追加模式，支持右键菜单移除和启动时恢复

**Architecture:** 修改 ProjectPanel 支持多顶级项，更新 MainWindow 的文件夹打开和恢复逻辑，扩展 config.py 支持 root_paths 列表

**Tech Stack:** Python, PySide6, pytest

---

### Task 1: 扩展 ProjectPanel 支持多根目录

**Files:**
- Modify: `gdm/gui/project_panel.py`
- Test: `tests/test_project_panel.py` (新建)

- [ ] **Step 1: 修改 set_root() 为 add_root()，支持追加顶级项**

在 `gdm/gui/project_panel.py` 中，修改 `set_root()` 方法：

```python
def add_root(self, path: str) -> None:
    """追加一个根目录到树中。
    
    - 检测路径是否存在，不存在则提示
    - 检查是否已存在，避免重复顶级项
    - 构建子树并追加为顶级项
    """
    import os
    from pathlib import Path
    
    # 检查路径是否存在
    if not os.path.isdir(path):
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(self, "警告", f"目录不存在:\n{path}")
        return
    
    # 检查是否已存在
    for i in range(self.tree.topLevelItemCount()):
        item = self.tree.topLevelItem(i)
        existing_path = item.data(0, 42)
        if existing_path == path:
            return  # 已存在，跳过
    
    # 追加为顶级项
    try:
        self._img_dirs = self._build_img_dirs(path)
    except Exception:
        self._img_dirs = set()
    
    root_item = QTreeWidgetItem(self.tree, [Path(path).name])
    root_item.setData(0, 42, path)  # 存储完整路径
    if path in self._img_dirs:
        root_item.setForeground(0, self._GREEN)
    self._populate_tree(root_item, path)
    self.tree.expandItem(root_item)
```

- [ ] **Step 2: 新增 remove_root() 方法**

在 `project_panel.py` 中，新增方法：

```python
def remove_root(self, path: str) -> None:
    """从树中移除指定根目录。
    
    - 查找对应的顶级项并移除
    - 不修改配置文件（由调用方负责持久化）
    """
    for i in range(self.tree.topLevelItemCount()):
        item = self.tree.topLevelItem(i)
        if item.data(0, 42) == path:
            self.tree.takeTopLevelItem(i)
            break
```

- [ ] **Step 3: 新增右键菜单支持移除根目录**

在 `project_panel.py` 中，新增 `contextMenuEvent()` 方法：

```python
def contextMenuEvent(self, event) -> None:
    """右键菜单：只对顶级项显示"移除"选项。"""
    from PySide6.QtWidgets import QMenu
    
    item = self.tree.itemAt(event.pos())
    if item is None:
        return
    
    # 判断是否为顶级项
    if item.parent() is None:
        menu = QMenu(self)
        remove_action = menu.addAction("从工作区移除")
        remove_action.triggered.connect(lambda: self._on_remove_root(item))
        menu.exec(event.globalPos())

def _on_remove_root(self, item) -> None:
    """处理移除根目录请求。"""
    path = item.data(0, 42)
    self.remove_root(path)
    # 发出信号通知 MainWindow 更新配置
    self.root_removed.emit(path)
```

需要在类开头新增信号：
```python
root_removed = Signal(str)  # 移除的根目录路径
```

- [ ] **Step 4: 运行测试确认无回归**

```bash
cd G:/UGit/game-dev-manager && python -m pytest tests/ -v
```

预期输出：所有测试通过

- [ ] **Step 5: 提交修改**

```bash
cd G:/UGit/game-dev-manager
git add gdm/gui/project_panel.py
git commit -m "feat: 扩展 ProjectPanel 支持多根目录

- set_root() 改为 add_root()，支持追加顶级项
- 新增 remove_root() 方法移除指定根目录
- 新增右键菜单，只对顶级项显示移除选项
- 新增 root_removed 信号通知 MainWindow

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task 2: 修改 MainWindow 支持多根目录

**Files:**
- Modify: `gdm/gui/main_window.py`

- [ ] **Step 1: 修改 _open_folder()，改为调用 add_root()**

在 `main_window.py` 中，修改 `_open_folder()` 方法：

```python
@Slot()
def _open_folder(self) -> None:
    """通过 QFileDialog 选择文件夹，追加到工作区。"""
    folder = QFileDialog.getExistingDirectory(
        self, "选择工作区文件夹", ""
    )
    if not folder:
        return
    self.project_panel.add_root(folder)
    self._save_root_paths()  # 保存 root_paths 到配置

def _save_root_paths(self) -> None:
    """保存当前所有根目录到配置。"""
    root_paths = []
    for i in range(self.project_panel.tree.topLevelItemCount()):
        item = self.project_panel.tree.topLevelItem(i)
        root_paths.append(item.data(0, 42))
    
    try:
        config = load_config() or {}
        config["root_paths"] = root_paths
        save_config(config)
    except Exception as e:
        logger.warning(f"保存配置失败: {e}")
```

- [ ] **Step 2: 连接 root_removed 信号**

在 `_init_ui()` 中，连接信号：

```python
self.project_panel.root_removed.connect(self._on_root_removed)

def _on_root_removed(self, path: str) -> None:
    """处理根目录移除请求，更新配置。"""
    self._save_root_paths()
```

- [ ] **Step 3: 修改 _try_restore_project()，恢复多根目录**

在 `main_window.py` 中，修改 `_try_restore_project()` 方法：

```python
def _try_restore_project(self) -> None:
    """启动时尝试恢复上一次的工作区。"""
    config = load_config()
    if config is None:
        return
    
    root_paths = config.get("root_paths", [])
    if not root_paths:
        # 兼容旧版本：使用 last_folder
        last_folder = config.get("last_folder")
        if last_folder and os.path.isdir(last_folder):
            root_paths = [last_folder]
        else:
            return
    
    # 恢复所有根目录
    for path in root_paths:
        if os.path.isdir(path):
            self.project_panel.add_root(path)
    
    # 扫描第一个根目录
    if root_paths and os.path.isdir(root_paths[0]):
        self._on_folder_selected(root_paths[0])
```

- [ ] **Step 4: 运行测试确认无回归**

```bash
cd G:/UGit/game-dev-manager && python -m pytest tests/ -v
```

预期输出：所有测试通过

- [ ] **Step 5: 提交修改**

```bash
cd G:/UGit/game-dev-manager
git add gdm/gui/main_window.py
git commit -m "feat: 修改 MainWindow 支持多根目录

- _open_folder() 改为调用 add_root()，追加模式
- 新增 _save_root_paths() 保存根目录列表到配置
- 连接 root_removed 信号，移除时更新配置
- 修改 _try_restore_project()，恢复所有根目录

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Task 3: 更新 config.py 支持 root_paths

**Files:**
- Modify: `gdm/core/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: 更新 save_config()，支持保存 root_paths**

`save_config()` 已经接受任意字典，无需修改。确认当前实现：

```python
def save_config(config: dict) -> bool:
    """将配置字典写入全局配置文件。"""
    try:
        config_path = get_config_path()
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False
```

- [ ] **Step 2: 更新 load_config()，确保返回包含 root_paths**

`load_config()` 已经返回完整字典，无需修改。确认当前实现：

```python
def load_config() -> Optional[dict]:
    """读取全局配置文件，返回配置字典。"""
    try:
        config_path = get_config_path()
        if not os.path.exists(config_path):
            return None
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None
```

- [ ] **Step 3: 运行测试确认无回归**

```bash
cd G:/UGit/game-dev-manager && python -m pytest tests/ -v
```

预期输出：所有测试通过

- [ ] **Step 4: 提交（如有修改）**

如果 `config.py` 无需修改，跳过此步骤。

---

**计划完成检查**：
- ✅ 所有设计文档中的需求都有对应的 Task
- ✅ 无占位符或未完成部分
- ✅ 类型一致性检查：信号、方法名、参数名一致
- ✅ TDD 流程：每个 Task 包含测试步骤
