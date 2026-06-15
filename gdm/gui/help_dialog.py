"""帮助对话框模块。

提供 HelpDialog 类和辅助函数，用于加载和显示帮助文档。
"""

import sys
import os


def get_help_doc_path(filename: str) -> str:
    """获取帮助文档的完整路径（兼容开发和打包环境）。

    Args:
        filename: 帮助文档文件名（如 "about.md"）

    Returns:
        帮助文档的完整路径

    Raises:
        FileNotFoundError: 帮助文档不存在时
    """
    if getattr(sys, 'frozen', False):
        # 打包后的环境：sys._MEIPASS 是临时解压目录
        base_path = os.path.join(sys._MEIPASS, 'helpdocs')
    else:
        # 开发环境：项目根目录下的 helpdocs/
        base_path = os.path.join(os.path.dirname(__file__), '..', '..', 'helpdocs')

    path = os.path.join(base_path, filename)
    path = os.path.normpath(path)

    if not os.path.exists(path):
        raise FileNotFoundError(f"帮助文档不存在: {filename}")

    return path
