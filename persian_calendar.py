"""
Persian (Jalali) Calendar Date Selection Component and Utilities.
Provides a modern CustomTkinter Jalali date picker dialog, input widgets,
and conversion/formatting functions adhering to the application's UI design system.
"""

from __future__ import annotations

import datetime
import os
import sys
import tkinter as tk
import tkinter.font as tkfont
from typing import Any, Callable

import customtkinter as ctk
import jdatetime
from PIL import Image

# Persian Calendar Constants
PERSIAN_MONTHS = [
    "فروردین",
    "اردیبهشت",
    "خرداد",
    "تیر",
    "مرداد",
    "شهریور",
    "مهر",
    "آبان",
    "آذر",
    "دی",
    "بهمن",
    "اسفند",
]

PERSIAN_WEEKDAYS_SHORT = ["ش", "ی", "د", "س", "چ", "پ", "ج"]
PERSIAN_WEEKDAYS_FULL = [
    "شنبه",
    "یک‌شنبه",
    "دوشنبه",
    "سه‌شنبه",
    "چهارشنبه",
    "پنج‌شنبه",
    "جمعه",
]

_PERSIAN_DIGITS_TRANS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
_ASCII_DIGITS_TRANS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def to_ascii_digits(text: str | None) -> str:
    """Converts Persian and Arabic numerals to standard ASCII digits."""
    if not text:
        return ""
    return str(text).translate(_ASCII_DIGITS_TRANS)


def to_persian_digits(val: int | str) -> str:
    """Converts standard ASCII digits to Persian digits."""
    return str(val).translate(_PERSIAN_DIGITS_TRANS)


def is_leap_jalali_year(year: int) -> bool:
    """Checks if a given Jalali year is a leap year."""
    try:
        return bool(jdatetime.date(year, 1, 1).isleap())
    except Exception:
        # Algorithmic fallback
        rem = year % 33
        return rem in (1, 5, 9, 13, 17, 22, 26, 30)


def get_days_in_jalali_month(year: int, month: int) -> int:
    """Returns total days in the specified Jalali month (1 to 12)."""
    if 1 <= month <= 6:
        return 31
    if 7 <= month <= 11:
        return 30
    if month == 12:
        return 30 if is_leap_jalali_year(year) else 29
    return 30


def get_jalali_first_weekday(year: int, month: int) -> int:
    """
    Returns the weekday index of the 1st day of the given Jalali month.
    In jdatetime: Saturday = 0, Sunday = 1, ..., Friday = 6.
    """
    try:
        return jdatetime.date(year, month, 1).weekday()
    except Exception:
        return 0


def format_jalali_date(date_val: jdatetime.date | datetime.date) -> str:
    """Formats a Jalali date into standard YYYY-MM-DD string."""
    if isinstance(date_val, datetime.date) and not isinstance(date_val, jdatetime.date):
        date_val = jdatetime.date.fromgregorian(date=date_val)
    return f"{date_val.year:04d}-{date_val.month:02d}-{date_val.day:02d}"


def format_jalali_date_long(date_val: jdatetime.date | datetime.date) -> str:
    """Formats a Jalali date into Persian text e.g. 'چهارشنبه، ۲۵ شهریور ۱۴۰۵'."""
    if isinstance(date_val, datetime.date) and not isinstance(date_val, jdatetime.date):
        date_val = jdatetime.date.fromgregorian(date=date_val)
    w_name = PERSIAN_WEEKDAYS_FULL[date_val.weekday()]
    m_name = PERSIAN_MONTHS[date_val.month - 1]
    day_fa = to_persian_digits(date_val.day)
    year_fa = to_persian_digits(date_val.year)
    return f"{w_name}، {day_fa} {m_name} {year_fa}"


