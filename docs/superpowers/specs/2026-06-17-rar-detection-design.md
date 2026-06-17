# 设计文档：RAR 格式检测与提示

**日期**: 2026-06-17

## 目标

在全量解压功能中，检测 `.rar` 文件但不尝试解压，结束后在结果对话框中列出所有 RAR 文件，提示用户手动处理。

## 背景

当前全量解压仅支持 `.zip`、`.tar`、`.gz`、`.bz2`、`.xz`、`.tgz` 六种格式。RAR 是私有格式，Python 标准库不支持，引入外部工具会增加环境依赖。同时用户表示不需要自动解压 RAR，只需知道有哪些 RAR 文件即可。

## Before / After

```
Before: 扫描目录，.rar 文件被完全忽略，用户不知道它们存在
After:  .rar 文件被检测到并在结果中列出，提示用户手动解压
```

## 改动

### 1. `gdm/core/extractor.py` — 扩展格式、分离 RAR

**`SUPPORTED_ARCHIVE_EXTENSIONS` 加 `.rar`：**

```python
SUPPORTED_ARCHIVE_EXTENSIONS = {".zip", ".tar", ".gz", ".bz2", ".xz", ".tgz", ".rar"}
```

**`extract_all()` 返回值改为 4 元组：**

```python
def extract_all(
    directory: str,
    progress_callback=None,
) -> Tuple[int, int, List[str], List[str]]:
    """返回 (成功数, 失败数, 失败路径列表, rar 文件路径列表)。"""
```

**在循环中分离 RAR 文件：**

在 `while True` 循环中，扫描结果按扩展名分为两组——RAR 文件收集但不处理，其余正常解压。循环仅以非 RAR 文件为判断条件继续：

```python
# 函数开头初始化
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
        # ... 原有解压逻辑不变 ...

return success_count, fail_count, failed_paths, sorted(all_rar_files)
```

### 2. `gdm/gui/main_window.py` — 结果对话框追加 RAR 提示

在 `_open_extract_all()` 中更新解压调用和结果展示：

```python
success, fail, failed_list, rar_list = extract_all(
    directory, progress_callback=update_progress
)
progress.close()

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

## 影响范围

- 修改文件: `gdm/core/extractor.py`、`gdm/gui/main_window.py`
- `extract_all()` 返回值从 3 元组变为 4 元组，向后不兼容
- 仅 `main_window.py` 一处调用点，易于追踪
- 初始弹窗中的压缩包数量和大小统计已包含 RAR 文件（因为 `find_archives` 会找到它们）
