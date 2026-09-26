"""
Categories and Dewey Classification view scaffold (Student 1).
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


class CategoriesView(QWidget):
    """
    Categories & Dewey classification management page.
    Assigned to: Student 1 (دانشجوی شماره ۱)
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
        lbl_task = QLabel("📌 صفحه دسته‌بندی‌ها و درخت رده‌بندی دیویی (اختصاص‌یافته به دانشجوی شماره ۱)")
        lbl_task.setFont(get_app_font(11, QFont.Weight.Bold))
        lbl_task.setStyleSheet(f"color: {COLOR_PRIMARY};")

        lbl_desc = QLabel(
            "وظایف این بخش:\n"
            "۱. نمایش دسته‌بندی‌های ده‌گانه رده‌بندی دهدهی دیویی (DDC) و گروه‌بندی موضوعی کتب.\n"
            "۲. اتصال به DeweyService و DeweyAIAgent جهت پیشنهاد و رده‌بندی خودکار کتب فاقد کد دیویی.\n"
            "۳. آمار تعداد کتب موجود در هر رده موضوعی."
        )
        lbl_desc.setFont(get_app_font(9.5))
        lbl_desc.setStyleSheet(f"color: {COLOR_TEXT_MAIN};")

        info_layout.addWidget(lbl_task)
        info_layout.addWidget(lbl_desc)
        card_layout.addWidget(info_box)

        main_layout.addWidget(card)
