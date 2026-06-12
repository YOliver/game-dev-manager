# Game Dev Manager

游戏开发资源管理工具，帮助游戏开发者高效管理和预览精灵图（Sprite）资源。

## 功能特性

- **资源扫描**：自动扫描指定目录，提取精灵图元数据（尺寸、文件大小、格式、色彩模式等）
- **缩略图预览**：异步加载缩略图，支持大批量图片快速浏览，不阻塞 UI
- **详情展示**：侧边面板显示选中图片的预览图和详细元数据信息
- **批量重命名**：支持多种重命名模式（前缀+序号、查找替换、正则替换、添加后缀）
- **多选区支持**：支持单选和多选，多选时显示汇总信息

## 环境要求

- Python >= 3.8
- Windows 10 / 11 (x64)

## 安装依赖

```bash
pip install -r requirements.txt
```

依赖清单：

| 依赖 | 版本要求 | 用途 |
|------|----------|------|
| PySide6 | >= 6.5.0 | GUI 框架 |
| Pillow | >= 10.0.0 | 图片处理 |
| pytest | >= 7.0.0 | 单元测试（开发） |

## 使用方式

### 方式一：直接运行源码

```bash
python -m gdm.main
```

或使用启动脚本（Windows）：

双击 `start.bat`

### 方式二：使用安装包

1. 执行 `release.bat` 构建安装包
2. 运行生成的安装包（`installer/Game_Dev_Manager_Setup.exe`）
3. 从开始菜单或桌面快捷方式启动

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| Ctrl + O | 打开文件夹 |
| F5 | 刷新当前目录 |

## 构建方式

### 构建可执行文件（exe）

```bash
pyinstaller --onefile --windowed --name GameDevManager gdm/main.py
```

### 构建安装包

1. 先构建 exe（如上）
2. 安装 Inno Setup
3. 执行：

```bash
"%(ProgramFiles(x86))%\Inno Setup 6\ISCC.exe" installer.iss
```

或直接使用一键构建脚本：

双击 `release.bat`（Windows）

## 项目结构

```
game-dev-manager/
├── gdm/                    # 主程序包
│   ├── main.py              # 程序入口
│   ├── core/                # 核心逻辑
│   │   ├── models.py        # 数据模型
│   │   ├── scanner.py       # 资源扫描
│   │   ├── renamer.py      # 重命名逻辑
│   │   └── metadata.py     # 元数据提取
│   ├── gui/                 # GUI 组件
│   │   ├── main_window.py   # 主窗口
│   │   ├── thumbnail_view.py # 缩略图视图
│   │   ├── detail_panel.py   # 详情面板
│   │   └── rename_dialog.py  # 重命名对话框
│   └── utils/               # 工具函数
├── tests/                   # 单元测试
├── helpdocs/                # 帮助文档
├── requirements.txt          # 依赖清单
├── start.bat                # 启动脚本
├── release.bat              # 打包脚本
└── README.md                # 项目说明
```

## 版本历史

### v1.0.0 (2026-06-12)

- 初始版本
- 实现资源扫描、缩略图预览、详情展示、批量重命名功能
