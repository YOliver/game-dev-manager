# RAR 格式检测与提示 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在全量解压中检测 `.rar` 文件，不解压，结束后提示用户手动处理。

**Architecture:** 在 `extractor.py` 中扩展 `SUPPORTED_ARCHIVE_EXTENSIONS` 加入 `.rar`，`extract_all()` 循环中用 set 分离收集 RAR 文件并跳过解压，返回值新增第 4 个元素（RAR 文件列表）。`main_window.py` 调用侧适配 4 返回值并在结果对话框追加 RAR 提示。

**Tech Stack:** Python stdlib (os, set, sorted)

---

### Task 1: 扩展 extractor.py 支持 RAR 检测

**Files:**
- Modify: `gdm/core/extractor.py`

- [ ] **Step 1: 更新文件头注释**

将第 3 行 `支持 zip, tar, gz, bz2, xz` 改为 `支持 zip, tar, gz, bz2, xz, rar（仅检测）`：

```python
"""压缩包解压模块。

支持 zip, tar, gz, bz2, xz, rar（仅检测）格式的递归解压。
"""
```

- [ ] **Step 2: 在 `SUPPORTED_ARCHIVE_EXTENSIONS` 中加入 `.rar`**

```python
SUPPORTED_ARCHIVE_EXTENSIONS = {".zip", ".tar", ".gz", ".bz2", ".xz", ".tgz", ".rar"}
```

- [ ] **Step 3: 修改 `extract_all()` 签名和返回值**

修改函数签名，返回值从 3 元组改为 4 元组：

```python
def extract_all(
    directory: str,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> Tuple[int, int, List[str], List[str]]:
    """递归解压目录下所有压缩包（含嵌套）。

    返回 (成功数, 失败数, 失败文件路径列表, rar 文件路径列表)。
    """
```

- [ ] **Step 4: 在 `extract_all()` 循环中分离 RAR 文件**

将循环体改为先分离 RAR 再处理。原代码：

```python
    success_count = 0
    fail_count = 0
    failed_paths: List[str] = []

    while True:
        archives = find_archives(directory)
        if not archives:
            break

        total_count = len(archives)
        any_success = False
        for archive_path in archives:
```

改为：

```python
    success_count = 0
    fail_count = 0
    failed_paths: List[str] = []
    all_rar_files: set[str] = set()

    while True:
        archives = find_archives(directory)
        if not archives:
            break

        # 分离 RAR 文件（用 set 避免跨轮重复）
        rar_files = [a for a in archives if a.lower().endswith(".rar")]
        others = [a for a in archives if not a.lower().endswith(".rar")]
        all_rar_files.update(rar_files)

        if not others:
            break

        total_count = len(others)
        any_success = False
        for archive_path in others:
```

- [ ] **Step 5: 修改 `extract_all()` 的 return 语句**

将末行 `return success_count, fail_count, failed_paths` 改为：

```python
    return success_count, fail_count, failed_paths, sorted(all_rar_files)
```

- [ ] **Step 6: 提交**

```bash
git add gdm/core/extractor.py
git commit -m "feat: 全量解压支持 RAR 格式检测（仅检测，不解压）"
```

---

### Task 2: 更新 main_window.py 结果展示

**Files:**
- Modify: `gdm/gui/main_window.py`

- [ ] **Step 1: 适配 4 元组返回值**

将行 481 的调用：

```python
        success, fail, failed_list = extract_all(directory, progress_callback=update_progress)
```

改为：

```python
        success, fail, failed_list, rar_list = extract_all(directory, progress_callback=update_progress)
```

- [ ] **Step 2: 在结果对话框中追加 RAR 提示**

在行 489 的 `if failed_list:` 块之后、`QMessageBox.information` 之前，增加 RAR 提示：

```python
        if rar_list:
            msg += "\n\n⚠ 以下 RAR 文件无法自动解压，请手动处理：\n"
            msg += "\n".join(rar_list[:10])
            if len(rar_list) > 10:
                msg += f"\n... 共 {len(rar_list)} 个"
```

完整的结果构建代码应为：

```python
        msg = f"解压完成：成功 {success} 个，失败 {fail} 个"
        if failed_list:
            msg += "\n\n失败文件：\n" + "\n".join(failed_list[:10])
            if len(failed_list) > 10:
                msg += f"\n... 共 {len(failed_list)} 个"
        if rar_list:
            msg += "\n\n⚠ 以下 RAR 文件无法自动解压，请手动处理：\n"
            msg += "\n".join(rar_list[:10])
            if len(rar_list) > 10:
                msg += f"\n... 共 {len(rar_list)} 个"

        QMessageBox.information(self, "全量解压", msg)
```

- [ ] **Step 3: 提交**

```bash
git add gdm/gui/main_window.py
git commit -m "feat: 全量解压结果对话框追加 RAR 文件提示"
```

---

### Task 3: 编写测试

**Files:**
- Modify: `tests/test_extractor.py`（如不存在则创建）

- [ ] **Step 1: 编写 RAR 文件检测测试**

```python
import os
import tempfile
from gdm.core.extractor import find_archives, extract_all


def test_find_archives_includes_rar():
    """find_archives 应检测 .rar 文件。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建测试文件
        open(os.path.join(tmpdir, "test.zip"), "w").close()
        open(os.path.join(tmpdir, "test.rar"), "w").close()

        archives = find_archives(tmpdir)
        names = [os.path.basename(a) for a in archives]
        assert "test.rar" in names
        assert "test.zip" in names


def test_extract_all_skips_rar():
    """extract_all 应跳过 .rar 文件并返回其路径。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建一个真正的 zip（含单个文件）和一个 .rar 占位
        import zipfile
        zip_path = os.path.join(tmpdir, "test.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("hello.txt", "hello")

        rar_path = os.path.join(tmpdir, "test.rar")
        open(rar_path, "w").close()

        success, fail, failed, rar_list = extract_all(tmpdir)

        assert success == 1  # zip 解压成功
        assert fail == 0
        assert len(rar_list) == 1
        assert "test.rar" in rar_list[0]


def test_extract_all_rar_dedup():
    """RAR 文件在同一目录多次扫描不会重复。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        rar_path = os.path.join(tmpdir, "test.rar")
        open(rar_path, "w").close()

        success, fail, failed, rar_list = extract_all(tmpdir)

        assert len(rar_list) == 1
```

- [ ] **Step 2: 运行测试**

```bash
pytest tests/test_extractor.py -v
```

预期：全部 PASS

- [ ] **Step 3: 提交**

```bash
git add tests/test_extractor.py
git commit -m "test: 新增 RAR 检测和跳过解压测试"
```