def parse_jalali_date(val: Any) -> jdatetime.date | None:
    """
    Parses a string or date object into a validated jdatetime.date instance.
    Accepts 'YYYY-MM-DD', 'YYYY/MM/DD', 'YYYY.MM.DD' in Persian or English digits.
    """
    if val is None:
        return None
    if isinstance(val, jdatetime.date):
        return val
    if isinstance(val, datetime.date):
        return jdatetime.date.fromgregorian(date=val)

    s = to_ascii_digits(str(val)).strip()
    if not s:
        return None

    cleaned = s.replace("/", "-").replace(".", "-").replace("_", "-")
    parts = cleaned.split("-")
    if len(parts) == 3:
        try:
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            if y < 100:
                y += 1400
            max_days = get_days_in_jalali_month(y, m)
            if 1 <= m <= 12 and 1 <= d <= max_days:
                return jdatetime.date(y, m, d)
        except Exception:
            return None
    return None


def is_valid_jalali_date(val: Any) -> bool:
    """Checks whether the input represents a valid Jalali date."""
    return parse_jalali_date(val) is not None


def jalali_to_gregorian(val: str | jdatetime.date) -> datetime.date | None:
    """Converts a Jalali date string or jdatetime.date to Gregorian datetime.date."""
    jdt = parse_jalali_date(val)
    if jdt is None:
        return None
    try:
        return jdt.togregorian()
    except Exception:
        return None


def jalali_to_gregorian_str(val: str | jdatetime.date) -> str | None:
    """Converts a Jalali date string to Gregorian ISO 'YYYY-MM-DD'."""
    g = jalali_to_gregorian(val)
    return g.strftime("%Y-%m-%d") if g else None


def gregorian_to_jalali(val: str | datetime.date) -> jdatetime.date | None:
    """Converts a Gregorian date string or date to jdatetime.date."""
    if isinstance(val, jdatetime.date):
        return val
    if isinstance(val, datetime.date):
        return jdatetime.date.fromgregorian(date=val)
    s = str(val).strip()
    try:
        dt = datetime.datetime.strptime(s[:10], "%Y-%m-%d").date()
        return jdatetime.date.fromgregorian(date=dt)
    except Exception:
        return None


def gregorian_to_jalali_str(val: str | datetime.date) -> str | None:
    """Converts a Gregorian date string to Jalali 'YYYY-MM-DD'."""
    j = gregorian_to_jalali(val)
    return format_jalali_date(j) if j else None


def get_today_jalali() -> jdatetime.date:
    """Returns today's date in the Jalali calendar."""
    return jdatetime.date.today()


def add_days_jalali(base_date: jdatetime.date, days: int) -> jdatetime.date:
    """Adds or subtracts days from a Jalali date."""
    return base_date + jdatetime.timedelta(days=days)


# Icon caching
_icons_cache: dict[tuple[str, int, int], ctk.CTkImage] = {}


def _get_calendar_icon(size: tuple[int, int] = (16, 16)) -> ctk.CTkImage | None:
    """Loads the lucide calendar.png icon if available."""
    cache_key = ("calendar", size[0], size[1])
    if cache_key in _icons_cache:
        return _icons_cache[cache_key]

    base_dir = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
    icon_path = os.path.join(base_dir, "assets", "icons", "lucide", "calendar.png")
    if not os.path.exists(icon_path):
        # Alternative path check
        alt_path = os.path.join(os.path.dirname(__file__), "assets", "icons", "lucide", "calendar.png")
        if os.path.exists(alt_path):
            icon_path = alt_path

    if os.path.exists(icon_path):
        try:
            pil_img = Image.open(icon_path).convert("RGBA")
            r, g, b, a = pil_img.split()
            white_img = Image.merge("RGBA", (Image.new("L", pil_img.size, 255),) * 3 + (a,))
            ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=white_img, size=size)
            _icons_cache[cache_key] = ctk_img
            return ctk_img
        except Exception:
            return None
    return None


