# 记住上次打开的文件夹 - 设计文档

## 背景

当前 `Game Dev Manager` 启动时，只会尝试从当前工作目录读取 `.gdm.json` 来恢复项目。这导致：
- 如果从其他目录启动程序，无法恢复上次的工作区
- 用户每次都需要手动重新选择文件夹

**目标：** 程序启动时自动打开上次打开的文件夹，提升用户体验。

## 需求

1. 程序启动时，自动打开上次打开的文件夹（如果存在）
2. 用户通过"打开文件夹"选择新文件夹后，记住该路径
3. 如果上次打开的文件夹已不存在，静默跳过，不显示错误
4. 配置与项目分离，存储在用户级配置目录

## 设计

### 配置文件设计

**位置：** `%APPDATA%\Game Dev Manager\config.json`

- `%APPDATA%` 在 Windows 上通常是 `C:\Users\<用户名>\AppData\Roaming`
- 这是 Windows 上存储用户级应用数据的标准位置

**内容：**

```json
{
  "last_folder": "C:\\Users\\oliveryin\\Pictures\\sprites"
}
```

**读取逻辑：**

1. 启动时读取配置文件
2. 如果 `last_folder` 存在且是有效目录 → 自动打开该文件夹
3. 如果配置文件不存在、路径无效、或读取失败 → 静默跳过，不显示错误

**保存逻辑：**

1. 用户通过"打开文件夹"选择文件夹后
2. 扫描并加载精灵图
3. 将文件夹路径保存到配置文件

### 错误处理

| 场景 | 处理方式 |
|------|----------|
| 配置文件不存在（首次启动） | 静默跳过，不显示错误 |
| `last_folder` 路径不存在或无效 | 静默跳过，不显示错误 |
| 配置文件损坏（非 JSON） | 静默跳过，不显示错误 |
| 保存配置失败（权限问题等） | 静默失败，不影响主流程 |

## 实现计划

### 新建文件

| 文件 | 说明 |
|------|------|
| `gdm/core/config.py` | 配置文件读写模块 |

**`config.py` 接口设计：**

```python
"""配置管理模块。

负责读取和写入全局配置文件（记住上次打开的文件夹等）。
"""

import json
import os
from typing import Optional

def get_config_path() -> str:
    """返回配置文件路径：%APPDATA%\Game Dev Manager\config.json"""
    ...

def load_config() -> Optional[dict]:
    """读取配置文件，返回配置字典；失败返回 None。"""
    ...

def save_config(config: dict) -> bool:
    """保存配置到文件，成功返回 True。"""
    ...
```

### 修改文件

| 文件 | 修改内容 |
|------|----------|
| `gdm/gui/main_window.py` | 修改 `_try_restore_project()` 和 `_set_workspace()` |

**`main_window.py` 修改点：**

1. **`_try_restore_project()`**：
   - 改为从全局配置文件读取 `last_folder`
   - 路径有效则调用 `_set_workspace(folder)`

2. **`_set_workspace()`**：
   - 在扫描并加载精灵图后，调用 `save_config({"last_folder": folder})`

## 测试计划

| 测试场景 | 预期结果 |
|----------|----------|
| 首次启动（无配置文件） | 不恢复，显示空白界面 |
| 正常启动（配置文件有效） | 自动打开上次文件夹，显示缩略图 |
| 上次文件夹已删除 | 静默跳过，显示空白界面 |
| 用户选择新文件夹 | 记住新路径，下次启动时恢复 |
| 配置文件损坏 | 静默跳过，不崩溃 |
