"""文件夹扫描

扫描指定目录中的图片文件，提取元数据并返回 SpriteInfo 列表。
"""

from pathlib import Path
from typing import List

from gdm.core.models import SpriteInfo
from gdm.core.metadata import extract

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
        if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
            sprites.append(extract(str(file_path)))

    return sprites
