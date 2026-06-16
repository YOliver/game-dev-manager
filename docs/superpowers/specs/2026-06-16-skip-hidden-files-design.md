---
name: Skip Hidden Files Design
description: 扫描文件时跳过以 . 开头的隐藏文件（如 macOS AppleDouble 文件 ._xxx.png）
type: design
---

# 跳过隐藏文件设计

## 背景

在 Windows 上解压 macOS 压缩的 ZIP 包时，macOS 会为每个文件生成 `AppleDouble` 元数据文件（如 `._Example Scene.png`），存放在 `__MACOSX` 目录下或与原文件并列。

这些文件：
- 扩展名是 `.png`/`.jpg` 等，会通过扩展名过滤
- 文件内容不是有效图片，`Pillow` 读取时报 `cannot identify image file`
- 导致扫描日志出现大量无意义报错

## 目标

扫描图片文件时，跳过所有文件名以 `.` 开头的文件（Unix/macOS 隐藏文件约定）。

**注意：隐藏目录（以 `.` 开头的目录）不跳过，继续扫描其中的文件，以保证不漏文件。**

## 新增辅助函数

在 `gdm/utils/helpers.py` 中新增 `is_hidden()` 函数：

```python
from pathlib import Path

def is_hidden(file_path: Path) -> bool:
    """判断文件是否为隐藏文件（文件名以 . 开头）。"""
    return file_path.name.startswith(".")
```

> 只处理文件名前缀 `.` 的情况，不处理 Windows NTFS 隐藏属性（与用户需求一致）。

## 改动点

### 1. `gdm/core/scanner.py`

两处过滤条件，`scan()` 第 35 行和 `scan_with_progress()` 第 65 行，新增 `not is_hidden(file_path)` 检查：

```python
# 修改后
if (file_path.is_file()
    and file_path.suffix.lower() in SUPPORTED_EXTENSIONS
    and not is_hidden(file_path)):
```

需新增导入：`from gdm.utils.helpers import is_hidden`

### 2. `gdm/core/cache/scanner_cached.py`

`snapshot_folder()` 使用 `os.walk`，在扩展名检查前跳过隐藏文件：

```python
# 修改后
for sub_dir, dirs, files in os.walk(root):
    for fname in files:
        if fname.startswith("."):
            continue
        ext = os.path.splitext(fname)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            continue
        ...
```

> `scanner_cached.py` 使用 `os.path` API，此处用字符串方法 `startswith(".")` 判断，与 `is_hidden()` 逻辑等价但避免 `Path` 转换。
>
> **不跳过隐藏目录**——`dirs` 列表不做过滤，隐藏目录内的文件仍会被扫描，其中的隐藏文件（如 `._xxx.png`）会被文件名检查过滤掉。

### 3. `gdm/utils/helpers.py`

新增 `is_hidden()` 函数（如上所示）。

## 测试

- `tests/test_scanner.py`：新增测试，构造以 `.` 开头的临时文件，验证 `scan()` 不返回该文件
- 手动验证：用包含 `.__MACOSX/._xxx.png` 的真实素材目录扫描，确认无报错，且隐藏目录中的普通文件仍被扫描

## 影响范围

| 文件 | 改动类型 |
|------|---------|
| `gdm/utils/helpers.py` | 新增 `is_hidden()` |
| `gdm/core/scanner.py` | 两处过滤条件 + 导入 |
| `gdm/core/cache/scanner_cached.py` | 跳过隐藏文件（`fname.startswith(".")`） |
| `tests/test_scanner.py` | 新增测试用例 |
