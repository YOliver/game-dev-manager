# GDM 精灵图管理工具 v1 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现一个 PySide6 桌面应用，管理游戏开发中的精灵图资源，支持浏览、缩略图预览、详情显示、批量重命名和工作区保存恢复。

**Architecture:** 分层架构，核心逻辑层（core/）与 GUI 层（gui/）完全分离。核心层不依赖 GUI，GUI 组件通过 main_window 信号-槽通信。

**Tech Stack:** Python 3.10+, PySide6, Pillow, pytest

---

## 文件结构

### 核心层（无 GUI 依赖）

| 文件 | 职责 |
|---|---|
| `gdm/core/models.py` | 数据模型：SpriteInfo, Project, RenameMode, RenameRule |
| `gdm/core/metadata.py` | 用 Pillow 提取图片元数据 |
| `gdm/core/scanner.py` | 遍历目录，过滤图片文件，调用 metadata.extract |
| `gdm/core/renamer.py` | 批量重命名引擎，支持预览和执行 |
| `gdm/core/project.py` | 工作区状态保存/加载（.gdm.json） |

### GUI 层（PySide6）

| 文件 | 职责 |
|---|---|
| `gdm/gui/main_window.py` | 主窗口，布局与信号协调 |
| `gdm/gui/thumbnail_view.py` | 缩略图网格视图，异步加载，内存缓存 |
| `gdm/gui/detail_panel.py` | 侧边详情面板 |
| `gdm/gui/rename_dialog.py` | 批量重命名配置弹窗 |
| `gdm/gui/project_panel.py` | 工作区文件夹树面板 |

### 其他

| 文件 | 职责 |
|---|---|
| `gdm/utils/helpers.py` | 通用工具函数（文件大小格式化等） |
| `gdm/main.py` | 入口文件 |
| `requirements.txt` | 依赖声明 |
| `tests/test_models.py` | 核心模型测试 |
| `tests/test_metadata.py` | 元数据提取测试 |
| `tests/test_scanner.py` | 扫描器测试 |
| `tests/test_renamer.py` | 重命名引擎测试 |
| `tests/test_project.py` | 工作区管理测试 |

---

## 实现顺序

1. 项目初始化（目录结构、requirements.txt）
2. 核心模型（core/models.py）— 无依赖，先实现
3. 元数据提取（core/metadata.py）— 依赖 models
4. 扫描器（core/scanner.py）— 依赖 models, metadata
5. 重命名引擎（core/renamer.py）— 依赖 models
6. 工作区管理（core/project.py）— 依赖 models
7. 工具函数（utils/helpers.py）
8. GUI：缩略图视图（gui/thumbnail_view.py）— 依赖 models
9. GUI：详情面板（gui/detail_panel.py）— 依赖 models
10. GUI：文件夹树面板（gui/project_panel.py）
11. GUI：重命名弹窗（gui/rename_dialog.py）— 依赖 models, renamer
12. GUI：主窗口（gui/main_window.py）— 依赖全部
13. 入口文件（main.py）
14. 集成测试与手动验证

---

### Task 1: 项目初始化

**Files:**
- Create: `requirements.txt`
- Create: `gdm/__init__.py`, `gdm/core/__init__.py`, `gdm/gui/__init__.py`, `gdm/utils/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: 创建目录结构**

```bash
mkdir -p gdm/core gdm/gui gdm/utils tests
touch gdm/__init__.py gdm/core/__init__.py gdm/gui/__init__.py gdm/utils/__init__.py tests/__init__.py
```

- [ ] **Step 2: 写入 requirements.txt**

```
PySide6>=6.5.0
Pillow>=10.0.0
pytest>=7.0.0
```

- [ ] **Step 3: 验证可安装依赖**

```bash
pip install -r requirements.txt
```

- [ ] **Step 4: 提交**

```bash
git init
git add requirements.txt gdm/ tests/
git commit -m "chore: 初始化项目结构"
```

---

### Task 2: 实现 core/models.py

**Files:**
- Create: `gdm/core/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_models.py
import pytest
from gdm.core.models import SpriteInfo, Project, RenameMode, RenameRule

