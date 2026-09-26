"""
Main Application Window for PySide6 version of Bager Library.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui_pyside.components.header import HeaderBar
from ui_pyside.components.sidebar import DualSidebar
from ui_pyside.theme import (
    COLOR_BG_MAIN,
    get_master_stylesheet,
)
from ui_pyside.views.books_view import BooksView
from ui_pyside.views.categories_view import CategoriesView
from ui_pyside.views.loans_view import LoansView
from ui_pyside.views.members_view import MembersView
from ui_pyside.views.users_view import SettingsView, UsersView


class MainWindow(QMainWindow):
    """
    Root application shell with Header, Navigation Rails, and Views Stack.
    """

    def __init__(self, current_user: dict | None = None):
        super().__init__()
        self.current_user = current_user or {"username": "مدیر کتابخانه", "role": "admin"}
        self.setWindowTitle("سامانه مدیریت کتابخانه - موسسه آموزشی جهت")
        self.resize(1180, 760)
        self.setMinimumSize(960, 600)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        self._views: dict[str, QWidget] = {}
        self._init_ui()
        self.setStyleSheet(get_master_stylesheet())

    def _init_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)

        root_vbox = QVBoxLayout(central)
        root_vbox.setContentsMargins(0, 0, 0, 0)
        root_vbox.setSpacing(0)

        # 1. Top Header Bar
        username = self.current_user.get("username", "مدیر کتابخانه")
        self.header = HeaderBar(self, username=username)
        self.header.settings_requested.connect(lambda: self.switch_page("settings"))
        self.header.logout_requested.connect(self.close)
        root_vbox.addWidget(self.header)

        # 2. Body Area (Dual Sidebar + Stacked Content)
        body_hbox = QHBoxLayout()
        body_hbox.setContentsMargins(0, 0, 0, 0)
        body_hbox.setSpacing(0)

        # Dual Sidebar
        self.sidebar = DualSidebar(self)
        self.sidebar.page_selected.connect(self.switch_page)
        body_hbox.addWidget(self.sidebar)

        # Content Canvas & Views Stack
        content_container = QWidget()
        content_container.setStyleSheet(f"background-color: {COLOR_BG_MAIN};")
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack)
        body_hbox.addWidget(content_container, stretch=1)

        root_vbox.addLayout(body_hbox, stretch=1)

        # Register Views
        self._add_view("books", BooksView())
        self._add_view("members", MembersView())
        self._add_view("loans", LoansView())
        self._add_view("returns", LoansView())
        self._add_view("categories", CategoriesView())
        self._add_view("users", UsersView())
        self._add_view("settings", SettingsView())

        self.switch_page("books")

    def _add_view(self, page_id: str, widget: QWidget) -> None:
        self._views[page_id] = widget
        self.stack.addWidget(widget)

    def switch_page(self, page_id: str) -> None:
        """Switches the active view in QStackedWidget and updates sidebar state."""
        if page_id in self._views:
            self.stack.setCurrentWidget(self._views[page_id])
            self.sidebar.set_active_page(page_id)
