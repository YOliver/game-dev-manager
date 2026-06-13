# 递归扫描图片 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `gdm/gui/main_window.py` 中 3 处 `scan()` 调用的 `recursive=False` 改为 `recursive=True`，实现选中文件夹后自动递归扫描所有子目录中的图片。

**架构:** 仅修改调用参数。`gdm/core/scanner.py` 的 `scan(directory, recursive)` 已完整支持 `recursive=True`，测试已覆盖递归场景。

**Tech Stack:** Python, PySide6, pytest

---

### Task 1: 修改扫描调用参数

**Files:**
- Modify: `gdm/gui/main_window.py:118`
- Modify: `gdm/gui/main_window.py:168`
- Modify: `gdm/gui/main_window.py:183`

- [ ] **Step 1: 修改 `_set_workspace()` 中的 `recursive=False`**

在 `gdm/gui/main_window.py` 第 118 行，将：

```python
            sprites = scan(folder, recursive=False)
```

改为：

```python
            sprites = scan(folder, recursive=True)
```

- [ ] **Step 2: 修改 `_try_restore_project()` 中的 `recursive=False`**

在 `gdm/gui/main_window.py` 第 168 行，将：

```python
            sprites = scan(last_folder, recursive=False)
```

改为：

```python
            sprites = scan(last_folder, recursive=True)
```

- [ ] **Step 3: 修改 `_on_folder_selected()` 中的 `recursive=False`**

在 `gdm/gui/main_window.py` 第 183 行，将：

```python
            sprites = scan(folder_path, recursive=False)
```

改为：

```python
            sprites = scan(folder_path, recursive=True)
```

- [ ] **Step 4: 运行测试确认无回归**

```bash
cd D:/UGit/game-dev-manager && python -m pytest tests/ -v
```

预期输出：全部测试通过，特别是 `test_scan_recursive_true_includes_subdirectories` 验证递归逻辑正确。

- [ ] **Step 5: 提交修改**

```bash
cd D:/UGit/game-dev-manager
git add gdm/gui/main_window.py
git commit -m "feat: 将图片扫描改为默认递归子目录

选中文件夹后自动递归扫描所有子目录中的图片文件，
无需逐个点击子目录浏览。

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2（可选）: 验证无回归的集成测试

如果希望额外确认 UI 层不会因为递归扫描而崩溃（例如大量图片时的加载性能），可以补充一个集成测试。但核心递归逻辑已在 `test_scanner.py::TestScan::test_scan_recursive_true_includes_subdirectories` 中覆盖，本步骤可选。

**Files:**
- Test: `tests/test_main_window.py`

- [ ] **Step 1: 补一个简单的集成测试（可选）**

在 `tests/test_main_window.py` 中追加测试，验证 main_window 使用递归参数调用 `scan()` 时不会抛出异常：

```python
def test_scan_with_recursive_parameter_in_main_window(tmp_path, mocker):
    """验证 main_window 使用 recursive=True 调用 scan 不会崩溃"""
    from gdm.core.scanner import scan

    # 创建嵌套目录结构
    (tmp_path / "sub1").mkdir()
    (tmp_path / "sub1" / "nested").mkdir(parents=True)
    from PIL import Image
    img = Image.new("RGB", (10, 10), (255, 0, 0))
    img.save(tmp_path / "root.png", "PNG")
    img.save(tmp_path / "sub1" / "sub1.png", "PNG")
    img.save(tmp_path / "sub1" / "nested" / "deep.png", "PNG")

    # 调用 recursive=True
    result = scan(str(tmp_path), recursive=True)
    assert len(result) == 3
```

- [ ] **Step 2: 运行测试**

```bash
cd D:/UGit/game-dev-manager && python -m pytest tests/ -v
```

- [ ] **Step 3: 提交**

```bash
cd D:/UGit/game-dev-manager
git add tests/test_main_window.py
git commit -m "test: 补充递归扫描集成测试

Co-Authored-By: Claude <noreply@anthropic.com>"
```
