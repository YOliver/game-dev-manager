"""Tests for help_dialog module."""

import os
import sys
import pytest
import unittest.mock as mock

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from PySide6 import QtCore

from gdm.gui.help_dialog import HelpDialog, get_help_doc_path, md_to_html


class TestGetHelpDocPath:
    """Tests for get_help_doc_path function."""

    def test_dev_environment(self):
        """Test path resolution in development environment."""
        # In dev environment, should point to project root helpdocs/
        path = get_help_doc_path("about.md")
        expected = os.path.join(os.path.dirname(__file__), '..', 'helpdocs', 'about.md')
        expected = os.path.normpath(expected)
        assert os.path.normpath(path) == expected

    def test_packaged_environment(self, monkeypatch):
        """Test path resolution in packaged environment (sys._MEIPASS)."""
        # Mock sys._MEIPASS
        monkeypatch.setattr(sys, '_MEIPASS', '/fake/meipass', raising=False)
        monkeypatch.setattr(sys, 'frozen', True, raising=False)
        # Mock os.path.exists 返回 True，避免 FileNotFoundError
        monkeypatch.setattr(os.path, 'exists', lambda x: True)

        path = get_help_doc_path("about.md")
        expected = os.path.join('/fake/meipass', 'helpdocs', 'about.md')
        expected = os.path.normpath(expected)
        assert os.path.normpath(path) == expected


class TestMdToHtml:
    """Tests for md_to_html function."""

    def test_basic_markdown(self):
        """Test basic Markdown to HTML conversion."""
        md_text = "# Title\n\nThis is a paragraph."
        html = md_to_html(md_text)
        assert "<h1>Title</h1>" in html
        assert "<p>This is a paragraph.</p>" in html

    def test_code_block(self):
        """Test fenced code block conversion."""
        md_text = "```python\nprint('hello')\n```"
        html = md_to_html(md_text)
        assert "<pre" in html
        assert "print('hello')" in html

    def test_table(self):
        """Test table conversion."""
        md_text = "| Col1 | Col2 |\n|------|------|\n| A    | B    |"
        html = md_to_html(md_text)
        assert "<table>" in html
        assert "<th>Col1</th>" in html


class TestHelpDialog:
    """HelpDialog 的集成测试。"""

    def test_load_doc_success(self, qtbot):
        """测试加载有效的帮助文档。"""
        dialog = HelpDialog()
        dialog.load_doc("about.md")
        # 验证文本浏览器有内容
        assert dialog.text_browser.toPlainText() != ""

    def test_load_doc_not_found(self, qtbot):
        """测试加载不存在的文档时显示警告。"""
        dialog = HelpDialog()
        # Mock QMessageBox.warning 以避免弹窗
        with mock.patch('gdm.gui.help_dialog.QMessageBox.warning') as mock_warning:
            dialog.load_doc("nonexistent.md")
            mock_warning.assert_called_once()

    def test_search_highlight(self, qtbot):
        """测试搜索功能高亮文本。"""
        dialog = HelpDialog()
        dialog.load_doc("about.md")

        # 输入搜索文本
        qtbot.keyClicks(dialog.search_box, "Game")
        qtbot.wait(100)

        # 验证存在高亮匹配
        assert dialog._total_matches > 0

    def test_search_navigation(self, qtbot):
        """测试搜索导航（上一个/下一个按钮）。"""
        dialog = HelpDialog()
        # 直接设置包含多个匹配项的 HTML 内容
        html_content = "<p>test test test</p><p>test test</p>"
        dialog.text_browser.setHtml(html_content)
        dialog._current_html = html_content

        # 输入搜索文本
        qtbot.keyClicks(dialog.search_box, "test")
        qtbot.wait(500)

        # 验证有至少 2 个匹配项
        assert dialog._total_matches >= 2

        # 验证导航按钮已启用
        assert dialog.prev_btn.isEnabled()
        assert dialog.next_btn.isEnabled()

        # 点击下一个按钮
        qtbot.mouseClick(dialog.next_btn, QtCore.Qt.LeftButton)
        qtbot.wait(500)

        # 验证当前匹配项已改变
        assert dialog._current_match == 1  # 从 0 移动到 1

        # 点击上一个按钮
        qtbot.mouseClick(dialog.prev_btn, QtCore.Qt.LeftButton)
        qtbot.wait(500)

        # 验证当前匹配项已改回
        assert dialog._current_match == 0  # 从 1 移动到 0