class JalaliDatePickerDialog(ctk.CTkToplevel):
    """
    Modern Persian / Jalali Calendar Date Picker Dialog.
    Features:
    - Iranian RTL day layout (Saturday on right, Friday on left).
    - Weekend (Friday) highlighted in red.
    - Today's date highlighted with green accent border.
    - Selected day highlighted in primary blue.
    - Quick navigation by Month (OptionMenu) and Year (OptionMenu / arrows).
    - Instant live header preview of selected date in full Persian.
    - 'Today' button to quickly jump to current date.
    - Double-click to instantly confirm and close.
    - Compatible with CustomTkinter light and dark modes.
    """

    def __init__(
        self,
        parent: tk.Tk | tk.Toplevel | ctk.CTk | ctk.CTkToplevel | None = None,
        initial_date: str | jdatetime.date | None = None,
        on_select: Callable[[str, jdatetime.date], None] | None = None,
        title: str = "انتخاب تاریخ شمسی",
        min_date: str | jdatetime.date | None = None,
        max_date: str | jdatetime.date | None = None,
        icon_path: str | None = None,
    ):
        super().__init__(parent)

        self.parent = parent
        self.on_select = on_select
        self.min_date = parse_jalali_date(min_date)
        self.max_date = parse_jalali_date(max_date)
        self.result: str | None = None
        self.result_date: jdatetime.date | None = None

        today = get_today_jalali()
        parsed_init = parse_jalali_date(initial_date)
        self.selected_date: jdatetime.date = parsed_init if parsed_init else today
        self.view_year: int = self.selected_date.year
        self.view_month: int = self.selected_date.month

        # Fonts configuration
        font_family = "IRANSansWeb(FaNum)"
        if parent:
            try:
                available = tkfont.families(self)
                if font_family not in available:
                    font_family = "Tahoma"
            except Exception:
                font_family = "Tahoma"

        self.font_title = ctk.CTkFont(family=font_family, size=13, weight="bold")
        self.font_normal = ctk.CTkFont(family=font_family, size=11)
        self.font_bold = ctk.CTkFont(family=font_family, size=11, weight="bold")
        self.font_small = ctk.CTkFont(family=font_family, size=10)

        self.title(title)
        self.geometry("360x460")
        self.resizable(False, False)

        if icon_path and os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        # Modal setup
        if parent:
            self.transient(parent)
            self.grab_set()

        # Keyboard bindings
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Return>", lambda e: self._confirm_selection())

        self._build_ui()
        self._center_dialog()
        self.focus_set()

    def _center_dialog(self):
        """Centers the picker on the parent window or screen."""
        self.update_idletasks()
        dialog_w = 360
        dialog_h = 460
        if self.parent:
            try:
                pw = self.parent.winfo_width()
                ph = self.parent.winfo_height()
                px = self.parent.winfo_rootx()
                py = self.parent.winfo_rooty()
                x = px + (pw - dialog_w) // 2
                y = py + (ph - dialog_h) // 2
                self.geometry(f"{dialog_w}x{dialog_h}+{max(40, x)}+{max(40, y)}")
                return
            except Exception:
                pass

        # Fallback screen center
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - dialog_w) // 2
        y = (sh - dialog_h) // 2
        self.geometry(f"{dialog_w}x{dialog_h}+{max(40, x)}+{max(40, y)}")

    def _build_ui(self):
        """Builds all UI components of the Jalali calendar."""
        # Top Header Banner Card
        self.header_frame = ctk.CTkFrame(self, corner_radius=8, fg_color=("#e2e8f0", "#1e293b"))
        self.header_frame.pack(fill=tk.X, padx=14, pady=(12, 6))

        self.lbl_selected_long = ctk.CTkLabel(
            self.header_frame,
            text="",
            font=self.font_title,
            text_color=("#2563eb", "#38bdf8"),
            anchor="center",
        )
        self.lbl_selected_long.pack(fill=tk.X, padx=10, pady=(8, 2))

        self.lbl_selected_sub = ctk.CTkLabel(
            self.header_frame,
            text="",
            font=self.font_small,
            text_color=("#64748b", "#94a3b8"),
            anchor="center",
        )
        self.lbl_selected_sub.pack(fill=tk.X, padx=10, pady=(0, 8))

        # Month and Year Navigation Toolbar
        self.nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.nav_frame.pack(fill=tk.X, padx=14, pady=(4, 6))

        # Next Month Button (moves month forward)
        self.btn_next_month = ctk.CTkButton(
            self.nav_frame,
            text="‹",
            font=ctk.CTkFont(family="Arial", size=15, weight="bold"),
            width=32,
            height=30,
            command=self._next_month,
            fg_color=("#cbd5e1", "#334155"),
            hover_color=("#94a3b8", "#475569"),
            text_color=("#0f172a", "#f8fafc"),
        )
        self.btn_next_month.pack(side=tk.LEFT, padx=2)

        # Month Selector
        self.month_var = tk.StringVar(value=PERSIAN_MONTHS[self.view_month - 1])
        self.combo_month = ctk.CTkOptionMenu(
            self.nav_frame,
            variable=self.month_var,
            values=PERSIAN_MONTHS,
            width=110,
            height=30,
            font=self.font_normal,
            dropdown_font=self.font_normal,
            command=self._on_month_changed,
        )
        self.combo_month.pack(side=tk.LEFT, padx=4)

        # Year Selector
        cur_year = get_today_jalali().year
        year_options = [str(y) for y in range(cur_year - 15, cur_year + 16)]
        if str(self.view_year) not in year_options:
            year_options.append(str(self.view_year))
            year_options.sort()

        self.year_var = tk.StringVar(value=str(self.view_year))
        self.combo_year = ctk.CTkOptionMenu(
            self.nav_frame,
            variable=self.year_var,
            values=year_options,
            width=85,
            height=30,
            font=self.font_normal,
            dropdown_font=self.font_normal,
            command=self._on_year_changed,
        )
        self.combo_year.pack(side=tk.RIGHT, padx=4)

        # Prev Month Button (moves month backward)
        self.btn_prev_month = ctk.CTkButton(
            self.nav_frame,
            text="›",
            font=ctk.CTkFont(family="Arial", size=15, weight="bold"),
            width=32,
            height=30,
            command=self._prev_month,
            fg_color=("#cbd5e1", "#334155"),
            hover_color=("#94a3b8", "#475569"),
            text_color=("#0f172a", "#f8fafc"),
        )
        self.btn_prev_month.pack(side=tk.RIGHT, padx=2)

        # Calendar Grid Frame
        self.calendar_card = ctk.CTkFrame(self, corner_radius=8)
        self.calendar_card.pack(fill=tk.BOTH, expand=True, padx=14, pady=4)

        # Weekdays Header (Saturday to Friday, right-to-left)
        # Saturday is column 6 (far right), Friday is column 0 (far left)
        self.weekday_frame = ctk.CTkFrame(self.calendar_card, fg_color="transparent")
        self.weekday_frame.pack(fill=tk.X, padx=6, pady=(6, 2))

        for col_idx in range(7):
            self.weekday_frame.grid_columnconfigure(col_idx, weight=1)

        # Persian days in short representation
        # Indices: 0=Saturday (col 6), 1=Sunday (col 5), ..., 6=Friday (col 0)
        for day_idx, day_name in enumerate(PERSIAN_WEEKDAYS_SHORT):
            grid_col = 6 - day_idx
            is_friday = day_idx == 6
            lbl = ctk.CTkLabel(
                self.weekday_frame,
                text=day_name,
                font=self.font_bold,
                text_color="#ef4444" if is_friday else ("#64748b", "#94a3b8"),
                width=38,
                anchor="center",
            )
            lbl.grid(row=0, column=grid_col, padx=1, pady=2)

        # Days Grid Container
        self.days_container = ctk.CTkFrame(self.calendar_card, fg_color="transparent")
        self.days_container.pack(fill=tk.BOTH, expand=True, padx=6, pady=(2, 6))

        for col_idx in range(7):
            self.days_container.grid_columnconfigure(col_idx, weight=1)
        for row_idx in range(6):
            self.days_container.grid_rowconfigure(row_idx, weight=1)

        # Action Buttons Footer
        self.footer_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.footer_frame.pack(fill=tk.X, padx=14, pady=(6, 12))

        self.btn_confirm = ctk.CTkButton(
            self.footer_frame,
            text="تأیید",
            font=self.font_bold,
            width=90,
            height=32,
            fg_color="#16a34a",
            hover_color="#15803d",
            command=self._confirm_selection,
        )
        self.btn_confirm.pack(side=tk.RIGHT, padx=(4, 0))

        self.btn_today = ctk.CTkButton(
            self.footer_frame,
            text="امروز",
            font=self.font_normal,
            width=75,
            height=32,
            fg_color="transparent",
            border_width=1,
            border_color="#0284c7",
            text_color=("#0284c7", "#38bdf8"),
            hover_color=("#e0f2fe", "#0c4a6e"),
            command=self._jump_to_today,
        )
        self.btn_today.pack(side=tk.RIGHT, padx=4)

        self.btn_cancel = ctk.CTkButton(
            self.footer_frame,
            text="انصراف",
            font=self.font_normal,
            width=75,
            height=32,
            fg_color="transparent",
            hover_color=("#e2e8f0", "#1e293b"),
            command=self.destroy,
        )
        self.btn_cancel.pack(side=tk.LEFT, padx=(0, 4))

        self._update_header_label()
        self._render_days_grid()

    def _update_header_label(self):
        """Updates top card banner with full Persian and ISO date representation."""
        if self.selected_date:
            self.lbl_selected_long.configure(text=format_jalali_date_long(self.selected_date))
            iso_str = format_jalali_date(self.selected_date)
            greg_str = jalali_to_gregorian_str(self.selected_date) or ""
            self.lbl_selected_sub.configure(text=f"شمسی: {iso_str}   |   میلادی: {greg_str}")

    def _on_month_changed(self, choice: str):
        if choice in PERSIAN_MONTHS:
            self.view_month = PERSIAN_MONTHS.index(choice) + 1
            self._render_days_grid()

    def _on_year_changed(self, choice: str):
        try:
            self.view_year = int(choice)
            self._render_days_grid()
        except ValueError:
            pass

    def _prev_month(self):
        """Moves view to previous month."""
        if self.view_month == 1:
            self.view_month = 12
            self.view_year -= 1
        else:
            self.view_month -= 1
        self._sync_toolbar_menus()
        self._render_days_grid()

    def _next_month(self):
        """Moves view to next month."""
        if self.view_month == 12:
            self.view_month = 1
            self.view_year += 1
        else:
            self.view_month += 1
        self._sync_toolbar_menus()
        self._render_days_grid()

    def _sync_toolbar_menus(self):
        self.month_var.set(PERSIAN_MONTHS[self.view_month - 1])
        y_str = str(self.view_year)
        if y_str not in self.combo_year.cget("values"):
            cur_vals = list(self.combo_year.cget("values"))
            cur_vals.append(y_str)
            cur_vals.sort()
            self.combo_year.configure(values=cur_vals)
        self.year_var.set(y_str)

    def _jump_to_today(self):
        today = get_today_jalali()
        self.selected_date = today
        self.view_year = today.year
        self.view_month = today.month
        self._sync_toolbar_menus()
        self._update_header_label()
        self._render_days_grid()

    def _render_days_grid(self):
        """Draws the day buttons in the 7x6 grid for the current view_year and view_month."""
        for widget in self.days_container.winfo_children():
            widget.destroy()

        today = get_today_jalali()
        start_weekday = get_jalali_first_weekday(self.view_year, self.view_month)
        days_count = get_days_in_jalali_month(self.view_year, self.view_month)

        for day in range(1, days_count + 1):
            cur_jdate = jdatetime.date(self.view_year, self.view_month, day)
            grid_pos = start_weekday + day - 1
            grid_row = grid_pos // 7
            col_offset = grid_pos % 7
            # RTL column mapping: Saturday (offset 0) -> col 6, Friday (offset 6) -> col 0
            grid_col = 6 - col_offset

            is_selected = (
                self.selected_date
                and self.selected_date.year == self.view_year
                and self.selected_date.month == self.view_month
                and self.selected_date.day == day
            )
            is_today = today.year == self.view_year and today.month == self.view_month and today.day == day
            is_friday = col_offset == 6

            # Range checks
            is_disabled = False
            if self.min_date and cur_jdate < self.min_date:
                is_disabled = True
            if self.max_date and cur_jdate > self.max_date:
                is_disabled = True

            # Styling
            border_col = None
            if is_disabled:
                fg_col = "transparent"
                txt_col = ("#94a3b8", "#475569")
                hover_col = fg_col
                border_w = 0
            elif is_selected:
                fg_col = "#2563eb"
                txt_col = "white"
                hover_col = "#1d4ed8"
                border_w = 0
            elif is_today:
                fg_col = ("#dcfce7", "#14532d")
                txt_col = ("#15803d", "#4ade80")
                hover_col = ("#bbf7d0", "#166534")
                border_w = 1
                border_col = "#16a34a"
            elif is_friday:
                fg_col = "transparent"
                txt_col = "#ef4444"
                hover_col = ("#fee2e2", "#3b1a1a")
                border_w = 0
            else:
                fg_col = "transparent"
                txt_col = ("#0f172a", "#f8fafc")
                hover_col = ("#e2e8f0", "#334155")
                border_w = 0

            btn_kwargs: dict[str, Any] = {
                "text": str(day),
                "font": self.font_bold if (is_selected or is_today) else self.font_normal,
                "width": 38,
                "height": 32,
                "corner_radius": 6,
                "fg_color": fg_col,
                "text_color": txt_col,
                "hover_color": hover_col,
                "border_width": border_w,
                "state": "disabled" if is_disabled else "normal",
                "command": lambda d=cur_jdate: self._on_day_clicked(d),
            }
            if border_col is not None:
                btn_kwargs["border_color"] = border_col

            btn = ctk.CTkButton(self.days_container, **btn_kwargs)
            # Double-click immediately confirms selection
            if not is_disabled:
                btn.bind("<Double-Button-1>", lambda e, d=cur_jdate: self._on_day_double_clicked(d))

            btn.grid(row=grid_row, column=grid_col, padx=2, pady=2, sticky="nsew")

    def _on_day_clicked(self, selected: jdatetime.date):
        self.selected_date = selected
        self._update_header_label()
        self._render_days_grid()

    def _on_day_double_clicked(self, selected: jdatetime.date):
        self.selected_date = selected
        self._confirm_selection()

    def _confirm_selection(self):
        if not self.selected_date:
            self.destroy()
            return

        formatted = format_jalali_date(self.selected_date)
        self.result = formatted
        self.result_date = self.selected_date

        if self.on_select:
            try:
                self.on_select(formatted, self.selected_date)
            except Exception:
                pass

        self.destroy()


