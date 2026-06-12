"""GDM 核心数据模型

定义项目中使用的数据类与枚举。
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class RenameMode(Enum):
    """重命名模式枚举"""

    PREFIX_NUMBER = "前缀+序号"
    FIND_REPLACE = "查找替换"
    REGEX = "正则替换"
    ADD_SUFFIX = "添加后缀"


@dataclass
class SpriteInfo:
    """雪碧图（精灵图）信息"""

    file_path: str   # 完整路径
    file_name: str   # 文件名（含扩展名）
    width: int       # 像素宽度
    height: int      # 像素高度
    file_size: int   # 文件大小（字节）
    format: str      # 图片格式（PNG/JPEG/WebP...）
    color_mode: str  # 色彩模式（RGB/RGBA/P...）


@dataclass
class Project:
    """项目信息

    v1 仅保存根目录路径，后续版本可扩展其他字段。
    """

    root_path: str  # 工作区根目录


@dataclass
class RenameRule:
    """重命名规则"""

    mode: RenameMode

    # 前缀+序号模式用
    prefix: Optional[str] = None
    start_index: int = 1
    padding: int = 3

    # 查找替换模式用
    find_text: Optional[str] = None
    replace_text: Optional[str] = None

    # 正则模式用
    regex_pattern: Optional[str] = None
    regex_replacement: Optional[str] = None

    # 添加后缀模式用
    suffix: Optional[str] = None
