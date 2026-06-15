# 记住所有已打开根目录 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 添加目录时及关闭窗口前保存 root_paths，修复恢复时重复扫描和 NameError bug

**Architecture:** 在 `_set_workspace()` 中追加 `_save_root_paths()` 调用，重写 `closeEvent()` 在关闭前保存，删除 `_try_restore_project()` 末尾的冗余扫描代码和死代码方法

**Tech Stack:** Python, PySide6, pytest

---

### Task 1: 更新测试 — 验证 _set_workspace 保存 root_paths

**Files:**
- Modify: `tests/test_main_window.py:99-120`

- [ ] **Step 1: 添加 root_paths 断言**

在 `TestSetWorkspaceSavesConfig.test_set_workspace_saves_config` 第 120 行后追加断言：

```python
        # 验证 root_paths 也被保存
        assert config.get("root_paths") == [test_folder]
```

- [ ] **Step 2: 运行测试确认通过**

```bash
python -m pytest tests/test_main_window.py::TestSetWorkspaceSavesConfig -v
```

预期：PASS（当前未调用 `_save_root_paths` 所以此断言会失败 — 属 TDD 正常流程）

- [ ] **Step 3: 提交**

```bash
git add tests/test_main_window.py
git commit -m "test: 新增 _set_workspace 应保存 root_paths 的断言"
```

---

### Task 2: 添加单元测试 — 验证 _save_root_paths 行为

**Files:**
- Modify: `tests/test_main_window.py`（末尾追加）

- [ ] **Step 1: 写入新测试类**

```python
class TestSaveRootPaths:
    """测试 _save_root_paths() 的保存行为。"""

    def test_save_root_paths_to_config(
        self, main_window, tmp_path, monkeypatch
    ):
        """_save_root_paths() 应将所有根目录保存到 root_paths 配置。"""
        from gdm.core.config import load_config

        # 设置三个模拟的根目录条目
        dirs = [str(tmp_path / "root_a"), str(tmp_path / "root_b"), str(tmp_path / "root_c")]
        for d in dirs:
            os.makedirs(d, exist_ok=True)

        mock_items = []
        for d in dirs:
            item = MagicMock()
            item.data.return_value = d
            mock_items.append(item)

        main_window.project_panel.tree.topLevelItemCount.return_value = len(dirs)
        main_window.project_panel.tree.topLevelItem.side_effect = lambda i: mock_items[i]

        # 调用 _save_root_paths
        main_window._save_root_paths()

        # 验证
        config = load_config()
        assert config is not None
        assert config.get("root_paths") == dirs
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_main_window.py::TestSaveRootPaths -v
```

预期：PASS（`_save_root_paths()` 已实现，此测试验证的是现有行为）

- [ ] **Step 3: 提交**

```bash
git add tests/test_main_window.py
git commit -m "test: 新增 _save_root_paths 行为的单元测试"
```

---

### Task 3: 添加集成测试 — 验证 closeEvent 保存 root_paths

**Files:**
- Modify: `tests/test_main_window.py`（末尾追加）

- [ ] **Step 1: 写入测试**

```python
class TestCloseEventSavesRootPaths:
    """测试 closeEvent() 应保存 root_paths 到配置。"""

    def test_close_event_saves_root_paths(
        self, tmp_path, monkeypatch, mock_scan, mock_ui_components, qapp
    ):
        """关闭主窗口前应调用 _save_root_paths()。"""
        from gdm.core.config import save_config

        monkeypatch.setenv("APPDATA", str(tmp_path))

        # 先保存根目录配置
        root_a = str(tmp_path / "root_a")
        root_b = str(tmp_path / "root_b")
        os.makedirs(root_a, exist_ok=True)
        os.makedirs(root_b, exist_ok=True)
        save_config({"root_paths": [root_a, root_b]})

        with patch("gdm.gui.main_window.MainWindow._save_root_paths") as mock_save:
            from gdm.gui.main_window import MainWindow

            window = MainWindow()
            window.close()

            # 验证 closeEvent 触发了 _save_root_paths
            mock_save.assert_called_once()
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_main_window.py::TestCloseEventSavesRootPaths -v
```

预期：FAIL — 因为 `closeEvent()` 尚未重写（TDD 正常流程）

- [ ] **Step 3: 提交**

```bash
git add tests/test_main_window.py
git commit -m "test: 新增 closeEvent 应保存 root_paths 的集成测试"
```

---

### Task 4: 添加集成测试 — 验证多根目录恢复

**Files:**
- Modify: `tests/test_main_window.py`（末尾追加）

- [ ] **Step 1: 写入测试**

