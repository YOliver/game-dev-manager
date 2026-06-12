"""侧边详情面板

显示单张/多张精灵图的预览图和元数据信息。
"""

from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gdm.core.models import SpriteInfo
from gdm.utils.helpers import format_file_size


class DetailPanel(QWidget):
    """侧边详情面板。

    显示单张精灵图的预览图和元数据，或多张精灵图的汇总信息。
    仅读取 SpriteInfo 字段，不调用任何核心模块。
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        """初始化 UI 组件。"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # 滚动区域（内容可能超出面板高度）
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)

        # 内容容器
        content_widget = QWidget()
        self._content_layout = QVBoxLayout(content_widget)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(8)

        # 预览图标签（固定 256x256，图片等比例缩放显示）
        self._preview_label = QLabel()
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setFixedSize(256, 256)
        self._preview_label.setStyleSheet(
            "border: 1px solid #ccc; background-color: #f0f0f0;"
        )
        self._content_layout.addWidget(
            self._preview_label, 0, Qt.AlignmentFlag.AlignCenter
        )

        # 单张信息：元数据表单
        self._form_layout = QFormLayout()
        self._form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._form_layout.setSpacing(4)

        self._name_label = QLabel()
        self._dimensions_label = QLabel()
        self._file_size_label = QLabel()
        self._format_label = QLabel()
        self._color_mode_label = QLabel()
        self._path_label = QLabel()
        self._path_label.setWordWrap(True)
        self._path_label.setStyleSheet("color: #666; font-size: 9pt;")

        self._form_layout.addRow("文件名：", self._name_label)
        self._form_layout.addRow("尺寸：", self._dimensions_label)
        self._form_layout.addRow("文件大小：", self._file_size_label)
        self._form_layout.addRow("格式：", self._format_label)
        self._form_layout.addRow("色彩模式：", self._color_mode_label)
        self._form_layout.addRow("路径：", self._path_label)

        self._content_layout.addLayout(self._form_layout)

        # 多张信息：汇总标签
        self._summary_label = QLabel()
        self._summary_label.setWordWrap(True)
        self._summary_label.setVisible(False)
        self._content_layout.addWidget(self._summary_label)

        # 弹簧，把内容顶到顶部
        self._content_layout.addStretch()

        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)

        # 初始空白状态
        self._clear()

    def _clear(self) -> None:
        """清空面板，显示占位提示。"""
        self._preview_label.setText("无预览")
        self._preview_label.setPixmap(QPixmap())
        self._name_label.setText("-")
        self._dimensions_label.setText("-")
        self._file_size_label.setText("-")
        self._format_label.setText("-")
        self._color_mode_label.setText("-")
        self._path_label.setText("-")
        self._summary_label.setText("")
        self._summary_label.setVisible(False)
        self._form_layout.setVisible(True)

    def update(self, sprite: SpriteInfo) -> None:
        """更新面板，显示单张精灵图信息。

        Args:
            sprite: 精灵图信息对象
        """
        self._form_layout.setVisible(True)
        self._summary_label.setVisible(False)

        # 预览图：256x256 区域内等比例缩放
        pixmap = QPixmap(sprite.file_path)
        if pixmap.isNull():
            self._preview_label.setText("无法加载图片")
            self._preview_label.setPixmap(QPixmap())
        else:
            scaled = pixmap.scaled(
                self._preview_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._preview_label.setPixmap(scaled)

        # 元数据
        self._name_label.setText(sprite.file_name)
        self._dimensions_label.setText(f"{sprite.width} × {sprite.height}")
        self._file_size_label.setText(format_file_size(sprite.file_size))
        self._format_label.setText(sprite.format)
        self._color_mode_label.setText(sprite.color_mode)
        self._path_label.setText(sprite.file_path)

    def update_multiple(self, sprites: List[SpriteInfo]) -> None:
        """更新面板，显示多张精灵图汇总信息。

        Args:
            sprites: 精灵图信息对象列表
        """
        self._form_layout.setVisible(False)
        self._summary_label.setVisible(True)

        # 清空预览图区域，显示选中数量提示
        self._preview_label.setText(f"已选中 {len(sprites)} 张")
        self._preview_label.setPixmap(QPixmap())

        total_size = sum(s.file_size for s in sprites)
        self._summary_label.setText(
            f"共 {len(sprites)} 张图片\n"
            f"总文件大小：{format_file_size(total_size)}"
        )
