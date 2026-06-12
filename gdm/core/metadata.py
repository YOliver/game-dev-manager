"""图片元数据提取

使用 Pillow 读取图片文件的尺寸、格式、色彩模式等元数据。
"""

from pathlib import Path
from PIL import Image
from gdm.core.models import SpriteInfo


def extract(file_path: str) -> SpriteInfo:
    """提取图片元数据，失败则返回部分信息。

    Args:
        file_path: 图片文件的完整路径。

    Returns:
        包含文件元数据的 SpriteInfo 对象。
        若图片内容无法读取，尺寸填 0，格式和色彩模式填 "UNKNOWN"。
        文件基本信息（路径、文件名、文件大小）始终可读取。
    """
    path = Path(file_path)
    file_name = path.name
    file_size = path.stat().st_size

    width, height = 0, 0
    img_format = "UNKNOWN"
    color_mode = "UNKNOWN"

    try:
        with Image.open(file_path) as img:
            width, height = img.size
            img_format = img.format or "UNKNOWN"
            color_mode = img.mode
    except Exception:
        pass  # 读取失败，使用默认值

    return SpriteInfo(
        file_path=file_path,
        file_name=file_name,
        width=width,
        height=height,
        file_size=file_size,
        format=img_format,
        color_mode=color_mode,
    )
