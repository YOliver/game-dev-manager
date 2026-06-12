# 缩略图自适应网格排列 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将缩略图网格宽度 `GRID_WIDTH` 从固定常量（160px）改为窗口宽度自适应计算，缩放窗口时每行能尽可能填满。

**Architecture:** 仅修改 `gdm/gui/thumbnail_view.py` 一个文件。核心变化：(1) 提取网格计算为静态方法 `_calculate_grid(available_width)`，(2) `ThumbnailDelegate` 的绘制改为读取 `rect.width()` 而不是全局常量，(3) `ThumbnailView` 重写 `resizeEvent` 加防抖触发 `_relayout()` 更新网格。

**Tech Stack:** PySide6 (QListWidget IconMode, QTimer, QStyledItemDelegate)

---

### Task 1: 添加动态网格常量与计算逻辑（含测试）

**Files:**
- Create: `tests/test_thumbnail_view.py`
- Modify: `gdm/gui/thumbnail_view.py`

- [ ] **Step 1: 添加 qapp fixture 和常量定义测试**

    创建 `tests/test_thumbnail_view.py`，添加 session 级别的 `qapp` fixture：

    ```python
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
    ```

- [ ] **Step 2: 编写 _calculate_grid 的预期常量测试（先确认常量值）**

    ```python
    def test_constants():
        """验证模块常量的合理性。"""
        from gdm.gui.thumbnail_view import MIN_WIDTH, MAX_WIDTH, BASE_GRID_WIDTH, SPACING

        assert MIN_WIDTH < MAX_WIDTH
        assert BASE_GRID_WIDTH == 160
        assert MIN_WIDTH == 140
        assert MAX_WIDTH == 176
        assert SPACING == 8
    ```

- [ ] **Step 3: 运行测试，确认因缺少常量而失败**

    运行：`pytest tests/test_thumbnail_view.py::test_constants -v`
    预期：`FAILED` — ImportError: cannot import name 'MIN_WIDTH'

- [ ] **Step 4: 在 thumbnail_view.py 中添加新常量**

    在文件顶部常量区域（`ICON_SIZE = 128` 之后）添加：

    ```python
    MIN_WIDTH = 140           # 网格最小宽度（像素），保证文字区可读
    MAX_WIDTH = 176           # 网格最大宽度（像素），防止间距过大
    BASE_GRID_WIDTH = 160     # 基础网格宽度，用于初始列数推算
    ```

    注意：删除旧的 `GRID_WIDTH = 160` 定义（它会被动态值替代）。

- [ ] **Step 5: 再次运行常量测试**

    运行：`pytest tests/test_thumbnail_view.py::test_constants -v`
    预期：`PASSED`

- [ ] **Step 6: 编写 _calculate_grid 的计算测试**

    ```python
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
    ```

- [ ] **Step 7: 运行计算测试，确认因缺少 _calculate_grid 而失败**

    运行：`pytest tests/test_thumbnail_view.py -v`
    预期：`FAILED` — AttributeError: type object 'ThumbnailView' has no attribute '_calculate_grid'

- [ ] **Step 8: 在 ThumbnailView 中添加 _calculate_grid 静态方法**

    在 `ThumbnailView.__init__` 之前（或类中合适位置）添加：

    ```python
    @staticmethod
    def _calculate_grid(available_width: int) -> tuple[int, int]:
        """根据可用宽度计算网格宽度和列数。

        Args:
            available_width: QListWidget viewport 可用宽度（像素）

        Returns:
            (grid_width, cols) 元组，grid_width 在 [MIN_WIDTH, MAX_WIDTH] 范围内
        """
        if available_width <= 0:
            return BASE_GRID_WIDTH, 1

        # 1. 粗算列数
        cols = max(1, available_width // (BASE_GRID_WIDTH + SPACING))

        # 2. 试算网格宽度
        grid_width = (available_width // cols) - SPACING

        # 3. 如超出范围，调整列数后重算
        if grid_width > MAX_WIDTH:
            cols += 1
            grid_width = (available_width // cols) - SPACING
        elif grid_width < MIN_WIDTH and cols > 1:
            cols -= 1
            grid_width = (available_width // cols) - SPACING

        # 4. 最终 clamp 保底
        grid_width = max(MIN_WIDTH, min(MAX_WIDTH, grid_width))
        return grid_width, cols
    ```

    同时在 __init__ 顶部添加 `QTimer` 的 import：

    ```python
    # 文件顶部 import 块中，在 QtCore 导入行追加 QTimer
    from PySide6.QtCore import QModelIndex, QObject, QRect, QRunnable, QSize, Qt, QThreadPool, QTimer, Signal
    ```

