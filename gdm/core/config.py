"""配置管理模块。

负责读取和写入全局配置文件（记住上次打开的文件夹等）。
"""

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


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
    except json.JSONDecodeError as e:
        logger.warning(f"配置文件格式错误: {config_path}, 错误: {e}")
        return None
    except OSError as e:
        logger.warning(f"读取配置文件失败: {config_path}, 错误: {e}")
        return None


def save_config(config: dict) -> bool:
    """保存配置到文件（原子写入），成功返回 True。"""
    if not isinstance(config, dict):
        logger.error("配置必须是字典类型")
        return False

    config_path = get_config_path()
    tmp_path = config_path + ".tmp"
    try:
        # 先写入临时文件，再原子重命名，避免崩溃留下半截无效 JSON
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, config_path)
        return True
    except TypeError as e:
        logger.error(f"配置包含不可序列化的数据: {e}")
        return False
    except OSError as e:
        logger.error(f"写入配置文件失败: {config_path}, 错误: {e}")
        return False
    finally:
        # 清理残留的临时文件
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
