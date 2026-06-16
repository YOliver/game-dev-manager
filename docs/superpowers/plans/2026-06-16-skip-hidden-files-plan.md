# Skip Hidden Files Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 扫描文件时跳过所有文件名以 `.` 开头的隐藏文件（如 macOS AppleDouble 文件 `._Example Scene.png`），同时保留隐藏目录的遍历以保证不漏文件。

**Architecture:** 在 `gdm/utils/helpers.py` 中新增 `is_hidden()` 辅助函数，在 `gdm/core/scanner.py` 和 `gdm/core/cache/scanner_cached.py` 的图片文件过滤条件中调用。

**Tech Stack:** Python 3.10+, Pillow, pytest

---

### Task 1: 新增 `is_hidden()` 工具函数

**Files:**
- Modify: `gdm/utils/helpers.py` (末尾新增函数)
- Test: `tests/test_helpers.py` (新建)

- [ ] **Step 1: 在 `gdm/utils/helpers.py` 末尾添加 `is_hidden()`**

```python
from pathlib import Path


def is_hidden(file_path: Path) -> bool:
    """判断文件是否为隐藏文件（文件名以 . 开头）。

    Args:
        file_path: 文件路径。

    Returns:
        文件名以 . 开头返回 True，否则 False。
    """
    return file_path.name.startswith(".")
```

需将文件开头的 `from pathlib import Path` 从无到有添加上去（当前文件无 import）。

- [ ] **Step 2: 新建 `tests/test_helpers.py`，编写测试**

```python
"""测试 gdm.utils.helpers 工具函数。"""

from pathlib import Path
import pytest
from gdm.utils.helpers import is_hidden


class TestIsHidden:
    def test_hidden_file_with_dot_prefix(self):
        """文件名以 . 开头应返回 True。"""
        assert is_hidden(Path("._Example.png")) is True
        assert is_hidden(Path(".hidden.jpg")) is True

    def test_normal_file_returns_false(self):
        """普通文件名应返回 False。"""
        assert is_hidden(Path("sprite.png")) is False
        assert is_hidden(Path("photo.jpg")) is False

    def test_hidden_file_in_subdirectory(self):
        """子目录中的隐藏文件也应识别。"""
        p = Path("assets/sprites/._hidden.png")
        assert is_hidden(p) is True

    def test_normal_file_in_subdirectory(self):
        """子目录中的普通文件应返回 False。"""
        p = Path("assets/sprites/normal.png")
        assert is_hidden(p) is False

    def test_hidden_directory_is_not_hidden_file(self):
        """目录名以 . 开头应返回 False（传入的是目录路径时）。"""
        p = Path(".__MACOSX/normal.png")
        # 注意：这里传入的是目录路径下的文件，文件名是 normal.png，应返回 False
        assert is_hidden(p) is False
        # 但如果直接传入目录路径，name 就是目录名
        assert is_hidden(Path(".__MACOSX")) is True
```

- [ ] **Step 3: 运行测试，验证通过**

Run: `cd G:/UGit/game-dev-manager && python -m pytest tests/test_helpers.py -v`
Expected: 5 passed

- [ ] **Step 4: Commit**

```bash
git add gdm/utils/helpers.py tests/test_helpers.py
git commit -m "feat(helpers): add is_hidden() utility to detect .-prefixed files"
```

---

### Task 2: `scanner.py` 过滤隐藏文件

**Files:**
- Modify: `gdm/core/scanner.py` (两处过滤条件)
- Modify: `tests/test_scanner.py` (新增测试)

- [ ] **Step 1: 编写失败的测试（验证隐藏文件被跳过）**

在 `tests/test_scanner.py` 中 `TestScan` 类添加两个新方法：

```python
    def test_scan_hidden_files_skipped(self, tmp_path):
        """测试扫描时跳过文件名以 . 开头的隐藏文件。"""
        img = Image.new("RGBA", (32, 32), (255, 0, 0, 255))
        img.save(tmp_path / "normal.png", "PNG")
        # 创建隐藏文件（模拟 macOS AppleDouble 文件）
        (tmp_path / "._hidden.png").write_bytes(b"fake png content")
        (tmp_path / ".DS_Store").write_bytes(b"fake ds store")

        result = scan(str(tmp_path), recursive=False)

        # 只应返回 normal.png
        assert len(result) == 1
        assert result[0].file_name == "normal.png"

    def test_scan_hidden_directory_files_still_scanned(self, tmp_path):
        """测试隐藏在隐藏目录中的普通文件仍被扫描。"""
        # 创建隐藏目录
        hidden_dir = tmp_path / ".__MACOSX"
        hidden_dir.mkdir()
        # 隐藏目录中的普通文件仍应被扫描
        img = Image.new("RGBA", (16, 16), (0, 255, 0, 255))
        img.save(hidden_dir / "real_texture.png", "PNG")
        # 隐藏目录中的隐藏文件应被跳过
        (hidden_dir / "._real_texture.png").write_bytes(b"fake")

        result = scan(str(tmp_path), recursive=True)

        assert len(result) == 1
        assert result[0].file_name == "real_texture.png"
```

- [ ] **Step 2: 运行测试，验证失败**

