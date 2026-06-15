# 全量解压进度提示

## 问题描述

全量解压操作可能耗时较长，当前没有任何进度反馈，用户无法知道解压进度。

## 设计方案

### 架构

给 `extract_all()` 添加 `progress_callback` 参数，MainWindow 传入回调函数，通过 `QProgressDialog` 显示进度。

### extractor.py 改动

`extract_all()` 新增 `progress_callback` 参数：

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
                    progress_callback(current, total_estimated, os.path.basename(archive_path))

        if not any_success:
            break

        archives = find_archives(directory)
        if archives:
            total_estimated += len(archives)

    return success_count, fail_count, failed_paths
```

### main_window.py 改动

`_open_extract_all()` 中添加 QProgressDialog：

```python
    progress = QProgressDialog("正在解压...", "取消", 0, 0, self)
    progress.setWindowTitle("全量解压")
    progress.setWindowModality(Qt.WindowModal)
    progress.setMinimumDuration(0)

    def update_progress(current: int, total: int, filename: str):
        progress.setMaximum(total)
        progress.setValue(current)
        progress.setLabelText(f"正在解压：{filename}\n已完成：{current}/{total}")

    success, fail, failed_list = extract_all(directory, progress_callback=update_progress)
    progress.close()
```

`QProgressDialog` 需追加到已有的 `QMessageBox` 导入行，将 `_open_extract_all()` 中的：

```python
from PySide6.QtWidgets import QMessageBox
```

改为：

```python
from PySide6.QtWidgets import QMessageBox, QProgressDialog
```

### 行为说明

- 确认后立即弹出进度窗口
- 显示当前解压文件名和完成数量
- 解压结束后自动关闭进度窗口
- 嵌套压缩包出现时动态增加总数

### 改动范围

| 文件 | 改动 |
|------|------|
| `gdm/core/extractor.py` | `extract_all()` 添加 `progress_callback` 参数 |
| `gdm/gui/main_window.py` | `_open_extract_all()` 创建 QProgressDialog，传入回调 |

### 不影响的内容

- `find_archives()` 和 `extract_archive()` 函数不变
- 确认对话框和结果提示不变
- 菜单注册不变
