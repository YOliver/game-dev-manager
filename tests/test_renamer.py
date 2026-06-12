"""renamer.py 的测试"""

import os
import tempfile
import pytest
from gdm.core.models import SpriteInfo, RenameRule, RenameMode
from gdm.core.renamer import preview, execute


def _make_sprite(file_path: str) -> SpriteInfo:
    """构造 SpriteInfo 对象（仅用于测试）"""
    return SpriteInfo(
        file_path=file_path,
        file_name=os.path.basename(file_path),
        width=100,
        height=100,
        file_size=1000,
        format="PNG",
        color_mode="RGBA",
    )


def _expected_path(directory: str, file_name: str) -> str:
    """构造跨平台预期路径"""
    return os.path.join(directory, file_name)


_TMPDIR = os.path.join("tests", "fixtures", "renamer_preview")


class TestPreview:
    """preview() 测试"""

    def test_prefix_number_mode(self):
        """前缀+序号模式：生成正确的新文件名"""
        sprites = [
            _make_sprite(os.path.join(_TMPDIR, "char_a.png")),
            _make_sprite(os.path.join(_TMPDIR, "char_b.png")),
            _make_sprite(os.path.join(_TMPDIR, "char_c.png")),
        ]
        rule = RenameRule(
            mode=RenameMode.PREFIX_NUMBER,
            prefix="sprite",
            start_index=1,
            padding=3,
        )

        results = preview(sprites, rule)

        assert len(results) == 3
        assert results[0] == (
            os.path.join(_TMPDIR, "char_a.png"),
            os.path.join(_TMPDIR, "sprite_001.png"),
        )
        assert results[1] == (
            os.path.join(_TMPDIR, "char_b.png"),
            os.path.join(_TMPDIR, "sprite_002.png"),
        )
        assert results[2] == (
            os.path.join(_TMPDIR, "char_c.png"),
            os.path.join(_TMPDIR, "sprite_003.png"),
        )

    def test_prefix_number_mode_custom_start(self):
        """前缀+序号模式：自定义起始序号"""
        sprites = [
            _make_sprite(os.path.join(_TMPDIR, "frame.png")),
            _make_sprite(os.path.join(_TMPDIR, "frame.png")),
        ]
        rule = RenameRule(
            mode=RenameMode.PREFIX_NUMBER,
            prefix="frame",
            start_index=10,
            padding=2,
        )

        results = preview(sprites, rule)

        assert results[0] == (
            os.path.join(_TMPDIR, "frame.png"),
            os.path.join(_TMPDIR, "frame_10.png"),
        )
        assert results[1] == (
            os.path.join(_TMPDIR, "frame.png"),
            os.path.join(_TMPDIR, "frame_11.png"),
        )

    def test_find_replace_mode(self):
        """查找替换模式：正确替换文件名中的文本"""
        sprites = [
            _make_sprite(os.path.join(_TMPDIR, "old_hero.png")),
            _make_sprite(os.path.join(_TMPDIR, "old_enemy.png")),
        ]
        rule = RenameRule(
            mode=RenameMode.FIND_REPLACE,
            find_text="old",
            replace_text="new",
        )

        results = preview(sprites, rule)

        assert results[0] == (
            os.path.join(_TMPDIR, "old_hero.png"),
            os.path.join(_TMPDIR, "new_hero.png"),
        )
        assert results[1] == (
            os.path.join(_TMPDIR, "old_enemy.png"),
            os.path.join(_TMPDIR, "new_enemy.png"),
        )

    def test_find_replace_mode_no_match(self):
        """查找替换模式：无匹配时返回原文件名"""
        sprites = [_make_sprite(os.path.join(_TMPDIR, "hero.png"))]
        rule = RenameRule(
            mode=RenameMode.FIND_REPLACE,
            find_text="not_exist",
            replace_text="new",
        )

        results = preview(sprites, rule)

        assert results[0] == (
            os.path.join(_TMPDIR, "hero.png"),
            os.path.join(_TMPDIR, "hero.png"),
        )

    def test_add_suffix_mode(self):
        """添加后缀模式：在文件名后扩展名前添加后缀"""
        sprites = [_make_sprite(os.path.join(_TMPDIR, "hero.png"))]
        rule = RenameRule(
            mode=RenameMode.ADD_SUFFIX,
            suffix="_v2",
        )

        results = preview(sprites, rule)

        assert results[0] == (
            os.path.join(_TMPDIR, "hero.png"),
            os.path.join(_TMPDIR, "hero_v2.png"),
        )

    def test_regex_mode(self):
        """正则替换模式：使用正则表达式替换"""
        sprites = [_make_sprite(os.path.join(_TMPDIR, "frame_001.png"))]
        rule = RenameRule(
            mode=RenameMode.REGEX,
            regex_pattern=r"frame_(\d+)",
            regex_replacement=r"anim_\1",
        )

        results = preview(sprites, rule)

        assert results[0] == (
            os.path.join(_TMPDIR, "frame_001.png"),
            os.path.join(_TMPDIR, "anim_001.png"),
        )


