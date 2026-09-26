"""
Top Header Bar component matching the institutional brand header.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui_pyside.theme import (
    COLOR_PRIMARY,
    COLOR_PRIMARY_DARK,
    COLOR_PRIMARY_LIGHT,
    get_app_font,
    get_icon,
)


class HeaderBar(QFrame):
    """
    Application top bar with branding, institution details, and user profile.
    """

    logout_requested = Signal()
    settings_requested = Signal()

    def __init__(self, parent: QWidget | None = None, username: str = "مدیر کتابخانه"):
        super().__init__(parent)
        self.username = username
        self.setFixedHeight(62)
        self.setObjectName("AppHeader")
        self.setStyleSheet(f"""
            QFrame#AppHeader {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {COLOR_PRIMARY_DARK}, stop:1 {COLOR_PRIMARY});
                border-bottom: 1px solid {COLOR_PRIMARY_DARK};
            }}
        """)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 0, 18, 0)
        layout.setSpacing(12)

        # Right side (RTL): Institution branding
        brand_layout = QHBoxLayout()
        brand_layout.setSpacing(10)

        # Logo / emblem button
        logo_btn = QPushButton()
        logo_btn.setIcon(get_icon("bookmark", color_hex="#FFFFFF", size=(24, 24)))
        logo_btn.setFixedSize(36, 36)
        logo_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.15);
                border: 1px solid rgba(255, 255, 255, 0.3);
                border-radius: 8px;
            }
        """)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(1)
        title_vbox.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        lbl_title = QLabel("موسسه آموزشی جهت")
        lbl_title.setFont(get_app_font(13, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #FFFFFF;")

        lbl_subtitle = QLabel("شتاب دهنده آموزش، فردا متمایز")
        lbl_subtitle.setFont(get_app_font(8.5, QFont.Weight.Normal))
        lbl_subtitle.setStyleSheet("color: #B8CCFF;")

        title_vbox.addWidget(lbl_title)
        title_vbox.addWidget(lbl_subtitle)

        brand_layout.addWidget(logo_btn)
        brand_layout.addLayout(title_vbox)

        layout.addLayout(brand_layout)
        layout.addStretch()

        # Left side (RTL): User profile pill
        self.profile_btn = QPushButton(f"  {self.username}  ▾")
        self.profile_btn.setIcon(get_icon("user", color_hex="#FFFFFF", size=(18, 18)))
        self.profile_btn.setFont(get_app_font(10, QFont.Weight.Medium))
        self.profile_btn.setFixedHeight(36)
        self.profile_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.12);
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.25);
                border-radius: 18px;
                padding: 4px 14px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.22);
            }
        """)
        self.profile_btn.clicked.connect(self._show_profile_menu)
        layout.addWidget(self.profile_btn)

    def _show_profile_menu(self) -> None:
        menu = QMenu(self)
        menu.setFont(get_app_font(10))
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                padding: 6px;
            }}
            QMenu::item {{
                padding: 8px 24px;
                border-radius: 6px;
                color: #172033;
            }}
            QMenu::item:selected {{
                background-color: {COLOR_PRIMARY_LIGHT};
                color: {COLOR_PRIMARY};
            }}
        """)
        act_settings = menu.addAction(get_icon("settings", size=(16, 16)), "تنظیمات سامانه")
        act_settings.triggered.connect(self.settings_requested.emit)
        menu.addSeparator()
        act_logout = menu.addAction(get_icon("x", color_hex="#DC2626", size=(16, 16)), "خروج از حساب")
        act_logout.triggered.connect(self.logout_requested.emit)

        menu.exec(self.profile_btn.mapToGlobal(self.profile_btn.rect().bottomLeft()))
