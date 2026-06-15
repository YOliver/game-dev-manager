"""测试 MainWindow 的 last_folder 配置保存与恢复。"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Signal


@pytest.fixture(scope="session", autouse=True)
def qapp():
    """创建 QApplication 实例。"""
    if QApplication.instance() is None:
        app = QApplication([])
    else:
        app = QApplication.instance()
    yield app


@pytest.fixture
def mock_scan():
    """模拟扫描过程，同步调用完成回调以返回空列表。"""
    with patch("gdm.gui.main_window.MainWindow._start_scan") as mock:
        def sync_start_scan(folder, on_finished):
            on_finished([])
        mock.side_effect = sync_start_scan
        yield mock


@pytest.fixture
def mock_ui_components():
    """模拟 UI 组件，使其具有正确的信号和方法。"""

    class MockProjectPanel(QWidget):
        """模拟 ProjectPanel，具有 folder_selected 信号和 add_root 方法。"""
        folder_selected = Signal(str)
        root_removed = Signal(str)

        def __init__(self, parent=None):
            super().__init__(parent)
            self.tree = MagicMock()

        def add_root(self, path):
            pass

        def remove_root(self, path):
            pass

    class MockThumbnailView(QWidget):
        """模拟 ThumbnailView，具有 selection_changed 信号和 load/show_progress/update_progress 方法。"""
        selection_changed = Signal(object)

        def __init__(self, parent=None):
            super().__init__(parent)

        def load(self, sprites):
            pass

        def show_progress(self):
            pass

        def update_progress(self, current, total):
            pass

    class MockDetailPanel(QWidget):
        """模拟 DetailPanel，具有 update 方法。"""

        def __init__(self, parent=None):
            super().__init__(parent)

        def update(self, sprite):
            pass

    with patch("gdm.gui.main_window.ProjectPanel", MockProjectPanel):
        with patch("gdm.gui.main_window.ThumbnailView", MockThumbnailView):
            with patch("gdm.gui.main_window.DetailPanel", MockDetailPanel):
                yield


@pytest.fixture
def main_window(tmp_path, monkeypatch, mock_ui_components, qapp):
    """创建 MainWindow 实例，模拟必要的依赖项。

    注意：此 fixture 会模拟 _try_restore_project 以避免启动时自动恢复。
    """
    # 模拟 APPDATA 环境变量，使配置路径指向临时目录
    monkeypatch.setenv("APPDATA", str(tmp_path))

    # 模拟 _try_restore_project 以避免启动时自动恢复
    with patch("gdm.gui.main_window.MainWindow._try_restore_project"):
        from gdm.gui.main_window import MainWindow
        window = MainWindow()
        yield window
        window.close()


class TestSetWorkspaceSavesConfig:
    """测试 _set_workspace() 应将 last_folder 保存到全局配置。"""

    def test_set_workspace_saves_config(
        self, main_window, mock_scan, tmp_path, monkeypatch
    ):
        """_set_workspace() 应在扫描并加载精灵图后，将 last_folder 保存到配置。"""
        from gdm.core.config import load_config, save_config

        # 确保初始配置为空
        config = load_config()
        assert config is None or "last_folder" not in config

        # 调用 _set_workspace
        test_folder = str(tmp_path / "test_project")
        os.makedirs(test_folder, exist_ok=True)
        main_window._set_workspace(test_folder)

        # 验证配置已保存
        config = load_config()
        assert config is not None
        assert config.get("last_folder") == test_folder


class TestTryRestoreProjectLoadsConfig:
    """测试 _try_restore_project() 应从全局配置加载 last_folder。"""

    def test_try_restore_project_loads_config(
        self, tmp_path, monkeypatch, mock_scan, mock_ui_components, qapp
    ):
        """_try_restore_project() 应从配置加载 last_folder 并恢复工作区。"""
        from gdm.core.config import save_config

        # 模拟 APPDATA 环境变量（必须在 save_config 之前设置）
        monkeypatch.setenv("APPDATA", str(tmp_path))

        # 在配置中保存 last_folder
        test_folder = str(tmp_path / "restored_project")
        os.makedirs(test_folder, exist_ok=True)
        save_config({"last_folder": test_folder})

        # 不模拟 _try_restore_project，让其实际执行
        from gdm.gui.main_window import MainWindow

        window = MainWindow()
        try:
            # 验证工作区已恢复
            assert window._project is not None
            assert window._project.root_path == test_folder
        finally:
            window.close()
