"""
Custom table cell widgets for badges, book covers, and operation buttons.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from ui_pyside.theme import (
    COLOR_BORDER,
    COLOR_PRIMARY,
    COLOR_PRIMARY_LIGHT,
    get_app_font,
    get_icon,
)


class BadgeCell(QWidget):
    """
    Renders rounded pill badges for status or categories.
    """

    def __init__(
        self,
        text: str,
        bg_color: str = COLOR_PRIMARY_LIGHT,
        fg_color: str = COLOR_PRIMARY,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label = QLabel(f" {text} ")
        label.setFont(get_app_font(8.5, QFont.Weight.Medium))
        label.setFixedHeight(24)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_color};
                color: {fg_color};
                border-radius: 12px;
                padding: 2px 10px;
            }}
        """)
        layout.addWidget(label)


class ActionButtonsCell(QWidget):
    """
    Renders action buttons: View, Edit, Menu for table rows.
    """

    view_clicked = Signal(int)
    edit_clicked = Signal(int)
    delete_clicked = Signal(int)

    def __init__(self, row_idx: int, parent: QWidget | None = None):
        super().__init__(parent)
        self.row_idx = row_idx
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # View button
        btn_view = QPushButton()
        btn_view.setIcon(get_icon("eye", color_hex=COLOR_PRIMARY, size=(16, 16)))
        btn_view.setFixedSize(26, 26)
        btn_view.setToolTip("مشاهده جزئیات")
        btn_view.clicked.connect(lambda: self.view_clicked.emit(self.row_idx))
        self._style_icon_btn(btn_view)

        # Edit button
        btn_edit = QPushButton()
        btn_edit.setIcon(get_icon("pencil", color_hex="#64748B", size=(15, 15)))
        btn_edit.setFixedSize(26, 26)
        btn_edit.setToolTip("ویرایش")
        btn_edit.clicked.connect(lambda: self.edit_clicked.emit(self.row_idx))
        self._style_icon_btn(btn_edit)

        # Delete/More button
        btn_del = QPushButton()
        btn_del.setIcon(get_icon("x", color_hex="#DC2626", size=(14, 14)))
        btn_del.setFixedSize(26, 26)
        btn_del.setToolTip("حذف")
        btn_del.clicked.connect(lambda: self.delete_clicked.emit(self.row_idx))
        self._style_icon_btn(btn_del)

        layout.addWidget(btn_view)
        layout.addWidget(btn_edit)
        layout.addWidget(btn_del)

    @staticmethod
    def _style_icon_btn(btn: QPushButton) -> None:
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {COLOR_BORDER};
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {COLOR_PRIMARY_LIGHT};
                border-color: {COLOR_PRIMARY};
            }}
        """)


class CoverThumbnailCell(QWidget):
    """
    Renders small book thumbnail rectangle (30x40px).
    """

    def __init__(self, cover_path: str | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        thumb = QLabel()
        thumb.setFixedSize(28, 38)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if cover_path:
            pix = QPixmap(cover_path)
            if not pix.isNull():
                thumb.setPixmap(
                    pix.scaled(
                        28,
                        38,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            else:
                self._fallback_thumb(thumb)
        else:
            self._fallback_thumb(thumb)

        layout.addWidget(thumb)

    @staticmethod
    def _fallback_thumb(label: QLabel) -> None:
        label.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1E3A8A, stop:1 #2563EB);
                border-radius: 4px;
                border: 1px solid #1E293B;
            }
        """)