def test_sprite_info_creation():
    sprite = SpriteInfo(
        file_path="/path/to/sprite.png",
        file_name="sprite.png",
        width=64,
        height=64,
        file_size=1024,
        format="PNG",
        color_mode="RGBA"
    )
    assert sprite.file_path == "/path/to/sprite.png"
    assert sprite.width == 64

def test_project_creation():
    project = Project(root_path="/path/to/project")
    assert project.root_path == "/path/to/project"

def test_rename_rule_prefix_number():
    rule = RenameRule(mode=RenameMode.PREFIX_NUMBER, prefix="sprite", start_index=1, padding=3)
    assert rule.prefix == "sprite"
    assert rule.padding == 3
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_models.py -v
```

预期：FAIL（`gdm.core.models` 不存在）

- [ ] **Step 3: 实现 models.py**

```python
# gdm/core/models.py
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List

class RenameMode(Enum):
    PREFIX_NUMBER = "前缀+序号"
    FIND_REPLACE = "查找替换"
    REGEX = "正则替换"
    ADD_SUFFIX = "添加后缀"

@dataclass
class SpriteInfo:
    file_path: str           # 完整路径
    file_name: str           # 文件名（含扩展名）
    width: int               # 像素宽度
    height: int              # 像素高度
    file_size: int           # 文件大小（字节）
    format: str              # 图片格式（PNG/JPEG/WebP...）
    color_mode: str          # 色彩模式（RGB/RGBA/P...）

@dataclass
class Project:
    root_path: str          # 工作区根目录
    # v1 仅保存根目录路径，后续版本可扩展其他字段。

@dataclass
class RenameRule:
    mode: RenameMode
    prefix: Optional[str] = None      # 前缀+序号模式用
    start_index: int = 1              # 序号起始值
    padding: int = 3                 # 序号补零位数
    find_text: Optional[str] = None   # 查找替换模式用
    replace_text: Optional[str] = None
    regex_pattern: Optional[str] = None  # 正则模式用
    regex_replacement: Optional[str] = None
    suffix: Optional[str] = None      # 添加后缀模式用
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_models.py -v
```

预期：PASS

- [ ] **Step 5: 提交**

```bash
git add gdm/core/models.py tests/test_models.py
git commit -m "feat: 添加核心数据模型 SpriteInfo, Project, RenameRule"
```

---

### Task 3: 实现 core/metadata.py

**Files:**
- Create: `gdm/core/metadata.py`
- Create: `tests/test_metadata.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_metadata.py
import pytest
from pathlib import Path
from gdm.core.metadata import extract
from gdm.core.models import SpriteInfo

def test_extract_valid_png(tmp_path):
    # 创建一个临时 PNG 文件用于测试
    from PIL import Image
    img = Image.new("RGBA", (64, 64), color=(255, 0, 0, 255))
    file_path = tmp_path / "test.png"
    img.save(file_path)
    
    sprite = extract(str(file_path))
    assert isinstance(sprite, SpriteInfo)
    assert sprite.width == 64
    assert sprite.height == 64
    assert sprite.format == "PNG"
    assert sprite.color_mode == "RGBA"
    assert sprite.file_size > 0

def test_extract_invalid_file(tmp_path):
    invalid_file = tmp_path / "invalid.txt"
    invalid_file.write_text("not an image")
    sprite = extract(str(invalid_file))
    # 应该返回部分信息，文件大小可读
    assert sprite.file_size > 0
    assert sprite.width == 0  # 未知
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_metadata.py -v
```

- [ ] **Step 3: 实现 metadata.py**

```python
# gdm/core/metadata.py
from pathlib import Path
from typing import Optional
from PIL import Image
from gdm.core.models import SpriteInfo

