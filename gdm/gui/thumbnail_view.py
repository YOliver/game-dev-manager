"""缩略图网格视图

使用 QListWidget（Icon Mode）实现精灵图缩略图网格，
支持异步加载缩略图，避免阻塞 UI。

使用自定义委托（ThumbnailDelegate）确保缩略图严格按方格排列，
所有图标统一为 128x128 正方形显示，文件名居中对齐。
"""

import os
from typing import Dict, List, Optional

from PySide6.QtCore import QModelIndex, QObject, QRect, QRunnable, QSize, Qt, QThreadPool, Signal
from PySide6.QtGui import QColor, QFontMetrics, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QListWidget,
    QListWidgetItem,
    QStyledItemDelegate,
    QWidget,
    QVBoxLayout,
    QStyle,
)

from gdm.core.models import SpriteInfo


# 常量定义
ICON_SIZE = 128          # 图标显示大小（像素）
TEXT_HEIGHT = 40          # 文件名区域高度（像素）
MIN_WIDTH = 140           # 网格最小宽度（像素），保证文字区可读
MAX_WIDTH = 176           # 网格最大宽度（像素），防止间距过大
BASE_GRID_WIDTH = 160     # 基础网格宽度，用于初始列数推算
GRID_HEIGHT = 184        # 网格高度 = 图标128 + 文字40 + 上下padding各8
SPACING = 8             # 网格间距（像素）


class _WorkerSignals(QObject):
    """Worker 内部信号类（必须在 QRunnable 外部定义，否则无法 emit）。"""

    finished = Signal(str, object)  # file_path, QImage | None


