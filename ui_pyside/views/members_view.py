"""
Members management view scaffold for Student 3 (اعضای کتابخانه).
"""

from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from ui_pyside.theme import (
    COLOR_PRIMARY,
    COLOR_PRIMARY_LIGHT,
    COLOR_TEXT_MAIN,
    get_app_font,
    get_icon,
)


class MembersView(QWidget):
    """
    Library Members management page.
    Assigned to: Student 3 (دانشجوی شماره ۳)
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)

        card = QFrame()
        card.setObjectName("ContentCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 14)
        card_layout.setSpacing(14)

        # Toolbar
        toolbar = QHBoxLayout()
        btn_add_member = QPushButton(" عضو جدید ")
        btn_add_member.setObjectName("BtnAddBook")
        btn_add_member.setIcon(get_icon("user-plus", color_hex=COLOR_TEXT_MAIN, size=(18, 18)))
        btn_add_member.setFixedHeight(38)

        search = QLineEdit()
        search.setPlaceholderText("جستجوی نام، کدملی، یا شماره تماس عضو...")
        search.setFixedHeight(38)

        toolbar.addWidget(btn_add_member)
        toolbar.addWidget(search, stretch=1)
        card_layout.addLayout(toolbar)

        # Student task guide box
        info_box = QFrame()
        info_box.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_PRIMARY_LIGHT};
                border: 1px dashed {COLOR_PRIMARY};
                border-radius: 8px;
                padding: 14px;
            }}
        """)
        info_layout = QVBoxLayout(info_box)
        lbl_task = QLabel("📌 صفحه مدیریت اعضای کتابخانه (اختصاص‌یافته به دانشجوی شماره ۳)")
        lbl_task.setFont(get_app_font(11, QFont.Weight.Bold))
        lbl_task.setStyleSheet(f"color: {COLOR_PRIMARY};")

        lbl_desc = QLabel(
            "وظایف این بخش:\n"
            "۱. پیاده‌سازی جدول اعضا شامل نام کاربری، شماره تماس، وضعیت عضویت و تعداد کتب امانت گرفته‌شده.\n"
            "۲. دیالوگ ثبت و ویرایش مشخصات عضو به همراه اعتبارسنجی شماره همراه ایرانی.\n"
            "۳. مشاهده سوابق امانات هر عضو و خروجی اکسل/CSV از فهرست اعضا."
        )
        lbl_desc.setFont(get_app_font(9.5))
        lbl_desc.setStyleSheet(f"color: {COLOR_TEXT_MAIN};")

        info_layout.addWidget(lbl_task)
        info_layout.addWidget(lbl_desc)
        card_layout.addWidget(info_box)

        # Table placeholder
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["#", "نام عضو", "شماره تماس", "تعداد امانت فعال", "عملیات"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        card_layout.addWidget(table, stretch=1)

        main_layout.addWidget(card)
