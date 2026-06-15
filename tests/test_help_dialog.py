"""Tests for help_dialog module."""

import os
import sys
import pytest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from gdm.gui.help_dialog import get_help_doc_path, md_to_html


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
