"""
Books management view - replicates dashboard screenshot with search, filters, table, and pagination.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database import db_p, get_db_connection
from ui_pyside.components.table_delegates import ActionButtonsCell, BadgeCell, CoverThumbnailCell
from ui_pyside.theme import (
    COLOR_BORDER,
    COLOR_PRIMARY,
    COLOR_PRIMARY_LIGHT,
    COLOR_SUCCESS,
    COLOR_SUCCESS_BG,
    COLOR_TEXT_MAIN,
    COLOR_TEXT_MUTED,
    COLOR_WARNING,
    COLOR_WARNING_BG,
    get_app_font,
    get_icon,
)

SAMPLE_BOOKS = [
    {
        "title": "شازده کوچولو",
        "category": "داستان و سنت اگزوپری",
        "author": "آنتوان دو سنت اگزوپری",
        "qty": "۳۵ جلد",
        "status": "موجود",
    },
    {"title": "ملت عشق", "category": "رمان", "author": "الیف شافاک", "qty": "۲۲ جلد", "status": "در حال امانت"},
    {"title": "قواعد ثروتمند شدن", "category": "موفقیت", "author": "ناپلئون هیل", "qty": "۱۸ جلد", "status": "موجود"},
    {"title": "دنیای سوفی", "category": "فلسفه", "author": "یوستین گردر", "qty": "۳۰ جلد", "status": "موجود"},
    {
        "title": "بیندیشید و ثروتمند شوید",
        "category": "موفقیت",
        "author": "ناپلئون هیل",
        "qty": "۱۵ جلد",
        "status": "در حال امانت",
    },
    {
        "title": "انسان در جستجوی معنا",
        "category": "روانشناسی",
        "author": "ویکتور فرانکل",
        "qty": "۲۶ جلد",
        "status": "موجود",
    },
    {"title": "۱۹۸۴", "category": "ادبیات خارجی", "author": "جورج اورول", "qty": "۲۰ جلد", "status": "موجود"},
    {"title": "شیمی آلی", "category": "علوم پایه", "author": "جان مک‌موریس", "qty": "۱۲ جلد", "status": "موجود"},
    {"title": "کیمیاگر", "category": "داستان و رمان", "author": "پائولو کوئیلو", "qty": "۲۳ جلد", "status": "موجود"},
    {
        "title": "تاریخ فلسفه",
        "category": "فلسفه",
        "author": "ریچارد ام. یتی",
        "qty": "۱۴ جلد",
        "status": "در حال امانت",
    },
]


class BooksView(QWidget):
    """
    Main Books catalogue dashboard view.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.books_data: list[dict[str, Any]] = []
        self._init_ui()
        self.load_data()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(0)

        # Main White Card Container
        self.card = QFrame()
        self.card.setObjectName("ContentCard")
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(16, 16, 16, 14)
        card_layout.setSpacing(14)

        # 1. Top Action Toolbar
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(10)

        # Add Book Primary Button (Yellow #FFC400)
        self.btn_add = QPushButton(" افزودن کتاب ")
        self.btn_add.setObjectName("BtnAddBook")
        self.btn_add.setIcon(get_icon("book-plus", color_hex=COLOR_TEXT_MAIN, size=(18, 18)))
        self.btn_add.setFont(get_app_font(10.5, QFont.Weight.Bold))
        self.btn_add.setFixedHeight(38)
        self.btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add.clicked.connect(self._on_add_book_clicked)

        # Category Dropdown
        self.combo_category = QComboBox()
        self.combo_category.setFixedHeight(38)
        self.combo_category.setFont(get_app_font(10))
        self.combo_category.addItem("همه دسته‌ها")
        self.combo_category.currentTextChanged.connect(self._filter_table)

        # Filter Toggle Button
        self.btn_filter = QPushButton(" فیلتر ")
        self.btn_filter.setObjectName("BtnFilter")
        self.btn_filter.setIcon(get_icon("filter", color_hex=COLOR_PRIMARY, size=(16, 16)))
        self.btn_filter.setFont(get_app_font(10))
        self.btn_filter.setFixedHeight(38)
        self.btn_filter.setCursor(Qt.CursorShape.PointingHandCursor)

        # Global Search Field
        self.search_input = QLineEdit()
        self.search_input.setFixedHeight(38)
        self.search_input.setPlaceholderText("جستجوی کتاب براساس عنوان، نویسنده یا کد کتاب...")
        self.search_input.setFont(get_app_font(10))
        self.search_input.textChanged.connect(self._filter_table)

        toolbar_layout.addWidget(self.btn_add)
        toolbar_layout.addWidget(self.combo_category)
        toolbar_layout.addWidget(self.btn_filter)
        toolbar_layout.addWidget(self.search_input, stretch=1)

        card_layout.addLayout(toolbar_layout)

        # 2. Table Widget
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels(
            ["", "#", "نام کتاب", "دسته‌بندی", "نویسنده", "قیمت / تعداد", "وضعیت", "جلد", "عملیات"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setFont(get_app_font(10))

        header = self.table.horizontalHeader()
        header.setFont(get_app_font(10, QFont.Weight.Bold))
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Fixed)

        self.table.setColumnWidth(0, 38)
        self.table.setColumnWidth(1, 44)
        self.table.setColumnWidth(7, 52)
        self.table.setColumnWidth(8, 110)

        card_layout.addWidget(self.table, stretch=1)

        # 3. Pagination Footer
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(4, 8, 4, 4)

        self.lbl_count = QLabel("۰ کتاب")
        self.lbl_count.setFont(get_app_font(9.5, QFont.Weight.Medium))
        self.lbl_count.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")
        footer_layout.addWidget(self.lbl_count)

        footer_layout.addStretch()

        pagination_box = QHBoxLayout()
        pagination_box.setSpacing(6)

        btn_next = QPushButton("›")
        btn_next.setFixedSize(32, 32)
        self._style_pagination_btn(btn_next)

        for p in [5, 4, 3, 2]:
            p_btn = QPushButton(str(p))
            p_btn.setFixedSize(32, 32)
            self._style_pagination_btn(p_btn)
            pagination_box.addWidget(p_btn)

        btn_active = QPushButton("1")
        btn_active.setFixedSize(32, 32)
        self._style_pagination_btn(btn_active, is_active=True)
        pagination_box.addWidget(btn_active)

        btn_prev = QPushButton("‹")
        btn_prev.setFixedSize(32, 32)
        self._style_pagination_btn(btn_prev)
        pagination_box.addWidget(btn_prev)

        footer_layout.addLayout(pagination_box)
        card_layout.addLayout(footer_layout)

        main_layout.addWidget(self.card)

    def load_data(self) -> None:
        """Fetches books from database, or populates sample data if DB is empty."""
        db_books = []
        try:
            with get_db_connection(db_p) as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT b.id, b.title, b.author, b.dewey_class, b.dewey_code,
                           (SELECT COUNT(*) FROM loans WHERE loans.book_id = b.id AND (loans.borrowed = 1 OR loans.borrowed = '1')) as is_borrowed
                    FROM books b
                    ORDER BY b.id ASC
                """)
                rows = cur.fetchall()
                for r in rows:
                    status_text = "در حال امانت" if r[5] > 0 else "موجود"
                    cat = r[3] or r[4] or "عمومی"
                    db_books.append(
                        {
                            "id": r[0],
                            "title": r[1] or "بدون عنوان",
                            "author": r[2] or "نامشخص",
                            "category": cat,
                            "qty": "۱ جلد",
                            "status": status_text,
                        }
                    )
        except Exception:
            pass

        self.books_data = db_books if len(db_books) >= 3 else SAMPLE_BOOKS
        self._populate_category_dropdown()
        self._render_table(self.books_data)

    def _populate_category_dropdown(self) -> None:
        categories = sorted({b.get("category", "") for b in self.books_data if b.get("category")})
        self.combo_category.blockSignals(True)
        self.combo_category.clear()
        self.combo_category.addItem("همه دسته‌ها")
        for cat in categories:
            self.combo_category.addItem(cat)
        self.combo_category.blockSignals(False)

    def _render_table(self, records: list[dict[str, Any]]) -> None:
        self.table.setRowCount(len(records))
        for row, item in enumerate(records):
            self.table.setRowHeight(row, 48)

            # 0. Selection Checkbox
            chk = QCheckBox()
            chk.setStyleSheet("margin-left: 10px;")
            self.table.setCellWidget(row, 0, chk)

            # 1. Index (#)
            item_num = QTableWidgetItem(str(row + 1))
            item_num.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_num.setForeground(QColor(COLOR_TEXT_MUTED))
            self.table.setItem(row, 1, item_num)

            # 2. Book Title
            item_title = QTableWidgetItem(item.get("title", ""))
            item_title.setFont(get_app_font(10, QFont.Weight.Medium))
            item_title.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 2, item_title)

            # 3. Category Pill
            cat_text = item.get("category", "عمومی")
            badge_cat = BadgeCell(cat_text, bg_color=COLOR_PRIMARY_LIGHT, fg_color=COLOR_PRIMARY)
            self.table.setCellWidget(row, 3, badge_cat)

            # 4. Author
            item_author = QTableWidgetItem(item.get("author", ""))
            item_author.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 4, item_author)

            # 5. Quantity
            item_qty = QTableWidgetItem(item.get("qty", "۱ جلد"))
            item_qty.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_qty.setForeground(QColor(COLOR_TEXT_MUTED))
            self.table.setItem(row, 5, item_qty)

            # 6. Status Pill
            status_text = item.get("status", "موجود")
            if status_text == "موجود":
                badge_status = BadgeCell("موجود", bg_color=COLOR_SUCCESS_BG, fg_color=COLOR_SUCCESS)
            else:
                badge_status = BadgeCell("در حال امانت", bg_color=COLOR_WARNING_BG, fg_color=COLOR_WARNING)
            self.table.setCellWidget(row, 6, badge_status)

            # 7. Book Cover Thumbnail
            thumb = CoverThumbnailCell()
            self.table.setCellWidget(row, 7, thumb)

            # 8. Action Buttons
            actions = ActionButtonsCell(row)
            actions.view_clicked.connect(self._on_view_clicked)
            actions.edit_clicked.connect(self._on_edit_clicked)
            actions.delete_clicked.connect(self._on_delete_clicked)
            self.table.setCellWidget(row, 8, actions)

        self.lbl_count.setText(f"{len(records)} کتاب")

    def _filter_table(self) -> None:
        query = self.search_input.text().strip().lower()
        selected_cat = self.combo_category.currentText()

        filtered = []
        for b in self.books_data:
            match_text = not query or (
                query in b.get("title", "").lower()
                or query in b.get("author", "").lower()
                or query in b.get("category", "").lower()
            )
            match_cat = (selected_cat == "همه دسته‌ها") or (b.get("category") == selected_cat)
            if match_text and match_cat:
                filtered.append(b)

        self._render_table(filtered)

    def _on_add_book_clicked(self) -> None:
        QMessageBox.information(
            self,
            "افزودن کتاب",
            "وظیفه دانشجوی شماره ۱:\nتکمیل پنجره افزودن کتاب، اتصال به ISBN و رده‌بندی هوشمند دیویی.",
        )

    def _on_view_clicked(self, row: int) -> None:
        title = self.table.item(row, 2).text() if self.table.item(row, 2) else ""
        QMessageBox.information(self, "مشاهده کتاب", f"جزئیات کتاب:\n{title}")

    def _on_edit_clicked(self, row: int) -> None:
        title = self.table.item(row, 2).text() if self.table.item(row, 2) else ""
        QMessageBox.information(self, "ویرایش کتاب", f"ویرایش کتاب:\n{title}\n(وظیفه دانشجوی شماره ۱)")

    def _on_delete_clicked(self, row: int) -> None:
        title = self.table.item(row, 2).text() if self.table.item(row, 2) else ""
        reply = QMessageBox.question(self, "حذف کتاب", f"آیا از حذف کتاب «{title}» اطمینان دارید؟")
        if reply == QMessageBox.StandardButton.Yes:
            self.table.removeRow(row)

    @staticmethod
    def _style_pagination_btn(btn: QPushButton, is_active: bool = False) -> None:
        if is_active:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLOR_PRIMARY};
                    color: #FFFFFF;
                    border: 1px solid {COLOR_PRIMARY};
                    border-radius: 6px;
                    font-weight: bold;
                }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #FFFFFF;
                    color: {COLOR_TEXT_MAIN};
                    border: 1px solid {COLOR_BORDER};
                    border-radius: 6px;
                }}
                QPushButton:hover {{
                    background-color: {COLOR_PRIMARY_LIGHT};
                    color: {COLOR_PRIMARY};
                    border-color: {COLOR_PRIMARY};
                }}
            """)
