"""
Dual Sidebar navigation component (Slim Icon Rail + Collapsible Sub-Sidebar).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui_pyside.theme import (
    COLOR_ACCENT,
    COLOR_BORDER,
    COLOR_PRIMARY,
    COLOR_PRIMARY_LIGHT,
    COLOR_TEXT_MAIN,
    COLOR_TEXT_MUTED,
    get_app_font,
    get_icon,
)


class IconRail(QFrame):
    """
    Slim vertical icon navigation rail (54px wide).
    """

    page_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedWidth(54)
        self.setStyleSheet(f"""
            IconRail {{
                background-color: #FFFFFF;
                border-left: 1px solid {COLOR_BORDER};
            }}
        """)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(7, 14, 7, 14)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # Top Accent Book Button
        top_btn = QPushButton()
        top_btn.setIcon(get_icon("book-open", color_hex="#172033", size=(20, 20)))
        top_btn.setFixedSize(38, 38)
        top_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_ACCENT};
                border: none;
                border-radius: 10px;
            }}
            QPushButton:hover {{
                background-color: #FFD033;
            }}
        """)
        top_btn.clicked.connect(lambda: self.page_selected.emit("books"))
        layout.addWidget(top_btn)

        # Rail Action Buttons
        rail_actions = [
            ("books", "book-open", "کتاب‌ها"),
            ("members", "user", "عضویت‌ها"),
            ("loans", "arrow-right-left", "امانت‌ها"),
            ("settings", "settings", "تنظیمات"),
        ]

        for page_id, icon_name, tooltip in rail_actions:
            btn = QPushButton()
            btn.setIcon(get_icon(icon_name, color_hex="#64748B", size=(19, 19)))
            btn.setFixedSize(36, 36)
            btn.setToolTip(tooltip)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    border: none;
                    border-radius: 8px;
                }}
                QPushButton:hover {{
                    background-color: {COLOR_PRIMARY_LIGHT};
                }}
            """)
            btn.clicked.connect(lambda checked=False, pid=page_id: self.page_selected.emit(pid))
            layout.addWidget(btn)

        layout.addStretch()

        # Bottom Language Badge
        lang_badge = QLabel("FA")
        lang_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lang_badge.setFixedSize(32, 32)
        lang_badge.setFont(get_app_font(9, QFont.Weight.Bold))
        lang_badge.setStyleSheet(f"""
            QLabel {{
                background-color: {COLOR_PRIMARY_LIGHT};
                color: {COLOR_PRIMARY};
                border-radius: 16px;
                border: 1px solid #BFDBFE;
            }}
        """)
        layout.addWidget(lang_badge)


class NavSidebar(QFrame):
    """
    Sub-sidebar navigation menu with collapsible toggle and search bar.
    """

    page_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedWidth(210)
        self.setStyleSheet(f"""
            NavSidebar {{
                background-color: #FFFFFF;
                border-left: 1px solid {COLOR_BORDER};
            }}
        """)
        self.buttons: dict[str, QPushButton] = {}
        self.active_page = "books"
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 14, 12, 14)
        layout.setSpacing(10)

        # Header with Title and Collapse Button
        header_row = QHBoxLayout()
        lbl_title = QLabel("کتابخانه")
        lbl_title.setFont(get_app_font(13, QFont.Weight.Bold))
        lbl_title.setStyleSheet(f"color: {COLOR_TEXT_MAIN};")

        self.collapse_btn = QPushButton()
        self.collapse_btn.setIcon(get_icon("filter", color_hex="#64748B", size=(16, 16)))
        self.collapse_btn.setFixedSize(28, 28)
        self.collapse_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background: {COLOR_PRIMARY_LIGHT};
            }}
        """)
        header_row.addWidget(lbl_title)
        header_row.addStretch()
        header_row.addWidget(self.collapse_btn)
        layout.addLayout(header_row)

        # Quick Search Box in Sidebar
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("جستجو...")
        self.search_box.setFont(get_app_font(9.5))
        self.search_box.setFixedHeight(32)
        self.search_box.setStyleSheet(f"""
            QLineEdit {{
                background-color: #F8FAFC;
                border: 1px solid {COLOR_BORDER};
                border-radius: 6px;
                padding: 4px 8px;
                color: {COLOR_TEXT_MAIN};
            }}
            QLineEdit:focus {{
                border: 1px solid {COLOR_PRIMARY};
                background-color: #FFFFFF;
            }}
        """)
        layout.addWidget(self.search_box)

        # Navigation Items List
        items = [
            ("books", "کتاب‌ها", "book-open"),
            ("members", "عضویت‌ها", "user"),
            ("loans", "امانت‌ها", "arrow-right-left"),
            ("returns", "بازگشت‌ها", "rotate-ccw"),
            ("categories", "دسته‌بندی‌ها", "filter"),
            ("users", "کاربران سامانه", "user-check"),
            ("settings", "تنظیمات", "settings"),
        ]

        for page_id, label, icon_name in items:
            btn = QPushButton(f"  {label}")
            btn.setIcon(get_icon(icon_name, color_hex="#2945D3" if page_id == "books" else "#64748B", size=(17, 17)))
            btn.setFont(get_app_font(10, QFont.Weight.Medium))
            btn.setFixedHeight(38)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, pid=page_id: self.select_page(pid, emit_signal=True))
            self.buttons[page_id] = btn
            layout.addWidget(btn)

        layout.addStretch()
        self.refresh_styles()

    def select_page(self, page_id: str, emit_signal: bool = True) -> None:
        if self.active_page == page_id and not emit_signal:
            return
        self.active_page = page_id
        self.refresh_styles()
        if emit_signal:
            self.page_selected.emit(page_id)

    def refresh_styles(self) -> None:
        for pid, btn in self.buttons.items():
            is_active = pid == self.active_page
            if is_active:
                btn.setIcon(get_icon(self._get_icon_name(pid), color_hex=COLOR_PRIMARY, size=(17, 17)))
                btn.setStyleSheet(f"""
                    QPushButton {{
                        text-align: right;
                        background-color: {COLOR_PRIMARY_LIGHT};
                        color: {COLOR_PRIMARY};
                        font-weight: bold;
                        border: none;
                        border-radius: 8px;
                        padding-right: 12px;
                    }}
                """)
            else:
                btn.setIcon(get_icon(self._get_icon_name(pid), color_hex=COLOR_TEXT_MUTED, size=(17, 17)))
                btn.setStyleSheet(f"""
                    QPushButton {{
                        text-align: right;
                        background-color: transparent;
                        color: {COLOR_TEXT_MAIN};
                        font-weight: normal;
                        border: none;
                        border-radius: 8px;
                        padding-right: 12px;
                    }}
                    QPushButton:hover {{
                        background-color: #F8FAFC;
                        color: {COLOR_PRIMARY};
                    }}
                """)

    def _get_icon_name(self, page_id: str) -> str:
        icon_map = {
            "books": "book-open",
            "members": "user",
            "loans": "arrow-right-left",
            "returns": "rotate-ccw",
            "categories": "filter",
            "users": "user-check",
            "settings": "settings",
        }
        return icon_map.get(page_id, "book-open")


class DualSidebar(QWidget):
    """
    Combined IconRail and NavSidebar widget with collapse support.
    """

    page_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.rail = IconRail(self)
        self.sidebar = NavSidebar(self)

        layout.addWidget(self.rail)
        layout.addWidget(self.sidebar)

        self.rail.page_selected.connect(self._on_rail_selected)
        self.sidebar.page_selected.connect(self.page_selected.emit)
        self.sidebar.collapse_btn.clicked.connect(self.toggle_sidebar)

    def _on_rail_selected(self, page_id: str) -> None:
        if self.sidebar.isHidden():
            self.sidebar.show()
        self.sidebar.select_page(page_id)

    def toggle_sidebar(self) -> None:
        self.sidebar.setVisible(not self.sidebar.isVisible())

    def set_active_page(self, page_id: str) -> None:
        self.sidebar.select_page(page_id, emit_signal=False)
