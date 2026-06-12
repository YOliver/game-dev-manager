"""主窗口

GDM 应用的主窗口，负责布局管理与信号协调。
"""

import logging
import os
from typing import List, Optional

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QWidget,
)
from PySide6.QtCore import Slot

from gdm.core.config import load_config, save_config
from gdm.core.models import Project, SpriteInfo
from gdm.core.project import load as load_project, save as save_project
from gdm.core.scanner import scan
from gdm.gui.detail_panel import DetailPanel
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
        self._init_ui()
        self._try_restore_project()

    def _init_ui(self) -> None:
        """初始化 UI 组件与布局。"""
        self.setWindowTitle("Game Dev Manager")
        self.setMinimumSize(1000, 600)

        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        # 左侧：项目面板
        self.project_panel = ProjectPanel()
        self.project_panel.folder_selected.connect(self._on_folder_selected)
        main_layout.addWidget(self.project_panel, 1)

        # 中间：缩略图视图
        self.thumbnail_view = ThumbnailView()
        self.thumbnail_view.selection_changed.connect(self._on_selection_changed)
        main_layout.addWidget(self.thumbnail_view, 3)

        # 右侧：详情面板
        self.detail_panel = DetailPanel()
        main_layout.addWidget(self.detail_panel, 1)

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

    def _set_workspace(self, folder: str) -> None:
        """设置工作区根目录，扫描并加载精灵图。"""
        self._project = Project(root_path=folder)
        self.project_panel.set_root(folder)

        sprites = scan(folder, recursive=False)
        self._current_sprites = sprites
        self.thumbnail_view.load(sprites)

        # 保存 last_folder 到全局配置
        try:
            save_config({"last_folder": folder})
        except Exception as e:
            logger.warning(f"保存配置失败: {e}")

        self._save_project()

    @Slot()
    def _save_project(self) -> None:
        """保存工作区到 .gdm.json。"""
        if self._project is None:
            return
        config_path = os.path.join(self._project.root_path, ".gdm.json")
        save_project(self._project, config_path)

    def _try_restore_project(self) -> None:
        """启动时尝试恢复上一次的工作区。

        从全局配置文件加载 last_folder，
        如果不存在或其中记录的目录已不存在，静默跳过。
        """
        config = load_config()
        if config is None:
            return

        last_folder = config.get("last_folder")
        if last_folder is None:
            return

        if not os.path.isdir(last_folder):
            return

        # 恢复 UI 状态（跳过再次保存，避免覆盖）
        self._project = Project(root_path=last_folder)
        self.project_panel.set_root(last_folder)

        try:
            sprites = scan(last_folder, recursive=False)
        except Exception as e:
            logger.warning(f"扫描文件夹失败: {last_folder}, 错误: {e}")
            sprites = []

        self._current_sprites = sprites
        self.thumbnail_view.load(sprites)

    # ------------------------------------------------------------------ #
    #  信号回调
    # ------------------------------------------------------------------ #

    def _on_folder_selected(self, folder_path: str) -> None:
        """左侧面板选中文件夹回调，加载该文件夹的精灵图到缩略图视图。"""
        sprites = scan(folder_path, recursive=False)
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
