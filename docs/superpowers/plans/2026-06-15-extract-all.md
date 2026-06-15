# 全量解压 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在"工具"菜单添加"全量解压"功能，递归解压选中目录下所有压缩包并删除原始文件

**Architecture:** 新增 `gdm/core/extractor.py` 作为纯逻辑模块，MainWindow 负责获取选中目录、确认对话框和调用入口

**Tech Stack:** Python stdlib (zipfile, tarfile, gzip, bz2, lzma), PySide6, pytest

---

### Task 1: 编写 extractor.py 的 TDD 测试

**Files:**
- Create: `tests/test_extractor.py`

- [ ] **Step 1: 写入测试文件**

```python
"""测试 extractor.py 的解压逻辑。"""

import os
import zipfile
import tarfile
import gzip
import bz2
import lzma
from pathlib import Path

import pytest

from gdm.core.extractor import (
    SUPPORTED_ARCHIVE_EXTENSIONS,
    find_archives,
    extract_archive,
    extract_all,
)


class TestSupportedExtensions:
    """测试支持的压缩包扩展名。"""

    def test_includes_common_formats(self):
        assert ".zip" in SUPPORTED_ARCHIVE_EXTENSIONS
        assert ".tar" in SUPPORTED_ARCHIVE_EXTENSIONS
        assert ".gz" in SUPPORTED_ARCHIVE_EXTENSIONS
        assert ".bz2" in SUPPORTED_ARCHIVE_EXTENSIONS
        assert ".xz" in SUPPORTED_ARCHIVE_EXTENSIONS
        assert ".tgz" in SUPPORTED_ARCHIVE_EXTENSIONS


class TestFindArchives:
    """测试 find_archives() 递归搜索压缩包。"""

    def test_finds_archives_recursively(self, tmp_path):
        d = Path(tmp_path)
        sub = d / "sub"
        sub.mkdir()
        (d / "a.zip").touch()
        (d / "b.tar").touch()
        (sub / "c.gz").touch()
        (d / "readme.txt").touch()  # 非压缩包

        result = find_archives(str(d))

        assert len(result) == 3
        assert str(d / "a.zip") in result
        assert str(d / "b.tar") in result
        assert str(sub / "c.gz") in result

    def test_empty_directory_returns_empty(self, tmp_path):
        result = find_archives(str(tmp_path))
        assert result == []

    def test_skips_unsupported_extensions(self, tmp_path):
        d = Path(tmp_path)
        (d / "readme.txt").touch()
        (d / "image.png").touch()

        result = find_archives(str(d))
        assert result == []


class TestExtractArchive:
    """测试 extract_archive() 单压缩包解压。"""

    def test_extract_zip(self, tmp_path):
        archive = tmp_path / "test.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("hello.txt", "hello world")

        result = extract_archive(str(archive))

        assert os.path.isdir(result)
        assert os.path.isfile(os.path.join(result, "hello.txt"))
        assert not os.path.exists(archive)  # 原始压缩包已删除

    def test_extract_tar(self, tmp_path):
        archive = tmp_path / "test.tar"
        with tarfile.open(archive, "w") as tf:
            info = tarfile.TarInfo("hello.txt")
            info.size = 11
            tf.addfile(info, io.BytesIO(b"hello world"))

        result = extract_archive(str(archive))

        assert os.path.isdir(result)
        assert os.path.isfile(os.path.join(result, "hello.txt"))
        assert not os.path.exists(archive)

    def test_extract_gz_single_file(self, tmp_path):
        archive = tmp_path / "data.gz"
        with gzip.open(archive, "wb") as f:
            f.write(b"hello world")

        result = extract_archive(str(archive))

        assert os.path.isdir(result)
        assert os.path.isfile(os.path.join(result, "data"))
        assert not os.path.exists(archive)

    def test_extract_bz2_single_file(self, tmp_path):
        archive = tmp_path / "data.bz2"
        with bz2.open(archive, "wb") as f:
            f.write(b"hello world")

        result = extract_archive(str(archive))

        assert os.path.isdir(result)
        assert not os.path.exists(archive)

    def test_extract_tar_gz(self, tmp_path):
        archive = tmp_path / "test.tar.gz"
        tgz_path = tmp_path / "test.tgz"
        import shutil

        with tarfile.open(archive, "w:gz") as tf:
            info = tarfile.TarInfo("hello.txt")
            s = io.BytesIO(b"hello world")
            info.size = 11
            tf.addfile(info, s)

        shutil.copyfile(archive, tgz_path)

        result = extract_archive(str(tgz_path))
        assert os.path.isdir(result)
        assert not os.path.exists(tgz_path)

    def test_duplicate_name_adds_copy_suffix(self, tmp_path):
        archive = tmp_path / "test.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("hello.txt", "hello")

        existing_dir = tmp_path / "test"
        existing_dir.mkdir()

        result = extract_archive(str(archive))

        assert result.endswith("副本")
        assert os.path.isdir(result)

    def test_unsupported_format_raises(self, tmp_path):
        archive = tmp_path / "test.unknown"
        archive.touch()

        with pytest.raises(ValueError):
            extract_archive(str(archive))


class TestExtractAll:
    """测试 extract_all() 递归解压全部。"""

    def test_extract_all_basic(self, tmp_path):
        d = Path(tmp_path)
        (d / "a.zip").touch()
        with zipfile.ZipFile(d / "a.zip", "w") as zf:
            zf.writestr("a.txt", "a")

        (d / "b.zip").touch()
        with zipfile.ZipFile(d / "b.zip", "w") as zf:
            zf.writestr("b.txt", "b")

        success, fail, failed_list = extract_all(str(d))

        assert success == 2
        assert fail == 0
        assert failed_list == []
        assert not os.path.exists(d / "a.zip")
        assert not os.path.exists(d / "b.zip")

    def test_extract_all_nested(self, tmp_path):
        d = Path(tmp_path)
        outer = d / "outer.zip"
        with zipfile.ZipFile(outer, "w") as zf:
            inner = d / "inner.zip"
            with zipfile.ZipFile(inner, "w") as if_zf:
                if_zf.writestr("data.txt", "data")
            zf.write(inner, "inner.zip")
        os.remove(inner)

        success, fail, _ = extract_all(str(d))

        assert success == 2  # outer + inner
        assert fail == 0

    def test_extract_all_no_archives(self, tmp_path):
        success, fail, _ = extract_all(str(tmp_path))
        assert success == 0
        assert fail == 0
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_extractor.py -v
```