- [ ] **Step 9: 运行计算测试，确认全部通过**

    运行：`pytest tests/test_thumbnail_view.py -v`
    预期：4 个测试全部 `PASSED`

- [ ] **Step 10: Commit**

    ```bash
    git add tests/test_thumbnail_view.py gdm/gui/thumbnail_view.py
    git commit -m "feat: 添加自适应网格宽度计算逻辑与常量

    - 删除硬编码 GRID_WIDTH，替换为 MIN_WIDTH/MAX_WIDTH/BASE_GRID_WIDTH
    - 添加 ThumbnailView._calculate_grid() 静态方法
    - 新增 tests/test_thumbnail_view.py

    Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
    ```

---

### Task 2: 更新 ThumbnailDelegate 使用动态宽度

**Files:**
- Modify: `gdm/gui/thumbnail_view.py`

- [ ] **Step 1: 给 ThumbnailDelegate 添加 grid_width 属性**

    在 `__init__` 末尾添加 `_grid_width` 实例变量：

    ```python
    class ThumbnailDelegate(QStyledItemDelegate):
        def __init__(self, parent: Optional[QWidget] = None) -> None:
            super().__init__(parent)
            self._grid_width = BASE_GRID_WIDTH  # 默认值
    ```

- [ ] **Step 2: 更新 sizeHint() 使用实例变量**

    ```python
    def sizeHint(
        self,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> QSize:
        """返回当前网格宽度（由 ThumbnailView 更新）。"""
        return QSize(self._grid_width, GRID_HEIGHT)
    ```

- [ ] **Step 3: 更新 paint() 使用 rect.width() 替代 GRID_WIDTH**

    找到 `paint()` 方法中所有出现 `GRID_WIDTH` 的地方，用 `rect.width()` 替换：

    ```python
    def paint(self, painter, option, index):
        painter.save()

        rect = option.rect
        icon_rect = QRect(
            rect.x() + (rect.width() - ICON_SIZE) // 2,  # ← 替换 GRID_WIDTH
            rect.y() + 8,
            ICON_SIZE,
            ICON_SIZE,
        )
        text_rect = QRect(
            rect.x() + 4,
            rect.y() + 8 + ICON_SIZE + 4,
            rect.width() - 8,    # ← 替换 GRID_WIDTH - 8
            TEXT_HEIGHT - 4,
        )

        # ... 其余不变
    ```

- [ ] **Step 4: 验证现有的测试没有破坏**

    运行：`pytest tests/test_thumbnail_view.py -v`
    预期：4 个测试全部 `PASSED`

- [ ] **Step 5: Commit**

    ```bash
    git add gdm/gui/thumbnail_view.py
    git commit -m "refactor: 更新 ThumbnailDelegate 使用动态网格宽度

    - sizeHint() 返回实例变量 _grid_width
    - paint() 使用 rect.width() 替代硬编码 GRID_WIDTH
    - 默认 _grid_width = BASE_GRID_WIDTH

    Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
    ```

---

### Task 3: 添加 _relayout 与 resize 响应

**Files:**
- Modify: `gdm/gui/thumbnail_view.py`

- [ ] **Step 1: 在 ThumbnailView.__init__ 中添加防抖定时器**

    在 `self._init_ui()` 调用之后（或内部合适位置）添加：

    ```python
    # 防抖定时器：窗口连续 resize 时延迟触发布局重排
    self._relayout_timer = QTimer(self)
    self._relayout_timer.setSingleShot(True)
    self._relayout_timer.setInterval(80)
    self._relayout_timer.timeout.connect(self._relayout)
    ```

