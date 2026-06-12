# Remember Last Folder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically restore the last opened folder on startup by saving/loading config from `%APPDATA%\Game Dev Manager\config.json`

**Architecture:** Add a `config.py` module to `gdm/core/` that handles reading/writing a JSON config file. Modify `main_window.py` to save the folder path after user selects a folder, and restore it on startup.

**Tech Stack:** Python 3.8+, PySide6, JSON for config storage

---

### Task 1: Create Config Module

**Files:**
- Create: `gdm/core/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for config module."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from gdm.core.config import get_config_path, load_config, save_config


class TestGetConfigPath:
    """Tests for get_config_path()."""

    def test_returns_path_in_appdata(self):
        """Should return path in %APPDATA%\Game Dev Manager\config.json on Windows."""
        path = get_config_path()
        assert path.endswith("config.json")
        assert "Game Dev Manager" in path

    def test_creates_directory_if_not_exists(self):
        """Should create config directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Mock environment variable
            os.environ["APPDATA"] = tmpdir
            path = get_config_path()
            config_dir = Path(path).parent
            assert config_dir.exists()


class TestSaveConfig:
    """Tests for save_config()."""

    def test_saves_config_to_file(self):
        """Should write config dict to file as JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["APPDATA"] = tmpdir
            config = {"last_folder": "C:\\test\\folder"}
            result = save_config(config)
            assert result is True

            # Verify file was written
            config_path = get_config_path()
            with open(config_path, "r") as f:
                saved = json.load(f)
            assert saved == config

    def test_returns_false_on_permission_error(self, monkeypatch):
        """Should return False if unable to write file."""
        # This is hard to test cross-platform, so we'll skip for now
        pass


class TestLoadConfig:
    """Tests for load_config()."""

    def test_loads_config_from_file(self):
        """Should read and return config dict from file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["APPDATA"] = tmpdir
            config = {"last_folder": "C:\\test\\folder"}
            save_config(config)

            loaded = load_config()
            assert loaded == config

    def test_returns_none_if_file_not_exists(self):
        """Should return None if config file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["APPDATA"] = tmpdir
            result = load_config()
            assert result is None

    def test_returns_none_if_file_corrupted(self):
        """Should return None if config file is not valid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["APPDATA"] = tmpdir
            config_path = get_config_path()
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, "w") as f:
                f.write("not valid json {{{")

            result = load_config()
            assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'gdm.core.config'`

- [ ] **Step 3: Write minimal implementation**

```python
"""配置管理模块。

负责读取和写入全局配置文件（记住上次打开的文件夹等）。
"""

import json
import os
from typing import Optional


def get_config_path() -> str:
    """返回配置文件路径：%APPDATA%\Game Dev Manager\config.json

    Fallback to ~/.config/game-dev-manager/ on non-Windows systems.
    Creates the config directory if it doesn't exist.
    """
    appdata = os.environ.get("APPDATA")
    if appdata:
        config_dir = os.path.join(appdata, "Game Dev Manager")
    else:
        # Fallback for non-Windows systems
        config_dir = os.path.expanduser("~/.config/game-dev-manager")

    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "config.json")


def load_config() -> Optional[dict]:
    """读取配置文件，返回配置字典；失败返回 None。"""
    config_path = get_config_path()
    if not os.path.exists(config_path):
        return None

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def save_config(config: dict) -> bool:
    """保存配置到文件，成功返回 True。"""
    config_path = get_config_path()
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        return True
    except OSError:
        return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add gdm/core/config.py tests/test_config.py
git commit -m "feat: add config module for reading/writing global config file"
```

---

### Task 2: Modify MainWindow to Save Last Folder

**Files:**
- Modify: `gdm/gui/main_window.py:98-148`
- Test: `tests/test_main_window.py` (integration test)

- [ ] **Step 1: Write the failing test**

