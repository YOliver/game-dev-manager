"""工作区状态保存与加载

提供 save() 和 load() 函数，用于持久化 Project 对象到 .gdm.json。
"""

import json
from pathlib import Path
from typing import Optional

from gdm.core.models import Project


def save(project: Project, path: str) -> None:
    """将工作区状态写入 .gdm.json

    Args:
        project: 要保存的 Project 对象
        path: 目标文件路径（如 .gdm.json）
    """
    data = {"root_path": project.root_path}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load(path: str) -> Optional[Project]:
    """读取 .gdm.json 恢复工作区。失败返回 None。

    Args:
        path: 文件路径（如 .gdm.json）

    Returns:
        Project 对象，或 None（文件不存在/格式错误时）
    """
    if not Path(path).exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Project(root_path=data["root_path"])
    except (json.JSONDecodeError, KeyError):
        return None