Run: `cd G:/UGit/game-dev-manager && python -m pytest tests/test_scanner.py::TestScan::test_scan_hidden_files_skipped tests/test_scanner.py::TestScan::test_scan_hidden_directory_files_still_scanned -v`
Expected: 2 FAILED (图片未被过滤，返回多余条目)

- [ ] **Step 3: 实现隐藏文件过滤**

在 `gdm/core/scanner.py` 中：

a) 添加导入（文件顶部）：

```python
from gdm.utils.helpers import is_hidden
```

b) 修改 `scan()` 第 35 行：

```python
# 修改前
if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_EXTENSIONS:

# 修改后
if (file_path.is_file()
    and file_path.suffix.lower() in SUPPORTED_EXTENSIONS
    and not is_hidden(file_path)):
```

c) 修改 `scan_with_progress()` 第 65 行（同上的过滤条件）：

```python
# 修改前
if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_EXTENSIONS:

# 修改后
if (file_path.is_file()
    and file_path.suffix.lower() in SUPPORTED_EXTENSIONS
    and not is_hidden(file_path)):
```

scan_with_progress() 中也是同样的 glob 循环，这两处在同一个函数内。

- [ ] **Step 4: 运行测试，验证通过**

Run: `cd G:/UGit/game-dev-manager && python -m pytest tests/test_scanner.py -v`
Expected: 10 passed (原有 8 个 + 新增 2 个)

- [ ] **Step 5: Commit**

```bash
git add gdm/core/scanner.py tests/test_scanner.py
git commit -m "feat(scanner): skip hidden files (.prefixed) in scan and scan_with_progress"
```

---

### Task 3: `scanner_cached.py` 过滤隐藏文件

**Files:**
- Modify: `gdm/core/cache/scanner_cached.py` (snapshot_folder 内一处过滤)
- Modify: `tests/cache/test_scanner_cached.py` (新增测试)

- [ ] **Step 1: 编写失败的测试**

在 `tests/cache/test_scanner_cached.py` 中 `TestSnapshotFolder` 类添加：

```python
    def test_skips_hidden_files(self, tmp_path):
        """测试 snapshot_folder 跳过文件名以 . 开头的文件。"""
        _make_png(tmp_path / "normal.png")
        (tmp_path / "._apple_double.png").write_bytes(b"fake png")
        (tmp_path / ".hidden.png").write_bytes(b"fake png")
        snaps = snapshot_folder(str(tmp_path))
        assert [s.file_name for s in snaps] == ["normal.png"]

    def test_does_not_skip_hidden_dirs(self, tmp_path):
        """测试隐藏目录内的普通文件仍被扫描。"""
        hidden_dir = tmp_path / ".__MACOSX"
        hidden_dir.mkdir()
        _make_png(hidden_dir / "real_texture.png")
        (hidden_dir / "._real_texture.png").write_bytes(b"fake png")
        snaps = snapshot_folder(str(tmp_path))
        assert [s.file_name for s in snaps] == ["real_texture.png"]
```

- [ ] **Step 2: 运行测试，验证失败**

Run: `cd G:/UGit/game-dev-manager && python -m pytest tests/cache/test_scanner_cached.py::TestSnapshotFolder::test_skips_hidden_files tests/cache/test_scanner_cached.py::TestSnapshotFolder::test_does_not_skip_hidden_dirs -v`
Expected: 2 FAILED

- [ ] **Step 3: 实现隐藏文件过滤**

修改 `gdm/core/cache/scanner_cached.py` 中 `snapshot_folder()` 的循环体。

原代码第 55-66 行：

```python
    for sub_dir, _dirs, files in os.walk(root):
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue
            full = os.path.join(sub_dir, fname)
```

改为：

```python
    for sub_dir, _dirs, files in os.walk(root):
        for fname in files:
            if fname.startswith("."):
                continue
            ext = os.path.splitext(fname)[1].lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue
            full = os.path.join(sub_dir, fname)
```

> 注意：`_dirs` 不改动（保留原始变量名 `_dirs`），隐藏目录仍然遍历。

- [ ] **Step 4: 运行测试，验证通过**

Run: `cd G:/UGit/game-dev-manager && python -m pytest tests/cache/test_scanner_cached.py -v`
Expected: 16 passed (原有 14 个 + 新增 2 个)

- [ ] **Step 5: Commit**

```bash
git add gdm/core/cache/scanner_cached.py tests/cache/test_scanner_cached.py
git commit -m "feat(cache): skip hidden files in snapshot_folder, keep hidden dirs traversal"
```

---

### Self-Review Checklist

- [ ] **Spec coverage:** 设计文档要求全部覆盖 —— `is_hidden()` 函数（Task 1）、`scanner.py` 过滤（Task 2）、`scanner_cached.py` 过滤（Task 3）、隐藏目录不跳过（Task 2 & 3）
- [ ] **Placeholder scan:** 无 TBD/TODO/placeholder
- [ ] **Type consistency:** `is_hidden(Path)` 签名一致，两处调用点类型兼容（scanner.py 用 `Path`，scanner_cached.py 用 `str.startswith`）

---
