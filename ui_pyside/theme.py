"""
Theme, colors, font loaders, and QSS stylesheets for PySide6 interface.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPixmap

BASE_DIR = Path(__file__).resolve().parent.parent

# Brand & System Palette
COLOR_PRIMARY = "#2945D3"
COLOR_PRIMARY_DARK = "#172B8F"
COLOR_PRIMARY_LIGHT = "#EAF0FF"
COLOR_ACCENT = "#FFC400"
COLOR_ACCENT_LIGHT = "#FFF7D6"
COLOR_BG_MAIN = "#F7F9FC"
COLOR_BG_CARD = "#FFFFFF"
COLOR_TEXT_MAIN = "#172033"
COLOR_TEXT_MUTED = "#64748B"
COLOR_BORDER = "#E2E8F0"

# Status colors
COLOR_SUCCESS = "#15803D"
COLOR_SUCCESS_BG = "#DCFCE7"
COLOR_WARNING = "#B45309"
COLOR_WARNING_BG = "#FFF7D6"
COLOR_DANGER = "#DC2626"
COLOR_DANGER_BG = "#FEE2E2"

_FONT_FAMILY = "IRANSansWeb(FaNum)"
_ICON_CACHE: dict[str, QIcon] = {}


def load_application_fonts() -> str:
    """Loads IranSans fonts into QFontDatabase and returns the preferred font family."""
    global _FONT_FAMILY
    fonts_dir = BASE_DIR / "assets" / "fonts" / "iransans" / "ttf"
    loaded_family = None

    if fonts_dir.exists():
        for font_file in fonts_dir.glob("*.ttf"):
            font_id = QFontDatabase.addApplicationFont(str(font_file))
            if font_id != -1 and not loaded_family:
                families = QFontDatabase.applicationFontFamilies(font_id)
                if families:
                    loaded_family = families[0]

    if loaded_family:
        _FONT_FAMILY = loaded_family
    return _FONT_FAMILY


def get_app_font(size: int = 10, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    """Returns application font with the specified point size and weight."""
    font = QFont(_FONT_FAMILY, size)
    font.setWeight(weight)
    return font


def get_icon(name: str, color_hex: str | None = None, size: tuple[int, int] = (20, 20)) -> QIcon:
    """Retrieves an icon from assets/icons/lucide, optionally tinting it."""
    cache_key = f"{name}_{color_hex}_{size[0]}x{size[1]}"
    if cache_key in _ICON_CACHE:
        return _ICON_CACHE[cache_key]

    icon_path = BASE_DIR / "assets" / "icons" / "lucide" / f"{name}.png"
    if not icon_path.exists():
        return QIcon()

    pixmap = QPixmap(str(icon_path))
    if pixmap.isNull():
        return QIcon()

    if color_hex:
        tinted = QPixmap(pixmap.size())
        tinted.fill(Qt.GlobalColor.transparent)
        painter = QPainter(tinted)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.drawPixmap(0, 0, pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(tinted.rect(), QColor(color_hex))
        painter.end()
        pixmap = tinted

    icon = QIcon(
        pixmap.scaled(size[0], size[1], Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    )
    _ICON_CACHE[cache_key] = icon
    return icon


def get_master_stylesheet() -> str:
    """Returns the master QSS style rules."""
    return f"""
    QWidget {{
        font-family: "{_FONT_FAMILY}", "IRANSans", "Segoe UI", "Tahoma";
        font-size: 13px;
        color: {COLOR_TEXT_MAIN};
        background: transparent;
        selection-background-color: {COLOR_PRIMARY};
        selection-color: #FFFFFF;
    }}

    QMainWindow {{
        background-color: {COLOR_BG_MAIN};
    }}

    /* Global Card Container */
    QFrame#ContentCard {{
        background-color: {COLOR_BG_CARD};
        border: 1px solid {COLOR_BORDER};
        border-radius: 12px;
    }}

    /* Search & Inputs */
    QLineEdit {{
        background-color: #FFFFFF;
        border: 1px solid {COLOR_BORDER};
        border-radius: 8px;
        padding: 7px 12px;
        color: {COLOR_TEXT_MAIN};
        font-size: 12px;
    }}

    QLineEdit:focus {{
        border: 1.5px solid {COLOR_PRIMARY};
    }}

    QComboBox {{
        background-color: #FFFFFF;
        border: 1px solid {COLOR_BORDER};
        border-radius: 8px;
        padding: 6px 12px;
        color: {COLOR_TEXT_MAIN};
        min-height: 22px;
    }}

    QComboBox:focus {{
        border: 1.5px solid {COLOR_PRIMARY};
    }}

    QComboBox::drop-down {{
        border: none;
        width: 20px;
        padding-left: 4px;
    }}

    QComboBox QAbstractItemView {{
        background-color: #FFFFFF;
        border: 1px solid {COLOR_BORDER};
        border-radius: 8px;
        padding: 4px;
        selection-background-color: {COLOR_PRIMARY_LIGHT};
        selection-color: {COLOR_PRIMARY};
    }}

    /* Buttons */
    QPushButton#BtnAddBook {{
        background-color: {COLOR_ACCENT};
        color: {COLOR_TEXT_MAIN};
        border: 1px solid #E5B000;
        border-radius: 8px;
        padding: 8px 18px;
        font-weight: bold;
        font-size: 13px;
    }}

    QPushButton#BtnAddBook:hover {{
        background-color: #FFD033;
    }}

    QPushButton#BtnAddBook:pressed {{
        background-color: #CCA000;
    }}

    QPushButton#BtnFilter {{
        background-color: #FFFFFF;
        color: {COLOR_PRIMARY};
        border: 1px solid {COLOR_BORDER};
        border-radius: 8px;
        padding: 7px 16px;
        font-weight: 500;
    }}

    QPushButton#BtnFilter:hover {{
        background-color: {COLOR_PRIMARY_LIGHT};
        border-color: {COLOR_PRIMARY};
    }}

    QPushButton#BtnNav {{
        text-align: right;
        background-color: transparent;
        border: none;
        border-radius: 8px;
        padding: 10px 14px;
        font-size: 13px;
        color: {COLOR_TEXT_MAIN};
    }}

    QPushButton#BtnNav:hover {{
        background-color: {COLOR_BG_MAIN};
        color: {COLOR_PRIMARY};
    }}

    QPushButton#BtnNav[active="true"] {{
        background-color: {COLOR_PRIMARY_LIGHT};
        color: {COLOR_PRIMARY};
        font-weight: bold;
    }}

    /* Table View */
    QTableWidget, QTableView {{
        background-color: #FFFFFF;
        border: none;
        gridline-color: transparent;
        outline: none;
        font-size: 12px;
    }}

    QTableWidget::item, QTableView::item {{
        border-bottom: 1px solid {COLOR_BORDER};
        padding: 6px;
        color: {COLOR_TEXT_MAIN};
    }}

    QTableWidget::item:selected, QTableView::item:selected {{
        background-color: {COLOR_PRIMARY_LIGHT};
        color: {COLOR_PRIMARY_DARK};
    }}

    QHeaderView::section {{
        background-color: #FFFFFF;
        color: {COLOR_TEXT_MUTED};
        border: none;
        border-bottom: 1.5px solid {COLOR_BORDER};
        padding: 10px 8px;
        font-size: 12px;
        font-weight: bold;
        text-align: right;
    }}

    /* Scrollbars */
    QScrollBar:vertical {{
        background: {COLOR_BG_MAIN};
        width: 8px;
        border-radius: 4px;
        margin: 0;
    }}

    QScrollBar::handle:vertical {{
        background: #CBD5E1;
        border-radius: 4px;
        min-height: 24px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: #94A3B8;
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    """
