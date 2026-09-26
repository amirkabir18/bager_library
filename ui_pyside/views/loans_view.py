"""
Loans view scaffold for Student 2 (امانت‌ها و بازگشت‌ها).
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


class LoansView(QWidget):
    """
    Loans & Returns management page.
    Assigned to: Student 2 (دانشجوی شماره ۲)
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
        btn_add_loan = QPushButton(" ثبت امانت جدید ")
        btn_add_loan.setObjectName("BtnAddBook")
        btn_add_loan.setIcon(get_icon("book-plus", color_hex=COLOR_TEXT_MAIN, size=(18, 18)))
        btn_add_loan.setFixedHeight(38)

        search = QLineEdit()
        search.setPlaceholderText("جستجوی امانت بر اساس نام کتاب، نام عضو، یا شماره تماس...")
        search.setFixedHeight(38)

        toolbar.addWidget(btn_add_loan)
        toolbar.addWidget(search, stretch=1)
        card_layout.addLayout(toolbar)

        # Placeholder info box for student
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
        lbl_task = QLabel("📌 صفحه مدیریت امانات و بازگشت‌ها (اختصاص‌یافته به دانشجوی شماره ۲)")
        lbl_task.setFont(get_app_font(11, QFont.Weight.Bold))
        lbl_task.setStyleSheet(f"color: {COLOR_PRIMARY};")

        lbl_desc = QLabel(
            "وظایف این بخش:\n"
            "۱. پیاده‌سازی جدول امانت‌های جاری و آرشیو بازگشتی‌ها با ستون‌های: کتاب، عضو، تاریخ امانت، تاریخ سررسید، وضعیت.\n"
            "۲. دیالوگ ثبت امانت جدید با قابلیت انتخاب هوشمند کتاب و عضو از دیتابیس.\n"
            "۳. امکان تمدید امانت، ثبت بازگشت کتاب و بررسی تاخیرها با تقویم شمسی (jdatetime)."
        )
        lbl_desc.setFont(get_app_font(9.5))
        lbl_desc.setStyleSheet(f"color: {COLOR_TEXT_MAIN};")

        info_layout.addWidget(lbl_task)
        info_layout.addWidget(lbl_desc)
        card_layout.addWidget(info_box)

        # Basic Table Structure
        table = QTableWidget()
        table.setColumnCount(7)
        table.setHorizontalHeaderLabels(
            ["#", "کتاب", "عضو امانت‌گیرنده", "تاریخ امانت", "سررسید بازگشت", "وضعیت", "عملیات"]
        )
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        card_layout.addWidget(table, stretch=1)

        main_layout.addWidget(card)