def open_jalali_date_picker(
    parent: tk.Tk | tk.Toplevel | ctk.CTk | ctk.CTkToplevel | None = None,
    initial_date: str | jdatetime.date | None = None,
    on_select: Callable[[str, jdatetime.date], None] | None = None,
    title: str = "انتخاب تاریخ شمسی",
    min_date: str | jdatetime.date | None = None,
    max_date: str | jdatetime.date | None = None,
    icon_path: str | None = None,
) -> JalaliDatePickerDialog:
    """
    Global helper function to instantiate and show the Jalali Date Picker dialog.
    """
    return JalaliDatePickerDialog(
        parent=parent,
        initial_date=initial_date,
        on_select=on_select,
        title=title,
        min_date=min_date,
        max_date=max_date,
        icon_path=icon_path,
    )


def create_date_picker_button(
    parent: Any,
    entry_widget: ctk.CTkEntry | tk.Entry,
    title: str = "انتخاب تاریخ",
    on_select: Callable[[str], None] | None = None,
    min_date: str | jdatetime.date | None = None,
    max_date: str | jdatetime.date | None = None,
    icon_path: str | None = None,
    width: int = 34,
    height: int = 32,
) -> ctk.CTkButton:
    """
    Creates a matching CustomTkinter calendar icon button that opens
    the Jalali Date Picker and fills entry_widget with the chosen date.
    """
    cal_icon = _get_calendar_icon(size=(16, 16))

    def _on_click():
        current_val = entry_widget.get().strip()
        toplevel = parent.winfo_toplevel() if hasattr(parent, "winfo_toplevel") else None

        def _handle_date_selected(date_str: str, date_obj: jdatetime.date):
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, date_str)
            if on_select:
                try:
                    on_select(date_str)
                except Exception:
                    pass

        open_jalali_date_picker(
            parent=toplevel,
            initial_date=current_val,
            on_select=_handle_date_selected,
            title=title,
            min_date=min_date,
            max_date=max_date,
            icon_path=icon_path,
        )

    btn = ctk.CTkButton(
        parent,
        text="" if cal_icon else "📅",
        image=cal_icon,
        width=width,
        height=height,
        fg_color=("#e2e8f0", "#1e293b"),
        hover_color=("#cbd5e1", "#334155"),
        text_color=("#0f172a", "#f8fafc"),
        command=_on_click,
    )
    return btn


