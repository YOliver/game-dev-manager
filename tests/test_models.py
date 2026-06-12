"""测试核心数据模型：SpriteInfo, Project, RenameRule"""

import pytest
from gdm.core.models import SpriteInfo, Project, RenameRule, RenameMode


class TestSpriteInfo:
    """测试 SpriteInfo 数据类"""

    def test_create_sprite_info_with_all_fields(self):
        """测试使用所有字段创建 SpriteInfo"""
        sprite = SpriteInfo(
            file_path="/path/to/sprite.png",
            file_name="sprite.png",
            width=100,
            height=200,
            file_size=12345,
            format="PNG",
            color_mode="RGBA",
        )
        assert sprite.file_path == "/path/to/sprite.png"
        assert sprite.file_name == "sprite.png"
        assert sprite.width == 100
        assert sprite.height == 200
        assert sprite.file_size == 12345
        assert sprite.format == "PNG"
        assert sprite.color_mode == "RGBA"

    def test_sprite_info_field_access(self):
        """测试 SpriteInfo 字段访问"""
        sprite = SpriteInfo(
            file_path="C:/game/assets/player.webp",
            file_name="player.webp",
            width=64,
            height=64,
            file_size=4096,
            format="WebP",
            color_mode="RGB",
        )
        assert isinstance(sprite.width, int)
        assert isinstance(sprite.height, int)
        assert isinstance(sprite.file_size, int)
        assert sprite.format in ("PNG", "JPEG", "WebP")
        assert sprite.color_mode in ("RGB", "RGBA", "P")

    def test_sprite_info_repr(self):
        """测试 SpriteInfo 的字符串表示"""
        sprite = SpriteInfo(
            file_path="sprite.png",
            file_name="sprite.png",
            width=32,
            height=32,
            file_size=1024,
            format="PNG",
            color_mode="RGBA",
        )
        # dataclass 自动生成 __repr__，确认它包含类名
        assert "SpriteInfo" in repr(sprite)


class TestProject:
    """测试 Project 数据类"""

    def test_create_project_with_root_path(self):
        """测试使用根目录路径创建 Project"""
        project = Project(root_path="/workspace/game-project")
        assert project.root_path == "/workspace/game-project"

    def test_project_field_access(self):
        """测试 Project 字段访问"""
        project = Project(root_path="G:/UGit/my-game")
        assert isinstance(project.root_path, str)
        assert project.root_path == "G:/UGit/my-game"

    def test_project_repr(self):
        """测试 Project 的字符串表示"""
        project = Project(root_path="/root")
        assert "Project" in repr(project)


class TestRenameMode:
    """测试 RenameMode 枚举"""

    def test_rename_mode_values(self):
        """测试 RenameMode 枚举值"""
        assert RenameMode.PREFIX_NUMBER.value == "前缀+序号"
        assert RenameMode.FIND_REPLACE.value == "查找替换"
        assert RenameMode.REGEX.value == "正则替换"
        assert RenameMode.ADD_SUFFIX.value == "添加后缀"

    def test_rename_mode_members(self):
        """测试 RenameMode 包含所有预期成员"""
        expected_members = {"PREFIX_NUMBER", "FIND_REPLACE", "REGEX", "ADD_SUFFIX"}
        actual_members = {m.name for m in RenameMode}
        assert actual_members == expected_members


class TestRenameRule:
    """测试 RenameRule 数据类"""

    def test_create_rename_rule_prefix_number(self):
        """测试创建前缀+序号模式的 RenameRule"""
        rule = RenameRule(
            mode=RenameMode.PREFIX_NUMBER,
            prefix="sprite_",
            start_index=1,
            padding=3,
        )
        assert rule.mode == RenameMode.PREFIX_NUMBER
        assert rule.prefix == "sprite_"
        assert rule.start_index == 1
        assert rule.padding == 3

    def test_create_rename_rule_find_replace(self):
        """测试创建查找替换模式的 RenameRule"""
        rule = RenameRule(
            mode=RenameMode.FIND_REPLACE,
            find_text="old",
            replace_text="new",
        )
        assert rule.mode == RenameMode.FIND_REPLACE
        assert rule.find_text == "old"
        assert rule.replace_text == "new"

    def test_create_rename_rule_regex(self):
        """测试创建正则替换模式的 RenameRule"""
        rule = RenameRule(
            mode=RenameMode.REGEX,
            regex_pattern=r"frame_(\d+)",
            regex_replacement=r"anim_\1",
        )
        assert rule.mode == RenameMode.REGEX
        assert rule.regex_pattern == r"frame_(\d+)"
        assert rule.regex_replacement == r"anim_\1"

    def test_create_rename_rule_add_suffix(self):
        """测试创建添加后缀模式的 RenameRule"""
        rule = RenameRule(
            mode=RenameMode.ADD_SUFFIX,
            suffix="_v2",
        )
        assert rule.mode == RenameMode.ADD_SUFFIX
        assert rule.suffix == "_v2"

    def test_rename_rule_default_values(self):
        """测试 RenameRule 默认值"""
        rule = RenameRule(mode=RenameMode.PREFIX_NUMBER)
        assert rule.prefix is None
        assert rule.start_index == 1
        assert rule.padding == 3
        assert rule.find_text is None
        assert rule.replace_text is None
        assert rule.regex_pattern is None
        assert rule.regex_replacement is None
        assert rule.suffix is None

    def test_rename_rule_repr(self):
        """测试 RenameRule 的字符串表示"""
        rule = RenameRule(mode=RenameMode.ADD_SUFFIX, suffix="_test")
        assert "RenameRule" in repr(rule)