预期：全部 FAIL（模块尚未创建，TDD 正常流程）

- [ ] **Step 3: 提交**

```bash
git add tests/test_extractor.py
git commit -m "test: 新增 extractor.py 的 TDD 测试"
```

---

### Task 2: 实现 extractor.py

**Files:**
- Create: `gdm/core/extractor.py`

- [ ] **Step 1: 写入实现代码**

```python
"""压缩包解压模块。

支持 zip, tar, gz, bz2, xz 格式的递归解压。
"""

import gzip
import bz2
import io
import lzma
import logging
import os
import shutil
import tarfile
import zipfile
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)

SUPPORTED_ARCHIVE_EXTENSIONS = {".zip", ".tar", ".gz", ".bz2", ".xz", ".tgz"}


def find_archives(directory: str) -> List[str]:
    """递归搜索目录下的所有压缩包，按文件名排序返回路径列表。"""
    archives = []
    for root, dirs, files in os.walk(directory):
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if fname.lower().endswith(".tar.gz"):
                ext = ".tar.gz"
            elif fname.lower().endswith(".tar.bz2"):
                ext = ".tar.bz2"
            elif fname.lower().endswith(".tar.xz"):
                ext = ".tar.xz"
            if ext in SUPPORTED_ARCHIVE_EXTENSIONS or fname.lower().endswith(".tgz"):
                archives.append(os.path.join(root, fname))
    return sorted(archives)


def _get_output_dir(archive_path: str) -> str:
    """根据压缩包路径生成输出目录名，重名时添加"副本"后缀。"""
    name = os.path.splitext(os.path.basename(archive_path))[0]
    # 处理 .tar.gz / .tar.bz2 / .tar.xz 双扩展名
    if name.endswith(".tar"):
        name = name[:-4]

    parent = os.path.dirname(archive_path)
    out_dir = os.path.join(parent, name)

    if not os.path.exists(out_dir):
        return out_dir

    # 重名处理
    counter = 1
    while os.path.exists(os.path.join(parent, f"{name} 副本{counter}" if counter > 1 else f"{name} 副本")):
        counter += 1

    if counter == 1:
        return os.path.join(parent, f"{name} 副本")
    return os.path.join(parent, f"{name} 副本{counter}")


def extract_archive(archive_path: str) -> str:
    """解压单个压缩包到同级目录，返回解压后的目录路径。

    解压完成后删除原始压缩包。
    """
    out_dir = _get_output_dir(archive_path)
    os.makedirs(out_dir, exist_ok=True)
    fname = os.path.basename(archive_path).lower()

    try:
        if fname.endswith(".zip"):
            with zipfile.ZipFile(archive_path, "r") as zf:
                zf.extractall(out_dir)
        elif fname.endswith((".tar.gz", ".tgz")) or (fname.endswith(".tar.gz")):
            with tarfile.open(archive_path, "r:gz") as tf:
                tf.extractall(out_dir)
        elif fname.endswith(".tar.bz2"):
            with tarfile.open(archive_path, "r:bz2") as tf:
                tf.extractall(out_dir)
        elif fname.endswith(".tar.xz"):
            with tarfile.open(archive_path, "r:xz") as tf:
                tf.extractall(out_dir)
        elif fname.endswith(".tar"):
            with tarfile.open(archive_path, "r") as tf:
                tf.extractall(out_dir)
        elif fname.endswith(".gz"):
            basename = os.path.splitext(os.path.basename(archive_path))[0]
            out_file = os.path.join(out_dir, basename)
            with gzip.open(archive_path, "rb") as f_in:
                with open(out_file, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
        elif fname.endswith(".bz2"):
            basename = os.path.splitext(os.path.basename(archive_path))[0]
            out_file = os.path.join(out_dir, basename)
            with bz2.open(archive_path, "rb") as f_in:
                with open(out_file, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
        elif fname.endswith(".xz"):
            basename = os.path.splitext(os.path.basename(archive_path))[0]
            out_file = os.path.join(out_dir, basename)
            with lzma.open(archive_path, "rb") as f_in:
                with open(out_file, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
        else:
            os.rmdir(out_dir)
            raise ValueError(f"不支持的压缩包格式: {archive_path}")

        os.remove(archive_path)
        return out_dir

    except Exception:
        # 清理可能创建的空目录
        if os.path.isdir(out_dir) and not os.listdir(out_dir):
            os.rmdir(out_dir)
        raise


def extract_all(directory: str) -> Tuple[int, int, List[str]]:
    """递归解压目录下所有压缩包（含嵌套）。

    返回 (成功数, 失败数, 失败文件路径列表)。
    """
    success_count = 0
    fail_count = 0
    failed_paths: List[str] = []

    while True:
        archives = find_archives(directory)
        if not archives:
            break

        new_archives_found = False
        for archive_path in archives:
            try:
                extract_archive(archive_path)
                success_count += 1
                new_archives_found = True
            except Exception as e:
                logger.warning(f"解压失败: {archive_path}, 错误: {e}")
                fail_count += 1
                failed_paths.append(archive_path)

        if not new_archives_found:
            break

    return success_count, fail_count, failed_paths
```

