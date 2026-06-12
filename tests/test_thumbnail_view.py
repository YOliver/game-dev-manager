"""测试缩略图网格自适应排列。"""

import pytest
from PySide6.QtWidgets import QApplication


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
