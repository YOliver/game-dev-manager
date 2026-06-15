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
            self._roots = []
            self.tree = MagicMock()

        def add_root(self, path):
            item = MagicMock()
            item.data.return_value = path
            self._roots.append(item)
            self.tree.topLevelItemCount.return_value = len(self._roots)
            self.tree.topLevelItem.side_effect = lambda i: self._roots[i]

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

        # 验证 root_paths 也被保存
        assert config.get("root_paths") == [test_folder]


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


class TestSaveRootPaths:
    """测试 _save_root_paths() 的保存行为。"""

    def test_save_root_paths_to_config(
        self, main_window, tmp_path
    ):
        """_save_root_paths() 应将所有根目录保存到 root_paths 配置。"""
        from gdm.core.config import load_config

        # 设置三个模拟的根目录条目
        dirs = [str(tmp_path / "root_a"), str(tmp_path / "root_b"), str(tmp_path / "root_c")]
        for d in dirs:
            os.makedirs(d, exist_ok=True)

        mock_items = []
        for d in dirs:
            item = MagicMock()
            item.data.return_value = d
            mock_items.append(item)

        main_window.project_panel.tree.topLevelItemCount.return_value = len(dirs)
        main_window.project_panel.tree.topLevelItem.side_effect = lambda i: mock_items[i]

        # 调用 _save_root_paths
        main_window._save_root_paths()

        # 验证
        config = load_config()
        assert config is not None
        assert config.get("root_paths") == dirs


class TestCloseEventSavesRootPaths:
    """测试 closeEvent() 应保存 root_paths 到配置。"""

    def test_close_event_saves_root_paths(
        self, tmp_path, monkeypatch, mock_scan, mock_ui_components, qapp
    ):
        """关闭主窗口前应调用 _save_root_paths()。"""
        from gdm.core.config import save_config

        monkeypatch.setenv("APPDATA", str(tmp_path))

        # 先保存根目录配置
        root_a = str(tmp_path / "root_a")
        root_b = str(tmp_path / "root_b")
        os.makedirs(root_a, exist_ok=True)
        os.makedirs(root_b, exist_ok=True)
        save_config({"root_paths": [root_a, root_b]})

        with patch("gdm.gui.main_window.MainWindow._save_root_paths") as mock_save:
            from gdm.gui.main_window import MainWindow

            window = MainWindow()
            window.close()

            # 验证 closeEvent 触发了 _save_root_paths
            mock_save.assert_called_once()


class TestTryRestoreProjectMultipleRoots:
    """测试 _try_restore_project() 应从 root_paths 恢复多个根目录。"""

    def test_restore_multiple_roots(
        self, tmp_path, monkeypatch, mock_scan, mock_ui_components, qapp
    ):
        """_try_restore_project() 应从配置的 root_paths 恢复所有有效目录。"""
        from gdm.core.config import save_config

        monkeypatch.setenv("APPDATA", str(tmp_path))

        # 创建多个有效目录
        root_a = str(tmp_path / "root_a")
        root_b = str(tmp_path / "root_b")
        root_c = str(tmp_path / "root_c")  # 不创建此目录，模拟已删除
        os.makedirs(root_a, exist_ok=True)
        os.makedirs(root_b, exist_ok=True)

        save_config({"root_paths": [root_a, root_b, root_c]})

        # mock_ui_components 已将 gdm.gui.main_window.ProjectPanel 替换为 MockProjectPanel
        from gdm.gui.main_window import ProjectPanel as MockPanel

        with patch.object(MockPanel, "add_root") as mock_add_root:
            from gdm.gui.main_window import MainWindow

            window = MainWindow()
            try:
                # 验证 _project 正确设置为第一个根目录
                assert window._project is not None
                assert window._project.root_path == root_a
                # 验证只恢复了存在的目录（root_c 被静默跳过）
                assert mock_add_root.call_count == 2
            finally:
                window.close()