- [ ] **Step 2: 运行测试确认通过**

```bash
python -m pytest tests/test_extractor.py -v
```

预期：全部 PASS（需确认后修正细节）

- [ ] **Step 3: 提交**

```bash
git add gdm/core/extractor.py
git commit -m "feat: 新增压缩包解压模块 extractor.py"
```

---

### Task 3: 编写 main_window.py 的 TDD 测试

**Files:**
- Modify: `tests/test_main_window.py`（末尾追加）

- [ ] **Step 1: 写入测试**

```python
class TestSelectedFolder:
    """测试 _selected_folder 追踪选中的目录。"""

    def test_selected_folder_initialized(self, main_window):
        """_selected_folder 应初始化为 None。"""
        assert main_window._selected_folder is None

    def test_selected_folder_updated_on_folder_select(self, main_window, tmp_path):
        """_on_folder_selected 应更新 _selected_folder。"""
        test_dir = str(tmp_path / "test_dir")
        os.makedirs(test_dir, exist_ok=True)

        main_window._on_folder_selected(test_dir)

        assert main_window._selected_folder == test_dir


class TestExtractAllMenu:
    """测试全量解压菜单项。"""

    def test_extract_action_exists(self, main_window):
        """全量解压 Action 应存在于 _toolbar_actions 工具列表中。"""
        tool_actions = main_window._toolbar_actions.get("工具", [])
        texts = [a.text() for a in tool_actions]
        assert "全量解压" in texts
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_main_window.py::TestSelectedFolder tests/test_main_window.py::TestExtractAllMenu -v
```