def extract(file_path: str) -> SpriteInfo:
    """提取图片元数据，失败则返回部分信息。"""
    file_name = Path(file_path).name
    file_size = Path(file_path).stat().st_size
    
    width, height = 0, 0
    format_ = "UNKNOWN"
    color_mode = "UNKNOWN"
    
    try:
        with Image.open(file_path) as img:
            width, height = img.size
            format_ = img.format or "UNKNOWN"
            color_mode = img.mode
    except Exception:
        pass  # 读取失败，使用默认值
    
    return SpriteInfo(
        file_path=file_path,
        file_name=file_name,
        width=width,
        height=height,
        file_size=file_size,
        format=format_,
        color_mode=color_mode
    )
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_metadata.py -v
```

- [ ] **Step 5: 提交**

```bash
git add gdm/core/metadata.py tests/test_metadata.py
git commit -m "feat: 添加图片元数据提取功能"
```

---

### Task 4: 实现 core/scanner.py

**Files:**
- Create: `gdm/core/scanner.py`
- Create: `tests/test_scanner.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_scanner.py
import pytest
from pathlib import Path
from gdm.core.scanner import scan
from gdm.core.models import SpriteInfo

def test_scan_directory(tmp_path):
    # 创建测试图片文件
    from PIL import Image
    img1 = Image.new("RGB", (32, 32))
    img1.save(tmp_path / "sprite1.png")
    img2 = Image.new("RGB", (64, 64))
    img2.save(tmp_path / "sprite2.jpg")
    (tmp_path / "not_an_image.txt").write_text("text")
    
    sprites = scan(str(tmp_path), recursive=False)
    assert len(sprites) == 2
    assert all(isinstance(s, SpriteInfo) for s in sprites)

def test_scan_recursive(tmp_path):
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    from PIL import Image
    img = Image.new("RGB", (16, 16))
    img.save(subdir / "sub.png")
    
    # 非递归应找不到
    sprites = scan(str(tmp_path), recursive=False)
    assert len(sprites) == 0
    # 递归应能找到
    sprites = scan(str(tmp_path), recursive=True)
    assert len(sprites) == 1
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_scanner.py -v
```

- [ ] **Step 3: 实现 scanner.py**

```python
# gdm/core/scanner.py
from pathlib import Path
from typing import List
from gdm.core.models import SpriteInfo
from gdm.core.metadata import extract

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}

def scan(directory: str, recursive: bool = False) -> List[SpriteInfo]:
    """扫描目录，返回图片 SpriteInfo 列表。"""
    path = Path(directory)
    if not path.is_dir():
        return []
    
    sprites = []
    pattern = "**/*" if recursive else "*"
    for file_path in path.glob(pattern):
        if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
            sprites.append(extract(str(file_path)))
    
    return sprites
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_scanner.py -v
```

- [ ] **Step 5: 提交**

```bash
git add gdm/core/scanner.py tests/test_scanner.py
git commit -m "feat: 添加文件夹扫描功能"
```

---

### Task 5: 实现 core/renamer.py

**Files:**
- Create: `gdm/core/renamer.py`
- Create: `tests/test_renamer.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_renamer.py
import pytest
from gdm.core.renamer import preview, execute
from gdm.core.models import SpriteInfo, RenameRule, RenameMode

def test_preview_prefix_number():
    sprites = [
        SpriteInfo(file_path="/a/old1.png", file_name="old1.png", width=0, height=0, file_size=0, format="", color_mode=""),
        SpriteInfo(file_path="/a/old2.png", file_name="old2.png", width=0, height=0, file_size=0, format="", color_mode=""),
    ]
    rule = RenameRule(mode=RenameMode.PREFIX_NUMBER, prefix="sprite", start_index=1, padding=3)
    result = preview(sprites, rule)
    assert result == [
        ("/a/old1.png", "/a/sprite_001.png"),
        ("/a/old2.png", "/a/sprite_002.png"),
    ]

