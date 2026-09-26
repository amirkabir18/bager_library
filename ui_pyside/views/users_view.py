"""
System Users and Settings scaffold views (Student 3).
"""

from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ui_pyside.theme import (
    COLOR_PRIMARY,
    COLOR_PRIMARY_LIGHT,
    COLOR_TEXT_MAIN,
    get_app_font,
)


class UsersView(QWidget):
    """
    Application Users and RBAC permissions page.
    Assigned to: Student 3 (دانشجوی شماره ۳)
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)

        card = QFrame()
        card.setObjectName("ContentCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)

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
        lbl_task = QLabel("📌 صفحه مدیریت کاربران سامانه و سطوح دسترسی (اختصاص‌یافته به دانشجوی شماره ۳)")
        lbl_task.setFont(get_app_font(11, QFont.Weight.Bold))
        lbl_task.setStyleSheet(f"color: {COLOR_PRIMARY};")

        lbl_desc = QLabel(
            "وظایف این بخش:\n"
            "۱. جدول کاربران سامانه با نمایش نقش‌ها (مدیر ارشد، مدیر، کتابدار).\n"
            "۲. دیالوگ ایجاد و ویرایش کاربر با احراز هویت دوعاملی (OTP) و رمزنگاری گذرواژه.\n"
            "۳. غیرفعال‌سازی و ریست رمز عبور کاربران بر اساس auth.py."
        )
        lbl_desc.setFont(get_app_font(9.5))
        lbl_desc.setStyleSheet(f"color: {COLOR_TEXT_MAIN};")

        info_layout.addWidget(lbl_task)
        info_layout.addWidget(lbl_desc)
        card_layout.addWidget(info_box)
        layout.addWidget(card)


class SettingsView(QWidget):
    """
    Settings and Notification preferences view.
    Assigned to: Student 3 (دانشجوی شماره ۳)
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)

        card = QFrame()
        card.setObjectName("ContentCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)

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
        lbl_task = QLabel("📌 صفحه تنظیمات، یادآوری‌ها و اعلان‌ها (اختصاص‌یافته به دانشجوی شماره ۳)")
        lbl_task.setFont(get_app_font(11, QFont.Weight.Bold))
        lbl_task.setStyleSheet(f"color: {COLOR_PRIMARY};")

        lbl_desc = QLabel(
            "وظایف این بخش:\n"
            "۱. تنظیمات ارسال اعلان تلگرام و پیامک برای یادآوری بازگشت کتاب.\n"
            "۲. تنظیم فواصل زمانی بررسی خودکار امانات و بازه پاکسازی OTP.\n"
            "۳. نمایش لاگ تاریخچه اعلان‌های ارسال‌شده (Notification Logs)."
        )
        lbl_desc.setFont(get_app_font(9.5))
        lbl_desc.setStyleSheet(f"color: {COLOR_TEXT_MAIN};")

        info_layout.addWidget(lbl_task)
        info_layout.addWidget(lbl_desc)
        card_layout.addWidget(info_box)
        layout.addWidget(card)
