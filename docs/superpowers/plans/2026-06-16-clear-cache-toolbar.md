# 清空缓存移到工具栏 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将"清空缩略图缓存"从"工具"菜单下拉框移动到工具栏，并删除冗余的 `addAction()` 调用，使工具菜单下拉框为空（与文件、帮助菜单行为一致）。

**Architecture:** 两处代码改动 + 两处测试改动，均在已有文件内完成。不创建新文件。

**Tech Stack:** Python 3, PySide6, pytest

**Spec:** `docs/superpowers/specs/2026-06-16-clear-cache-toolbar-design.md`

---

### Task 1: 修改测试 — expected_texts 新增"清空缩略图缓存"

**Files:**
- Modify: `tests/test_main_window.py:320`

- [ ] **Step 1: 修改 `test_toolbar_updates_on_menu_about_to_show` 的预期文本**

将 `TestToolbarUpdate.test_toolbar_updates_on_menu_about_to_show` (line 320) 的 `expected_texts` 增加"清空缩略图缓存"：

```python
expected_texts = ["批量重命名", "全量解压", "清空缩略图缓存"]
```

- [ ] **Step 2: 运行该测试验证失败（预期：因实现未修改，toolbar 只有 2 项）**

```bash
cd g:/UGit/game-dev-manager && python -m pytest tests/test_main_window.py::TestToolbarUpdate::test_toolbar_updates_on_menu_about_to_show -v
```

Expected: FAIL — `assert actual_texts == expected_texts`，因为 `_toolbar_actions` 还没加 `clear_cache_act`。

- [ ] **Step 3: 提交**

```bash
git add tests/test_main_window.py
git commit -m "test: add clear cache to toolbar expected_texts"
```

---

### Task 2: 新增回归测试 — 工具菜单 actions() 为空

**Files:**
- Modify: `tests/test_main_window.py` (在 `TestToolbarUpdate` 类末尾添加新方法)

- [ ] **Step 1: 在 `TestToolbarUpdate` 类中新增测试方法**

在 `test_toolbar_ignores_separators` 方法之后（`TestExtractAllMenu` 类之前）添加：

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

- [ ] **Step 2: 运行该测试验证失败（预期：当前工具菜单有 3 个子 Action）**

```bash
cd g:/UGit/game-dev-manager && python -m pytest tests/test_main_window.py::TestToolbarUpdate::test_tool_menu_has_no_children -v
```

Expected: FAIL — `assert len(tool_menu.actions()) == 0`，因为当前 `addAction()` 添加了 3 个 Action。

- [ ] **Step 3: 提交**

```bash
git add tests/test_main_window.py
git commit -m "test: add regression test for empty tool menu"
```

---

### Task 3: 删除 `tool_menu.addAction()` 调用

**Files:**
- Modify: `gdm/gui/main_window.py:134-136`

- [ ] **Step 1: 删除三行 `addAction()`**

删除 `_init_menubar()` 方法中的工具菜单子 Action 注册（lines 134-136）：

```python
tool_menu.addAction(rename_action)
tool_menu.addAction(extract_action)
tool_menu.addAction(clear_cache_act)
```

保留 `aboutToShow` 信号连接（line 138）：

```python
tool_menu.aboutToShow.connect(lambda: self._update_toolbar("工具"))
```

- [ ] **Step 2: 运行回归测试确认通过**

```bash
cd g:/UGit/game-dev-manager && python -m pytest tests/test_main_window.py::TestToolbarUpdate::test_tool_menu_has_no_children -v
```

Expected: PASS — 工具菜单的 `actions()` 为空。

- [ ] **Step 3: 提交**

```bash
git add gdm/gui/main_window.py
git commit -m "refactor: remove tool menu dropdown actions"
```

---

### Task 4: 将 `clear_cache_act` 加入工具栏字典

**Files:**
- Modify: `gdm/gui/main_window.py:157`

- [ ] **Step 1: 在 `_toolbar_actions["工具"]` 添加 `clear_cache_act`**

```python
# 原来
"工具": [rename_action, extract_action],
# 改为
"工具": [rename_action, extract_action, clear_cache_act],
```

- [ ] **Step 2: 运行测试确认通过**

```bash
cd g:/UGit/game-dev-manager && python -m pytest tests/test_main_window.py::TestToolbarUpdate::test_toolbar_updates_on_menu_about_to_show -v
```

Expected: PASS — toolbar 显示三项：批量重命名、全量解压、清空缩略图缓存。

- [ ] **Step 3: 提交**

```bash
git add gdm/gui/main_window.py
git commit -m "feat: add clear cache button to toolbar"
```

---

### Task 5: 运行全量测试并最终提交

**Files:** (无修改，仅验证)

- [ ] **Step 1: 运行 `test_main_window.py` 全部测试**

```bash
cd g:/UGit/game-dev-manager && python -m pytest tests/test_main_window.py -v
```

Expected: 全部 PASS。

- [ ] **Step 2: 运行全量测试套件**

```bash
cd g:/UGit/game-dev-manager && python -m pytest tests/ -v
```

Expected: 全部 PASS，无回归。

- [ ] **Step 3: （可选）手动验证**

启动应用，验证"工具"菜单点击时不弹出下拉框，工具栏显示三项按钮，点击"清空缩略图缓存"功能正常。

```bash
cd g:/UGit/game-dev-manager && python gdm
```
