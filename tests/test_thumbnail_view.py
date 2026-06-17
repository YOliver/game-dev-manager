"""测试缩略图网格自适应排列和计数标签。"""

import os
import pytest
from PySide6.QtWidgets import QApplication

from gdm.core.models import SpriteInfo


@pytest.fixture(scope="session", autouse=True)
def qapp():
    """创建 QApplication 实例。"""
    if QApplication.instance() is None:
        app = QApplication([])
    else:
        app = QApplication.instance()
    yield app


def test_constants():
    """验证模块常量的合理性。"""
    from gdm.gui.thumbnail_view import MIN_WIDTH, MAX_WIDTH, BASE_GRID_WIDTH, SPACING

    assert MIN_WIDTH < MAX_WIDTH
    assert BASE_GRID_WIDTH == 160
    assert MIN_WIDTH == 140
    assert MAX_WIDTH == 176
    assert SPACING == 8


def test_calculate_grid_normal():
    """正常宽度下，网格宽度应在合理范围内。"""
    from gdm.gui.thumbnail_view import ThumbnailView

    # available=1000 → 5 cols initial → 192px → >MAX_WIDTH → 6 cols → 158px
    grid_w, cols = ThumbnailView._calculate_grid(1000)
    assert cols == 6
    assert 140 <= grid_w <= 176
    # 可用宽度 / cols - SPACING 应与 grid_w 匹配
    assert grid_w == 1000 // cols - 8


def test_calculate_grid_very_narrow():
    """极窄窗口应 clamp 到 MIN_WIDTH。"""
    from gdm.gui.thumbnail_view import ThumbnailView

    # available=50 → 1 col → 42px → <MIN_WIDTH → 1 col → 42px → clamp to 140
    grid_w, cols = ThumbnailView._calculate_grid(50)
    assert cols == 1
    assert grid_w == 140  # clamped to MIN_WIDTH


def test_calculate_grid_very_wide():
    """超宽窗口网格宽度不超过 MAX_WIDTH。"""
    from gdm.gui.thumbnail_view import ThumbnailView

    grid_w, cols = ThumbnailView._calculate_grid(3000)
    assert grid_w <= 176
    assert cols > 15


def test_calculate_grid_just_right():
    """available_width 刚好整除时，应求整对齐。"""
    from gdm.gui.thumbnail_view import ThumbnailView

    # 168 * 6 = 1008 → 刚好 6 列时的宽度
    grid_w, cols = ThumbnailView._calculate_grid(1008)
    # 6 cols → 1008//6 - 8 = 160
    assert grid_w == 160
    assert cols == 6


def test_calculate_grid_zero_width():
    """零宽度或负宽度应返回兜底值。"""
    from gdm.gui.thumbnail_view import ThumbnailView

    grid_w_0, cols_0 = ThumbnailView._calculate_grid(0)
    assert grid_w_0 == 160
    assert cols_0 == 1

    grid_w_neg, cols_neg = ThumbnailView._calculate_grid(-10)
    assert grid_w_neg == 160
    assert cols_neg == 1


# ---- 计数标签测试 ----


@pytest.fixture
def thumbnail_view(qtbot):
    from gdm.gui.thumbnail_view import ThumbnailView
    view = ThumbnailView()
    qtbot.addWidget(view)
    return view


@pytest.fixture
def sample_sprites():
    return [
        SpriteInfo(
            file_path=os.path.join("/test", f"sprite_{i:03d}.png"),
            file_name=f"sprite_{i:03d}.png",
            width=64, height=64,
            file_size=1024, format="PNG", color_mode="RGBA",
        )
        for i in range(5)
    ]


def test_count_label_initial(thumbnail_view):
    """初始状态计数应为 0。"""
    assert thumbnail_view._count_label.text() == "0"


def test_count_label_after_load(thumbnail_view, sample_sprites):
    """加载精灵图后计数应正确。"""
    thumbnail_view.load(sample_sprites)
    assert thumbnail_view._count_label.text() == str(len(sample_sprites))


def test_count_label_after_remove(thumbnail_view, sample_sprites):
    """删除项后计数应减少。"""
    thumbnail_view.load(sample_sprites)
    keys = [
        (os.path.dirname(s.file_path), s.file_name)
        for s in sample_sprites[:2]
    ]
    thumbnail_view.apply_entries_removed(keys)
    assert thumbnail_view._count_label.text() == str(len(sample_sprites) - 2)


# ---- 前缀提取测试 ----


class TestExtractPrefix:
    """测试 _extract_prefix() 前缀提取。"""

    def test_extract_with_number_suffix(self):
        from gdm.gui.thumbnail_view import ThumbnailView
        assert ThumbnailView._extract_prefix("character_idle_001.png") == "character_idle"
        assert ThumbnailView._extract_prefix("enemy_boss_02.png") == "enemy_boss"
        assert ThumbnailView._extract_prefix("sprite_1.png") == "sprite"

    def test_extract_no_number_returns_other(self):
        from gdm.gui.thumbnail_view import ThumbnailView
        assert ThumbnailView._extract_prefix("icon.png") == "其他"
        assert ThumbnailView._extract_prefix("UI_button.png") == "其他"
        assert ThumbnailView._extract_prefix("bg.png") == "其他"

    def test_extract_multi_underscore(self):
        from gdm.gui.thumbnail_view import ThumbnailView
        assert ThumbnailView._extract_prefix("player_run_left_001.png") == "player_run_left"
