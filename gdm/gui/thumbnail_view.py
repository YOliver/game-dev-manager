"""缩略图网格视图

使用 QListWidget（Icon Mode）实现精灵图缩略图网格，
支持异步加载缩略图，避免阻塞 UI。
"""

import os
from typing import Dict, List, Optional

from PySide6.QtCore import QObject, QRunnable, QSize, Qt, QThreadPool, Signal
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QWidget, QVBoxLayout

from gdm.core.models import SpriteInfo


class _WorkerSignals(QObject):
    """Worker 内部信号类（必须在 QRunnable 外部定义，否则无法 emit）。"""

    finished = Signal(str, object)  # file_path, QImage | None


class ThumbnailLoadWorker(QRunnable):
    """异步加载缩略图的 Worker（QRunnable + QThreadPool）。

    在工作线程中加载图片为 QImage（线程安全），
    通过信号将结果传递到主线程后转换为 QPixmap。
    """

    def __init__(self, sprite: SpriteInfo, target_size: int = 128) -> None:
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
            image = image.scaled(
                QSize(self.target_size, self.target_size),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        # 附加文件修改时间，供缓存验证使用
        try:
            image._cache_mtime: Optional[float] = os.path.getmtime(file_path)
        except OSError:
            image._cache_mtime = None

        self.signals.finished.emit(file_path, image)


class ThumbnailView(QWidget):
    """缩略图网格视图。

    使用 QListWidget（Icon Mode）显示精灵图缩略图网格，
    支持异步加载缩略图，避免阻塞 UI。

    信号：
        selection_changed(SpriteInfo): 选中项变化时发射，携带对应的 SpriteInfo 对象
    """

    selection_changed = Signal(object)

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
        self._list_widget.setIconSize(QSize(128, 128))
        self._list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._list_widget.setSpacing(8)
        self._list_widget.setSelectionMode(
            QListWidget.SelectionMode.SingleSelection
        )
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
        pixmap = QPixmap(file_path)
        if pixmap.isNull():
            pixmap = QPixmap(128, 128)
            pixmap.fill(Qt.GlobalColor.Gray)
        else:
            pixmap = pixmap.scaled(
                QSize(128, 128),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

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