```python
class TestTryRestoreProjectMultipleRoots:
    """测试 _try_restore_project() 应从 root_paths 恢复多个根目录。"""

    def test_restore_multiple_roots(
        self, tmp_path, monkeypatch, mock_scan, mock_ui_components, qapp
    ):
        """_try_restore_project() 应从配置的 root_paths 恢复所有有效目录。"""
        from unittest.mock import patch
        from gdm.core.config import save_config

        monkeypatch.setenv("APPDATA", str(tmp_path))

        # 创建多个有效目录
        root_a = str(tmp_path / "root_a")
        root_b = str(tmp_path / "root_b")
        root_c = str(tmp_path / "root_c")  # 不创建此目录，模拟已删除
        os.makedirs(root_a, exist_ok=True)
        os.makedirs(root_b, exist_ok=True)

        save_config({"root_paths": [root_a, root_b, root_c]})

        from gdm.gui.main_window import MainWindow

        window = MainWindow()
        try:
            # 验证只恢复了存在的目录（root_c 被静默跳过）
            top_count = window.project_panel.tree.topLevelItemCount()
            assert top_count == 2
        finally:
            window.close()
```

- [ ] **Step 2: 运行测试确认通过**

```bash
python -m pytest tests/test_main_window.py::TestTryRestoreProjectMultipleRoots -v
```

预期：PASS（`_try_restore_project()` 已有 `os.path.isdir()` 判断正确跳过）

- [ ] **Step 3: 提交**

```bash
git add tests/test_main_window.py
git commit -m "test: 新增多根目录恢复的集成测试"
```

---

### Task 5: 实现功能 — _set_workspace + closeEvent + 修复 bug

**Files:**
- Modify: `gdm/gui/main_window.py`

- [ ] **Step 1: 在 `_set_workspace()` 中添加 `_save_root_paths()` 调用**

修改第 179 行，在 `add_root()` 后插入：

```python
    def _set_workspace(self, folder: str) -> None:
        """设置工作区根目录，后台扫描并加载精灵图。"""
        self._project = Project(root_path=folder)
        self.project_panel.add_root(folder)
        self._save_root_paths()  # 新增

        # 显示进度界面
        self.thumbnail_view.show_progress()

        # 启动后台扫描
        self._start_scan(folder, on_finished=self._on_workspace_scan_finished)
```

- [ ] **Step 2: 重写 `closeEvent()`**

在类末尾添加（`_on_root_removed` 方法之后）：

```python
    def closeEvent(self, event) -> None:
        """关闭窗口前保存根目录列表到配置。"""
        self._save_root_paths()
        super().closeEvent(event)
```

- [ ] **Step 3: 删除第 242-245 行冗余扫描代码**

删除 `_try_restore_project()` 中的：

```python
        # 显示进度界面
        self.thumbnail_view.show_progress()

        # 启动后台扫描
        self._start_scan(last_folder, on_finished=self._on_restore_scan_finished)
```

保留第 238-239 行的 `_on_folder_selected` 调用即可。

- [ ] **Step 4: 删除 `_on_restore_scan_finished()` 方法**

删除第 247-250 行的整个方法：

```python
    def _on_restore_scan_finished(self, sprites) -> None:
        """_try_restore_project 扫描完成回调（不保存配置）。"""
        self._current_sprites = sprites
        self.thumbnail_view.load(sprites)
```

- [ ] **Step 5: 运行全部测试**

```bash
python -m pytest tests/test_main_window.py -v
```

预期：全部 PASS

- [ ] **Step 6: 提交**

```bash
git add gdm/gui/main_window.py
git commit -m "fix: 添加目录时和关闭前保存 root_paths，修复恢复时重复扫描 bug"
```

---

### Task 6: 运行全量测试并提交

**Files:**
- 无新建/修改

- [ ] **Step 1: 运行全量测试**

```bash
python -m pytest tests/ -v
```

预期：全部 PASS

- [ ] **Step 2: 最终提交**

```bash
git add -A
git status
```

确保没有未提交的文件。如无其他变更则无需提交。

---

## 任务依赖顺序

```
Task 1 (test) → Task 2 (test) → Task 3 (test) → Task 4 (test) → Task 5 (impl) → Task 6 (full)
```

## 预期提交记录

```
test: 新增 _set_workspace 应保存 root_paths 的断言
test: 新增 _save_root_paths 行为的单元测试
test: 新增 closeEvent 应保存 root_paths 的集成测试
test: 新增多根目录恢复的集成测试
fix: 添加目录时和关闭前保存 root_paths，修复恢复时重复扫描 bug
```
