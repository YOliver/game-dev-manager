from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QMenu, QMessageBox
from PySide6.QtCore import Signal
from pathlib import Path
import os


class ProjectPanel(QWidget):
    """工作区文件夹树面板（支持多根目录）。"""
    _GREEN = QColor("#22c55e")  # 含图片目录的字体颜色
    folder_selected = Signal(str)  # 选中的文件夹路径
    root_removed = Signal(str)  # 移除的根目录路径

    def __init__(self):
        super().__init__()
        self.root_path: str = ""
        self._img_dirs: set[str] = set()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # 面板边距归零

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)          # 隐藏"文件夹"列标题
        self.tree.setIndentation(10)             # 缩进从默认20→10
        self.tree.setStyleSheet("""
            QTreeWidget {
                font-size: 11px;
            }
            QTreeWidget::item {
                padding: 1px 0px;
                margin: 0px;
                border: none;
            }
            QTreeWidget::item:selected {
                background-color: #0078d4;
                color: white;
            }
            QTreeWidget::item:selected:active {
                background-color: #0078d4;
                color: white;
            }
            QTreeWidget::branch {
                margin: 0px;
                padding: 0px;
            }
        """)
        self.tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.tree)

    def add_root(self, path: str) -> None:
        """追加一个根目录到树中。

        - 检测路径是否存在，不存在则提示
        - 检查是否已存在，避免重复顶级项
        - 构建子树并追加为顶级项
        """
        # 检查路径是否存在
        if not os.path.isdir(path):
            QMessageBox.warning(self, "警告", f"目录不存在:\n{path}")
            return

        # 检查是否已存在
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item.data(0, 42) == path:
                return  # 已存在，跳过

        # 构建子树并追加为顶级项
        try:
            self._img_dirs = self._build_img_dirs(path)
        except Exception:
            self._img_dirs = set()

        root_item = QTreeWidgetItem(self.tree, [Path(path).name])
        root_item.setData(0, 42, path)
        if path in self._img_dirs:
            root_item.setForeground(0, self._GREEN)
        self._populate_tree(root_item, path)

    def remove_root(self, path: str) -> None:
        """从树中移除指定根目录。"""
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item.data(0, 42) == path:
                self.tree.takeTopLevelItem(i)
                break

    def _populate_tree(self, parent_item: QTreeWidgetItem, parent_path: str):
        """递归填充子目录。"""
        try:
            for entry in sorted(Path(parent_path).iterdir()):
                if entry.is_dir() and not entry.name.startswith("."):
                    child = QTreeWidgetItem(parent_item, [entry.name])
                    child.setData(0, 42, str(entry))
                    if str(entry) in self._img_dirs:
                        child.setForeground(0, self._GREEN)
                    self._populate_tree(child, str(entry))
        except PermissionError:
            pass

    def _build_img_dirs(self, root_path: str) -> set[str]:
        """轻量扫描 root_path 下所有图片（仅检查扩展名），返回含图片的目录及所有父目录。"""
        from gdm.core.scanner import SUPPORTED_EXTENSIONS
        img_dirs: set[str] = set()
        root = Path(root_path)
        try:
            for file_path in root.rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                    img_dirs.add(str(file_path.parent))
        except PermissionError:
            pass
        all_parents: set[str] = set(img_dirs)
        for d in img_dirs:
            parent = Path(d).parent
            while str(parent) != root_path and str(parent) not in all_parents:
                all_parents.add(str(parent))
                parent = parent.parent
        if img_dirs:
            all_parents.add(root_path)
        return all_parents

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        path = item.data(0, 42)
        if path:
            self.folder_selected.emit(path)

    def contextMenuEvent(self, event) -> None:
        """右键菜单：只对顶级项显示"移除"选项。"""
        item = self.tree.itemAt(event.pos())
        if item is None:
            return

        # 判断是否为顶级项（根目录）
        if item.parent() is None:
            menu = QMenu(self)
            remove_action = menu.addAction("从工作区移除")
            remove_action.triggered.connect(lambda: self._on_remove_root(item))
            menu.exec(event.globalPos())

    def _on_remove_root(self, item) -> None:
        """处理移除根目录请求。"""
        path = item.data(0, 42)
        self.remove_root(path)
        self.root_removed.emit(path)
