"""批量重命名引擎

提供 preview() 和 execute() 函数，用于雪碧图文件的批量重命名。
"""

import os
import re
from typing import List, Tuple

from gdm.core.models import SpriteInfo, RenameRule, RenameMode


def preview(sprites: List[SpriteInfo], rule: RenameRule) -> List[Tuple[str, str]]:
    """返回（原路径, 新路径）对照表，不实际写入。

    Args:
        sprites: 雪碧图信息列表
        rule: 重命名规则

    Returns:
        (原路径, 新路径) 元组列表
    """
    results = []
    for i, sprite in enumerate(sprites):
        new_name = _generate_new_name(sprite.file_name, rule, i)
        new_path = os.path.join(os.path.dirname(sprite.file_path), new_name)
        results.append((sprite.file_path, new_path))
    return results


def execute(sprites: List[SpriteInfo], rule: RenameRule) -> Tuple[int, List[str]]:
    """执行重命名，原地更新 SpriteInfo 对象。

    Args:
        sprites: 雪碧图信息列表（会被原地修改）
        rule: 重命名规则

    Returns:
        (成功数量, 旧路径列表)
    """
    results = preview(sprites, rule)
    success_count = 0
    old_paths = []

    for sprite, (old_path, new_path) in zip(sprites, results):
        if os.path.exists(new_path) and new_path != old_path:
            continue  # 目标已存在，跳过
        try:
            os.rename(old_path, new_path)
            sprite.file_path = new_path
            sprite.file_name = os.path.basename(new_path)
            old_paths.append(old_path)
            success_count += 1
        except OSError:
            continue

    return success_count, old_paths


def _generate_new_name(original_name: str, rule: RenameRule, index: int) -> str:
    """根据规则生成新文件名。

    Args:
        original_name: 原始文件名（含扩展名）
        rule: 重命名规则
        index: 当前序号（从 0 开始）

    Returns:
        新文件名
    """
    name, ext = os.path.splitext(original_name)

    if rule.mode == RenameMode.PREFIX_NUMBER:
        new_name = f"{rule.prefix}_{index + rule.start_index:0{rule.padding}d}{ext}"
    elif rule.mode == RenameMode.FIND_REPLACE:
        new_name = original_name.replace(rule.find_text, rule.replace_text)
    elif rule.mode == RenameMode.REGEX:
        new_name = re.sub(rule.regex_pattern, rule.regex_replacement, original_name)
    elif rule.mode == RenameMode.ADD_SUFFIX:
        new_name = f"{name}{rule.suffix}{ext}"
    else:
        new_name = original_name

    return new_name