class TestExecute:
    """execute() 测试"""

    def test_execute_success(self):
        """成功重命名文件，返回正确结果"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建测试文件
            file1 = os.path.join(tmpdir, "char_a.png")
            file2 = os.path.join(tmpdir, "char_b.png")
            with open(file1, "w") as f:
                f.write("test")
            with open(file2, "w") as f:
                f.write("test")

            sprites = [
                SpriteInfo(
                    file_path=file1,
                    file_name="char_a.png",
                    width=100,
                    height=100,
                    file_size=1000,
                    format="PNG",
                    color_mode="RGBA",
                ),
                SpriteInfo(
                    file_path=file2,
                    file_name="char_b.png",
                    width=100,
                    height=100,
                    file_size=1000,
                    format="PNG",
                    color_mode="RGBA",
                ),
            ]
            rule = RenameRule(
                mode=RenameMode.PREFIX_NUMBER,
                prefix="sprite",
                start_index=1,
                padding=3,
            )

            success_count, old_paths = execute(sprites, rule)

            assert success_count == 2
            assert len(old_paths) == 2
            assert os.path.exists(os.path.join(tmpdir, "sprite_001.png"))
            assert os.path.exists(os.path.join(tmpdir, "sprite_002.png"))
            assert not os.path.exists(file1)
            assert not os.path.exists(file2)
            # SpriteInfo 对象已更新
            assert sprites[0].file_name == "sprite_001.png"
            assert sprites[1].file_name == "sprite_002.png"

    def test_execute_skip_if_target_exists(self):
        """目标文件已存在时跳过，不覆盖"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建原始文件和已存在的目标文件
            file1 = os.path.join(tmpdir, "char_a.png")
            target = os.path.join(tmpdir, "sprite_001.png")
            with open(file1, "w") as f:
                f.write("original")
            with open(target, "w") as f:
                f.write("existing")

            sprites = [
                SpriteInfo(
                    file_path=file1,
                    file_name="char_a.png",
                    width=100,
                    height=100,
                    file_size=1000,
                    format="PNG",
                    color_mode="RGBA",
                ),
            ]
            rule = RenameRule(
                mode=RenameMode.PREFIX_NUMBER,
                prefix="sprite",
                start_index=1,
                padding=3,
            )

            success_count, old_paths = execute(sprites, rule)

            # 应跳过，不重命名
            assert success_count == 0
            assert len(old_paths) == 0
            assert os.path.exists(file1)  # 原文件仍存在
            assert open(target).read() == "existing"  # 目标文件未被覆盖

    def test_execute_returns_correct_old_paths(self):
        """execute() 返回的旧路径列表正确"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, "a.png")
            file2 = os.path.join(tmpdir, "b.png")
            with open(file1, "w") as f:
                f.write("test")
            with open(file2, "w") as f:
                f.write("test")

            sprites = [
                SpriteInfo(
                    file_path=file1,
                    file_name="a.png",
                    width=100,
                    height=100,
                    file_size=1000,
                    format="PNG",
                    color_mode="RGBA",
                ),
                SpriteInfo(
                    file_path=file2,
                    file_name="b.png",
                    width=100,
                    height=100,
                    file_size=1000,
                    format="PNG",
                    color_mode="RGBA",
                ),
            ]
            rule = RenameRule(
                mode=RenameMode.FIND_REPLACE,
                find_text=".png",
                replace_text="_new.png",
            )

            success_count, old_paths = execute(sprites, rule)

            assert success_count == 2
            assert old_paths == [file1, file2]
