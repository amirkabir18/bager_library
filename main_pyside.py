"""
Entry point for the PySide6 version of Bager Library Management.
Run this script to launch the modern PySide6 interface.
"""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from auth import ensure_bootstrap_admin
from database import db_p, get_db_connection, init_database
from ui_pyside.main_window import MainWindow
from ui_pyside.theme import get_app_font, load_application_fonts


def main() -> None:
    # 1. Initialize SQLite Database & Bootstrap Admin
    with get_db_connection(db_p) as conn:
        init_database(conn)
        ensure_bootstrap_admin(database_path=db_p)

    # 2. Setup PySide6 Application
    app = QApplication(sys.argv)
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

    # 3. Load Brand IranSans Fonts
    load_application_fonts()
    app.setFont(get_app_font(10))

    # 4. Set Application Icon
    base_dir = os.path.dirname(__file__)
    icon_path = os.path.join(base_dir, "logo.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # 5. Launch Main Window
    window = MainWindow(current_user={"username": "مدیر کتابخانه", "role": "super admin"})
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