预期：FAIL（TDD 正常流程）

- [ ] **Step 3: 提交**

```bash
git add tests/test_main_window.py
git commit -m "test: 新增 _selected_folder 和全量解压菜单的 TDD 测试"
```

---

### Task 4: 实现 main_window.py 的改动

**Files:**
- Modify: `gdm/gui/main_window.py`

- [ ] **Step 1: 添加 `_selected_folder` 初始化**

在 `__init__()` 第 44 行后添加：

```python
        self._selected_folder: Optional[str] = None
```

- [ ] **Step 2: 在 `_on_folder_selected()` 中追踪选中目录**

修改第 270 行：

```python
    def _on_folder_selected(self, folder_path: str) -> None:
        """左侧面板选中文件夹回调，后台扫描并加载精灵图。"""
        self._selected_folder = folder_path
        self.thumbnail_view.show_progress()
        self._start_scan(folder_path, on_finished=self._on_tree_scan_finished)
```

- [ ] **Step 3: 添加全量解压 Action 到菜单和工具栏**

在 `_init_menubar()` 中的工具菜单区域，`rename_action` 之后添加：

```python
        extract_action = QAction("全量解压", self)
        extract_action.triggered.connect(self._open_extract_all)
```

修改 `_toolbar_actions` 字典中的"工具"列表：

```python
        self._toolbar_actions = {
            "文件": [open_action, save_action, exit_action],
            "工具": [rename_action, extract_action],
            "帮助": [manual_action, welcome_action, about_action],
        }
```

- [ ] **Step 4: 添加 `_open_extract_all()` 方法**

在 MainWindow 类末尾添加：

```python
    def _open_extract_all(self) -> None:
        """打开全量解压功能。"""
        from gdm.core.extractor import find_archives, extract_all

        directory = self._selected_folder or (self._project.root_path if self._project else None)
        if directory is None:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "全量解压", "请先在项目面板中选择一个目录")
            return

        archives = find_archives(directory)
        if not archives:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "全量解压", "未发现压缩包")
            return

        total_size = sum(os.path.getsize(p) for p in archives)
        size_mb = total_size / (1024 * 1024)

        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            "全量解压",
            f"共发现 {len(archives)} 个压缩包，总大小 {size_mb:.1f} MB\n"
            f"解压后原始压缩包将被删除",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        success, fail, failed_list = extract_all(directory)

        msg = f"解压完成：成功 {success} 个，失败 {fail} 个"
        if failed_list:
            msg += "\n\n失败文件：\n" + "\n".join(failed_list[:10])
            if len(failed_list) > 10:
                msg += f"\n... 共 {len(failed_list)} 个"

        QMessageBox.information(self, "全量解压", msg)

        # 刷新视图
        self._on_folder_selected(directory)
```

- [ ] **Step 5: 运行测试确认通过**

```bash
python -m pytest tests/test_main_window.py::TestSelectedFolder tests/test_main_window.py::TestExtractAllMenu -v
```

预期：PASS

- [ ] **Step 6: 提交**

```bash
git add gdm/gui/main_window.py
git commit -m "feat: 在工具菜单添加全量解压功能"
```

---

### Task 5: 运行全量测试

**Files:**
- 无新建/修改

- [ ] **Step 1: 运行全量测试**

```bash
python -m pytest tests/ -v
```

预期：全部 PASS

- [ ] **Step 2: 确认无未提交文件**

```bash
git status
```

---

## 任务依赖顺序

```
Task 1 (test extractor) → Task 2 (impl extractor) → Task 3 (test main_window) → Task 4 (impl main_window) → Task 5 (full test)
```

## 预期提交记录

```
test: 新增 extractor.py 的 TDD 测试
feat: 新增压缩包解压模块 extractor.py
test: 新增 _selected_folder 和全量解压菜单的 TDD 测试
feat: 在工具菜单添加全量解压功能
```
