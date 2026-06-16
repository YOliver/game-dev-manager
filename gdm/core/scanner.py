"""文件夹扫描

扫描指定目录中的图片文件，提取元数据并返回 SpriteInfo 列表。
"""

from pathlib import Path
from typing import Callable, List, Optional

from gdm.core.models import SpriteInfo
from gdm.core.metadata import extract
from gdm.utils.helpers import is_hidden

# 支持的图片扩展名
SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


def scan(directory: str, recursive: bool = False) -> List[SpriteInfo]:
    """扫描目录，返回图片 SpriteInfo 列表。

    Args:
        directory: 要扫描的目录路径。
        recursive: 是否递归扫描子目录，默认为 False。

    Returns:
        包含目录中所有图片文件元数据的 SpriteInfo 列表。
        如果目录不存在或不是目录，返回空列表。
    """
    path = Path(directory)
    if not path.is_dir():
        return []

    sprites: List[SpriteInfo] = []
    pattern = "**/*" if recursive else "*"

    for file_path in path.glob(pattern):
        if (file_path.is_file()
            and file_path.suffix.lower() in SUPPORTED_EXTENSIONS
            and not is_hidden(file_path)):
            sprites.append(extract(str(file_path)))

    return sprites


def scan_with_progress(
    directory: str,
    recursive: bool = True,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> List[SpriteInfo]:
    """带进度回调的扫描函数，先快速统计总数，再逐张提取元数据。

    Args:
        directory: 要扫描的目录路径
        recursive: 是否递归扫描子目录
        progress_callback: 进度回调，参数为 (已处理数, 总数)

    Returns:
        包含所有图片元数据的 SpriteInfo 列表。
    """
    path = Path(directory)
    if not path.is_dir():
        return []

    pattern = "**/*" if recursive else "*"

    # 阶段1：收集所有图片路径（仅检查扩展名，不读取内容）
    image_paths: list[str] = []
    for file_path in path.glob(pattern):
        if (file_path.is_file()
            and file_path.suffix.lower() in SUPPORTED_EXTENSIONS
            and not is_hidden(file_path)):
            image_paths.append(str(file_path))

    total = len(image_paths)

    # 阶段2：逐张提取元数据
    sprites: List[SpriteInfo] = []
    for i, fp in enumerate(image_paths):
        sprites.append(extract(fp))
        if progress_callback:
            progress_callback(i + 1, total)

    return sprites
