"""Tests for help_dialog module."""

import os
import sys
import pytest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from gdm.gui.help_dialog import get_help_doc_path


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
