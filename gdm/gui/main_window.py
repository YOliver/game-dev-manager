"""主窗口

GDM 应用的主窗口，负责布局管理与信号协调。
"""

import logging
import os
from typing import List, Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QSplitter,
    QWidget,
)

from gdm.core.config import load_config, save_config
from gdm.core.models import Project, SpriteInfo
from gdm.core.project import load as load_project, save as save_project
from gdm.gui.detail_panel import DetailPanel
from gdm.gui.help_dialog import HelpDialog
from gdm.gui.project_panel import ProjectPanel
from gdm.gui.rename_dialog import RenameDialog
from gdm.gui.thumbnail_view import ThumbnailView

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """GDM 主窗口。

    布局：左侧 ProjectPanel，中间 ThumbnailView，右侧 DetailPanel。
    负责菜单栏创建与信号协调。
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._project: Optional[Project] = None
        self._current_sprites: List[SpriteInfo] = []
        self._scan_pending: Optional[tuple[str, object]] = None  # (folder, on_finished)
        self._init_ui()
        self._try_restore_project()

    def _init_ui(self) -> None:
        """初始化 UI 组件与布局。"""
        self.setWindowTitle("Game Dev Manager")
        self.setMinimumSize(1000, 600)

        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 使用 QSplitter 实现可拖动分隔条
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(4)

        # 左侧：项目面板
        self.project_panel = ProjectPanel()
        self.project_panel.folder_selected.connect(self._on_folder_selected)
        self.project_panel.root_removed.connect(self._on_root_removed)
        splitter.addWidget(self.project_panel)

        # 中间：缩略图视图
        self.thumbnail_view = ThumbnailView()
        self.thumbnail_view.selection_changed.connect(self._on_selection_changed)
        splitter.addWidget(self.thumbnail_view)

        # 右侧：详情面板
        self.detail_panel = DetailPanel()
        splitter.addWidget(self.detail_panel)

        # 设置拉伸因子，实现 1:5:5 比例
        splitter.setStretchFactor(0, 1)  # 左侧面板
        splitter.setStretchFactor(1, 5)  # 中间面板
        splitter.setStretchFactor(2, 5)  # 右侧面板

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.addWidget(splitter)

        # 菜单栏
        self._init_menubar()

    def _init_menubar(self) -> None:
        """初始化菜单栏。"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件")

        open_action = file_menu.addAction("打开文件夹")
        open_action.triggered.connect(self._open_folder)

        save_action = file_menu.addAction("保存工作区")
        save_action.triggered.connect(self._save_project)

        file_menu.addSeparator()

        exit_action = file_menu.addAction("退出")
        exit_action.triggered.connect(self.close)

        # 工具菜单
        tool_menu = menubar.addMenu("工具")

        rename_action = tool_menu.addAction("批量重命名")
        rename_action.triggered.connect(self._open_rename_dialog)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助")

        manual_action = help_menu.addAction("使用手册")
        manual_action.triggered.connect(lambda: self._open_help_doc("使用手册.md"))

        welcome_action = help_menu.addAction("欢迎")
        welcome_action.triggered.connect(lambda: self._open_help_doc("welcome.md"))

        about_action = help_menu.addAction("软件信息")
        about_action.triggered.connect(lambda: self._open_help_doc("about.md"))

    # ------------------------------------------------------------------ #
    #  工作区管理
    # ------------------------------------------------------------------ #

    @Slot()
    def _open_folder(self) -> None:
        """通过 QFileDialog 选择文件夹，设置工作区。"""
        folder = QFileDialog.getExistingDirectory(
            self, "选择工作区文件夹", ""
        )
        if not folder:
            return
        self._set_workspace(folder)

    def _start_scan(self, folder: str, on_finished) -> None:
        """启动扫描（主线程同步 + processEvents 保持响应）。

        如果已有扫描在进行，记录为待处理，当前扫描结束后自动执行。
        """
        if self._scan_pending is not None:
            # 已有待处理扫描，替换为最新的请求
            self._scan_pending = (folder, on_finished)
            return

        self._scan_pending = (folder, on_finished)
        self._run_scan()

    def _run_scan(self) -> None:
        """执行待处理的扫描（主线程同步 + processEvents 保持响应）。"""
        if self._scan_pending is None:
            return

        folder, on_finished = self._scan_pending
        self._scan_pending = None  # 清除待处理，允许新请求排队

        try:
            from gdm.core.scanner import scan_with_progress

            def progress_callback(current: int, total: int) -> None:
                self.thumbnail_view.update_progress(current, total)
                QApplication.processEvents()  # 刷新进度条并处理 UI 事件

            sprites = scan_with_progress(folder, recursive=True,
                                         progress_callback=progress_callback)
            on_finished(sprites)
        except Exception as e:
            logger.warning(f"扫描文件夹失败: {folder}, 错误: {e}")
            on_finished([])

        # 检查是否有新的待处理扫描（用户在扫描期间点击了其他目录）
        if self._scan_pending is not None:
            self._run_scan()

    def _set_workspace(self, folder: str) -> None:
        """设置工作区根目录，后台扫描并加载精灵图。"""
        self._project = Project(root_path=folder)
        self.project_panel.add_root(folder)

        # 显示进度界面
        self.thumbnail_view.show_progress()

        # 启动后台扫描
        self._start_scan(folder, on_finished=self._on_workspace_scan_finished)

    def _on_workspace_scan_finished(self, sprites) -> None:
        """_set_workspace 扫描完成回调。"""
        self._current_sprites = sprites
        self.thumbnail_view.load(sprites)

        # 保存 last_folder 到全局配置
        folder = self._project.root_path
        try:
            save_config({"last_folder": folder})
        except Exception as e:
            logger.warning(f"保存配置失败: {e}")

        # 保存项目文件
        try:
            self._save_project()
        except Exception as e:
            logger.warning(f"保存项目失败: {e}")

    @Slot()
    def _save_project(self) -> None:
        """保存工作区到 .gdm.json。"""
        if self._project is None:
            return
        config_path = os.path.join(self._project.root_path, ".gdm.json")
        save_project(self._project, config_path)

    def _try_restore_project(self) -> None:
        """启动时尝试恢复上一次的工作区。"""
        config = load_config()
        if config is None:
            return

        # 恢复多个根目录
        root_paths = config.get("root_paths", [])
        if not root_paths:
            # 兼容旧版本：使用 last_folder
            last_folder = config.get("last_folder")
            if last_folder and os.path.isdir(last_folder):
                root_paths = [last_folder]
            else:
                return

        # 设置当前项目（使用第一个根目录）
        self._project = Project(root_path=root_paths[0])

        # 恢复所有根目录
        for path in root_paths:
            if os.path.isdir(path):
                self.project_panel.add_root(path)

        # 扫描第一个根目录
        if os.path.isdir(root_paths[0]):
            self._on_folder_selected(root_paths[0])

        # 显示进度界面
        self.thumbnail_view.show_progress()

        # 启动后台扫描
        self._start_scan(root_paths[0], on_finished=self._on_restore_scan_finished)

    def _on_restore_scan_finished(self, sprites) -> None:
        """_try_restore_project 扫描完成回调（不保存配置）。"""
        self._current_sprites = sprites
        self.thumbnail_view.load(sprites)

    # ------------------------------------------------------------------ #
    #  信号回调
    # ------------------------------------------------------------------ #

    def _on_folder_selected(self, folder_path: str) -> None:
        """左侧面板选中文件夹回调，后台扫描并加载精灵图。"""
        self.thumbnail_view.show_progress()
        self._start_scan(folder_path, on_finished=self._on_tree_scan_finished)

    def _on_tree_scan_finished(self, sprites) -> None:
        """左侧树点击扫描完成回调（不保存配置）。"""
        self._current_sprites = sprites
        self.thumbnail_view.load(sprites)

    def _on_selection_changed(self, sprite: SpriteInfo) -> None:
        """缩略图选中项变化回调，更新详情面板。"""
        self.detail_panel.update(sprite)

    # ------------------------------------------------------------------ #
    #  批量重命名
    # ------------------------------------------------------------------ #

    @Slot()
    def _open_rename_dialog(self) -> None:
        """打开批量重命名对话框。"""
        if not self._current_sprites:
            return

        dialog = RenameDialog(self._current_sprites, self)
        dialog.renamed.connect(self._on_renamed)
        dialog.exec()

    def _on_renamed(self, old_paths: List[str], sprites: List[SpriteInfo]) -> None:
        """重命名完成回调，更新缩略图缓存并刷新视图。

        Args:
            old_paths: 重命名前的文件路径列表
            sprites: 更新后的 SpriteInfo 对象列表（file_path 已为新路径）
        """
        new_paths = [s.file_path for s in sprites]
        self.thumbnail_view.update_cache_keys(old_paths, new_paths)

        # 刷新当前文件夹视图
        if self._current_sprites:
            current_folder = os.path.dirname(self._current_sprites[0].file_path)
            self._on_folder_selected(current_folder)

    # ------------------------------------------------------------------ #
    #  帮助菜单
    # ------------------------------------------------------------------ #

    @Slot()
    def _open_help_doc(self, filename: str) -> None:
        """打开帮助文档对话框。

        Args:
            filename: 帮助文档文件名
        """
        dialog = HelpDialog(self)
        # 根据文件名设置窗口标题
        title_map = {
            "使用手册.md": "使用手册",
            "welcome.md": "欢迎",
            "about.md": "软件信息",
        }
        dialog.setWindowTitle(title_map.get(filename, "帮助"))
        dialog.load_doc(filename)
        dialog.exec()

    def _save_root_paths(self) -> None:
        """保存当前所有根目录到配置。"""
        root_paths = []
        for i in range(self.project_panel.tree.topLevelItemCount()):
            item = self.project_panel.tree.topLevelItem(i)
            root_paths.append(item.data(0, 42))

        try:
            config = load_config() or {}
            config["root_paths"] = root_paths
            save_config(config)
        except Exception as e:
            logger.warning(f"保存配置失败: {e}")

    def _on_root_removed(self, path: str) -> None:
        """处理根目录移除请求，更新配置。"""
        self._save_root_paths()