class JalaliDateEntry(ctk.CTkFrame):
    """
    Composite CustomTkinter field combining a date Entry and a Jalali Calendar picker button.
    Standardized for seamless replacement or insertion across any form.
    """

    def __init__(
        self,
        master: Any,
        placeholder_text: str = "YYYY-MM-DD",
        initial_date: str | jdatetime.date | None = None,
        font: Any = None,
        height: int = 32,
        on_date_changed: Callable[[str], None] | None = None,
        min_date: str | jdatetime.date | None = None,
        max_date: str | jdatetime.date | None = None,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.on_date_changed = on_date_changed
        self.min_date = min_date
        self.max_date = max_date

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)

        self.entry = ctk.CTkEntry(
            self,
            font=font,
            justify="right",
            height=height,
            placeholder_text=placeholder_text,
        )
        self.entry.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        self.btn_picker = create_date_picker_button(
            self,
            entry_widget=self.entry,
            on_select=self._on_picker_select,
            min_date=min_date,
            max_date=max_date,
            width=height + 2,
            height=height,
        )
        self.btn_picker.grid(row=0, column=0, sticky="w")

        if initial_date:
            d_str = format_jalali_date(initial_date) if isinstance(initial_date, jdatetime.date) else str(initial_date)
            self.set(d_str)

    def _on_picker_select(self, date_str: str):
        if self.on_date_changed:
            try:
                self.on_date_changed(date_str)
            except Exception:
                pass

    def get(self) -> str:
        return self.entry.get().strip()

    def set(self, val: str | jdatetime.date):
        self.entry.delete(0, tk.END)
        s = format_jalali_date(val) if isinstance(val, jdatetime.date) else str(val)
        self.entry.insert(0, s)

    def set_date(self, val: str | jdatetime.date):
        self.set(val)

    def delete(self, first: int, last: int | None = None):
        self.entry.delete(first, last)

    def insert(self, index: int, string: str):
        self.entry.insert(index, string)

    def get_date(self) -> jdatetime.date | None:
        return parse_jalali_date(self.get())

    def bind(self, sequence=None, func=None, add=None):
        return self.entry.bind(sequence, func, add)
