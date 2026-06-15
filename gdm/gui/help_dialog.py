"""帮助对话框模块。

提供 HelpDialog 类和辅助函数，用于加载和显示帮助文档。
"""

import sys
import os

import markdown

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                               QTextBrowser, QLineEdit, QPushButton,
                               QLabel, QMessageBox, QWidget)
from PySide6.QtGui import QTextCursor, QTextCharFormat, QBrush, QColor, QTextDocument


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
        """搜索框文字变化回调，触发搜索和高亮。"""
        self._search(text)

    def _search(self, text: str) -> None:
        """搜索并高亮所有匹配项。"""
        # 清除旧高亮（重新加载 HTML）
        if self._current_html:
            self.text_browser.setHtml(self._current_html)

        self._current_match = 0
        self._total_matches = 0

        if not text:
            self._update_nav_buttons()
            return

        # 查找所有匹配项（用于计数）
        document = self.text_browser.document()
        cursor = QTextCursor(document)

        # 从文档开始查找（大小写不敏感）
        while True:
            cursor = document.find(text, cursor)
            if cursor.isNull():
                break
            self._total_matches += 1

        self._update_nav_buttons()

        # 跳转到第一个匹配项
        if self._total_matches > 0:
            self._jump_to_match(0)

    def _update_nav_buttons(self) -> None:
        """更新导航按钮状态和计数器。"""
        has_matches = self._total_matches > 0
        self.prev_btn.setEnabled(has_matches)
        self.next_btn.setEnabled(has_matches)
        self.counter_label.setVisible(has_matches)

        if has_matches:
            self.counter_label.setText(f"第 {self._current_match + 1}/{self._total_matches} 项")
        else:
            if self.search_box.text():
                self.counter_label.setText("无结果")
                self.counter_label.setVisible(True)

    def _jump_to_match(self, index: int) -> None:
        """跳转到指定匹配项。"""
        if not (0 <= index < self._total_matches):
            return

        self._current_match = index

        # 清除之前的高亮，重新高亮所有项
        if self._current_html:
            self.text_browser.setHtml(self._current_html)

        # 重新应用高亮（当前项用不同颜色）
        document = self.text_browser.document()
        all_text = self.search_box.text()

        cursor_all = QTextCursor(document)
        format_normal = QTextCharFormat()
        format_normal.setBackground(QBrush(QColor("#FFFF00")))  # 黄色

        format_current = QTextCharFormat()
        format_current.setBackground(QBrush(QColor("#FFA500")))  # 橙色（当前项）

        matches = []
        while True:
            # PySide6/Qt6 中不使用 FindCaseSensitively 标志即为大小写不敏感搜索
            cursor_all = document.find(all_text, cursor_all)
            if cursor_all.isNull():
                break
            matches.append(QTextCursor(cursor_all))

        for i, match_cursor in enumerate(matches):
            if i == index:
                match_cursor.mergeCharFormat(format_current)
            else:
                match_cursor.mergeCharFormat(format_normal)

        # 滚动到当前项
        self.text_browser.setTextCursor(matches[index])
        self.text_browser.ensureCursorVisible()

        self._update_nav_buttons()

    def _on_prev_clicked(self) -> None:
        """上一个按钮点击回调。"""
        if self._total_matches == 0:
            return
        new_index = (self._current_match - 1) % self._total_matches
        self._jump_to_match(new_index)

    def _on_next_clicked(self) -> None:
        """下一个按钮点击回调。"""
        if self._total_matches == 0:
            return
        new_index = (self._current_match + 1) % self._total_matches
        self._jump_to_match(new_index)


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
