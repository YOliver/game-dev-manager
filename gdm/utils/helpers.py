from pathlib import Path


def format_file_size(size_bytes: int) -> str:
    """将字节数格式化为 KB/MB 字符串。"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def is_hidden(file_path: Path) -> bool:
    """判断文件是否为隐藏文件（文件名以 . 开头）。

    Args:
        file_path: 文件路径。

    Returns:
        文件名以 . 开头返回 True，否则 False。
    """
    return file_path.name.startswith(".")
