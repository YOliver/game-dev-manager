"""持久化缓存子包：SQLite 存元数据 + 缩略图 blob。"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QStandardPaths


@dataclass
class CachedEntry:
    """缓存中的单个文件记录，覆盖 SpriteInfo 全部字段 + 缓存校验字段。"""

    folder_path: str
    file_name: str
    width: int
    height: int
    size: int
    format: str
    color_mode: str
    mtime_ns: int
    thumb_blob: Optional[bytes]
    thumb_mtime_ns: Optional[int]


def get_cache_dir() -> Path:
    """返回缓存目录路径，必要时创建。"""
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    cache_dir = Path(base) / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_db_path() -> Path:
    """返回 cache.db 完整路径。"""
    return get_cache_dir() / "cache.db"