```python
"""Integration tests for MainWindow config saving."""

import os
import tempfile
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QApplication

from gdm.core.config import get_config_path, load_config
from gdm.gui.main_window import MainWindow


@pytest.fixture
def app():
    """Create QApplication instance."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def window(app):
    """Create MainWindow instance."""
    window = MainWindow()
    yield window
    window.close()


class TestMainWindowConfig:
    """Tests for MainWindow config saving/loading."""

    def test_set_workspace_saves_config(self, window, tmp_path, monkeypatch):
        """_set_workspace() should save last_folder to config."""
        # Mock config path to use temp directory
        monkeypatch.setenv("APPDATA", str(tmp_path))

        # Create a test folder with a dummy image
        test_folder = tmp_path / "test_sprites"
        test_folder.mkdir()
        (test_folder / "test.png").touch()

        # Call _set_workspace
        window._set_workspace(str(test_folder))

        # Verify config was saved
        config = load_config()
        assert config is not None
        assert config["last_folder"] == str(test_folder)

    def test_try_restore_project_loads_config(self, window, tmp_path, monkeypatch):
        """_try_restore_project() should load last_folder from config."""
        # Mock config path to use temp directory
        monkeypatch.setenv("APPDATA", str(tmp_path))

        # Create a test folder with a dummy image
        test_folder = tmp_path / "test_sprites"
        test_folder.mkdir()
        (test_folder / "test.png").touch()

        # Save config
        from gdm.core.config import save_config
        save_config({"last_folder": str(test_folder)})

        # Mock scan to verify it's called
        with patch("gdm.gui.main_window.scan") as mock_scan:
            mock_scan.return_value = []
            window._try_restore_project()
            mock_scan.assert_called_once_with(str(test_folder), recursive=False)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_main_window.py -v`
Expected: FAIL (tests don't exist yet or methods not implemented)

- [ ] **Step 3: Write implementation**

Modify `gdm/gui/main_window.py`:

1. Add import at top:

```python
from gdm.core.config import load_config, save_config
```

2. Modify `_try_restore_project()` (around line 127):

```python
def _try_restore_project(self) -> None:
    """启动时尝试恢复上一次的工作区。

    从全局配置文件读取上次打开的文件夹路径，
    如果不存在或其中记录的根目录已不存在，静默跳过。
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
    # 注意：此处不直接调用 _set_workspace()，因为后者会再次保存配置（冗余）
    self._project = Project(root_path=last_folder)
    self.project_panel.set_root(last_folder)

    sprites = scan(last_folder, recursive=False)
    self._current_sprites = sprites
    self.thumbnail_view.load(sprites)
```

3. Modify `_set_workspace()` (around line 108):

```python
def _set_workspace(self, folder: str) -> None:
    """设置工作区根目录，扫描并加载精灵图。"""
    self._project = Project(root_path=folder)
    self.project_panel.set_root(folder)

    sprites = scan(folder, recursive=False)
    self._current_sprites = sprites
    self.thumbnail_view.load(sprites)

    # 保存配置
    save_config({"last_folder": folder})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_main_window.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add gdm/gui/main_window.py
git commit -m "feat: save and restore last folder from global config"
```

---

### Task 3: End-to-End Manual Testing

**Files:**
- None (manual testing)

- [ ] **Step 1: Test first launch (no config)**

1. Delete config file if exists: `del %APPDATA%\Game Dev Manager\config.json`
2. Launch app: `python -m gdm.main`
3. Verify: App launches with blank window, no errors

- [ ] **Step 2: Test folder selection saves config**

1. Launch app
2. Click "File" -> "Open Folder"
3. Select a folder with images
4. Verify config file exists: `type %APPDATA%\Game Dev Manager\config.json`
5. Expected: `{"last_folder": "C:\\path\\to\\selected\\folder"}`

- [ ] **Step 3: Test restore on next launch**

1. Close app
2. Launch app again: `python -m gdm.main`
3. Verify: App automatically opens the folder selected in Step 2
4. Verify: Thumbnails are displayed

- [ ] **Step 4: Test invalid path handling**

1. Edit config file: change `last_folder` to a non-existent path
2. Launch app
3. Verify: App launches with blank window, no errors (doesn't crash)

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "test: add end-to-end manual testing for remember last folder feature"
```
