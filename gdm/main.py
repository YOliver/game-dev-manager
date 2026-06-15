import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from gdm.gui.main_window import MainWindow


def get_icon_path():
    """获取图标路径，兼容开发环境和打包后的运行环境"""
    if getattr(sys, 'frozen', False):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, 'resources', 'app_icon.ico')


def main():
    app = QApplication(sys.argv)
    icon_path = get_icon_path()
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
