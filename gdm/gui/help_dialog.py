"""帮助对话框模块。

提供 HelpDialog 类和辅助函数，用于加载和显示帮助文档。
"""

import sys
import os

import markdown

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                               QTextBrowser, QLineEdit, QPushButton,
                               QLabel, QMessageBox, QWidget)
from PySide6.QtGui import QTextCursor, QTextCharFormat, QBrush, QColor


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


class HelpDialog(QDialog):
    """帮助对话框。

    显示 Markdown 帮助文档（转 HTML 后显示），支持搜索高亮。
    """

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self._current_html = ""
        self._highlights: list = []
        self._current_match = 0
        self._total_matches = 0
        self._init_ui()

    def _init_ui(self) -> None:
        """初始化 UI 组件与布局。"""
        self.setWindowTitle("帮助")
        self.setMinimumSize(700, 500)
        self.resize(700, 500)

        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(5)

        # 顶部：搜索栏
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("🔍"))

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("搜索...")
        self.search_box.textChanged.connect(self._on_search_text_changed)
        search_layout.addWidget(self.search_box)

        main_layout.addLayout(search_layout)

        # 中间：文本浏览器
        self.text_browser = QTextBrowser()
        main_layout.addWidget(self.text_browser)

        # 底部：导航按钮和计数器
        nav_layout = QHBoxLayout()

        self.prev_btn = QPushButton("◀ 上一个")
        self.prev_btn.clicked.connect(self._on_prev_clicked)
        self.prev_btn.setEnabled(False)
        nav_layout.addWidget(self.prev_btn)

        self.counter_label = QLabel("")
        self.counter_label.setVisible(False)
        nav_layout.addWidget(self.counter_label)

        self.next_btn = QPushButton("下一个 ▶")
        self.next_btn.clicked.connect(self._on_next_clicked)
        self.next_btn.setEnabled(False)
        nav_layout.addWidget(self.next_btn)

        nav_layout.addStretch()

        main_layout.addLayout(nav_layout)

    def load_doc(self, filename: str) -> None:
        """加载并显示帮助文档。

        Args:
            filename: 帮助文档文件名（如 "about.md"）
        """
        md_text = ""  # 初始化，防止异常时未定义
        try:
            path = get_help_doc_path(filename)
            with open(path, 'r', encoding='utf-8') as f:
                md_text = f.read()
            html = md_to_html(md_text)
            self.text_browser.setHtml(html)
            self._current_html = html
        except FileNotFoundError:
            QMessageBox.warning(self, "错误", f"帮助文档缺失：{filename}")
        except Exception as e:
            # 降级：显示原始文本
            self.text_browser.setPlainText(md_text)

    def _on_search_text_changed(self, text: str) -> None:
        """搜索文本变化时的处理（待实现）。"""
        # TODO: 实现搜索高亮逻辑
        pass

    def _on_prev_clicked(self) -> None:
        """上一个匹配按钮点击时的处理（待实现）。"""
        # TODO: 实现上一个匹配导航
        pass

    def _on_next_clicked(self) -> None:
        """下一个匹配按钮点击时的处理（待实现）。"""
        # TODO: 实现下一个匹配导航
        pass


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