- [ ] **Step 2: 添加 _relayout() 方法**

    ```python
    def _relayout(self) -> None:
        """根据当前视图宽度重新计算并应用网格布局。

        计算最优网格宽度，更新 delegate，保留滚动位置。
        """
        if not self._sprites:
            return

        available_width = self._list_widget.viewport().width()
        grid_width, _ = self._calculate_grid(available_width)

        # 更新委托的网格宽度（确保 sizeHint 返回正确值）
        self._delegate._grid_width = grid_width

        # 保存滚动位置
        scroll_pos = self._list_widget.verticalScrollBar().value()

        # 应用新网格大小
        self._list_widget.setGridSize(QSize(grid_width, GRID_HEIGHT))

        # 恢复滚动位置
        self._list_widget.verticalScrollBar().setValue(scroll_pos)
    ```

- [ ] **Step 3: 重写 resizeEvent**

    ```python
    def resizeEvent(self, event) -> None:
        """窗口尺寸变化时，防抖触发布局重排。"""
        super().resizeEvent(event)
        self._relayout_timer.start()
    ```

- [ ] **Step 4: 验证代码可导入且无语法错误**

    运行：`python -c "from gdm.gui.thumbnail_view import ThumbnailView; print('OK')"`
    预期：输出 `OK`

- [ ] **Step 5: Commit**

    ```bash
    git add gdm/gui/thumbnail_view.py
    git commit -m "feat: 添加 _relayout 与 resizeEvent 防抖响应

    - resizeEvent 中启动 80ms 单次定时器
    - _relayout() 计算最优网格宽度 → setGridSize → 恢复滚动位置
    - 空数据时跳过重排

    Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
    ```

---

### Task 4: 更新 load() 触发初始重排

**Files:**
- Modify: `gdm/gui/thumbnail_view.py`

- [ ] **Step 1: 在 load() 末尾添加 _relayout() 调用**

    找到 `load()` 方法的末尾（在异步加载循环之后），追加：

    ```python
    def load(self, sprites: List[SpriteInfo]) -> None:
        """加载精灵图列表到网格视图。"""
        self._sprites = list(sprites)
        # ... 其余代码不变 ...

        # 异步加载所有缩略图
        for sprite in sprites:
            self._load_thumbnail_async(sprite)

        # 根据当前窗口宽度进行自适应排列
        self._relayout()
    ```

- [ ] **Step 2: 验证现有测试全部通过**

    运行：`pytest tests/test_thumbnail_view.py -v`
    预期：4 个测试全部 `PASSED`

- [ ] **Step 3: Commit**

    ```bash
    git add gdm/gui/thumbnail_view.py
    git commit -m "feat: load() 末尾触发 _relayout() 自适应排列

    - 加载精灵图后立即根据当前窗口宽度自适应网格

    Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
    ```

---

### Task 5: 手动测试验证

- [ ] **Step 1: 启动应用**

    运行：`python -m gdm.main`
    预期：应用正常启动

- [ ] **Step 2: 打开含多张图片的文件夹**

    操作：菜单 → 文件 → 打开文件夹 → 选择一个图片文件夹
    预期：缩略图按网格排列，行末无明显空白

- [ ] **Step 3: 拖拽窗口宽度**

    操作：左右拖拽窗口边缘，观察缩略图排列
    预期：
    - 窗口变宽时，每行格数增加，行末空白减少
    - 窗口变窄时，每行格数减少，不会出现横向滚动条
    - 连续拖拽时无闪烁（防抖生效）
    - 停止拖拽后布局短暂延迟（~80ms）后更新

- [ ] **Step 4: 检查超长文件名**

    操作：选择包含超长文件名的图片，确认在动态宽度下省略号正常工作
    预期：文件名显示在网格下方，超长时以 `...` 省略

- [ ] **Step 5: 检查滚动位置**

    操作：先滚动到较后的位置，再拖拽窗口宽度
    预期：重排后滚动位置保持在原来的浏览位置附近

- [ ] **Step 6: 检查极端窄窗口**

    操作：将窗口缩到最小（宽度 < 300px）
    预期：仍能看到 1 列缩略图，网格不崩
