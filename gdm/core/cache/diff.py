"""纯函数 diff：比较缓存条目与文件系统快照。"""

from dataclasses import dataclass
from typing import List, Tuple

from gdm.core.cache import CachedEntry


@dataclass(frozen=True)
class FileSnapshot:
    """文件系统中扫描到的单个文件快照（不含元数据，未读 Pillow）。"""

    folder_path: str
    file_name: str
    mtime_ns: int
    size: int


def compute_diff(
    cached: List[CachedEntry],
    current: List[FileSnapshot],
) -> Tuple[List[FileSnapshot], List[FileSnapshot], List[Tuple[str, str]]]:
    """按 (folder_path, file_name) 复合键比对。

    Returns:
        (added, changed, removed)
        added/changed: List[FileSnapshot]
        removed: List[(folder_path, file_name)]
    """
    cached_map = {(e.folder_path, e.file_name): e for e in cached}
    current_map = {(s.folder_path, s.file_name): s for s in current}

    added: List[FileSnapshot] = []
    changed: List[FileSnapshot] = []
    for key, snap in current_map.items():
        if key not in cached_map:
            added.append(snap)
        else:
            entry = cached_map[key]
            if entry.mtime_ns != snap.mtime_ns or entry.size != snap.size:
                changed.append(snap)

    removed: List[Tuple[str, str]] = [
        key for key in cached_map if key not in current_map
    ]

    return added, changed, removed
