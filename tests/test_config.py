"""测试配置管理模块。"""

import json
import os
import tempfile
from pathlib import Path

import pytest

from gdm.core.config import get_config_path, load_config, save_config


class TestGetConfigPath:
    """测试 get_config_path()。"""

    def test_returns_path_in_appdata(self, monkeypatch):
        """应返回 %APPDATA%\\Game Dev Manager\\config.json 路径。"""
        path = get_config_path()
        assert path.endswith("config.json")
        assert "Game Dev Manager" in path

    def test_creates_directory_if_not_exists(self, monkeypatch):
        """如果配置目录不存在，应创建它。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            monkeypatch.setenv("APPDATA", tmpdir)
            path = get_config_path()
            config_dir = Path(path).parent
            assert config_dir.exists()


class TestSaveConfig:
    """测试 save_config()。"""

    def test_saves_config_to_file(self, monkeypatch):
        """应将配置字典写入文件（JSON 格式）。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            monkeypatch.setenv("APPDATA", tmpdir)
            config = {"last_folder": "C:\\test\\folder"}
            result = save_config(config)
            assert result is True

            # 验证文件已写入
            config_path = get_config_path()
            with open(config_path, "r") as f:
                saved = json.load(f)
            assert saved == config

    @pytest.mark.skip(reason="权限错误测试跨平台较困难，需要特殊环境设置")
    def test_returns_false_on_permission_error(self, monkeypatch):
        """如果无法写入文件，应返回 False。"""
        pass

    def test_returns_false_for_non_dict_input(self):
        """如果传入非字典参数，应返回 False。"""
        result = save_config(None)
        assert result is False

        result = save_config("string")
        assert result is False

        result = save_config([1, 2, 3])
        assert result is False

    def test_returns_false_for_non_serializable_input(self):
        """如果传入不可序列化的对象，应返回 False。"""
        result = save_config({"key": set([1, 2, 3])})  # set 不可 JSON 序列化
        assert result is False


class TestLoadConfig:
    """测试 load_config()。"""

    def test_loads_config_from_file(self, monkeypatch):
        """应读取并返回配置文件中的配置字典。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            monkeypatch.setenv("APPDATA", tmpdir)
            config = {"last_folder": "C:\\test\\folder"}
            save_config(config)

            loaded = load_config()
            assert loaded == config

    def test_returns_none_if_file_not_exists(self, monkeypatch):
        """如果配置文件不存在，应返回 None。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            monkeypatch.setenv("APPDATA", tmpdir)
            result = load_config()
            assert result is None

    def test_returns_none_if_file_corrupted(self, monkeypatch):
        """如果配置文件不是有效的 JSON，应返回 None。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            monkeypatch.setenv("APPDATA", tmpdir)
            config_path = get_config_path()
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, "w") as f:
                f.write("not valid json {{{")

            result = load_config()
            assert result is None
