# 全量解压进度提示 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 全量解压时显示 QProgressDialog，展示当前解压文件名和完成进度

**Architecture:** extract_all() 添加 progress_callback 参数，MainWindow 传入回调更新 QProgressDialog

**Tech Stack:** Python, PySide6 (QProgressDialog), pytest

---

### Task 1: 更新测试 — 验证 progress_callback 被调用

**Files:**
- Modify: `tests/test_extractor.py`

- [ ] **Step 1: 追加测试方法**

在 `TestExtractAll` 类末尾追加：

```python
    def test_extract_all_with_progress_callback(self, tmp_path):
        """progress_callback 应在每个压缩包处理后被调用。"""
        d = Path(tmp_path)
        with zipfile.ZipFile(d / "a.zip", "w") as zf:
            zf.writestr("a.txt", "a")
        with zipfile.ZipFile(d / "b.zip", "w") as zf:
            zf.writestr("b.txt", "b")

        calls = []
        def cb(current, total, filename):
            calls.append((current, total, filename))

        success, fail, _ = extract_all(str(d), progress_callback=cb)

        assert success == 2
        assert len(calls) >= 2  # 至少被调用 2 次
        # 最后一次调用 total 应 >= 2
        assert calls[-1][1] >= 2
```

- [ ] **Step 2: 运行测试确认通过**

```bash
python -m pytest tests/test_extractor.py::TestExtractAll::test_extract_all_with_progress_callback -v
```

预期：PASS（progress_callback 是可选参数，不传也能正常工作）

- [ ] **Step 3: 提交**

```bash
git add tests/test_extractor.py
git commit -m "test: 新增 extract_all progress_callback 的测试"
```

---

### Task 2: 实现 extract_all 的 progress_callback

**Files:**
- Modify: `gdm/core/extractor.py`

- [ ] **Step 1: 修改 extract_all() 函数签名和逻辑**

将 `extract_all()` 改为如下实现：

```python
def extract_all(directory: str, progress_callback=None) -> Tuple[int, int, List[str]]:
    """递归解压目录下所有压缩包（含嵌套）。

    Args:
        directory: 目标目录
        progress_callback: 可选回调 (current: int, total: int, filename: str) -> None

    返回 (成功数, 失败数, 失败文件路径列表)
    """
    success_count = 0
    fail_count = 0
    failed_paths: List[str] = []

    archives = find_archives(directory)
    total_estimated = len(archives)

    while True:
        if not archives and total_estimated == 0:
            break

        any_success = False
        for archive_path in archives:
            try:
                extract_archive(archive_path)
                success_count += 1
                any_success = True
            except Exception as e:
                logger.warning(f"解压失败: {archive_path}, 错误: {e}")
                fail_count += 1
                failed_paths.append(archive_path)
            finally:
                current = success_count + fail_count
                if progress_callback:
                    progress_callback(current, total_estimated,
                                     os.path.basename(archive_path))

        if not any_success:
            break

        archives = find_archives(directory)
        if archives:
            total_estimated += len(archives)

    return success_count, fail_count, failed_paths
```

- [ ] **Step 2: 运行 extractor 测试确认全部通过**

```bash
python -m pytest tests/test_extractor.py -v
```

预期：全部 PASS

- [ ] **Step 3: 提交**

```bash
git add gdm/core/extractor.py
git commit -m "feat: extract_all 添加 progress_callback 进度回调"
```

---

### Task 3: 在 main_window 中添加 QProgressDialog

**Files:**
- Modify: `gdm/gui/main_window.py`

- [ ] **Step 1: 修改 `_open_extract_all()` 方法**

将该方法修改为：

```python
    def _open_extract_all(self) -> None:
        """打开全量解压功能。"""
        from gdm.core.extractor import find_archives, extract_all
        from PySide6.QtWidgets import QMessageBox, QProgressDialog

        directory = self._selected_folder or (self._project.root_path if self._project else None)
        if directory is None:
            QMessageBox.warning(self, "全量解压", "请先在项目面板中选择一个目录")
            return

        archives = find_archives(directory)
        if not archives:
            QMessageBox.information(self, "全量解压", "未发现压缩包")
            return

        total_size = sum(os.path.getsize(p) for p in archives)
        size_mb = total_size / (1024 * 1024)

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

        progress = QProgressDialog("正在解压...", None, 0, 0, self)
        progress.setWindowTitle("全量解压")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)

        def update_progress(current: int, total: int, filename: str):
            progress.setMaximum(total)
            progress.setValue(current)
            progress.setLabelText(f"正在解压：{filename}\n已完成：{current}/{total}")

        success, fail, failed_list = extract_all(directory, progress_callback=update_progress)
        progress.close()

        msg = f"解压完成：成功 {success} 个，失败 {fail} 个"
        if failed_list:
            msg += "\n\n失败文件：\n" + "\n".join(failed_list[:10])
            if len(failed_list) > 10:
                msg += f"\n... 共 {len(failed_list)} 个"

        QMessageBox.information(self, "全量解压", msg)

        self._on_folder_selected(directory)
```

- [ ] **Step 2: 运行 main_window 测试确认通过**

```bash
python -m pytest tests/test_main_window.py::TestExtractAllMenu -v
```

预期：PASS

- [ ] **Step 3: 提交**

```bash
git add gdm/gui/main_window.py
git commit -m "feat: 全量解压添加 QProgressDialog 进度提示"
```

---

### Task 4: 运行全量测试

**Files:**
- 无新建/修改

- [ ] **Step 1: 运行全量测试**

```bash
python -m pytest tests/ -v
```

预期：全部 PASS

---

## 任务依赖顺序

```
Task 1 (test) → Task 2 (impl extractor) → Task 3 (impl main_window) → Task 4 (full test)
```

## 预期提交记录

```
test: 新增 extract_all progress_callback 的测试
feat: extract_all 添加 progress_callback 进度回调
feat: 全量解压添加 QProgressDialog 进度提示
```