class ThumbnailLoadWorker(QRunnable):
    """异步加载缩略图的 Worker（QRunnable + QThreadPool）。

    在工作线程中加载图片为 QImage（线程安全），
    通过信号将结果传递到主线程后转换为 QPixmap。
    """

    def __init__(self, sprite: SpriteInfo, target_size: int = ICON_SIZE) -> None:
        super().__init__()
        self.sprite = sprite
        self.target_size = target_size
        self.signals = _WorkerSignals()

    def run(self) -> None:
        """在工作线程中加载图片并缩放到目标尺寸。"""
        file_path = self.sprite.file_path
        image = QImage(file_path)

        if image.isNull():
            # 创建灰色占位缩略图
            image = QImage(
                self.target_size,
                self.target_size,
                QImage.Format.Format_ARGB32,
            )
            image.fill(Qt.GlobalColor.Gray)
        else:
            # 缩放到目标尺寸（保持宽高比，居中放置到正方形画布）
            scaled = image.scaled(
                QSize(self.target_size, self.target_size),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            # 创建正方形画布（透明背景）
            square_image = QImage(
                self.target_size,
                self.target_size,
                QImage.Format.Format_ARGB32,
            )
            square_image.fill(QColor(0, 0, 0, 0))  # 透明
            # 居中绘制
            x = (self.target_size - scaled.width()) // 2
            y = (self.target_size - scaled.height()) // 2
            painter = QPainter(square_image)
            painter.drawImage(x, y, scaled)
            painter.end()
            image = square_image

        # 附加文件修改时间，供缓存验证使用
        try:
            image._cache_mtime: Optional[float] = os.path.getmtime(file_path)
        except OSError:
            image._cache_mtime = None

        self.signals.finished.emit(file_path, image)


class ThumbnailDelegate(QStyledItemDelegate):
    """自定义委托，确保缩略图严格按方格排列显示。

    每个项占据固定大小（GRID_WIDTH x GRID_HEIGHT）：
    - 图标区域：ICON_SIZE x ICON_SIZE（居中显示）
    - 文本区域：GRID_WIDTH x TEXT_HEIGHT（居中对齐，超长省略）
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,  # type: ignore[name-defined]
        index: QModelIndex,  # type: ignore[name-defined]
    ) -> None:
        """绘制列表项（图标 + 文件名）。"""
        # 保存 painter 状态
        painter.save()

        # 计算绘制区域
        rect = option.rect
        icon_rect = QRect(
            rect.x() + (GRID_WIDTH - ICON_SIZE) // 2,
            rect.y() + 8,
            ICON_SIZE,
            ICON_SIZE,
        )
        text_rect = QRect(
            rect.x() + 4,
            rect.y() + 8 + ICON_SIZE + 4,
            GRID_WIDTH - 8,
            TEXT_HEIGHT - 4,
        )

        # 绘制选中背景
        if option.state & QStyle.State_Selected:  # type: ignore[attr-defined]
            painter.fillRect(rect, option.palette.highlight())
            painter.setPen(option.palette.highlightedText().color())
        else:
            painter.setPen(option.palette.text().color())

        # 绘制图标
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        if icon is not None:
            if isinstance(icon, QIcon):
                pixmap = icon.pixmap(QSize(ICON_SIZE, ICON_SIZE))
            elif isinstance(icon, QPixmap):
                pixmap = icon.scaled(
                    QSize(ICON_SIZE, ICON_SIZE),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            else:
                pixmap = QPixmap(ICON_SIZE, ICON_SIZE)
                pixmap.fill(Qt.GlobalColor.Gray)
            painter.drawPixmap(icon_rect, pixmap)

        # 绘制文件名（居中，超长省略）
        text = index.data(Qt.ItemDataRole.DisplayRole)
        if text is not None:
            font_metrics = QFontMetrics(painter.font())
            elided_text = font_metrics.elidedText(
                text, Qt.TextElideMode.ElideRight, text_rect.width()
            )
            painter.drawText(
                text_rect, Qt.AlignmentFlag.AlignCenter, elided_text
            )

        # 恢复 painter 状态
        painter.restore()

    def sizeHint(
        self,
        option: QStyleOptionViewItem,  # type: ignore[name-defined]
        index: QModelIndex,  # type: ignore[name-defined]
    ) -> QSize:
        """返回固定大小，确保所有项排列整齐。"""
        return QSize(GRID_WIDTH, GRID_HEIGHT)


class ThumbnailView(QWidget):
    """缩略图网格视图。

    使用 QListWidget（Icon Mode）显示精灵图缩略图网格，
    使用 ThumbnailDelegate 确保严格按方格排列。

    信号：
        selection_changed(SpriteInfo): 选中项变化时发射，携带对应的 SpriteInfo 对象
    """

    selection_changed = Signal(object)

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

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        # 缩略图内存缓存：file_path -> QPixmap
        self._thumbnails: Dict[str, QPixmap] = {}
        # 当前加载的精灵图列表
        self._sprites: List[SpriteInfo] = []
        # file_path -> QListWidgetItem 映射
        self._items: Dict[str, QListWidgetItem] = {}
        # 正在加载中的 worker（防止重复提交）
        self._pending_workers: Dict[str, ThumbnailLoadWorker] = {}

        self._init_ui()

    def _init_ui(self) -> None:
        """初始化 UI 组件。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._list_widget = QListWidget(self)
        self._list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        self._list_widget.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self._list_widget.setGridSize(QSize(GRID_WIDTH, GRID_HEIGHT))
        self._list_widget.setSpacing(SPACING)
        self._list_widget.setUniformItemSizes(True)
        self._list_widget.setWordWrap(False)
        self._list_widget.setSelectionMode(
            QListWidget.SelectionMode.SingleSelection
        )

        # 使用自定义委托确保严格对齐
        self._delegate = ThumbnailDelegate(self)
        self._list_widget.setItemDelegate(self._delegate)

        self._list_widget.itemSelectionChanged.connect(self._on_selection_changed)

        layout.addWidget(self._list_widget)

    def load(self, sprites: List[SpriteInfo]) -> None:
        """加载精灵图列表到网格视图。

        Args:
            sprites: 精灵图信息列表
        """
        self._sprites = list(sprites)
        self._items.clear()
        self._pending_workers.clear()
        self._list_widget.clear()

        for sprite in sprites:
            item = QListWidgetItem(sprite.file_name)
            item.setData(Qt.ItemDataRole.UserRole, sprite)
            self._list_widget.addItem(item)
            self._items[sprite.file_path] = item

        # 异步加载所有缩略图
        for sprite in sprites:
            self._load_thumbnail_async(sprite)

    def _load_thumbnail_async(self, sprite: SpriteInfo) -> None:
        """异步加载单个精灵图的缩略图。

        先检查内存缓存是否有效，命中则直接设置图标；
        未命中则提交 Worker 到线程池进行异步加载。
        """
        file_path = sprite.file_path

        # 检查缓存
        if file_path in self._thumbnails:
            cached = self._thumbnails[file_path]
            if self._is_cache_valid(file_path, cached):
                item = self._items.get(file_path)
                if item is not None:
                    item.setIcon(QIcon(cached))
                return

        # 防止重复提交
        if file_path in self._pending_workers:
            return

        worker = ThumbnailLoadWorker(sprite)
        worker.signals.finished.connect(self._on_thumbnail_loaded)
        self._pending_workers[file_path] = worker
        QThreadPool.globalInstance().start(worker)

    def _is_cache_valid(self, file_path: str, pixmap: QPixmap) -> bool:
        """检查缓存是否有效（通过文件修改时间）。

        Args:
            file_path: 图片文件路径
            pixmap: 缓存的 QPixmap 对象（附带有 _cache_mtime 属性）

        Returns:
            缓存有效返回 True，否则返回 False
        """
        try:
            current_mtime = os.path.getmtime(file_path)
            cached_mtime: Optional[float] = getattr(pixmap, "_cache_mtime", None)
            return cached_mtime is not None and current_mtime == cached_mtime
        except OSError:
            return False

    def _on_thumbnail_loaded(self, file_path: str, image: QImage) -> None:
        """缩略图加载完成回调（在主线程执行）。

        Worker 传递过来的是 QImage（线程安全），
        此处转换为 QPixmap 并设置到对应的列表项。
        """
        self._pending_workers.pop(file_path, None)

        if image is None or image.isNull():
            return

        # QImage → QPixmap（必须在主线程执行）
        pixmap = QPixmap.fromImage(image)

        # 继承缓存修改时间
        try:
            pixmap._cache_mtime = image._cache_mtime
        except AttributeError:
            pixmap._cache_mtime = None

        self._thumbnails[file_path] = pixmap
        item = self._items.get(file_path)
        if item is not None:
            item.setIcon(QIcon(pixmap))

    def _get_thumbnail(self, sprite: SpriteInfo) -> QPixmap:
        """获取缩略图（优先使用缓存，未命中则同步加载）。

        供外部直接获取某张精灵图的缩略图，
        通常在需要预览场景下调用的。

        Args:
            sprite: 精灵图信息

        Returns:
            缩略图 QPixmap（128x128）
        """
        file_path = sprite.file_path

        # 检查缓存
        if file_path in self._thumbnails:
            cached = self._thumbnails[file_path]
            if self._is_cache_valid(file_path, cached):
                return cached

        # 同步加载（后备方案）
        image = QImage(file_path)
        if image.isNull():
            pixmap = QPixmap(ICON_SIZE, ICON_SIZE)
            pixmap.fill(Qt.GlobalColor.Gray)
        else:
            # 缩放到目标尺寸（保持宽高比，居中放置到正方形画布）
            scaled = image.scaled(
                QSize(ICON_SIZE, ICON_SIZE),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            # 创建正方形画布（透明背景）
            pixmap = QPixmap(ICON_SIZE, ICON_SIZE)
            pixmap.fill(QColor(0, 0, 0, 0))  # 透明
            # 居中绘制
            x = (ICON_SIZE - scaled.width()) // 2
            y = (ICON_SIZE - scaled.height()) // 2
            painter = QPainter(pixmap)
            painter.drawImage(x, y, scaled)
            painter.end()

        try:
            pixmap._cache_mtime: Optional[float] = os.path.getmtime(file_path)
        except OSError:
            pixmap._cache_mtime = None

        self._thumbnails[file_path] = pixmap
        return pixmap

    def _on_selection_changed(self) -> None:
        """当前选中项变化时发射 selection_changed 信号。"""
        selected = self._list_widget.selectedItems()
        if selected:
            item = selected[0]
            sprite = item.data(Qt.ItemDataRole.UserRole)
            if sprite is not None:
                self.selection_changed.emit(sprite)

    def update_cache_keys(self, old_paths: List[str], new_paths: List[str]) -> None:
        """重命名后更新缓存 key。

        当文件被重命名后，缓存中的 key（旧路径）需要更新为新路径，
        否则缓存会失效并触发不必要的重新加载。

        Args:
            old_paths: 重命名前的文件路径列表
            new_paths: 重命名后的文件路径列表（与 old_paths 一一对应）
        """

        def _do_update(
            mapping: Dict[str, object], old: str, new: str
        ) -> None:
            """更新任意 dict 的 key。"""
            if old in mapping:
                mapping[new] = mapping.pop(old)

        for old_path, new_path in zip(old_paths, new_paths):
            _do_update(self._thumbnails, old_path, new_path)
            _do_update(self._items, old_path, new_path)
            _do_update(self._pending_workers, old_path, new_path)
