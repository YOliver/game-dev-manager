"""测试 gdm.utils.helpers 工具函数。"""

from pathlib import Path
import pytest
from gdm.utils.helpers import is_hidden


class TestIsHidden:
    def test_hidden_file_with_dot_prefix(self):
        """文件名以 . 开头应返回 True。"""
        assert is_hidden(Path("._Example.png")) is True
        assert is_hidden(Path(".hidden.jpg")) is True

    def test_normal_file_returns_false(self):
        """普通文件名应返回 False。"""
        assert is_hidden(Path("sprite.png")) is False
        assert is_hidden(Path("photo.jpg")) is False

    def test_hidden_file_in_subdirectory(self):
        """子目录中的隐藏文件也应识别。"""
        p = Path("assets/sprites/._hidden.png")
        assert is_hidden(p) is True

    def test_normal_file_in_subdirectory(self):
        """子目录中的普通文件应返回 False。"""
        p = Path("assets/sprites/normal.png")
        assert is_hidden(p) is False

    def test_hidden_directory_is_not_hidden_file(self):
        """目录名以 . 开头应返回 False（传入的是目录路径时）。"""
        p = Path(".__MACOSX/normal.png")
        # 注意：这里传入的是目录路径下的文件，文件名是 normal.png，应返回 False
        assert is_hidden(p) is False
        # 但如果直接传入目录路径，name 就是目录名
        assert is_hidden(Path(".__MACOSX")) is True
