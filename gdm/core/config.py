"""配置管理模块。

负责读取和写入全局配置文件（记住上次打开的文件夹等）。
"""

import json
import os
from typing import Optional


def get_config_path() -> str:
    """返回配置文件路径：%APPDATA%\\Game Dev Manager\\config.json

    在非 Windows 系统上回退到 ~/.config/game-dev-manager/。
    如果配置目录不存在，则创建它。
    """
    appdata = os.environ.get("APPDATA")
    if appdata:
        config_dir = os.path.join(appdata, "Game Dev Manager")
    else:
        # 非 Windows 系统的回退方案
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
