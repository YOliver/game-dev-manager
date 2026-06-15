"""帮助对话框模块。

提供 HelpDialog 类和辅助函数，用于加载和显示帮助文档。
"""

import sys
import os

import markdown


def md_to_html(md_text: str) -> str:
    """将 Markdown 文本转换为 HTML（带样式）。

    Args:
        md_text: Markdown 格式的文本

    Returns:
        完整的 HTML 文档字符串（包含 <style>）
    """
    extensions = [
        'tables',           # 表格支持
        'fenced_code',      # 代码块支持（```）
        'nl2br',           # 换行转 <br>
    ]
    html_body = markdown.markdown(md_text, extensions=extensions)

    # 包裹完整 HTML 文档，添加 CSS 样式
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
            font-size: 14px;
            line-height: 1.6;
            padding: 10px 20px;
        }}
        h1, h2, h3 {{
            color: #333;
        }}
        code {{
            background-color: #f0f0f0;
            padding: 2px 4px;
            border-radius: 3px;
            font-family: "Consolas", "Monaco", monospace;
        }}
        pre {{
            background-color: #f5f5f5;
            padding: 10px;
            border-radius: 5px;
            overflow-x: auto;
        }}
        pre code {{
            background-color: transparent;
            padding: 0;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}
        th {{
            background-color: #f0f0f0;
        }}
    </style>
</head>
<body>
{html_body}
</body>
</html>"""
    return html


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