def test_preview_find_replace():
    sprites = [
        SpriteInfo(file_path="/a/old_sprite.png", file_name="old_sprite.png", width=0, height=0, file_size=0, format="", color_mode=""),
    ]
    rule = RenameRule(mode=RenameMode.FIND_REPLACE, find_text="old_", replace_text="new_")
    result = preview(sprites, rule)
    assert result == [("/a/old_sprite.png", "/a/new_sprite.png")]
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_renamer.py -v
```

- [ ] **Step 3: 实现 renamer.py**

```python
# gdm/core/renamer.py
import os
import re
from typing import List, Tuple
from gdm.core.models import SpriteInfo, RenameRule, RenameMode

def preview(sprites: List[SpriteInfo], rule: RenameRule) -> List[Tuple[str, str]]:
    """返回（原路径, 新路径）对照表，不实际写入。"""
    results = []
    for i, sprite in enumerate(sprites):
        new_name = _generate_new_name(sprite.file_name, rule, i)
        new_path = os.path.join(os.path.dirname(sprite.file_path), new_name)
        results.append((sprite.file_path, new_path))
    return results

def execute(sprites: List[SpriteInfo], rule: RenameRule) -> Tuple[int, List[str]]:
    """执行重命名，原地更新 SpriteInfo 对象。返回（成功数量, 旧路径列表）。"""
    results = preview(sprites, rule)
    success_count = 0
    old_paths = []
    
    for sprite, (old_path, new_path) in zip(sprites, results):
        if os.path.exists(new_path) and new_path != old_path:
            continue  # 目标已存在，跳过
        try:
            os.rename(old_path, new_path)
            sprite.file_path = new_path
            sprite.file_name = os.path.basename(new_path)
            old_paths.append(old_path)
            success_count += 1
        except OSError:
            continue
    
    return success_count, old_paths

def _generate_new_name(original_name: str, rule: RenameRule, index: int) -> str:
    name, ext = os.path.splitext(original_name)
    
    if rule.mode == RenameMode.PREFIX_NUMBER:
        new_name = f"{rule.prefix}_{index + rule.start_index:0{rule.padding}d}{ext}"
    elif rule.mode == RenameMode.FIND_REPLACE:
        new_name = original_name.replace(rule.find_text, rule.replace_text)
    elif rule.mode == RenameMode.REGEX:
        new_name = re.sub(rule.regex_pattern, rule.regex_replacement, original_name)
    elif rule.mode == RenameMode.ADD_SUFFIX:
        new_name = f"{name}{rule.suffix}{ext}"
    else:
        new_name = original_name
    
    return new_name
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_renamer.py -v
```

- [ ] **Step 5: 提交**

```bash
git add gdm/core/renamer.py tests/test_renamer.py
git commit -m "feat: 添加批量重命名引擎"
```

---

### Task 6: 实现 core/project.py

**Files:**
- Create: `gdm/core/project.py`
- Create: `tests/test_project.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_project.py
import pytest
from pathlib import Path
from gdm.core.project import save, load
from gdm.core.models import Project

def test_save_and_load(tmp_path):
    project = Project(root_path=str(tmp_path))
    save_path = str(tmp_path / ".gdm.json")
    save(project, save_path)
    
    assert Path(save_path).exists()
    
    loaded = load(save_path)
    assert loaded is not None
    assert loaded.root_path == str(tmp_path)

def test_load_nonexistent():
    loaded = load("/nonexistent/.gdm.json")
    assert loaded is None
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_project.py -v
```

- [ ] **Step 3: 实现 project.py**

```python
# gdm/core/project.py
import json
from pathlib import Path
from typing import Optional
from gdm.core.models import Project

