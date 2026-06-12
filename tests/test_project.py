"""测试工作区状态保存与加载：save, load"""

import json
import tempfile
from pathlib import Path

import pytest

from gdm.core.models import Project


# load() 和 save() 在 project.py 中实现
# 测试先写，导入会在实现后通过


class TestSave:
    """测试 save() 函数"""

    def test_save_writes_json_file(self):
        """测试 save() 将 Project 写入 JSON 文件"""
        from gdm.core.project import save

        project = Project(root_path="/workspace/my-game")
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json", encoding="utf-8"
        ) as tmp:
            tmp_path = tmp.name

        try:
            save(project, tmp_path)

            # 验证文件存在且内容为合法 JSON
            assert Path(tmp_path).exists()
            with open(tmp_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            assert data == {"root_path": "/workspace/my-game"}
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_save_handles_chinese_path(self):
        """测试 save() 正确处理含中文的路径"""
        from gdm.core.project import save

        project = Project(root_path="G:/UGit/游戏项目/精灵图")
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json", encoding="utf-8"
        ) as tmp:
            tmp_path = tmp.name

        try:
            save(project, tmp_path)

            with open(tmp_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            assert data == {"root_path": "G:/UGit/游戏项目/精灵图"}
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class TestLoad:
    """测试 load() 函数"""

    def test_load_restores_project_from_json(self):
        """测试 load() 从 JSON 文件恢复 Project 对象"""
        from gdm.core.project import load

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json", encoding="utf-8"
        ) as tmp:
            json.dump({"root_path": "/workspace/my-game"}, tmp, ensure_ascii=False)
            tmp_path = tmp.name

        try:
            result = load(tmp_path)

            assert result is not None
            assert isinstance(result, Project)
            assert result.root_path == "/workspace/my-game"
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_load_returns_none_when_file_not_exists(self):
        """测试 load() 文件不存在时返回 None"""
        from gdm.core.project import load

        result = load("/path/that/does/not/exist.json")
        assert result is None

    def test_load_returns_none_on_invalid_json(self):
        """测试 load() JSON 格式错误时返回 None"""
        from gdm.core.project import load

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json", encoding="utf-8"
        ) as tmp:
            tmp.write("这不是合法的 JSON {{}")
            tmp_path = tmp.name

        try:
            result = load(tmp_path)
            assert result is None
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_load_returns_none_on_missing_root_path_key(self):
        """测试 load() JSON 缺少 root_path 字段时返回 None"""
        from gdm.core.project import load

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json", encoding="utf-8"
        ) as tmp:
            json.dump({"other_key": "value"}, tmp)
            tmp_path = tmp.name

        try:
            result = load(tmp_path)
            assert result is None
        finally:
            Path(tmp_path).unlink(missing_ok=True)
