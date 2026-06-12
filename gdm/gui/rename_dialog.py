"""批量重命名配置弹窗

提供重命名模式选择、参数输入、预览和执行的对话框。
"""

from typing import List, Optional, Tuple

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gdm.core.models import SpriteInfo, RenameRule, RenameMode
from gdm.core.renamer import execute, preview


class RenameDialog(QDialog):
    """批量重命名配置弹窗。

    支持四种重命名模式：
    1. 前缀 + 序号
    2. 查找替换
    3. 正则替换
    4. 添加后缀

    信号：
        renamed(List[str], List[SpriteInfo]): 重命名完成后发射，
            携带旧路径列表和更新后的 SpriteInfo 对象列表
    """

    renamed = pyqtSignal(list, list)

    def __init__(
        self, sprites: List[SpriteInfo], parent: Optional[QWidget] = None
    ) -> None:
        """初始化重命名对话框。

        Args:
            sprites: 待重命名的精灵图信息列表
            parent: 父窗口
        """
        super().__init__(parent)
        self._sprites = sprites
        self._init_ui()

    def _init_ui(self) -> None:
        """初始化 UI 组件。"""
        self.setWindowTitle("批量重命名")
        self.setMinimumWidth(500)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)

        # 1. 模式选择区
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("重命名模式："))
        self._mode_combo = QComboBox()
        for mode in RenameMode:
            self._mode_combo.addItem(mode.value, mode)
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_layout.addWidget(self._mode_combo)
        mode_layout.addStretch()
        main_layout.addLayout(mode_layout)

        # 2. 参数输入区（使用 QStackedWidget 动态切换）
        self._param_stack = QStackedWidget()

        # 模式 1：前缀 + 序号
        self._param_stack.addWidget(self._create_prefix_number_widget())

        # 模式 2：查找替换
        self._param_stack.addWidget(self._create_find_replace_widget())

        # 模式 3：正则替换
        self._param_stack.addWidget(self._create_regex_widget())

        # 模式 4：添加后缀
        self._param_stack.addWidget(self._create_add_suffix_widget())

        main_layout.addWidget(self._param_stack)

        # 3. 预览列表
        preview_group = QGroupBox("预览（原文件名 → 新文件名）")
        preview_layout = QVBoxLayout(preview_group)
        self._preview_list = QListWidget()
        self._preview_list.setMaximumHeight(200)
        preview_layout.addWidget(self._preview_list)
        main_layout.addWidget(preview_group)

        # 4. 按钮区
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self._preview_button = QPushButton("预览")
        self._preview_button.clicked.connect(self._on_preview)
        button_layout.addWidget(self._preview_button)

        self._ok_button = QPushButton("确认")
        self._ok_button.setDefault(True)
        self._ok_button.clicked.connect(self._on_accept)
        button_layout.addWidget(self._ok_button)

        self._cancel_button = QPushButton("取消")
        self._cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self._cancel_button)

        main_layout.addLayout(button_layout)

        # 初始状态：更新预览
        self._update_preview()

    def _create_prefix_number_widget(self) -> QWidget:
        """创建"前缀 + 序号"模式的参数输入组件。

        Returns:
            参数输入组件
        """
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self._prefix_edit = QLineEdit()
        self._prefix_edit.setPlaceholderText("例如：sprite")
        self._prefix_edit.textChanged.connect(self._update_preview)
        layout.addRow("前缀：", self._prefix_edit)

        self._start_index_spin = QSpinBox()
        self._start_index_spin.setMinimum(0)
        self._start_index_spin.setValue(1)
        self._start_index_spin.valueChanged.connect(self._update_preview)
        layout.addRow("起始序号：", self._start_index_spin)

        self._padding_spin = QSpinBox()
        self._padding_spin.setMinimum(1)
        self._padding_spin.setMaximum(10)
        self._padding_spin.setValue(3)
        self._padding_spin.valueChanged.connect(self._update_preview)
        layout.addRow("补零位数：", self._padding_spin)

        return widget

    def _create_find_replace_widget(self) -> QWidget:
        """创建"查找替换"模式的参数输入组件。

        Returns:
            参数输入组件
        """
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self._find_edit = QLineEdit()
        self._find_edit.setPlaceholderText("要查找的文本")
        self._find_edit.textChanged.connect(self._update_preview)
        layout.addRow("查找：", self._find_edit)

        self._replace_edit = QLineEdit()
        self._replace_edit.setPlaceholderText("替换成的文本（留空表示删除）")
        self._replace_edit.textChanged.connect(self._update_preview)
        layout.addRow("替换：", self._replace_edit)

        return widget

    def _create_regex_widget(self) -> QWidget:
        """创建"正则替换"模式的参数输入组件。

        Returns:
            参数输入组件
        """
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self._regex_pattern_edit = QLineEdit()
        self._regex_pattern_edit.setPlaceholderText("正则表达式（例如：(.*)\\.png）")
        self._regex_pattern_edit.textChanged.connect(self._update_preview)
        layout.addRow("正则表达式：", self._regex_pattern_edit)

        self._regex_replacement_edit = QLineEdit()
        self._regex_replacement_edit.setPlaceholderText(
            "替换文本（例如：new_\\1.png）"
        )
        self._regex_replacement_edit.textChanged.connect(self._update_preview)
        layout.addRow("替换文本：", self._regex_replacement_edit)

        return widget

    def _create_add_suffix_widget(self) -> QWidget:
        """创建"添加后缀"模式的参数输入组件。

        Returns:
            参数输入组件
        """
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self._suffix_edit = QLineEdit()
        self._suffix_edit.setPlaceholderText("例如：_compressed")
        self._suffix_edit.textChanged.connect(self._update_preview)
        layout.addRow("后缀：", self._suffix_edit)

        return widget

    def _on_mode_changed(self, index: int) -> None:
        """模式切换回调，更新参数输入区和预览。

        Args:
            index: 当前选中的模式索引
        """
        self._param_stack.setCurrentIndex(index)
        self._update_preview()

    def _update_preview(self) -> None:
        """更新预览列表。"""
        try:
            rule = self._build_rule()
            if rule is None:
                self._preview_list.clear()
                return
        except ValueError:
            self._preview_list.clear()
            return

        results: List[Tuple[str, str]] = preview(self._sprites, rule)
        self._preview_list.clear()

        for old_path, new_path in results:
            old_name = self._get_file_name(old_path)
            new_name = self._get_file_name(new_path)
            item = QListWidgetItem(f"{old_name}  →  {new_name}")
            item.setToolTip(f"原路径：{old_path}\n新路径：{new_path}")
            self._preview_list.addItem(item)

    @staticmethod
    def _get_file_name(file_path: str) -> str:
        """从完整路径中提取文件名。

        Args:
            file_path: 完整文件路径

        Returns:
            文件名（含扩展名）
        """
        import os

        return os.path.basename(file_path)

    def _build_rule(self) -> Optional[RenameRule]:
        """从 UI 输入构建 RenameRule 对象。

        Returns:
            RenameRule 对象，如果输入无效则返回 None
        """
        mode: RenameMode = self._mode_combo.currentData()

        if mode == RenameMode.PREFIX_NUMBER:
            prefix = self._prefix_edit.text().strip()
            if not prefix:
                return None
            return RenameRule(
                mode=mode,
                prefix=prefix,
                start_index=self._start_index_spin.value(),
                padding=self._padding_spin.value(),
            )

        elif mode == RenameMode.FIND_REPLACE:
            find_text = self._find_edit.text()
            if not find_text:
                return None
            return RenameRule(
                mode=mode,
                find_text=find_text,
                replace_text=self._replace_edit.text(),
            )

        elif mode == RenameMode.REGEX:
            pattern = self._regex_pattern_edit.text()
            if not pattern:
                return None
            return RenameRule(
                mode=mode,
                regex_pattern=pattern,
                regex_replacement=self._regex_replacement_edit.text(),
            )

        elif mode == RenameMode.ADD_SUFFIX:
            suffix = self._suffix_edit.text().strip()
            if not suffix:
                return None
            return RenameRule(mode=mode, suffix=suffix)

        return None

    def _on_preview(self) -> None:
        """预览按钮点击事件。"""
        self._update_preview()

    def _on_accept(self) -> None:
        """确认按钮点击事件，执行重命名。"""
        rule = self._build_rule()
        if rule is None:
            QMessageBox.warning(self, "输入错误", "请填写必要的参数。")
            return

        # 执行重命名
        success_count, old_paths = execute(self._sprites, rule)

        if success_count == 0:
            QMessageBox.warning(
                self, "重命名失败", "没有文件被重命名，请检查参数或文件权限。"
            )
            return

        # 显示成功消息
        QMessageBox.information(
            self, "重命名完成", f"成功重命名 {success_count} 个文件。"
        )

        # 发射 renamed 信号
        self.renamed.emit(old_paths, self._sprites)

        # 关闭对话框
        self.accept()