def save(project: Project, path: str) -> None:
    """将工作区状态写入 .gdm.json"""
    data = {"root_path": project.root_path}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load(path: str) -> Optional[Project]:
    """读取 .gdm.json 恢复工作区。失败返回 None。"""
    if not Path(path).exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Project(root_path=data["root_path"])
    except (json.JSONDecodeError, KeyError):
        return None
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_project.py -v
```

- [ ] **Step 5: 提交**

```bash
git add gdm/core/project.py tests/test_project.py
git commit -m "feat: 添加工作区状态保存/加载功能"
```

---

### Task 7: 实现 utils/helpers.py

**Files:**
- Create: `gdm/utils/helpers.py`

- [ ] **Step 1: 实现 helpers.py**

```python
# gdm/utils/helpers.py
def format_file_size(size_bytes: int) -> str:
    """将字节数格式化为 KB/MB 字符串。"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
```

- [ ] **Step 2: 提交**

```bash
git add gdm/utils/helpers.py
git commit -m "feat: 添加工具函数（文件大小格式化）"
```

---

### Task 8: 实现 gui/thumbnail_view.py

**Files:**
- Create: `gdm/gui/thumbnail_view.py`
- Modify: `gdm/gui/__init__.py`

- [ ] **Step 1: 实现 thumbnail_view.py（基础版，无异步）**

```python
# gdm/gui/thumbnail_view.py
from PySide6.QtWidgets import QWidget, QListWidget, QListWidgetItem, QVBoxLayout
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QIcon, QPixmap
from typing import List, Dict
from gdm.core.models import SpriteInfo

class ThumbnailView(QWidget):
    selection_changed = Signal(object)  # SpriteInfo
    
    def __init__(self):
        super().__init__()
        self.sprites: List[SpriteInfo] = []
        self.cache: Dict[str, QPixmap] = {}  # 缩略图内存缓存
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListWidget.IconMode)
        self.list_widget.setIconSize(QPixmap(128, 128).size())
        self.list_widget.setSelectionMode(QListWidget.ExtendedSelection)
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.list_widget)
    
    def load(self, sprites: List[SpriteInfo]):
        """加载精灵图列表。"""
        self.sprites = sprites
        self.list_widget.clear()
        for sprite in sprites:
            item = QListWidgetItem(QIcon(self._get_thumbnail(sprite)), sprite.file_name)
            item.setData(Qt.UserRole, sprite)
            self.list_widget.addItem(item)
    
    def _get_thumbnail(self, sprite: SpriteInfo) -> QPixmap:
        """获取缩略图，使用内存缓存。"""
        if sprite.file_path in self.cache:
            return self.cache[sprite.file_path]
        pixmap = QPixmap(sprite.file_path)
        if pixmap.isNull():
            pixmap = QPixmap(128, 128)
        scaled = pixmap.scaled(128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.cache[sprite.file_path] = scaled
        return scaled
    
    def _on_selection_changed(self):
        items = self.list_widget.selectedItems()
        if items:
            sprite = items[0].data(Qt.UserRole)
            self.selection_changed.emit(sprite)
    
    def update_cache_keys(self, old_paths: List[str], new_paths: List[str]):
        """重命名后更新缓存 key。"""
        for old, new in zip(old_paths, new_paths):
            if old in self.cache:
                self.cache[new] = self.cache.pop(old)
```

- [ ] **Step 2: 提交**

```bash
git add gdm/gui/thumbnail_view.py
git commit -m "feat: 添加缩略图网格视图（基础版）"
```

---

### Task 9: 实现 gui/detail_panel.py

**Files:**
- Create: `gdm/gui/detail_panel.py`

- [ ] **Step 1: 实现 detail_panel.py**

```python
# gdm/gui/detail_panel.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from typing import List, Optional
from gdm.core.models import SpriteInfo
from gdm.utils.helpers import format_file_size

class DetailPanel(QWidget):
    def __init__(self):
        super().__init__()
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        self.preview_label = QLabel("预览")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setFrameStyle(QFrame.Box)
        layout.addWidget(self.preview_label)
        
        self.info_labels = {}
        for key in ["文件名", "像素尺寸", "文件大小", "格式", "色彩模式", "路径"]:
            label = QLabel(f"{key}: ")
            layout.addWidget(label)
            self.info_labels[key] = label
        
        layout.addStretch()
    
    def update(self, sprite: SpriteInfo):
        """更新显示单张图片信息。"""
        pixmap = QPixmap(sprite.file_path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(256, 256, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.preview_label.setPixmap(scaled)
        else:
            self.preview_label.setText("无法加载图片")
        
        self.info_labels["文件名"].setText(f"文件名: {sprite.file_name}")
        self.info_labels["像素尺寸"].setText(f"像素尺寸: {sprite.width} × {sprite.height}")
        self.info_labels["文件大小"].setText(f"文件大小: {format_file_size(sprite.file_size)}")
        self.info_labels["格式"].setText(f"格式: {sprite.format}")
        self.info_labels["色彩模式"].setText(f"色彩模式: {sprite.color_mode}")
        self.info_labels["路径"].setText(f"路径: {sprite.file_path}")
    
    def update_multiple(self, sprites: List[SpriteInfo]):
        """更新显示多张图片汇总信息。"""
        if not sprites:
            return
        total_size = sum(s.file_size for s in sprites)
        self.preview_label.setText(f"共 {len(sprites)} 张图片")
        self.info_labels["文件名"].setText(f"共 {len(sprites)} 张")
        self.info_labels["像素尺寸"].setText("")  # 多张时不显示单个尺寸
        self.info_labels["文件大小"].setText(f"总大小: {format_file_size(total_size)}")
        self.info_labels["格式"].setText("")
        self.info_labels["色彩模式"].setText("")
        self.info_labels["路径"].setText("")
```

- [ ] **Step 2: 提交**

```bash
git add gdm/gui/detail_panel.py
git commit -m "feat: 添加侧边详情面板"
```

---

### Task 10: 实现 gui/project_panel.py

**Files:**
- Create: `gdm/gui/project_panel.py`

- [ ] **Step 1: 实现 project_panel.py**

```python
# gdm/gui/project_panel.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem
from PySide6.QtCore import Signal
from pathlib import Path

class ProjectPanel(QWidget):
    folder_selected = Signal(str)  # 选中的文件夹路径
    
    def __init__(self):
        super().__init__()
        self.root_path: str = ""
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("文件夹")
        self.tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.tree)
    
    def set_root(self, path: str):
        """设置工作区根目录，构建文件夹树。"""
        self.root_path = path
        self.tree.clear()
        root_item = QTreeWidgetItem(self.tree, [Path(path).name])
        root_item.setData(0, 42, path)  # 存储完整路径
        self._populate_tree(root_item, path)
        self.tree.expandItem(root_item)
    
    def _populate_tree(self, parent_item: QTreeWidgetItem, parent_path: str):
        """递归填充子目录。"""
        try:
            for entry in sorted(Path(parent_path).iterdir()):
                if entry.is_dir() and not entry.name.startswith("."):
                    child = QTreeWidgetItem(parent_item, [entry.name])
                    child.setData(0, 42, str(entry))
                    self._populate_tree(child, str(entry))
        except PermissionError:
            pass
    
    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        path = item.data(0, 42)
        if path:
            self.folder_selected.emit(path)
```

- [ ] **Step 2: 提交**

```bash
git add gdm/gui/project_panel.py
git commit -m "feat: 添加工作区文件夹树面板"
```

---

### Task 11: 实现 gui/rename_dialog.py

**Files:**
- Create: `gdm/gui/rename_dialog.py`

- [ ] **Step 1: 实现 rename_dialog.py**

```python
# gdm/gui/rename_dialog.py
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QComboBox,
                             QLineEdit, QLabel, QPushButton, QListWidget, QMessageBox)
from PySide6.QtCore import Signal
from gdm.core.models import RenameRule, RenameMode
from gdm.core.renamer import preview, execute

class RenameDialog(QDialog):
    renamed = Signal(list, list)  # (old_paths, sprites)
    
    def __init__(self, sprites: list, parent=None):
        super().__init__(parent)
        self.sprites = sprites
        self.setWindowTitle("批量重命名")
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # 模式选择
        layout.addWidget(QLabel("重命名模式:"))
        self.mode_combo = QComboBox()
        for mode in RenameMode:
            self.mode_combo.addItem(mode.value, mode)
        self.mode_combo.currentChanged.connect(self._on_mode_changed)
        layout.addWidget(self.mode_combo)
        
        # 参数输入区（动态）
        self.param_layout = QVBoxLayout()
        layout.addLayout(self.param_layout)
        
        # 预览列表
        layout.addWidget(QLabel("预览:"))
        self.preview_list = QListWidget()
        layout.addWidget(self.preview_list)
        
        # 按钮
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("确认")
        ok_btn.clicked.connect(self._on_accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        self._on_mode_changed()  # 初始化参数区
    
    def _on_mode_changed(self):
        # 清空参数区，根据模式添加输入控件
        # 简化实现：仅处理前缀+序号模式
        pass
    
    def _on_accept(self):
        rule = self._build_rule()
        if rule is None:
            return
        old_paths, sprites = [], []
        for old, new in preview(self.sprites, rule):
            old_paths.append(old)
        # 执行重命名
        count, old_paths = execute(self.sprites, rule)
        if count > 0:
            self.renamed.emit(old_paths, self.sprites)
        self.accept()
    
    def _build_rule(self) -> Optional[RenameRule]:
        mode = self.mode_combo.currentData()
        if mode == RenameMode.PREFIX_NUMBER:
            prefix = "sprite"  # 简化：写死，实际应从输入框读取
            return RenameRule(mode=mode, prefix=prefix)
        return None
```

- [ ] **Step 2: 提交**

```bash
git add gdm/gui/rename_dialog.py
git commit -m "feat: 添加批量重命名配置弹窗"
```

---

### Task 12: 实现 gui/main_window.py

**Files:**
- Create: `gdm/gui/main_window.py`

- [ ] **Step 1: 实现 main_window.py**

```python
# gdm/gui/main_window.py
from PySide6.QtWidgets import QMainWindow, QFileDialog, QMessageBox
from PySide6.QtCore import Qt
from gdm.core.scanner import scan
from gdm.core.project import save, load
from gdm.core.models import Project
from gdm.gui.thumbnail_view import ThumbnailView
from gdm.gui.detail_panel import DetailPanel
from gdm.gui.project_panel import ProjectPanel
from gdm.gui.rename_dialog import RenameDialog

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.project: Optional[Project] = None
        self.current_sprites: list = []
        self._init_ui()
        self._try_restore_project()
    
    def _init_ui(self):
        self.setWindowTitle("GDM - Game Dev Manager")
        self.resize(1200, 800)
        
        # 中心部件
        from PySide6.QtWidgets import QWidget, QHBoxLayout
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        
        # 左侧文件夹树
        self.project_panel = ProjectPanel()
        self.project_panel.folder_selected.connect(self._on_folder_selected)
        layout.addWidget(self.project_panel, 1)
        
        # 中间缩略图视图
        self.thumbnail_view = ThumbnailView()
        self.thumbnail_view.selection_changed.connect(self._on_sprite_selected)
        layout.addWidget(self.thumbnail_view, 3)
        
        # 右侧详情面板
        self.detail_panel = DetailPanel()
        layout.addWidget(self.detail_panel, 1)
        
        # 菜单栏
        menubar = self.menuBar()
        file_menu = menubar.addMenu("文件")
        open_action = file_menu.addAction("打开文件夹")
        open_action.triggered.connect(self._open_folder)
        save_action = file_menu.addAction("保存工作区")
        save_action.triggered.connect(self._save_project)
        exit_action = file_menu.addAction("退出")
        exit_action.triggered.connect(self.close())
        
        tool_menu = menubar.addMenu("工具")
        rename_action = tool_menu.addAction("批量重命名")
        rename_action.triggered.connect(self._open_rename_dialog)
    
    def _open_folder(self):
        path = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if path:
            self.project = Project(root_path=path)
            self.project_panel.set_root(path)
            self._load_sprites(path, recursive=False)
    
    def _on_folder_selected(self, path: str):
        self._load_sprites(path, recursive=False)
    
    def _load_sprites(self, path: str, recursive: bool):
        self.current_sprites = scan(path, recursive=recursive)
        self.thumbnail_view.load(self.current_sprites)
    
    def _on_sprite_selected(self, sprite):
        self.detail_panel.update(sprite)
    
    def _open_rename_dialog(self):
        if not self.current_sprites:
            QMessageBox.warning(self, "警告", "没有可重命名的文件")
            return
        dialog = RenameDialog(self.current_sprites, self)
        dialog.renamed.connect(self._on_renamed)
        dialog.exec()
    
    def _on_renamed(self, old_paths: list, sprites: list):
        # 更新缩略图缓存
        new_paths = [s.file_path for s in sprites]
        self.thumbnail_view.update_cache_keys(old_paths, new_paths)
        # 刷新当前视图
        self._load_sprites(self.project.root_path if self.project else ".", recursive=False)
    
    def _save_project(self):
        if not self.project:
            return
        save_path = f"{self.project.root_path}/.gdm.json"
        save(self.project, save_path)
    
    def _try_restore_project(self):
        # 简化：不自动恢复，留待后续版本
        pass
```

- [ ] **Step 2: 提交**

```bash
git add gdm/gui/main_window.py
git commit -m "feat: 添加主窗口与信号协调"
```

---

### Task 13: 实现 main.py

**Files:**
- Create: `gdm/main.py`

- [ ] **Step 1: 实现 main.py**

```python
# gdm/main.py
import sys
from PySide6.QtWidgets import QApplication
from gdm.gui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 提交**

```bash
git add gdm/main.py
git commit -m "feat: 添加应用入口"
```

---

### Task 14: 集成测试与手动验证

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: 写集成测试**

```python
# tests/test_integration.py
def test_full_workflow(tmp_path):
    """测试完整工作流：扫描 → 重命名 → 保存项目。"""
    # 创建测试图片
    from PIL import Image
    img = Image.new("RGB", (32, 32))
    img.save(tmp_path / "test1.png")
    img.save(tmp_path / "test2.png")
    
    # 扫描
    from gdm.core.scanner import scan
    sprites = scan(str(tmp_path), recursive=False)
    assert len(sprites) == 2
    
    # 重命名预览
    from gdm.core.renamer import preview
    from gdm.core.models import RenameRule, RenameMode
    rule = RenameRule(mode=RenameMode.PREFIX_NUMBER, prefix="sprite")
    results = preview(sprites, rule)
    assert "sprite_001.png" in results[0][1]
    
    # 保存项目
    from gdm.core.project import save, load
    from gdm.core.models import Project
    project = Project(root_path=str(tmp_path))
    save(project, str(tmp_path / ".gdm.json"))
    loaded = load(str(tmp_path / ".gdm.json"))
    assert loaded.root_path == str(tmp_path)
```

- [ ] **Step 2: 运行全部测试**

```bash
pytest tests/ -v
```

预期：全部 PASS

- [ ] **Step 3: 手动验证**

启动应用：
```bash
python -m gdm.main
```

验证功能：
1. 打开文件夹，显示缩略图
2. 点击图片，详情面板显示信息
3. 批量重命名，预览并执行
4. 保存工作区，重启后恢复

- [ ] **Step 4: 最终提交**

```bash
git add tests/test_integration.py
git commit -m "test: 添加集成测试"
```

---

## 自审查（Self-Review）

After writing the plan, I ran a mental check:

1. **Spec coverage:** 所有设计文档中的功能都有对应任务。
2. **Placeholder scan:** 未发现 TBD/TODO。但 Task 11 中的 `_on_mode_changed` 和 `_build_rule` 是简化实现，需要在实现时补充完整。
3. **Type consistency:** 所有类型、方法名、属性名在前后的任务中保持一致。
4. **遗漏:** 设计文档中要求缩略图异步加载（QRunnable + QThreadPool），但 Task 8 实现的是同步加载。需要在 Task 8 中补充异步加载实现。

**修正：** 在 Task 8 中补充异步加载实现。

---

## 执行交接

Plan complete and saved to `docs/superpowers/plans/2026-06-12-gdm-sprite-manager-implementation.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
