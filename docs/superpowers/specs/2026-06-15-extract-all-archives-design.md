# 全量解压

## 问题描述

用户需要在项目面板选中目录中批量解压所有压缩包，递归处理嵌套压缩包，解压后自动删除原始压缩文件。

## 设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 支持格式 | zip, tar, gz, bz2, xz | Python 标准库原生支持，无需额外依赖 |
| 嵌套处理 | 递归解压全部 | 压缩包内的压缩包也解压 |
| 解压范围 | 当前选中目录 | 项目面板点击的目录 |
| 同名冲突 | 添加"副本"后缀 | 避免覆盖已有文件 |
| 确认机制 | 弹 QMessageBox 确认 | 告知用户压缩包数量和总大小 |

## 架构

新增 `gdm/core/extractor.py`，修改 `gdm/gui/main_window.py`。

### extractor.py — 核心解压逻辑

```python
SUPPORTED_ARCHIVE_EXTENSIONS = {".zip", ".tar", ".gz", ".bz2", ".xz", ".tgz"}

def find_archives(directory: str) -> List[str]:
    """递归搜索目录下的所有压缩包，按文件名排序返回路径列表"""

def get_archive_info(archive_path: str) -> dict:
    """获取压缩包信息：size 字段"""

def extract_archive(archive_path: str) -> str:
    """解压单个压缩包到同级目录，返回解压后的目录名。
    
    - 自动检测格式（zip/tar/gz/bz2/xz）
    - 重名时添加"副本"后缀（如 "dir 副本"、"dir 副本2"）
    - 解压完成后删除原始压缩包
    """

def extract_all(directory: str) -> Tuple[int, int, List[str]]:
    """递归解压目录下所有压缩包。
    
    流程：find_archives → 逐个 extract_archive → 删除 → 再 find_archives
    → 循环直到无新压缩包（处理嵌套）
    
    返回 (成功数, 失败数, 失败文件路径列表)
    """
```

### 格式检测

```python
def _open_archive(archive_path: str):
    """根据扩展名选择合适的打开方式。
    
    .zip       → zipfile.ZipFile
    .tar       → tarfile.open("r")
    .tar.gz    → tarfile.open("r:gz")
    .tgz       → tarfile.open("r:gz")
    .tar.bz2   → tarfile.open("r:bz2")
    .tar.xz    → tarfile.open("r:xz")
    .gz        → gzip.open (单文件)
    .bz2       → bz2.open (单文件)
    .xz        → lzma.open (单文件)
    """
```

### 错误处理

- 不支持的格式：跳过，计入失败
- 损坏的压缩包：跳过，计入失败
- 权限不足：跳过，计入失败
- 所有异常 catch 后记录到 log，不中断后续处理

### main_window.py — 菜单注册和调用入口

**追踪选中目录：** 在 `_on_folder_selected()` 中新增 `self._selected_folder = folder_path`，追踪用户当前点击的树节点。

```python
def _open_extract_all(self) -> None:
    """打开全量解压功能。
    
    1. 获取当前选中目录：self._selected_folder or self._project.root_path
    2. 扫描压缩包：find_archives(directory)
    3. 弹出 QMessageBox 确认（数量 + 总大小）
    4. 用户确认后执行 extract_all(directory)
    5. 弹出结果提示（成功/失败数）
    6. 刷新视图：_on_folder_selected(directory)
    """
```

目录获取优先级：先取用户在树中点击的目录（`_selected_folder`），未点击时回退到工作区根目录（`_project.root_path`）。

**初始化：** 在 `__init__()` 中添加 `self._selected_folder: Optional[str] = None`。

**_on_folder_selected 修改：**

```python
def _on_folder_selected(self, folder_path: str) -> None:
    self._selected_folder = folder_path  # 追踪当前选中
    self.thumbnail_view.show_progress()
    self._start_scan(folder_path, on_finished=self._on_tree_scan_finished)
```

**菜单注册（`_init_menubar()`）：**

```python
extract_action = QAction("全量解压", self)
extract_action.triggered.connect(self._open_extract_all)
```

**_toolbar_actions 字典中追加：**

```python
"工具": [rename_action, extract_action],
```

### 确认对话框

确认时仅显示压缩包原始信息（文件名、大小），"副本"命名在执行解压时动态处理。

```
QMessageBox.question(title="全量解压",
    text="共发现 N 个压缩包，总大小 X MB\n解压后原始压缩包将被删除")
```

### 结果提示

```
QMessageBox.information(title="全量解压",
    text="解压完成：成功 X 个，失败 Y 个")
如有失败，追加失败文件列表。
```

### 改动范围

| 文件 | 改动 |
|------|------|
| `gdm/core/extractor.py` | 新建 |
| `gdm/gui/main_window.py` | 添加菜单项、`_open_extract_all` 方法、`_selected_folder` 成员变量 |

### 边缘情况处理

| 场景 | 行为 |
|------|------|
| 未选中任何目录 | 提示"请先在项目面板中选择一个目录" |
| 未发现压缩包 | 提示"未发现压缩包" |
| 空压缩包 | 正常解压（产生空目录），计为成功 |
| 单文件压缩包（.gz） | 以文件名（去扩展名）创建目录，放入解压文件 |
| 确认对话框点取消 | 不执行任何操作 |

### 不改动的内容

- 项目面板选中机制不变
- 扫描器和元数据模块不变
