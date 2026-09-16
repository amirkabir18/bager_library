import datetime
import os
import sqlite3
import sys
import tempfile
import threading
import tkinter as tk
import tkinter.font as tkfont
import webbrowser
from tkinter import messagebox, ttk

import customtkinter as ctk
import jdatetime
from PIL import Image

from notifications import LoanReminderManager, NotificationEngine
from updater import (
    DownloadManager,
    UpdateChecker,
    apply_update,
    format_size,
    format_speed,
    load_app_info,
)

base_dir = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
icon_p = os.path.join(base_dir, "logo.ico")
fonts_dir = os.path.join(base_dir, "assets", "fonts", "iransans", "ttf")


def load_fonts():
    if sys.platform == "win32":
        try:
            import ctypes
            import glob

            if os.path.exists(fonts_dir):
                for font_file in glob.glob(os.path.join(fonts_dir, "*.ttf")):
                    ctypes.windll.gdi32.AddFontResourceExW(os.path.abspath(font_file), 0x10, 0)
        except Exception:
            pass


load_fonts()

from auth import (
    OTPCleanupManager,
    OTPService,
    authenticate,
    create_user,
    delete_user,
    ensure_bootstrap_admin,
    get_user_by_identifier,
    is_super_admin,
    mask_phone_number,
    normalize_phone_number,
    update_user,
)
from database import (
    clear_notification_logs,
    db_p,
    get_all_settings,
    get_db_connection,
    get_notification_logs,
    init_database,
    is_ai_features_enabled,
    is_internet_access_enabled,
    log_notification,
    rtl_display_order,
    set_setting,
    tr,
)
from persian_calendar import (
    create_date_picker_button,
    format_jalali_date,
    get_today_jalali,
    jalali_to_gregorian_str,
    parse_jalali_date,
)
from services.book_service import BookService
from services.dewey_ai_agent import (
    get_boot_internet_status,
    init_boot_internet_check,
    probe_internet_connectivity,
    set_boot_internet_status,
)
from services.dewey_service import DeweyService, is_valid_dewey

dewey_service = DeweyService()
book_service = BookService(dewey_service=dewey_service)

with get_db_connection(db_p) as _init_conn:
    init_database(_init_conn)
    ensure_bootstrap_admin(database_path=db_p)
    _init_cur = _init_conn.cursor()
    _init_cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables_data = _init_cur.fetchall()
    table_names = [str(r[0]) for r in tables_data]
    tabel_name = "books"
    _init_cur.execute(f'PRAGMA table_info("{tabel_name}")')
    columns: list[str] = [str(row[1]) for row in _init_cur.fetchall()]

# CustomTkinter Global Theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

root = ctk.CTk()
root.title("کتابخانه باقر العلوم")
root.geometry("1080x720")
root.minsize(920, 620)

notification_engine = NotificationEngine(root, icon_path=icon_p, db_path=db_p)
reminder_manager = LoanReminderManager(root, db_p, notification_engine)
reminder_manager.start()
otp_cleanup_manager = OTPCleanupManager(root, db_p)
otp_cleanup_manager.start()


# Application boot-time internet check
def run_boot_internet_check():
    try:
        init_boot_internet_check(database_path=db_p, timeout=1.2)
        try:
            root.after(
                0,
                lambda: update_boot_net_status_label() if "update_boot_net_status_label" in globals() else None,
            )
        except Exception:
            pass
    except Exception:
        pass


boot_net_thread = threading.Thread(target=run_boot_internet_check, daemon=True)
boot_net_thread.start()


def is_ai_available() -> bool:
    """Checks whether AI features are enabled in settings and internet was verified at boot."""
    return is_ai_features_enabled(db_p) and get_boot_internet_status(db_p)


if os.path.exists(icon_p):
    try:
        root.iconbitmap(icon_p)
    except Exception:
        pass

available_families = tkfont.families(root)
FONT_FAMILY = "IRANSansWeb(FaNum)" if "IRANSansWeb(FaNum)" in available_families else "Tahoma"

try:
    ctk.ThemeManager.theme["CTkFont"]["family"] = FONT_FAMILY
except Exception:
    pass

FONT_TITLE = ctk.CTkFont(family=FONT_FAMILY, size=15, weight="bold")
FONT_HEADER = ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold")
FONT_NORMAL = ctk.CTkFont(family=FONT_FAMILY, size=11)
FONT_BOLD = ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold")
FONT_SMALL = ctk.CTkFont(family=FONT_FAMILY, size=10)

icons_cache: dict[tuple[str, int, int, bool], ctk.CTkImage] = {}


def get_icon(name: str, size: tuple[int, int] = (18, 18), white_only: bool = False) -> ctk.CTkImage | None:
    cache_key = (name, size[0], size[1], white_only)
    if cache_key in icons_cache:
        return icons_cache[cache_key]
    icon_path = os.path.join(base_dir, "assets", "icons", "lucide", f"{name}.png")
    if os.path.exists(icon_path):
        try:
            pil_img = Image.open(icon_path).convert("RGBA")
            r, g, b, a = pil_img.split()
            white_img = Image.merge(
                "RGBA",
                (
                    Image.new("L", pil_img.size, 255),
                    Image.new("L", pil_img.size, 255),
                    Image.new("L", pil_img.size, 255),
                    a,
                ),
            )
            light_img = white_img if white_only else pil_img
            ctk_img = ctk.CTkImage(light_image=light_img, dark_image=white_img, size=size)
            icons_cache[cache_key] = ctk_img
            return ctk_img
        except Exception:
            return None
    return None


def create_icon_button(
    parent,
    text: str,
    icon_name: str | None = None,
    command=None,
    font=None,
    fg_color=None,
    hover_color=None,
    width=None,
    height=32,
    corner_radius=8,
    **kwargs,
) -> ctk.CTkButton:
    is_colored_btn = fg_color not in (None, "transparent")
    img = get_icon(icon_name, white_only=is_colored_btn) if icon_name else None
    btn_kwargs = {
        "text": text,
        "command": command,
        "font": font or FONT_NORMAL,
        "height": height,
        "corner_radius": corner_radius,
        "compound": "right",
    }
    if width is not None:
        btn_kwargs["width"] = width
    if fg_color is not None:
        btn_kwargs["fg_color"] = fg_color
    if hover_color is not None:
        btn_kwargs["hover_color"] = hover_color
    if img:
        btn_kwargs["image"] = img
    btn_kwargs.update(kwargs)
    return ctk.CTkButton(parent, **btn_kwargs)


def apply_treeview_styling(mode="dark"):
    st = ttk.Style()
    st.theme_use("clam")
    if mode == "dark":
        bg_col = "#242424"
        fg_col = "#f1f5f9"
        field_col = "#242424"
        head_bg = "#1e1e1e"
        head_fg = "#ffffff"
        head_active = "#333333"
        sel_bg = "#1f538d"
        sel_fg = "#ffffff"
    else:
        bg_col = "#ffffff"
        fg_col = "#0f172a"
        field_col = "#ffffff"
        head_bg = "#f1f5f9"
        head_fg = "#0f172a"
        head_active = "#e2e8f0"
        sel_bg = "#3b82f6"
        sel_fg = "#ffffff"

    st.configure(
        "Treeview",
        background=bg_col,
        foreground=fg_col,
        fieldbackground=field_col,
        rowheight=32,
        font=(FONT_FAMILY, 10),
        borderwidth=0,
    )
    st.configure(
        "Treeview.Heading",
        background=head_bg,
        foreground=head_fg,
        relief="flat",
        font=(FONT_FAMILY, 10, "bold"),
        padding=6,
    )
    st.map("Treeview", background=[("selected", sel_bg)], foreground=[("selected", sel_fg)])
    st.map("Treeview.Heading", background=[("active", head_active)])


apply_treeview_styling("dark")

current_user: dict | None = None

ALLOWED_DELETE_TABLES = {"books", "members", "loans", "auth_users"}


def bind_table_delete(tree_widget, table_name, id_col_index=0, on_deleted=None):
    if table_name not in ALLOWED_DELETE_TABLES:
        raise ValueError(f"Table '{table_name}' is not allowed for deletion via bind_table_delete")

    def on_delete_key(event):
        selected = tree_widget.selection()
        if not selected:
            return

        valid_items = []
        for item_id in selected:
            values = tree_widget.item(item_id, "values")
            if not values or len(values) <= id_col_index:
                continue
            if str(values[0]).startswith("❌"):
                continue
            rec_id = values[id_col_index]
            if table_name == "auth_users" and current_user and str(rec_id) == str(current_user.get("id")):
                messagebox.showwarning("هشدار", "نمی‌توانید حساب کاربری فعال خود را حذف کنید!", parent=root)
                continue
            valid_items.append((item_id, rec_id))

        if not valid_items:
            return

        confirm = messagebox.askyesno("تأیید حذف", "آیا از حذف این ردیف اطمینان دارید؟", parent=root)
        if not confirm:
            return

        if table_name == "auth_users":
            all_succeeded = True
            deleted_items = []
            for item_id, rec_id in valid_items:
                try:
                    del_ok, msg = delete_user(int(rec_id), database_path=db_p)
                except Exception as ex:
                    del_ok, msg = False, str(ex)
                if del_ok:
                    deleted_items.append(item_id)
                else:
                    all_succeeded = False
                    messagebox.showerror("خطا در حذف کاربر", msg, parent=root)
            for item_id in deleted_items:
                try:
                    tree_widget.delete(item_id)
                except Exception:
                    pass
            if all_succeeded and deleted_items:
                messagebox.showinfo("موفق", "کاربر با موفقیت حذف شد.", parent=root)
            if on_deleted:
                on_deleted()
            return

        del_conn = get_db_connection(db_p)
        try:
            del_cur = del_conn.cursor()
            for item_id, rec_id in valid_items:
                if table_name == "loans":
                    del_cur.execute("DELETE FROM notification_logs WHERE loan_id = ?", (rec_id,))
                del_cur.execute(f"DELETE FROM `{table_name}` WHERE id = ?", (rec_id,))
            del_conn.commit()
            for item_id, _ in valid_items:
                try:
                    tree_widget.delete(item_id)
                except Exception:
                    pass
            messagebox.showinfo("موفق", "ردیف با موفقیت حذف شد.", parent=root)
            if on_deleted:
                on_deleted()
        except Exception as e:
            try:
                del_conn.rollback()
            except Exception:
                pass
            messagebox.showerror("خطا", f"خطا در حذف اطلاعات: {e}", parent=root)
        finally:
            del_conn.close()

    tree_widget.bind("<Delete>", on_delete_key)


# ==================== Shell Header & Navigation ====================
header_frame = ctk.CTkFrame(root, height=54, corner_radius=10)
header_frame.pack(fill=tk.X, padx=12, pady=(10, 6))

title_box = ctk.CTkFrame(header_frame, fg_color="transparent")
title_box.pack(side=tk.RIGHT, padx=(4, 12), pady=6)

lbl_app_logo = ctk.CTkLabel(
    title_box,
    text="کتابخانه باقر العلوم",
    font=FONT_TITLE,
)
lbl_app_logo.pack(side=tk.RIGHT)

left_actions = ctk.CTkFrame(header_frame, fg_color="transparent")
left_actions.pack(side=tk.LEFT, padx=(12, 4), pady=6)

btn_user_profile = ctk.CTkButton(
    left_actions,
    text=" ورود به سامانه ",
    font=FONT_NORMAL,
    height=34,
    corner_radius=8,
    fg_color="#2563eb",
    hover_color="#1d4ed8",
    command=lambda: switch_tab("login"),
)
btn_user_profile.pack(side=tk.LEFT)
lbl_user_badge = btn_user_profile  # Keep backwards compatibility reference

nav_bar = ctk.CTkFrame(header_frame, fg_color="transparent")
nav_bar.pack(side=tk.RIGHT, padx=4, fill=tk.Y)

content_container = ctk.CTkFrame(root, corner_radius=10, fg_color="transparent")
content_container.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 10))

login_frame = ctk.CTkFrame(content_container, corner_radius=10)
books_frame = ctk.CTkFrame(content_container, corner_radius=10)
tabel_frame = ctk.CTkFrame(content_container, corner_radius=10)
member_frame = ctk.CTkFrame(content_container, corner_radius=10)
auth_users_frame = ctk.CTkFrame(content_container, corner_radius=10)
help_frame = ctk.CTkFrame(content_container, corner_radius=10)
settings_frame = ctk.CTkFrame(content_container, corner_radius=10)

filter_settings = {
    "column": "all",
    "match_mode": "contains",
    "availability": "all",
    "dewey_class": "all",
    "sort_col": "id",
    "sort_dir": "ASC",
}

current_active_tab = "login"
nav_buttons: dict[str, ctk.CTkButton] = {}
active_tabs_data: dict[str, dict] = {}
active_user_popover: ctk.CTkToplevel | None = None
current_header_mode = "compact"
resize_timer_id = None


def close_user_profile_popover():
    global active_user_popover
    if active_user_popover is not None:
        try:
            if active_user_popover.winfo_exists():
                active_user_popover.destroy()
        except Exception:
            pass
        active_user_popover = None


def open_user_profile_popover():
    global active_user_popover
    if active_user_popover is not None and active_user_popover.winfo_exists():
        close_user_profile_popover()
        return

    if current_user is None:
        switch_tab("login")
        return

    popover = ctk.CTkToplevel(root)
    active_user_popover = popover
    popover.overrideredirect(True)
    if os.path.exists(icon_p):
        try:
            popover.iconbitmap(icon_p)
        except Exception:
            pass

    u_name = str(current_user.get("username", "کاربر"))
    raw_role = str(current_user.get("role", "librarian")).strip().lower()
    role_fa = tr(raw_role)
    phone_num = str(current_user.get("phone_number", ""))
    u_id = current_user.get("id")
    telegram_chat = str(current_user.get("telegram_chat_id") or "").strip()
    is_active = current_user.get("is_active", 1)
    created_at_val = str(current_user.get("created_at") or "")

    root.update_idletasks()
    bx = btn_user_profile.winfo_rootx()
    by = btn_user_profile.winfo_rooty() + btn_user_profile.winfo_height() + 6
    p_w = 310
    p_h = 415 if raw_role in ("super admin", "superadmin", "admin") else 380
    popover.geometry(f"{p_w}x{p_h}+{bx}+{by}")

    card = ctk.CTkFrame(
        popover,
        corner_radius=12,
        border_width=1,
        border_color=("#cbd5e1", "#334155"),
        fg_color=("#ffffff", "#1e293b"),
    )
    card.pack(fill=tk.BOTH, expand=True)

    header_box = ctk.CTkFrame(card, fg_color="transparent")
    header_box.pack(fill=tk.X, padx=16, pady=(14, 6))

    role_colors = {
        "super admin": ("#064e3b", "#34d399"),
        "superadmin": ("#064e3b", "#34d399"),
        "admin": ("#1e3a8a", "#60a5fa"),
        "librarian": ("#78350f", "#fbbf24"),
    }
    r_bg, r_text = role_colors.get(raw_role, ("#1e293b", "#94a3b8"))

    name_row = ctk.CTkFrame(header_box, fg_color="transparent")
    name_row.pack(fill=tk.X)
    ctk.CTkLabel(
        name_row,
        text=f"  {u_name}",
        image=get_icon("user"),
        compound="right",
        font=FONT_HEADER,
        text_color=("#0f172a", "#f8fafc"),
        anchor="e",
    ).pack(side=tk.RIGHT)

    badge_row = ctk.CTkFrame(header_box, fg_color="transparent")
    badge_row.pack(fill=tk.X, pady=(6, 0))

    role_pill = ctk.CTkLabel(
        badge_row,
        text=f" {role_fa} ",
        font=FONT_SMALL,
        fg_color=r_bg,
        text_color=r_text,
        corner_radius=6,
        height=22,
    )
    role_pill.pack(side=tk.RIGHT, padx=(0, 6))

    if is_active in (1, "1", True):
        status_text = "حساب فعال"
        st_color = ("#15803d", "#34d399")
        st_bg = ("#dcfce7", "#064e3b")
    else:
        status_text = "غیرفعال"
        st_color = ("#dc2626", "#f87171")
        st_bg = ("#fee2e2", "#450a0a")

    ctk.CTkLabel(
        badge_row,
        text=f" {status_text} ",
        font=FONT_SMALL,
        text_color=st_color,
        fg_color=st_bg,
        corner_radius=6,
        height=22,
        anchor="center",
    ).pack(side=tk.LEFT)

    ctk.CTkFrame(card, height=1, fg_color=("#e2e8f0", "#334155")).pack(fill=tk.X, padx=14, pady=(4, 6))

    info_box = ctk.CTkFrame(card, corner_radius=8, fg_color=("#f8fafc", "#0f172a"))
    info_box.pack(fill=tk.X, padx=14, pady=4)

    def add_info_row(parent, label, value):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill=tk.X, padx=10, pady=3)
        ctk.CTkLabel(row, text=label, font=FONT_SMALL, text_color=("#64748b", "#94a3b8"), anchor="e").pack(
            side=tk.RIGHT
        )
        ctk.CTkLabel(row, text=value, font=FONT_SMALL, text_color=("#0f172a", "#f8fafc"), anchor="w").pack(side=tk.LEFT)

    if phone_num:
        add_info_row(info_box, "شماره تماس:", phone_num)
    if u_id is not None:
        add_info_row(info_box, "شناسه کاربر:", f"#{u_id}")

    tg_display = telegram_chat if telegram_chat else "ثبت نشده"
    add_info_row(info_box, "شناسه تلگرام:", tg_display)

    if created_at_val:
        created_display = created_at_val[:10]
        if jdatetime is not None:
            try:
                dt = datetime.datetime.fromisoformat(created_at_val.split(".")[0])
                jdt = jdatetime.datetime.fromgregorian(datetime=dt)
                created_display = jdt.strftime("%Y/%m/%d")
            except Exception:
                pass
        add_info_row(info_box, "تاریخ عضویت:", created_display)

    ctk.CTkFrame(card, height=1, fg_color=("#e2e8f0", "#334155")).pack(fill=tk.X, padx=14, pady=(6, 4))

    def go_to_users():
        close_user_profile_popover()
        switch_tab("users")

    def go_to_settings():
        close_user_profile_popover()
        switch_tab("settings")

    def do_logout():
        close_user_profile_popover()
        logout()

    if raw_role in ("super admin", "superadmin", "admin"):
        btn_users = ctk.CTkButton(
            card,
            text=" مدیریت کاربران سامانه ",
            image=get_icon("user-plus"),
            compound="right",
            font=FONT_NORMAL,
            height=30,
            fg_color="transparent",
            hover_color=("#f1f5f9", "#334155"),
            text_color=("#1e293b", "#f8fafc"),
            anchor="e",
            command=go_to_users,
        )
        btn_users.pack(fill=tk.X, padx=12, pady=2)

    btn_set = ctk.CTkButton(
        card,
        text=" تنظیمات و اعلان‌ها ",
        image=get_icon("filter"),
        compound="right",
        font=FONT_NORMAL,
        height=30,
        fg_color="transparent",
        hover_color=("#f1f5f9", "#334155"),
        text_color=("#1e293b", "#f8fafc"),
        anchor="e",
        command=go_to_settings,
    )
    btn_set.pack(fill=tk.X, padx=12, pady=2)

    edit_account_btn = ctk.CTkButton(
        card,
        text=" ویرایش مشخصات من ",
        image=get_icon("user", white_only=True),
        compound="right",
        font=FONT_NORMAL,
        height=32,
        fg_color="#2563eb",
        hover_color="#1d4ed8",
        text_color="#ffffff",
        anchor="center",
        command=lambda: open_edit_my_account_popup(current_user),
    )
    edit_account_btn.pack(fill=tk.X, padx=14, pady=(6, 12))

    btn_out = ctk.CTkButton(
        card,
        text=" خروج از حساب کاربری ",
        image=get_icon("x", white_only=True),
        compound="right",
        font=FONT_NORMAL,
        height=32,
        fg_color="#dc2626",
        hover_color="#b91c1c",
        text_color="#ffffff",
        anchor="center",
        command=do_logout,
    )
    btn_out.pack(fill=tk.X, padx=14, pady=(6, 12))

    popover.bind("<Escape>", lambda e: close_user_profile_popover())

    def on_popover_focus_out(event):
        try:
            focused = root.focus_get()
            if active_user_popover and active_user_popover.winfo_exists():
                if focused and str(focused).startswith(str(active_user_popover)):
                    return
        except Exception:
            pass
        close_user_profile_popover()

    popover.bind("<FocusOut>", lambda e: root.after(150, lambda ev=e: on_popover_focus_out(ev)))
    popover.focus_force()
    popover.focus_force()


def update_responsive_header():
    global current_header_mode
    if not root.winfo_exists():
        return
    w = root.winfo_width()
    if w >= 1220:
        new_mode = "expanded"
    elif w >= 980:
        new_mode = "compact"
    else:
        new_mode = "minimal"

    if new_mode == current_header_mode and len(active_tabs_data) > 0:
        return
    current_header_mode = new_mode

    if new_mode == "minimal":
        lbl_app_logo.configure(text="کتابخانه")
    else:
        lbl_app_logo.configure(text="کتابخانه باقر العلوم")

    if current_user is not None and btn_user_profile.winfo_exists():
        u_name = str(current_user.get("username", ""))
        u_role = tr(str(current_user.get("role", "")))
        if new_mode == "minimal":
            btn_user_profile.configure(text=f" ▾ {u_name} ", width=100)
        else:
            btn_user_profile.configure(text=f" ▾ {u_name} ({u_role}) ", width=135)

    for tid, data in active_tabs_data.items():
        btn = data.get("button")
        if btn and btn.winfo_exists():
            if new_mode == "expanded":
                btn.configure(text=f" {data['full']} ", font=FONT_NORMAL)
                btn.pack_configure(padx=3)
            elif new_mode == "compact":
                btn.configure(text=f" {data['short']} ", font=FONT_NORMAL)
                btn.pack_configure(padx=2)
            else:
                btn.configure(text=f" {data['short']} ", font=FONT_SMALL)
                btn.pack_configure(padx=1)


def on_root_resize(event):
    global resize_timer_id
    if event.widget == root:
        if resize_timer_id is not None:
            root.after_cancel(resize_timer_id)
        resize_timer_id = root.after(50, update_responsive_header)


root.bind("<Configure>", on_root_resize)


def switch_tab(tab_name: str):
    close_user_profile_popover()
    global current_active_tab
    frames = {
        "login": login_frame,
        "books": books_frame,
        "loans": tabel_frame,
        "members": member_frame,
        "users": auth_users_frame,
        "help": help_frame,
        "settings": settings_frame,
    }
    for k, f in frames.items():
        f.pack_forget()

    if tab_name == "login" and current_user is not None:
        tab_name = "books"

    target = frames.get(tab_name, books_frame)
    target.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
    current_active_tab = tab_name

    for k, btn in nav_buttons.items():
        if k == tab_name:
            btn.configure(fg_color="#1f538d", text_color="#ffffff")
        else:
            btn.configure(fg_color="transparent", text_color=("#334155", "#94a3b8"))


class NavigationManager:
    def select(self, target_frame):
        frames = {
            "login": login_frame,
            "books": books_frame,
            "loans": tabel_frame,
            "members": member_frame,
            "users": auth_users_frame,
            "help": help_frame,
            "settings": settings_frame,
        }
        for k, f in frames.items():
            if f == target_frame:
                switch_tab(k)
                return


notebook = NavigationManager()


def rebuild_tabs():
    close_user_profile_popover()
    for w in nav_bar.winfo_children():
        w.destroy()
    nav_buttons.clear()
    active_tabs_data.clear()

    w_width = root.winfo_width() if root.winfo_width() > 200 else 1080
    is_expanded = w_width >= 1220
    is_minimal = w_width < 980

    if current_user is None:
        btn_user_profile.configure(
            text=" ورود به سامانه ",
            image=get_icon("user-plus"),
            compound="right",
            font=FONT_NORMAL,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            text_color="#ffffff",
            border_width=0,
            width=120,
            command=lambda: switch_tab("login"),
        )
        tabs_config = [
            ("login", "ورود به سامانه", "ورود", "user-plus"),
            ("help", "راهنما", "راهنما", "bookmark"),
        ]
        default_tab = "login"
    else:
        u_role = tr(str(current_user.get("role", "")))
        u_name = str(current_user.get("username", ""))
        profile_btn_text = f" ▾ {u_name} " if is_minimal else f" ▾ {u_name} ({u_role}) "
        profile_btn_width = 105 if is_minimal else 135

        btn_user_profile.configure(
            text=profile_btn_text,
            image=get_icon("user"),
            compound="right",
            font=FONT_NORMAL,
            fg_color=("#e2e8f0", "#1e293b"),
            hover_color=("#cbd5e1", "#334155"),
            text_color=("#0f172a", "#f8fafc"),
            border_width=1,
            border_color=("#cbd5e1", "#334155"),
            width=profile_btn_width,
            command=open_user_profile_popover,
        )

        user_role = str(current_user.get("role", "")).strip().lower()
        tabs_config = [
            ("books", "جستجوی کتاب", "کتاب‌ها", "book-open"),
            ("loans", "جدول امانات", "امانات", "arrow-right-left"),
            ("members", "اعضای کتابخانه", "اعضا", "user-plus"),
        ]
        if user_role in ("super admin", "superadmin", "admin"):
            tabs_config.append(("users", "مدیریت کاربران", "کاربران", "user-plus"))
            try:
                search_users()
            except Exception:
                pass
        tabs_config.extend(
            [
                ("settings", "تنظیمات و اعلان‌ها", "تنظیمات", "filter"),
                ("help", "راهنما", "راهنما", "bookmark"),
            ]
        )
        default_tab = "books"
        try:
            load_settings_into_ui()
            load_notification_logs_ui()
        except Exception:
            pass

    for tab_id, full_lbl, short_lbl, tab_icon in tabs_config:
        disp_text = full_lbl if is_expanded else short_lbl
        btn = ctk.CTkButton(
            nav_bar,
            text=f" {disp_text} ",
            image=get_icon(tab_icon),
            compound="right",
            font=FONT_SMALL if is_minimal else FONT_NORMAL,
            height=34,
            corner_radius=8,
            fg_color="transparent",
            text_color=("#334155", "#94a3b8"),
            hover_color=("#e2e8f0", "#2d3748"),
            command=lambda tid=tab_id: switch_tab(tid),
        )
        px = 1 if is_minimal else (2 if not is_expanded else 3)
        btn.pack(side=tk.RIGHT, padx=px)
        nav_buttons[tab_id] = btn
        active_tabs_data[tab_id] = {
            "button": btn,
            "full": full_lbl,
            "short": short_lbl,
        }

    switch_tab(default_tab)


rebuild_tabs()


def open_edit_my_account_popup(user):
    popup = ctk.CTkToplevel(root)
    popup.title("ویرایش مشخصات حساب کاربری")
    popup.geometry("480x570")
    popup.resizable(False, False)
    if os.path.exists(icon_p):
        try:
            popup.iconbitmap(icon_p)
        except Exception:
            pass

    popup.transient(root)
    popup.grab_set()

    root.update_idletasks()
    rx = root.winfo_rootx()
    ry = root.winfo_rooty()
    rw = root.winfo_width()
    rh = root.winfo_height()
    px = max(50, rx + (rw - 480) // 2)
    py = max(50, ry + (rh - 570) // 2)
    popup.geometry(f"+{px}+{py}")

    # Header
    header_f = ctk.CTkFrame(popup, fg_color="transparent")
    header_f.pack(fill=tk.X, padx=20, pady=(14, 6))
    ctk.CTkLabel(header_f, text="ویرایش مشخصات حساب من", font=FONT_TITLE, anchor="center").pack(fill=tk.X)
    ctk.CTkLabel(
        header_f,
        text="مشاهده شناسه‌های ورود و ویرایش اطلاعات شخصی حساب کاربری",
        font=FONT_SMALL,
        text_color="#94a3b8",
        anchor="center",
    ).pack(fill=tk.X, pady=(2, 0))

    # --- Section 1: Read-only Identity Card ---
    card_id = ctk.CTkFrame(
        popup,
        corner_radius=10,
        border_width=1,
        border_color=("#cbd5e1", "#334155"),
        fg_color=("#f8fafc", "#0f172a"),
    )
    card_id.pack(fill=tk.X, padx=20, pady=(4, 6))

    id_top = ctk.CTkFrame(card_id, fg_color="transparent")
    id_top.pack(fill=tk.X, padx=14, pady=(10, 4))

    ctk.CTkLabel(
        id_top,
        text=" شناسه‌های هویتی حساب ",
        image=get_icon("lock", size=(16, 16)),
        compound="right",
        font=FONT_HEADER,
        text_color=("#1e293b", "#f8fafc"),
        anchor="e",
    ).pack(side=tk.RIGHT)

    badge_frame = ctk.CTkFrame(id_top, fg_color="transparent")
    badge_frame.pack(side=tk.LEFT)

    raw_role = str(user.get("role", "librarian")).strip().lower()
    role_fa = tr(raw_role)
    role_colors = {
        "super admin": ("#064e3b", "#34d399"),
        "superadmin": ("#064e3b", "#34d399"),
        "admin": ("#1e3a8a", "#60a5fa"),
        "librarian": ("#78350f", "#fbbf24"),
    }
    r_bg, r_text = role_colors.get(raw_role, ("#1e293b", "#94a3b8"))

    ctk.CTkLabel(
        badge_frame,
        text=f" نقش: {role_fa} ",
        font=FONT_SMALL,
        fg_color=r_bg,
        text_color=r_text,
        corner_radius=6,
        height=22,
    ).pack(side=tk.LEFT, padx=(0, 4))

    can_edit_creds = is_super_admin(current_user)

    if can_edit_creds:
        ctk.CTkLabel(
            badge_frame,
            text=" قابل ویرایش (مدیر ارشد) ",
            font=FONT_SMALL,
            fg_color=("#dcfce7", "#064e3b"),
            text_color=("#15803d", "#34d399"),
            corner_radius=6,
            height=22,
        ).pack(side=tk.LEFT)

        r_uname = ctk.CTkFrame(card_id, fg_color="transparent")
        r_uname.pack(fill=tk.X, padx=14, pady=3)
        ctk.CTkLabel(r_uname, text="نام کاربری:", font=FONT_NORMAL, width=105, anchor="e").pack(
            side=tk.RIGHT, padx=(4, 0)
        )
        u_name_ent = ctk.CTkEntry(r_uname, font=FONT_NORMAL, justify="right", height=32)
        u_name_ent.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        u_name_ent.insert(0, str(user.get("username") or ""))

        r_phone = ctk.CTkFrame(card_id, fg_color="transparent")
        r_phone.pack(fill=tk.X, padx=14, pady=3)
        ctk.CTkLabel(r_phone, text="شماره همراه:", font=FONT_NORMAL, width=105, anchor="e").pack(
            side=tk.RIGHT, padx=(4, 0)
        )
        u_phone_ent = ctk.CTkEntry(r_phone, font=FONT_NORMAL, justify="right", height=32)
        u_phone_ent.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        u_phone_ent.insert(0, str(user.get("phone_number") or ""))

        note_text = "دسترسی مدیر ارشد فعال است: می‌توانید نام کاربری و شماره تماس را ویرایش نمایید."
    else:
        ctk.CTkLabel(
            badge_frame,
            text=" غیرقابل تغییر ",
            font=FONT_SMALL,
            fg_color=("#e2e8f0", "#1e293b"),
            text_color=("#64748b", "#94a3b8"),
            corner_radius=6,
            height=22,
        ).pack(side=tk.LEFT)

        def add_id_row(parent, label, value, icon_name):
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill=tk.X, padx=14, pady=3)
            ctk.CTkLabel(
                row,
                text=label,
                font=FONT_NORMAL,
                width=105,
                anchor="e",
                text_color=("#64748b", "#94a3b8"),
            ).pack(side=tk.RIGHT, padx=(4, 0))

            val_box = ctk.CTkFrame(row, corner_radius=6, fg_color=("#e2e8f0", "#1e293b"), height=32)
            val_box.pack(side=tk.RIGHT, fill=tk.X, expand=True)
            val_box.pack_propagate(False)

            icon_img = get_icon(icon_name, size=(15, 15)) if icon_name else None
            lbl_val = ctk.CTkLabel(
                val_box,
                text=f"  {value}  ",
                image=icon_img,
                compound="right",
                font=FONT_BOLD,
                text_color=("#0f172a", "#f1f5f9"),
                anchor="e",
            )
            lbl_val.pack(side=tk.RIGHT, padx=10, fill=tk.BOTH, expand=True)

        add_id_row(card_id, "نام کاربری:", str(user.get("username") or "-"), "user")
        add_id_row(card_id, "شماره همراه:", str(user.get("phone_number") or "-"), "phone")
        note_text = "نام کاربری و شماره همراه فقط با دسترسی مدیر ارشد (Super Admin) قابل ویرایش هستند."

    note_row = ctk.CTkFrame(card_id, fg_color="transparent")
    note_row.pack(fill=tk.X, padx=14, pady=(4, 10))

    ctk.CTkLabel(
        note_row,
        text="",
        image=get_icon("info", size=(14, 14)),
        width=18,
    ).pack(side=tk.RIGHT, padx=(4, 0), anchor="ne")

    ctk.CTkLabel(
        note_row,
        text=note_text,
        font=FONT_SMALL,
        text_color=("#64748b", "#94a3b8"),
        anchor="e",
        justify="right",
    ).pack(side=tk.RIGHT, fill=tk.X, expand=True)

    # --- Section 2: Editable Settings Card ---
    card_edit = ctk.CTkFrame(
        popup,
        corner_radius=10,
        border_width=1,
        border_color=("#cbd5e1", "#334155"),
        fg_color=("#ffffff", "#1e293b"),
    )
    card_edit.pack(fill=tk.X, padx=20, pady=(4, 8))

    edit_top = ctk.CTkFrame(card_edit, fg_color="transparent")
    edit_top.pack(fill=tk.X, padx=14, pady=(10, 4))

    ctk.CTkLabel(
        edit_top,
        text=" تنظیمات قابل ویرایش ",
        image=get_icon("key", size=(16, 16)),
        compound="right",
        font=FONT_HEADER,
        text_color=("#1e293b", "#f8fafc"),
        anchor="e",
    ).pack(side=tk.RIGHT)

    # Telegram Chat ID Row
    row_tg = ctk.CTkFrame(card_edit, fg_color="transparent")
    row_tg.pack(fill=tk.X, padx=14, pady=(4, 2))
    ctk.CTkLabel(row_tg, text="شناسه تلگرام:", font=FONT_NORMAL, width=105, anchor="e").pack(side=tk.RIGHT, padx=(4, 0))
    u_tg_ent = ctk.CTkEntry(
        row_tg,
        font=FONT_NORMAL,
        justify="right",
        height=32,
        placeholder_text="مثال: 123456789 (اختیاری)",
    )
    u_tg_ent.pack(side=tk.RIGHT, fill=tk.X, expand=True)
    if user.get("telegram_chat_id"):
        u_tg_ent.insert(0, str(user.get("telegram_chat_id", "")))

    ctk.CTkLabel(
        card_edit,
        text="جهت دریافت کدهای ورود یک‌بارمصرف (OTP) و اعلانات سیستم در تلگرام",
        font=FONT_SMALL,
        text_color=("#64748b", "#94a3b8"),
        anchor="e",
    ).pack(fill=tk.X, padx=14, pady=(0, 6))

    # Password Row with Show/Hide toggle
    row_pwd = ctk.CTkFrame(card_edit, fg_color="transparent")
    row_pwd.pack(fill=tk.X, padx=14, pady=(4, 2))
    ctk.CTkLabel(row_pwd, text="رمز عبور جدید:", font=FONT_NORMAL, width=105, anchor="e").pack(
        side=tk.RIGHT, padx=(4, 0)
    )

    pwd_container = ctk.CTkFrame(row_pwd, fg_color="transparent")
    pwd_container.pack(side=tk.RIGHT, fill=tk.X, expand=True)

    u_pwd_ent = ctk.CTkEntry(
        pwd_container,
        font=FONT_NORMAL,
        justify="right",
        height=32,
        show="*",
        placeholder_text="در صورت عدم نیاز به تغییر خالی بگذارید",
    )
    u_pwd_ent.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0))

    icon_eye = get_icon("eye", size=(16, 16))
    icon_eye_off = get_icon("eye-off", size=(16, 16))

    def toggle_pwd_visibility():
        if u_pwd_ent.cget("show") == "*":
            u_pwd_ent.configure(show="")
            btn_eye.configure(image=icon_eye_off)
        else:
            u_pwd_ent.configure(show="*")
            btn_eye.configure(image=icon_eye)

    btn_eye = ctk.CTkButton(
        pwd_container,
        text="",
        image=icon_eye,
        width=34,
        height=32,
        fg_color=("#e2e8f0", "#334155"),
        hover_color=("#cbd5e1", "#475569"),
        command=toggle_pwd_visibility,
    )
    btn_eye.pack(side=tk.LEFT)

    ctk.CTkLabel(
        card_edit,
        text="حداقل ۴ کاراکتر (در صورت پر شدن، رمز عبور قبلی با مقدار جدید جایگزین می‌شود)",
        font=FONT_SMALL,
        text_color=("#64748b", "#94a3b8"),
        anchor="e",
    ).pack(fill=tk.X, padx=14, pady=(0, 10))

    def do_save_account():
        if can_edit_creds:
            uname = u_name_ent.get().strip()
            phone = u_phone_ent.get().strip()
            if not uname:
                messagebox.showwarning("خطا", "لطفاً نام کاربری را وارد کنید!", parent=popup)
                u_name_ent.focus()
                return
            if not phone:
                messagebox.showwarning("خطا", "لطفاً شماره تلفن را وارد کنید!", parent=popup)
                u_phone_ent.focus()
                return
            norm_phone = normalize_phone_number(phone)
            if len(norm_phone) != 11 or not norm_phone.startswith("09"):
                messagebox.showerror("خطا", "فرمت شماره تلفن نامعتبر است!\nمثال: 09123456789", parent=popup)
                u_phone_ent.focus()
                return
        else:
            uname = str(user.get("username", ""))
            phone = str(user.get("phone_number", ""))
            norm_phone = normalize_phone_number(phone)

        tg = u_tg_ent.get().strip() or None
        pwd = u_pwd_ent.get().strip() or None

        if pwd and len(pwd) < 4:
            messagebox.showwarning("رمز عبور", "رمز عبور جدید باید حداقل ۴ کاراکتر باشد!", parent=popup)
            u_pwd_ent.focus()
            return

        uid = user.get("id")
        if not uid:
            existing = get_user_by_identifier(uname, database_path=db_p)
            if existing:
                uid = existing.get("id")
        if not uid:
            messagebox.showerror("خطا", "شناسه حساب کاربری یافت نشد.", parent=popup)
            return

        success, msg, updated_user = update_user(
            user_id=uid,
            username=uname,
            phone_number=norm_phone,
            password=pwd,
            telegram_chat_id=tg,
            database_path=db_p,
        )

        if success and updated_user:
            global current_user
            current_user = updated_user
            messagebox.showinfo("موفق", msg, parent=popup)
            popup.destroy()
            u_role_str = tr(str(current_user.get("role", "")))
            u_name_str = str(current_user.get("username", ""))
            lbl_user_badge.configure(text=f"{u_name_str} ({u_role_str})")
            show_logged_in_view(current_user)
            if "search_users" in globals():
                try:
                    search_users()
                except Exception:
                    pass
        else:
            messagebox.showerror("خطا", msg, parent=popup)

    # Actions
    btn_f = ctk.CTkFrame(popup, fg_color="transparent")
    btn_f.pack(fill=tk.X, padx=20, pady=(6, 14))

    btn_save = create_icon_button(
        btn_f,
        text=" ذخیره تغییرات ",
        icon_name="check",
        command=do_save_account,
        font=FONT_BOLD,
        fg_color="#16a34a",
        hover_color="#15803d",
        height=34,
        width=135,
    )
    btn_save.pack(side=tk.RIGHT, padx=5)

    btn_cancel = create_icon_button(
        btn_f,
        text=" انصراف ",
        icon_name="x",
        command=popup.destroy,
        font=FONT_NORMAL,
        fg_color="transparent",
        hover_color=("#e2e8f0", "#1e293b"),
        height=34,
        width=90,
    )
    btn_cancel.pack(side=tk.LEFT, padx=5)


def show_logged_in_view(user):
    for widget in login_frame.winfo_children():
        widget.destroy()

    ctk.CTkLabel(login_frame, text="وضعیت حساب کاربری", font=FONT_TITLE).pack(pady=(20, 10))

    info_card = ctk.CTkFrame(login_frame, corner_radius=12, width=480)
    info_card.pack(pady=10, padx=20, fill=tk.X)

    role_val = str(user.get("role", ""))
    role_fa = tr(role_val)

    title_row = ctk.CTkFrame(info_card, fg_color="transparent")
    title_row.pack(fill=tk.X, padx=20, pady=(15, 10))
    ctk.CTkLabel(title_row, text="مشخصات حساب کاربری فعال", font=FONT_HEADER).pack(side=tk.RIGHT)

    ctk.CTkLabel(info_card, text=f"نام کاربری: {user.get('username', '')}", font=FONT_BOLD, anchor="e").pack(
        fill=tk.X, padx=20, pady=4
    )
    ctk.CTkLabel(info_card, text=f"شماره تلفن: {user.get('phone_number', '')}", font=FONT_NORMAL, anchor="e").pack(
        fill=tk.X, padx=20, pady=4
    )
    role_badge = ctk.CTkLabel(
        info_card, text=f"نقش کاربری: {role_fa}", font=FONT_BOLD, text_color="#10b981", anchor="e"
    )
    role_badge.pack(fill=tk.X, padx=20, pady=4)

    if user.get("telegram_chat_id"):
        ctk.CTkLabel(
            info_card, text=f"شناسه چت تلگرام: {user.get('telegram_chat_id')}", font=FONT_NORMAL, anchor="e"
        ).pack(fill=tk.X, padx=20, pady=(4, 15))
    else:
        ctk.CTkLabel(info_card, text="", font=FONT_SMALL).pack(pady=4)

    btn_row = ctk.CTkFrame(login_frame, fg_color="transparent")
    btn_row.pack(pady=20)

    edit_account_btn = create_icon_button(
        btn_row,
        text=" ویرایش مشخصات من ",
        font=FONT_BOLD,
        fg_color="#2563eb",
        hover_color="#1d4ed8",
        height=38,
        command=lambda: open_edit_my_account_popup(user),
    )
    edit_account_btn.pack(side=tk.RIGHT, padx=6)

    logout_btn = create_icon_button(
        btn_row,
        text=" خروج از حساب کاربری ",
        icon_name="x",
        font=FONT_BOLD,
        fg_color="#dc2626",
        hover_color="#b91c1c",
        height=38,
        command=logout,
    )
    logout_btn.pack(side=tk.LEFT, padx=6)


def show_login_view():
    for widget in login_frame.winfo_children():
        widget.destroy()

    ctk.CTkLabel(login_frame, text="ورود به سامانه کتابخانه باقر العلوم", font=FONT_TITLE).pack(pady=(25, 10))

    card = ctk.CTkFrame(login_frame, corner_radius=12, width=440)
    card.pack(pady=10, padx=20)

    card_header = ctk.CTkLabel(card, text=" ورود با رمز یکبار مصرف (OTP) ", font=FONT_HEADER)
    card_header.pack(pady=(16, 10))

    step1_frame = ctk.CTkFrame(card, fg_color="transparent")
    step1_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 16))

    status_lbl = ctk.CTkLabel(
        step1_frame,
        text="شماره تلفن همراه خود را وارد کنید:",
        font=FONT_NORMAL,
        wraplength=380,
        justify="center",
    )
    status_lbl.pack(pady=8)

    phone_entry = ctk.CTkEntry(
        step1_frame,
        placeholder_text="مثال: 09123456789",
        font=FONT_NORMAL,
        justify="center",
        width=260,
        height=36,
    )
    phone_entry.pack(pady=6)
    phone_entry.focus()

    step2_frame = ctk.CTkFrame(card, fg_color="transparent")

    otp_info_lbl = ctk.CTkLabel(
        step2_frame, text="", font=FONT_NORMAL, text_color="#38bdf8", wraplength=380, justify="center"
    )
    otp_info_lbl.pack(pady=6)

    otp_code_lbl = ctk.CTkLabel(step2_frame, text="کد تأیید ۶ رقمی را وارد کنید:", font=FONT_NORMAL)
    otp_code_lbl.pack(pady=4)

    otp_entry = ctk.CTkEntry(
        step2_frame,
        font=ctk.CTkFont(family=FONT_FAMILY, size=16, weight="bold"),
        justify="center",
        width=160,
        height=40,
    )
    otp_entry.pack(pady=6)

    pwd_frame = ctk.CTkFrame(card, fg_color="transparent")
    pwd_status_lbl = ctk.CTkLabel(
        pwd_frame,
        text="شماره تلفن یا نام کاربری و رمز عبور را وارد کنید:",
        font=FONT_NORMAL,
        wraplength=380,
        justify="center",
    )
    pwd_status_lbl.pack(pady=6)

    ctk.CTkLabel(pwd_frame, text="نام کاربری یا شماره تلفن:", font=FONT_NORMAL).pack(pady=2)
    pwd_ident_entry = ctk.CTkEntry(pwd_frame, font=FONT_NORMAL, justify="center", width=260, height=36)
    pwd_ident_entry.pack(pady=4)

    ctk.CTkLabel(pwd_frame, text="رمز عبور:", font=FONT_NORMAL).pack(pady=2)
    pwd_val_entry = ctk.CTkEntry(pwd_frame, font=FONT_NORMAL, justify="center", width=260, height=36, show="*")
    pwd_val_entry.pack(pady=4)

    pending_phone = {"val": ""}

    def switch_to_pwd():
        step1_frame.pack_forget()
        step2_frame.pack_forget()
        card_header.configure(text=" ورود با رمز عبور (آفلاین) ")
        pwd_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 16))
        current_entered = phone_entry.get().strip()
        if current_entered:
            pwd_ident_entry.delete(0, tk.END)
            pwd_ident_entry.insert(0, current_entered)
            pwd_val_entry.focus()
        else:
            pwd_ident_entry.focus()

    def switch_to_otp():
        pwd_frame.pack_forget()
        step2_frame.pack_forget()
        card_header.configure(text=" ورود با رمز یکبار مصرف (OTP) ")
        step1_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 16))
        phone_entry.focus()

    def do_pwd_login(event=None):
        ident = pwd_ident_entry.get().strip()
        pwd = pwd_val_entry.get().strip()
        if not ident or not pwd:
            pwd_status_lbl.configure(text="لطفاً نام کاربری و رمز عبور را وارد کنید!", text_color="#ef4444")
            return
        success, msg, u = authenticate(ident, pwd, mode="password", database_path=db_p)
        if success and u:
            on_login_success(u)
        else:
            pwd_status_lbl.configure(text=msg or "اطلاعات ورود نادرست است.", text_color="#ef4444")

    def reset_to_step1():
        step2_frame.pack_forget()
        pwd_frame.pack_forget()
        card_header.configure(text=" ورود با رمز یکبار مصرف (OTP) ")
        step1_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 16))
        status_lbl.configure(text="شماره تلفن همراه خود را وارد کنید:", text_color=("#1f2937", "#f8fafc"))
        phone_entry.delete(0, tk.END)
        phone_entry.insert(0, pending_phone["val"])
        phone_entry.focus()

    def do_request_otp(event=None):
        raw_phone = phone_entry.get().strip()
        norm_phone = normalize_phone_number(raw_phone)
        if len(norm_phone) != 11 or not norm_phone.startswith("09"):
            status_lbl.configure(text="شماره تلفن نامعتبر است! مثال: 09123456789", text_color="#ef4444")
            phone_entry.focus()
            return

        u = get_user_by_identifier(norm_phone, database_path=db_p)
        if not u:
            status_lbl.configure(text="کاربری با این شماره تلفن یافت نشد.", text_color="#ef4444")
            messagebox.showerror("خطا", "کاربری با این شماره تلفن در سامانه یافت نشد.", parent=root)
            return

        otp_s = OTPService(database_path=db_p)
        req_res = otp_s.request_otp(norm_phone)
        if req_res[0]:
            pending_phone["val"] = norm_phone
            step1_frame.pack_forget()
            step2_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 16))
            otp_info_lbl.configure(text=f"کد تأیید به شماره {mask_phone_number(norm_phone)} ارسال شد.")
            otp_entry.delete(0, tk.END)
            otp_entry.focus()
        else:
            status_lbl.configure(text=f"خطا در ارسال کد:\n{req_res[1]}", text_color="#ef4444")
            btn_fallback_pwd.configure(text_color="#ef4444")

    def do_verify_otp(event=None):
        code = otp_entry.get().strip()
        if len(code) != 6 or not code.isdigit():
            otp_code_lbl.configure(text="کد OTP باید ۶ رقم عددی باشد.", text_color="#ef4444")
            otp_entry.focus()
            return

        target_phone = pending_phone["val"]
        otp_s = OTPService(database_path=db_p)
        verify_res = otp_s.verify_otp(target_phone, code)
        if verify_res[0]:
            u = get_user_by_identifier(target_phone, database_path=db_p)
            on_login_success(u)
        else:
            otp_code_lbl.configure(text=f"کد اشتباه یا منقضی است: {verify_res[1]}", text_color="#ef4444")
            otp_entry.focus()

    btn_req_otp = create_icon_button(
        step1_frame,
        text=" درخواست کد OTP ",
        icon_name="arrow-right-left",
        font=FONT_BOLD,
        width=220,
        height=36,
        command=do_request_otp,
    )
    btn_req_otp.pack(pady=(10, 4))

    btn_fallback_pwd = create_icon_button(
        step1_frame,
        text=" ورود با رمز عبور (آفلاین) ",
        font=FONT_NORMAL,
        fg_color="transparent",
        text_color=("#2563eb", "#38bdf8"),
        hover_color=("#e2e8f0", "#1e293b"),
        height=32,
        command=switch_to_pwd,
    )
    btn_fallback_pwd.pack(pady=4)

    btn_verify = create_icon_button(
        step2_frame,
        text=" تأیید و ورود ",
        icon_name="check",
        font=FONT_BOLD,
        width=200,
        height=36,
        command=do_verify_otp,
    )
    btn_verify.pack(pady=8)

    btn_back = create_icon_button(
        step2_frame,
        text=" تغییر شماره / ارسال مجدد ",
        icon_name="rotate-ccw",
        font=FONT_NORMAL,
        fg_color="transparent",
        hover_color=("#e2e8f0", "#1e293b"),
        height=32,
        command=reset_to_step1,
    )
    btn_back.pack(pady=3)

    btn_step2_pwd = create_icon_button(
        step2_frame,
        text=" ورود با رمز عبور آفلاین ",
        font=FONT_NORMAL,
        fg_color="transparent",
        text_color=("#2563eb", "#38bdf8"),
        hover_color=("#e2e8f0", "#1e293b"),
        height=32,
        command=switch_to_pwd,
    )
    btn_step2_pwd.pack(pady=3)

    btn_do_pwd = create_icon_button(
        pwd_frame,
        text=" ورود به سامانه ",
        icon_name="check",
        font=FONT_BOLD,
        width=200,
        height=36,
        command=do_pwd_login,
    )
    btn_do_pwd.pack(pady=8)

    btn_back_to_otp = create_icon_button(
        pwd_frame,
        text=" بازگشت به ورود با پیامک/تلگرام (OTP) ",
        icon_name="arrow-right-left",
        font=FONT_NORMAL,
        fg_color="transparent",
        text_color=("#2563eb", "#38bdf8"),
        hover_color=("#e2e8f0", "#1e293b"),
        height=32,
        command=switch_to_otp,
    )
    btn_back_to_otp.pack(pady=4)

    phone_entry.bind("<Return>", do_request_otp)
    otp_entry.bind("<Return>", do_verify_otp)
    pwd_val_entry.bind("<Return>", do_pwd_login)
    pwd_ident_entry.bind("<Return>", lambda e: pwd_val_entry.focus())


def on_login_success(user):
    global current_user
    current_user = user

    show_logged_in_view(user)
    rebuild_tabs()

    search()
    search_members()
    refresh_loans_table()


def logout():
    global current_user
    current_user = None

    rebuild_tabs()
    show_login_view()


search_bar_frame = ctk.CTkFrame(books_frame, corner_radius=8, height=48)
search_bar_frame.pack(fill=tk.X, padx=10, pady=(10, 6))
search_bar_frame.columnconfigure(5, weight=1)

sub_btn = create_icon_button(search_bar_frame, text=" جستجو ", icon_name="search", font=FONT_BOLD, width=80)
sub_btn.grid(row=0, column=0, padx=(8, 4), pady=6)

filter_btn = create_icon_button(search_bar_frame, text=" فیلترها ", icon_name="filter", font=FONT_NORMAL, width=85)
filter_btn.grid(row=0, column=1, padx=4, pady=6)

reclassify_all_btn = create_icon_button(
    search_bar_frame,
    text=" رده‌بندی دسته‌ای ",
    icon_name="layers",
    font=FONT_NORMAL,
    width=115,
)
reclassify_all_btn.grid(row=0, column=2, padx=4, pady=6)

edit_book_btn = create_icon_button(
    search_bar_frame,
    text=" ویرایش کتاب ",
    icon_name="pencil",
    font=FONT_NORMAL,
    width=95,
)
edit_book_btn.grid(row=0, column=3, padx=4, pady=6)

add_book_btn = create_icon_button(
    search_bar_frame,
    text=" افزودن کتاب ",
    icon_name="book-plus",
    font=FONT_NORMAL,
    fg_color="#16a34a",
    hover_color="#15803d",
    width=105,
)
add_book_btn.grid(row=0, column=4, padx=4, pady=6)

entry_serch = ctk.CTkEntry(
    search_bar_frame,
    placeholder_text="جستجو در بین کتاب‌ها (عنوان، نویسنده، شابک، کد دیویی و ...)",
    font=FONT_NORMAL,
    justify="right",
    height=36,
)
entry_serch.grid(row=0, column=5, sticky="ew", padx=(4, 8), pady=6)

tree_frame = ctk.CTkFrame(books_frame, corner_radius=8)
tree_frame.pack(padx=10, pady=(0, 10), fill=tk.BOTH, expand=True)

scrollbar = ctk.CTkScrollbar(tree_frame)
scrollbar.pack(side=tk.LEFT, fill=tk.Y, padx=(4, 0), pady=4)

tree = ttk.Treeview(tree_frame, yscrollcommand=scrollbar.set, columns=columns, show="headings", height=15)
scrollbar.configure(command=tree.yview)
for col in columns:
    tree.heading(col, text=tr(col), anchor=tk.CENTER)
    tree.column(col, anchor=tk.CENTER)

visible_book_cols = [c for c in ["id", "title", "author", "dewey_code", "dewey_subject", "isbn"] if c in columns]
tree["displaycolumns"] = list(reversed(visible_book_cols))

if "id" in columns:
    tree.column("id", width=55, minwidth=40, anchor=tk.CENTER)
if "title" in columns:
    tree.column("title", width=230, minwidth=130, anchor=tk.E)
if "author" in columns:
    tree.column("author", width=140, minwidth=90, anchor=tk.E)
if "dewey_code" in columns:
    tree.column("dewey_code", width=85, minwidth=65, anchor=tk.CENTER)
if "dewey_subject" in columns:
    tree.column("dewey_subject", width=140, minwidth=90, anchor=tk.E)
if "isbn" in columns:
    tree.column("isbn", width=125, minwidth=85, anchor=tk.CENTER)

tree.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(4, 8), pady=4)


def update_filter_button_indicator():
    is_custom = (
        filter_settings["column"] != "all"
        or filter_settings["match_mode"] != "contains"
        or filter_settings["availability"] != "all"
        or filter_settings.get("dewey_class", "all") != "all"
        or filter_settings["sort_col"] != "id"
        or filter_settings["sort_dir"] != "ASC"
    )
    if is_custom:
        filter_btn.configure(text=" فیلترها (فعال) ", fg_color="#2563eb")
    else:
        filter_btn.configure(text=" فیلترها ", fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"])


def search(event=None):
    search_value = entry_serch.get().strip()

    tree.delete(*tree.get_children())

    temp_conn = get_db_connection(db_p)
    try:
        temp_cursor = temp_conn.cursor()

        where_conditions: list[str] = []
        params: list[str] = []

        if search_value:
            selected_col = filter_settings.get("column", "all")
            match_mode = filter_settings.get("match_mode", "contains")

            if match_mode == "exact":
                pattern = search_value
                op = "="
            elif match_mode == "startswith":
                pattern = f"{search_value}%"
                op = "LIKE"
            else:
                pattern = f"%{search_value}%"
                op = "LIKE"

            if selected_col == "all":
                searchable_cols = [
                    c for c in columns if c in ["title", "author", "isbn", "dewey_code", "dewey_subject", "id"]
                ]
                sub_conds = [f"{col} {op} ?" for col in searchable_cols]
                where_conditions.append("(" + " OR ".join(sub_conds) + ")")
                params.extend([pattern] * len(searchable_cols))
            elif selected_col in columns:
                where_conditions.append(f"{selected_col} {op} ?")
                params.append(pattern)

        dewey_cls = filter_settings.get("dewey_class", "all")
        if dewey_cls != "all":
            cls_digit = str(dewey_cls).strip()[:1]
            where_conditions.append("(SUBSTR(COALESCE(dewey_code, ''), 1, 1) = ?)")
            params.append(cls_digit)

        avail = filter_settings.get("availability", "all")
        if avail == "borrowed":
            where_conditions.append("title IN (SELECT book_id FROM loans WHERE borrowed = 1 OR borrowed = '1')")
        elif avail == "available":
            where_conditions.append("title NOT IN (SELECT book_id FROM loans WHERE borrowed = 1 OR borrowed = '1')")

        query = f"SELECT {', '.join(columns)} FROM {tabel_name}"
        if where_conditions:
            query += " WHERE " + " AND ".join(where_conditions)

        sort_col = filter_settings.get("sort_col", "id")
        if sort_col not in columns:
            sort_col = "id"
        sort_dir = filter_settings.get("sort_dir", "ASC")
        if sort_dir not in ("ASC", "DESC"):
            sort_dir = "ASC"

        if sort_col in ("dewey_code",):
            query += f" ORDER BY {sort_col} COLLATE dewey {sort_dir}"
        else:
            query += f" ORDER BY {sort_col} {sort_dir}"

        temp_cursor.execute(query, tuple(params))
        results = temp_cursor.fetchall()

        if results:
            for row in results:
                tree.insert("", "end", values=tuple(row))
        else:
            tree.insert("", "end", values=("❌ نتیجه‌ای یافت نشد!",) + ("",) * (len(columns) - 1))

    except Exception as e:
        messagebox.showerror("خطا", f"خطا در جستجو: {str(e)}")
    finally:
        temp_conn.close()


sub_btn.configure(command=search)


def open_filter_popup():
    popup = ctk.CTkToplevel(root)
    popup.title("فیلترهای پیشرفته جستجو")
    popup.geometry("500x570")
    popup.resizable(False, False)
    if os.path.exists(icon_p):
        try:
            popup.iconbitmap(icon_p)
        except Exception:
            pass

    popup.transient(root)
    popup.grab_set()

    root.update_idletasks()
    rx = root.winfo_rootx()
    ry = root.winfo_rooty()
    rw = root.winfo_width()
    rh = root.winfo_height()
    px = max(50, rx + (rw - 500) // 2)
    py = max(50, ry + (rh - 570) // 2)
    popup.geometry(f"+{px}+{py}")

    col_var = tk.StringVar(value=filter_settings["column"])
    match_var = tk.StringVar(value=filter_settings["match_mode"])
    avail_var = tk.StringVar(value=filter_settings["availability"])
    dewey_cls_var = tk.StringVar(value=filter_settings.get("dewey_class", "all"))
    sort_col_var = tk.StringVar(value=filter_settings["sort_col"])
    sort_dir_var = tk.StringVar(value=filter_settings["sort_dir"])

    group_col = ctk.CTkFrame(popup, corner_radius=8)
    group_col.pack(fill=tk.X, padx=15, pady=(10, 4))
    ctk.CTkLabel(group_col, text="جستجو در ستون", font=FONT_BOLD, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))

    col_frame_1 = ctk.CTkFrame(group_col, fg_color="transparent")
    col_frame_1.pack(fill=tk.X, padx=6, pady=(0, 2))
    row1_cols = [("همه ستون‌ها", "all"), ("عنوان کتاب", "title"), ("نویسنده", "author"), ("شابک", "isbn")]
    for text_fa, val in row1_cols:
        if val == "all" or val in columns:
            rb = ctk.CTkRadioButton(col_frame_1, text=text_fa, variable=col_var, value=val, font=FONT_NORMAL)
            rb.pack(side=tk.RIGHT, padx=6)

    col_frame_2 = ctk.CTkFrame(group_col, fg_color="transparent")
    col_frame_2.pack(fill=tk.X, padx=6, pady=(0, 6))
    row2_cols = [("کد دیویی", "dewey_code"), ("موضوع دیویی", "dewey_subject"), ("شناسه", "id")]
    for text_fa, val in row2_cols:
        if val in columns:
            rb = ctk.CTkRadioButton(col_frame_2, text=text_fa, variable=col_var, value=val, font=FONT_NORMAL)
            rb.pack(side=tk.RIGHT, padx=6)

    group_dewey = ctk.CTkFrame(popup, corner_radius=8)
    group_dewey.pack(fill=tk.X, padx=15, pady=4)
    ctk.CTkLabel(group_dewey, text="فیلتر موضوعی دیویی", font=FONT_BOLD, anchor="e").pack(
        fill=tk.X, padx=10, pady=(6, 2)
    )
    dewey_opts = [
        ("همه موضوعات", "all"),
        ("۰۰۰ - کلیات و علوم کامپیوتر", "000"),
        ("۱۰۰ - فلسفه و روان‌شناسی", "100"),
        ("۲۰۰ - دین و الهیات", "200"),
        ("۳۰۰ - علوم اجتماعی", "300"),
        ("۴۰۰ - زبان و زبان‌شناسی", "400"),
        ("۵۰۰ - علوم محض و طبیعی", "500"),
        ("۶۰۰ - فناوری و مهندسی", "600"),
        ("۷۰۰ - هنر و سرگرمی", "700"),
        ("۸۰۰ - ادبیات", "800"),
        ("۹۰۰ - تاریخ و جغرافیا", "900"),
    ]
    dewey_cb = ctk.CTkOptionMenu(
        group_dewey,
        font=FONT_NORMAL,
        values=[opt[0] for opt in dewey_opts],
    )
    cur_d_val = next((opt[0] for opt in dewey_opts if opt[1] == dewey_cls_var.get()), "همه موضوعات")
    dewey_cb.set(cur_d_val)
    dewey_cb.pack(fill=tk.X, padx=10, pady=(0, 6))

    group_mode = ctk.CTkFrame(popup, corner_radius=8)
    group_mode.pack(fill=tk.X, padx=15, pady=4)
    ctk.CTkLabel(group_mode, text="نوع تطابق جستجو", font=FONT_BOLD, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))
    mode_frame = ctk.CTkFrame(group_mode, fg_color="transparent")
    mode_frame.pack(fill=tk.X, padx=6, pady=(0, 6))
    rb_contains = ctk.CTkRadioButton(
        mode_frame, text="شامل عبارت", variable=match_var, value="contains", font=FONT_NORMAL
    )
    rb_contains.pack(side=tk.RIGHT, padx=8)
    rb_starts = ctk.CTkRadioButton(
        mode_frame, text="شروع با عبارت", variable=match_var, value="startswith", font=FONT_NORMAL
    )
    rb_starts.pack(side=tk.RIGHT, padx=8)
    rb_exact = ctk.CTkRadioButton(mode_frame, text="مطابقت دقیق", variable=match_var, value="exact", font=FONT_NORMAL)
    rb_exact.pack(side=tk.RIGHT, padx=8)

    group_avail = ctk.CTkFrame(popup, corner_radius=8)
    group_avail.pack(fill=tk.X, padx=15, pady=4)
    ctk.CTkLabel(group_avail, text="وضعیت امانت کتاب", font=FONT_BOLD, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))
    avail_frame = ctk.CTkFrame(group_avail, fg_color="transparent")
    avail_frame.pack(fill=tk.X, padx=6, pady=(0, 6))
    rb_av_all = ctk.CTkRadioButton(avail_frame, text="همه کتاب‌ها", variable=avail_var, value="all", font=FONT_NORMAL)
    rb_av_all.pack(side=tk.RIGHT, padx=6)
    rb_av_avail = ctk.CTkRadioButton(
        avail_frame, text="فقط موجود", variable=avail_var, value="available", font=FONT_NORMAL
    )
    rb_av_avail.pack(side=tk.RIGHT, padx=6)
    rb_av_borrowed = ctk.CTkRadioButton(
        avail_frame, text="فقط در امانت", variable=avail_var, value="borrowed", font=FONT_NORMAL
    )
    rb_av_borrowed.pack(side=tk.RIGHT, padx=6)

    group_sort = ctk.CTkFrame(popup, corner_radius=8)
    group_sort.pack(fill=tk.X, padx=15, pady=4)
    ctk.CTkLabel(group_sort, text="مرتب‌سازی نتایج", font=FONT_BOLD, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))
    sort_frame = ctk.CTkFrame(group_sort, fg_color="transparent")
    sort_frame.pack(fill=tk.X, padx=6, pady=(0, 6))

    ctk.CTkLabel(sort_frame, text="بر اساس:", font=FONT_NORMAL).pack(side=tk.RIGHT, padx=(5, 0))
    sort_cols_available = [c for c in ["title", "author", "dewey_code", "id"] if c in columns]
    sort_col_cb = ctk.CTkOptionMenu(
        sort_frame,
        width=135,
        font=FONT_NORMAL,
        values=[tr(c) for c in sort_cols_available],
    )
    sort_col_cb.set(tr(sort_col_var.get()))
    sort_col_cb.pack(side=tk.RIGHT, padx=5)

    ctk.CTkLabel(sort_frame, text="ترتیب:", font=FONT_NORMAL).pack(side=tk.RIGHT, padx=(12, 0))
    sort_dir_cb = ctk.CTkOptionMenu(sort_frame, width=105, font=FONT_NORMAL, values=["صعودی", "نزولی"])
    sort_dir_cb.set("صعودی" if sort_dir_var.get() == "ASC" else "نزولی")
    sort_dir_cb.pack(side=tk.RIGHT, padx=5)

    action_frame = ctk.CTkFrame(popup, fg_color="transparent")
    action_frame.pack(fill=tk.X, padx=15, pady=(12, 8))

    def apply_filters():
        filter_settings["column"] = col_var.get()
        filter_settings["match_mode"] = match_var.get()
        filter_settings["availability"] = avail_var.get()

        disp_dewey = dewey_cb.get()
        dewey_map = {opt[0]: opt[1] for opt in dewey_opts}
        filter_settings["dewey_class"] = dewey_map.get(disp_dewey, "all")

        disp_col = sort_col_cb.get()
        disp_map = {tr(c): c for c in columns}
        filter_settings["sort_col"] = disp_map.get(disp_col, "id")
        filter_settings["sort_dir"] = "ASC" if sort_dir_cb.get() == "صعودی" else "DESC"

        update_filter_button_indicator()
        popup.destroy()
        search()

    def reset_filters():
        filter_settings["column"] = "all"
        filter_settings["match_mode"] = "contains"
        filter_settings["availability"] = "all"
        filter_settings["dewey_class"] = "all"
        filter_settings["sort_col"] = "id"
        filter_settings["sort_dir"] = "ASC"

        update_filter_button_indicator()
        popup.destroy()
        search()

    btn_apply = create_icon_button(
        action_frame,
        text=" اعمال فیلتر ",
        icon_name="check",
        font=FONT_BOLD,
        fg_color="#2563eb",
        hover_color="#1d4ed8",
        command=apply_filters,
    )
    btn_apply.pack(side=tk.RIGHT, padx=4)

    btn_reset = create_icon_button(
        action_frame,
        text=" تنظیم مجدد ",
        icon_name="rotate-ccw",
        font=FONT_NORMAL,
        fg_color="transparent",
        hover_color=("#e2e8f0", "#1e293b"),
        command=reset_filters,
    )
    btn_reset.pack(side=tk.RIGHT, padx=4)

    btn_cancel = create_icon_button(
        action_frame,
        text=" انصراف ",
        icon_name="x",
        font=FONT_NORMAL,
        fg_color="transparent",
        hover_color=("#e2e8f0", "#1e293b"),
        command=popup.destroy,
    )
    btn_cancel.pack(side=tk.LEFT, padx=4)


filter_btn.configure(command=open_filter_popup)


def open_add_book_popup():
    popup = ctk.CTkToplevel(root)
    popup.title("ثبت کتاب جدید و رده‌بندی دیویی")
    popup.geometry("500x485")
    popup.resizable(False, False)
    if os.path.exists(icon_p):
        try:
            popup.iconbitmap(icon_p)
        except Exception:
            pass

    popup.transient(root)
    popup.grab_set()

    root.update_idletasks()
    rx = root.winfo_rootx()
    ry = root.winfo_rooty()
    rw = root.winfo_width()
    rh = root.winfo_height()
    px = max(50, rx + (rw - 500) // 2)
    py = max(50, ry + (rh - 485) // 2)
    popup.geometry(f"+{px}+{py}")

    ctk.CTkLabel(popup, text="ثبت کتاب جدید و رده‌بندی دیویی", font=FONT_TITLE).pack(pady=(12, 8))

    form_f = ctk.CTkFrame(popup, fg_color="transparent")
    form_f.pack(fill=tk.BOTH, expand=True, padx=20, pady=0)

    # ISBN row with online lookup button
    row_isbn = ctk.CTkFrame(form_f, fg_color="transparent")
    row_isbn.pack(fill=tk.X, pady=4)
    ctk.CTkLabel(row_isbn, text="شابک:", font=FONT_NORMAL, width=105, anchor="e").pack(side=tk.RIGHT, padx=(5, 0))
    btn_lookup_isbn = create_icon_button(
        row_isbn,
        text=" استعلام آنلاین ",
        icon_name="search",
        font=FONT_SMALL,
        width=105,
        height=32,
        fg_color="#2563eb",
        hover_color="#1d4ed8",
    )
    btn_lookup_isbn.pack(side=tk.LEFT, padx=(5, 0))
    ent_isbn = ctk.CTkEntry(
        row_isbn, font=FONT_NORMAL, justify="right", height=32, placeholder_text="شابک ۱۰ یا ۱۳ رقمی"
    )
    ent_isbn.pack(side=tk.RIGHT, fill=tk.X, expand=True)

    # Title row
    row_title = ctk.CTkFrame(form_f, fg_color="transparent")
    row_title.pack(fill=tk.X, pady=4)
    ctk.CTkLabel(row_title, text="عنوان کتاب:", font=FONT_BOLD, width=105, anchor="e").pack(side=tk.RIGHT, padx=(5, 0))
    ent_title = ctk.CTkEntry(
        row_title, font=FONT_NORMAL, justify="right", height=32, placeholder_text="عنوان کتاب (الزامی)"
    )
    ent_title.pack(side=tk.RIGHT, fill=tk.X, expand=True)

    # Author row
    row_author = ctk.CTkFrame(form_f, fg_color="transparent")
    row_author.pack(fill=tk.X, pady=4)
    ctk.CTkLabel(row_author, text="نویسنده:", font=FONT_NORMAL, width=105, anchor="e").pack(side=tk.RIGHT, padx=(5, 0))
    ent_author = ctk.CTkEntry(
        row_author, font=FONT_NORMAL, justify="right", height=32, placeholder_text="نام نویسنده / پدیدآورنده"
    )
    ent_author.pack(side=tk.RIGHT, fill=tk.X, expand=True)

    # Auto classify button (shown only if system has internet access)
    row_ai = ctk.CTkFrame(form_f, fg_color="transparent")
    btn_auto_ddc = create_icon_button(
        row_ai,
        text=" پیشنهاد هوشمند رده دیویی با هوش مصنوعی ",
        icon_name="zap",
        font=FONT_NORMAL,
        height=30,
        fg_color="#0284c7",
        hover_color="#0369a1",
    )
    btn_auto_ddc.pack(fill=tk.X)

    # Dewey Code row
    row_dewey = ctk.CTkFrame(form_f, fg_color="transparent")
    row_dewey.pack(fill=tk.X, pady=4)
    ctk.CTkLabel(row_dewey, text="کد دیویی:", font=FONT_NORMAL, width=105, anchor="e").pack(side=tk.RIGHT, padx=(5, 0))
    ent_dewey = ctk.CTkEntry(
        row_dewey, font=FONT_NORMAL, justify="center", height=32, placeholder_text="مانند: 510 یا 641.5"
    )
    ent_dewey.pack(side=tk.RIGHT, fill=tk.X, expand=True)

    # Dewey Subject row
    row_subject = ctk.CTkFrame(form_f, fg_color="transparent")
    row_subject.pack(fill=tk.X, pady=4)
    ctk.CTkLabel(row_subject, text="موضوع دیویی:", font=FONT_NORMAL, width=105, anchor="e").pack(
        side=tk.RIGHT, padx=(5, 0)
    )
    ent_subject = ctk.CTkEntry(
        row_subject, font=FONT_NORMAL, justify="right", height=32, placeholder_text="موضوع رده (مانند ریاضیات، فیزیک)"
    )
    ent_subject.pack(side=tk.RIGHT, fill=tk.X, expand=True)

    # Shelf location preview card
    shelf_card = ctk.CTkFrame(form_f, corner_radius=6, fg_color=("#f1f5f9", "#1e293b"))
    shelf_card.pack(fill=tk.X, pady=(5, 3), padx=2)
    shelf_lbl = ctk.CTkLabel(
        shelf_card,
        text="محل قفسه: تعیین نشده",
        font=FONT_SMALL,
        text_color=("#475569", "#94a3b8"),
        anchor="e",
    )
    shelf_lbl.pack(fill=tk.X, padx=10, pady=5)

    status_lbl = ctk.CTkLabel(form_f, text="", font=FONT_SMALL, anchor="center")
    status_lbl.pack(fill=tk.X, pady=(1, 3))

    classification_meta = {"source": None, "confidence": 0.0}

    # Show AI classification button if AI features are enabled and internet was verified at boot time
    if is_ai_available():
        row_ai.pack(fill=tk.X, pady=(3, 5), before=row_dewey)

    def update_shelf_preview(*args):
        code = ent_dewey.get().strip()
        if code and is_valid_dewey(code):
            loc = dewey_service.get_shelf_location(code)
            shelf_lbl.configure(text=f"📍 {loc.get('shelf_label')}")
        else:
            shelf_lbl.configure(text="محل قفسه: تعیین نشده")

    ent_dewey.bind("<KeyRelease>", update_shelf_preview)

    def on_user_dewey_edit(event):
        classification_meta["source"] = "manual"
        classification_meta["confidence"] = 1.0

    ent_dewey.bind("<Key>", on_user_dewey_edit)
    ent_subject.bind("<Key>", on_user_dewey_edit)

    def do_isbn_lookup():
        if not is_internet_access_enabled(db_p):
            messagebox.showwarning(
                "دسترسی به اینترنت", "دسترسی به اینترنت در تنظیمات برنامه غیرفعال شده است.", parent=popup
            )
            return
        raw_isbn = ent_isbn.get().strip()
        if not raw_isbn:
            messagebox.showwarning("شابک", "لطفاً ابتدا مقدار شابک را وارد نمایید!", parent=popup)
            ent_isbn.focus()
            return
        status_lbl.configure(text="در حال استعلام اطلاعات شابک...", text_color="#3b82f6")
        popup.update()

        def _fetch_thread():
            try:
                res = book_service.lookup_isbn_and_classify(raw_isbn)

                def _apply():
                    if res.get("title"):
                        ent_title.delete(0, tk.END)
                        ent_title.insert(0, res["title"])
                    if res.get("author"):
                        ent_author.delete(0, tk.END)
                        ent_author.insert(0, res["author"])
                    if res.get("dewey_code"):
                        ent_dewey.delete(0, tk.END)
                        ent_dewey.insert(0, res["dewey_code"])
                    if res.get("dewey_subject"):
                        ent_subject.delete(0, tk.END)
                        ent_subject.insert(0, res["dewey_subject"])
                    classification_meta["source"] = res.get("dewey_source", "api")
                    classification_meta["confidence"] = res.get("dewey_confidence", 0.95)
                    update_shelf_preview()
                    if res.get("title"):
                        status_lbl.configure(
                            text=f"اطلاعات کتاب دریافت شد (رده: {res.get('dewey_code') or 'نامشخص'})",
                            text_color="#16a34a",
                        )
                    else:
                        status_lbl.configure(
                            text="اطلاعات آنلاین برای این شابک یافت نشد. می‌توانید اطلاعات را دستی وارد کنید.",
                            text_color="#d97706",
                        )

                popup.after(0, _apply)
            except Exception as ex:
                err_text = str(ex)
                popup.after(
                    0, lambda msg=err_text: status_lbl.configure(text=f"خطا در استعلام: {msg}", text_color="#ef4444")
                )

        threading.Thread(target=_fetch_thread, daemon=True).start()

    btn_lookup_isbn.configure(command=do_isbn_lookup)

    def do_auto_classify_title():
        if not is_ai_available():
            messagebox.showwarning(
                "هوش مصنوعی",
                "قابلیت‌های هوش مصنوعی یا دسترسی به اینترنت در تنظیمات برنامه غیرفعال است.",
                parent=popup,
            )
            return
        t = ent_title.get().strip()
        a = ent_author.get().strip()
        if not t:
            messagebox.showwarning("خطا", "لطفاً ابتدا عنوان کتاب را وارد کنید!", parent=popup)
            ent_title.focus()
            return
        status_lbl.configure(text="در حال استعلام رده دیویی با هوش مصنوعی...", text_color="#38bdf8")
        popup.update()

        def _worker():
            try:
                c_res = book_service.dewey_service.detect_with_ai(title=t, author=a if a else None)

                def _apply():
                    if c_res and c_res.dewey_code:
                        ent_dewey.delete(0, tk.END)
                        ent_dewey.insert(0, c_res.dewey_code)
                        ent_subject.delete(0, tk.END)
                        ent_subject.insert(0, c_res.dewey_subject or "")
                        classification_meta["source"] = c_res.dewey_source
                        classification_meta["confidence"] = c_res.dewey_confidence
                        update_shelf_preview()
                        status_lbl.configure(
                            text=f"رده پیشنهادی (هوش مصنوعی): {c_res.dewey_code} - {c_res.dewey_subject} ({int(c_res.dewey_confidence * 100)} درصد اطمینان)",
                            text_color="#16a34a",
                        )
                    else:
                        status_lbl.configure(text="رده قطعی بر اساس عنوان یافت نشد.", text_color="#d97706")

                popup.after(0, _apply)
            except Exception as ex:
                err_msg = str(ex)
                popup.after(
                    0, lambda msg=err_msg: status_lbl.configure(text=f"خطا در هوش مصنوعی: {msg}", text_color="#ef4444")
                )

        threading.Thread(target=_worker, daemon=True).start()

    btn_auto_ddc.configure(command=do_auto_classify_title)

    def do_insert_book():
        t = ent_title.get().strip()
        if not t:
            messagebox.showwarning("خطا", "لطفاً عنوان کتاب را وارد کنید!", parent=popup)
            ent_title.focus()
            return
        a = ent_author.get().strip() or None
        i = ent_isbn.get().strip() or None
        d = ent_dewey.get().strip() or None
        s = ent_subject.get().strip() or None

        if d and not is_valid_dewey(d):
            messagebox.showerror(
                "کد دیویی نامعتبر",
                "کد دیویی وارد شده معتبر نیست. کد باید عددی بین 000 تا 999 با اعشار اختیاری باشد.",
                parent=popup,
            )
            ent_dewey.focus()
            return

        try:
            source = classification_meta["source"] or ("manual" if d else None)
            book_service.register_book(
                title=t,
                author=a,
                isbn=i,
                dewey_code=d,
                dewey_subject=s,
                dewey_source=source,
                auto_classify=True,
                conn_or_path=db_p,
            )
            messagebox.showinfo("موفق", "اطلاعات کتاب و رده‌بندی دیویی با موفقیت ثبت شد!", parent=popup)
            popup.destroy()
            search()
        except sqlite3.IntegrityError:
            messagebox.showerror("خطا", "این کتاب (شابک تکراری) قبلاً ثبت شده است!", parent=popup)
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در ثبت کتاب: {e}", parent=popup)

    btn_f = ctk.CTkFrame(popup, fg_color="transparent")
    btn_f.pack(pady=(4, 14), padx=20, fill=tk.X)
    btn_save = create_icon_button(
        btn_f,
        text=" ثبت اطلاعات کتاب ",
        icon_name="check",
        command=do_insert_book,
        font=FONT_BOLD,
        fg_color="#16a34a",
        hover_color="#15803d",
        width=135,
    )
    btn_save.pack(side=tk.RIGHT, padx=5)
    btn_cancel = create_icon_button(
        btn_f,
        text=" انصراف ",
        icon_name="x",
        command=popup.destroy,
        font=FONT_NORMAL,
        fg_color="transparent",
        hover_color=("#e2e8f0", "#1e293b"),
        width=90,
    )
    btn_cancel.pack(side=tk.LEFT, padx=5)


def open_edit_book_popup(book_id: int | None = None):
    if book_id is None:
        selected = tree.selection()
        if not selected:
            messagebox.showinfo("راهنما", "لطفاً ابتدا یک کتاب را از جدول انتخاب کنید.", parent=root)
            return
        vals = tree.item(selected[0], "values")
        if not vals or str(vals[0]).startswith("❌"):
            return
        id_idx = columns.index("id") if "id" in columns else 0
        try:
            book_id = int(vals[id_idx])
        except (ValueError, IndexError):
            return

    book = book_service.get_book(book_id, conn_or_path=db_p)
    if not book:
        messagebox.showerror("خطا", "اطلاعات کتاب یافت نشد!", parent=root)
        return

    popup = ctk.CTkToplevel(root)
    book_title_display = book.get("title") or ""
    popup.title(f"ویرایش کتاب ({book_title_display})")
    popup.geometry("500x485")
    popup.resizable(False, False)
    if os.path.exists(icon_p):
        try:
            popup.iconbitmap(icon_p)
        except Exception:
            pass

    popup.transient(root)
    popup.grab_set()

    root.update_idletasks()
    rx = root.winfo_rootx()
    ry = root.winfo_rooty()
    rw = root.winfo_width()
    rh = root.winfo_height()
    px = max(50, rx + (rw - 500) // 2)
    py = max(50, ry + (rh - 485) // 2)
    popup.geometry(f"+{px}+{py}")

    ctk.CTkLabel(popup, text="ویرایش اطلاعات کتاب و رده دیویی", font=FONT_TITLE).pack(pady=(12, 8))

    form_f = ctk.CTkFrame(popup, fg_color="transparent")
    form_f.pack(fill=tk.BOTH, expand=True, padx=20, pady=0)

    # Title
    row_t = ctk.CTkFrame(form_f, fg_color="transparent")
    row_t.pack(fill=tk.X, pady=4)
    ctk.CTkLabel(row_t, text="عنوان کتاب:", font=FONT_BOLD, width=105, anchor="e").pack(side=tk.RIGHT, padx=(5, 0))
    ent_t = ctk.CTkEntry(row_t, font=FONT_NORMAL, justify="right", height=32, placeholder_text="عنوان کتاب (الزامی)")
    ent_t.insert(0, book.get("title") or "")
    ent_t.pack(side=tk.RIGHT, fill=tk.X, expand=True)

    # Author
    row_a = ctk.CTkFrame(form_f, fg_color="transparent")
    row_a.pack(fill=tk.X, pady=4)
    ctk.CTkLabel(row_a, text="نویسنده:", font=FONT_NORMAL, width=105, anchor="e").pack(side=tk.RIGHT, padx=(5, 0))
    ent_a = ctk.CTkEntry(
        row_a, font=FONT_NORMAL, justify="right", height=32, placeholder_text="نام پدیدآورنده یا نویسنده"
    )
    ent_a.insert(0, book.get("author") or "")
    ent_a.pack(side=tk.RIGHT, fill=tk.X, expand=True)

    # ISBN
    row_i = ctk.CTkFrame(form_f, fg_color="transparent")
    row_i.pack(fill=tk.X, pady=4)
    ctk.CTkLabel(row_i, text="شابک:", font=FONT_NORMAL, width=105, anchor="e").pack(side=tk.RIGHT, padx=(5, 0))
    ent_i = ctk.CTkEntry(row_i, font=FONT_NORMAL, justify="right", height=32, placeholder_text="شابک ۱۰ یا ۱۳ رقمی")
    ent_i.insert(0, book.get("isbn") or "")
    ent_i.pack(side=tk.RIGHT, fill=tk.X, expand=True)

    # Reclassify button (shown only if system has internet access and AI enabled)
    row_re = ctk.CTkFrame(form_f, fg_color="transparent")
    btn_reclassify_single = create_icon_button(
        row_re,
        text=" پیشنهاد مجدد رده دیویی با هوش مصنوعی ",
        icon_name="zap",
        font=FONT_NORMAL,
        height=30,
        fg_color="#0284c7",
        hover_color="#0369a1",
    )
    btn_reclassify_single.pack(fill=tk.X)

    # Show AI reclassify button if AI features are enabled and internet was verified at boot time
    if is_ai_available():
        row_re.pack(fill=tk.X, pady=(3, 5))

    # Dewey Code
    row_d = ctk.CTkFrame(form_f, fg_color="transparent")
    row_d.pack(fill=tk.X, pady=4)
    ctk.CTkLabel(row_d, text="کد دیویی:", font=FONT_NORMAL, width=105, anchor="e").pack(side=tk.RIGHT, padx=(5, 0))
    ent_d = ctk.CTkEntry(row_d, font=FONT_NORMAL, justify="center", height=32, placeholder_text="مانند: 510 یا 641.5")
    ent_d.insert(0, book.get("dewey_code") or "")
    ent_d.pack(side=tk.RIGHT, fill=tk.X, expand=True)

    # Dewey Subject
    row_s = ctk.CTkFrame(form_f, fg_color="transparent")
    row_s.pack(fill=tk.X, pady=4)
    ctk.CTkLabel(row_s, text="موضوع دیویی:", font=FONT_NORMAL, width=105, anchor="e").pack(side=tk.RIGHT, padx=(5, 0))
    ent_s = ctk.CTkEntry(row_s, font=FONT_NORMAL, justify="right", height=32, placeholder_text="موضوع رده")
    ent_s.insert(0, book.get("dewey_subject") or "")
    ent_s.pack(side=tk.RIGHT, fill=tk.X, expand=True)

    # Meta display
    DEWEY_SOURCE_FA = {
        "manual": "دستی",
        "api": "استعلام آنلاین",
        "mapping": "نگاشت موضوعی",
        "keyword": "واژگان کلیدی",
        "rule": "قوانین رده‌بندی",
        "ai": "هوش مصنوعی",
        "unknown": "تعیین‌نشده",
    }
    raw_src = str(book.get("dewey_source") or "unknown").strip().lower()
    src_display = DEWEY_SOURCE_FA.get(raw_src, "تعیین‌نشده")
    conf_val = int((book.get("dewey_confidence") or 0) * 100)

    meta_f = ctk.CTkFrame(form_f, corner_radius=6, fg_color=("#f1f5f9", "#1e293b"))
    meta_f.pack(fill=tk.X, pady=(5, 3), padx=2)
    meta_lbl = ctk.CTkLabel(
        meta_f,
        text=f"منبع رده: {src_display}  |  درجه اطمینان: {conf_val} درصد",
        font=FONT_SMALL,
        text_color=("#475569", "#94a3b8"),
        anchor="e",
    )
    meta_lbl.pack(fill=tk.X, padx=10, pady=(4, 2))

    shelf_lbl = ctk.CTkLabel(
        meta_f,
        text="",
        font=FONT_SMALL,
        text_color=("#475569", "#94a3b8"),
        anchor="e",
    )
    shelf_lbl.pack(fill=tk.X, padx=10, pady=(2, 4))

    def update_shelf_lbl():
        code = ent_d.get().strip()
        if code and is_valid_dewey(code):
            loc = dewey_service.get_shelf_location(code)
            shelf_lbl.configure(text=f"📍 {loc.get('shelf_label')}")
        else:
            shelf_lbl.configure(text="محل قفسه: تعیین نشده")

    update_shelf_lbl()
    ent_d.bind("<KeyRelease>", lambda e: update_shelf_lbl())

    def do_reclassify():
        if not is_ai_available():
            messagebox.showwarning(
                "هوش مصنوعی",
                "قابلیت‌های هوش مصنوعی یا دسترسی به اینترنت در تنظیمات برنامه غیرفعال است.",
                parent=popup,
            )
            return
        t = ent_t.get().strip()
        a = ent_a.get().strip()
        if not t:
            messagebox.showwarning("خطا", "لطفاً ابتدا عنوان کتاب را وارد کنید!", parent=popup)
            return

        def _worker():
            try:
                c_res = dewey_service.detect_with_ai(title=t, author=a if a else None)

                def _apply():
                    if c_res and c_res.dewey_code:
                        ent_d.delete(0, tk.END)
                        ent_d.insert(0, c_res.dewey_code)
                        ent_s.delete(0, tk.END)
                        ent_s.insert(0, c_res.dewey_subject or "")
                        update_shelf_lbl()
                        new_src_fa = DEWEY_SOURCE_FA.get(str(c_res.dewey_source).lower(), "هوش مصنوعی")
                        new_conf = int(c_res.dewey_confidence * 100)
                        meta_lbl.configure(text=f"منبع جدید: {new_src_fa}  |  درجه اطمینان: {new_conf} درصد")
                    else:
                        messagebox.showinfo("رده‌بندی", "رده مشخصی برای این کتاب پیدا نشد.", parent=popup)

                popup.after(0, _apply)
            except Exception as ex:
                err_msg = str(ex)
                popup.after(
                    0, lambda msg=err_msg: messagebox.showerror("خطا", f"خطا در هوش مصنوعی: {msg}", parent=popup)
                )

        threading.Thread(target=_worker, daemon=True).start()

    btn_reclassify_single.configure(command=do_reclassify)

    def do_save_edit():
        new_title = ent_t.get().strip()
        if not new_title:
            messagebox.showwarning("خطا", "عنوان کتاب نمی‌تواند خالی باشد!", parent=popup)
            return
        new_author = ent_a.get().strip() or None
        new_isbn = ent_i.get().strip() or None
        new_code = ent_d.get().strip() or None
        new_subj = ent_s.get().strip() or None

        if new_code and not is_valid_dewey(new_code):
            messagebox.showerror("خطا", "کد دیویی وارد شده معتبر نیست!", parent=popup)
            return

        temp_conn = get_db_connection(db_p)
        try:
            temp_cur = temp_conn.cursor()
            cls_name = dewey_service.get_class_name(new_code) if new_code else None
            temp_cur.execute(
                """
                UPDATE books SET
                    title = ?,
                    author = ?,
                    isbn = ?,
                    dewey_code = ?,
                    dewey_class = ?,
                    dewey_subject = ?,
                    dewey_confidence = ?,
                    dewey_source = ?
                WHERE id = ?
                """,
                (
                    new_title,
                    new_author,
                    new_isbn,
                    new_code,
                    cls_name,
                    new_subj,
                    1.0 if new_code else 0.0,
                    "manual",
                    book_id,
                ),
            )
            temp_conn.commit()
            messagebox.showinfo("موفق", "اطلاعات کتاب با موفقیت به‌روزرسانی شد.", parent=popup)
            popup.destroy()
            search()
        except sqlite3.IntegrityError:
            messagebox.showerror("خطا", "شابک وارد شده تکراری است!", parent=popup)
        except Exception as ex:
            messagebox.showerror("خطا", f"خطا در به‌روزرسانی کتاب: {ex}", parent=popup)
        finally:
            temp_conn.close()

    btn_f = ctk.CTkFrame(popup, fg_color="transparent")
    btn_f.pack(pady=(4, 14), padx=20, fill=tk.X)
    btn_save = create_icon_button(
        btn_f,
        text=" ذخیره تغییرات ",
        icon_name="check",
        command=do_save_edit,
        font=FONT_BOLD,
        fg_color="#16a34a",
        hover_color="#15803d",
        width=135,
    )
    btn_save.pack(side=tk.RIGHT, padx=5)
    btn_cancel = create_icon_button(
        btn_f,
        text=" انصراف ",
        icon_name="x",
        command=popup.destroy,
        font=FONT_NORMAL,
        fg_color="transparent",
        hover_color=("#e2e8f0", "#1e293b"),
        width=90,
    )
    btn_cancel.pack(side=tk.LEFT, padx=5)


def open_reclassify_all_dialog():
    confirm = messagebox.askyesno(
        "رده‌بندی دسته‌ای کتاب‌ها",
        "آیا مایلید تمام کتاب‌های فاقد رده یا رده‌بندی‌شده سیستمی به صورت خودکار رده‌بندی شوند؟\n\n"
        "نکته: رده‌های تنظیم‌شده به صورت دستی (Manual) بدون تغییر حفظ خواهند شد.",
        parent=root,
    )
    if not confirm:
        return

    progress_win = ctk.CTkToplevel(root)
    progress_win.title("در حال رده‌بندی...")
    progress_win.geometry("320x120")
    progress_win.resizable(False, False)
    progress_win.transient(root)
    progress_win.grab_set()
    ctk.CTkLabel(progress_win, text="در حال پردازش و رده‌بندی کتاب‌ها...", font=FONT_NORMAL).pack(pady=20)
    p_bar = ctk.CTkProgressBar(progress_win, mode="indeterminate")
    p_bar.pack(fill=tk.X, padx=30, pady=5)
    p_bar.start()

    def _worker():
        try:
            res = book_service.reclassify_all_books(force=False, conn_or_path=db_p)

            def _done():
                progress_win.destroy()
                messagebox.showinfo(
                    "پایان رده‌بندی",
                    f"رده‌بندی هوشمند به پایان رسید:\n\n"
                    f"• کل کتاب‌ها: {res['total']}\n"
                    f"• رده‌بندی‌شده / به‌روزرسانی‌شده: {res['updated']}\n"
                    f"• حفظ شده (رده دستی): {res['skipped_manual']}\n"
                    f"• بدون رده مشخص: {res['unclassified']}",
                    parent=root,
                )
                search()

            root.after(0, _done)
        except Exception as ex:
            err_msg = str(ex)

            def _err(msg=err_msg):
                progress_win.destroy()
                messagebox.showerror("خطا", f"خطا در رده‌بندی: {msg}", parent=root)

            root.after(0, _err)

    threading.Thread(target=_worker, daemon=True).start()


def do_reclassify_selected_book():
    selected = tree.selection()
    if not selected:
        messagebox.showinfo("راهنما", "لطفاً ابتدا یک کتاب را انتخاب کنید.", parent=root)
        return
    vals = tree.item(selected[0], "values")
    if not vals or str(vals[0]).startswith("❌"):
        return
    id_idx = columns.index("id") if "id" in columns else 0
    try:
        book_id = int(vals[id_idx])
        c_res = book_service.reclassify_book(book_id, force=True, conn_or_path=db_p)
        if c_res and c_res.dewey_code:
            messagebox.showinfo(
                "رده‌بندی دیویی",
                f"کتاب با موفقیت رده‌بندی شد:\nکد: {c_res.dewey_code}\nموضوع: {c_res.dewey_subject}",
                parent=root,
            )
        else:
            messagebox.showinfo("رده‌بندی دیویی", "رده مشخصی برای این کتاب پیدا نشد.", parent=root)
        search()
    except Exception as ex:
        messagebox.showerror("خطا", f"خطا در رده‌بندی: {ex}", parent=root)


book_context_menu = tk.Menu(root, tearoff=0)
book_context_menu.add_command(label="ویرایش کتاب و رده دیویی...", command=open_edit_book_popup)
book_context_menu.add_command(label="رده‌بندی خودکار این کتاب", command=do_reclassify_selected_book)
book_context_menu.add_separator()
book_context_menu.add_command(label="ثبت امانت این کتاب...", command=lambda: on_double_click(None))


def show_book_context_menu(event):
    row_id = tree.identify_row(event.y)
    if row_id:
        tree.selection_set(row_id)
        book_context_menu.tk_popup(event.x_root, event.y_root)


tree.bind("<Button-3>", show_book_context_menu)
reclassify_all_btn.configure(command=open_reclassify_all_dialog)
edit_book_btn.configure(command=open_edit_book_popup)
add_book_btn.configure(command=open_add_book_popup)
bind_table_delete(tree, tabel_name, id_col_index=columns.index("id") if "id" in columns else 0, on_deleted=search)

search_after_id = None


def on_key_release(event):
    global search_after_id
    if search_after_id is not None:
        root.after_cancel(search_after_id)
    search_after_id = root.after(200, search)


# ==================== اعضای کتابخانه (Library Members) ====================
member_tabel_name = "members"
cursor_mem = sqlite3.connect(db_p).cursor()
cursor_mem.execute(f'PRAGMA table_info("{member_tabel_name}")')
member_column: list[str] = [str(row[1]) for row in cursor_mem.fetchall()]
cursor_mem.connection.close()

member_filter_settings = {
    "column": "all",
    "match_mode": "contains",
    "sort_col": "id",
    "sort_dir": "ASC",
}

search_bar_frame_member = ctk.CTkFrame(member_frame, corner_radius=8, height=48)
search_bar_frame_member.pack(fill=tk.X, padx=10, pady=(10, 6))
search_bar_frame_member.columnconfigure(4, weight=1)

sub_btn_member = create_icon_button(
    search_bar_frame_member, text=" جستجو ", icon_name="search", font=FONT_BOLD, width=85
)
sub_btn_member.grid(row=0, column=0, padx=(8, 4), pady=6)

filter_btn_member = create_icon_button(
    search_bar_frame_member, text=" فیلترها ", icon_name="filter", font=FONT_NORMAL, width=85
)
filter_btn_member.grid(row=0, column=1, padx=4, pady=6)

edit_member_btn = create_icon_button(
    search_bar_frame_member,
    text=" ویرایش عضو ",
    icon_name="edit",
    font=FONT_NORMAL,
    width=100,
)
edit_member_btn.grid(row=0, column=2, padx=4, pady=6)

add_member_btn = create_icon_button(
    search_bar_frame_member,
    text=" افزودن عضو ",
    icon_name="user-plus",
    font=FONT_NORMAL,
    fg_color="#16a34a",
    hover_color="#15803d",
    width=105,
)
add_member_btn.grid(row=0, column=3, padx=4, pady=6)

entry_search_member = ctk.CTkEntry(
    search_bar_frame_member,
    placeholder_text="جستجو در اعضا (نام، شماره تماس و ...)",
    font=FONT_NORMAL,
    justify="right",
    height=36,
)
entry_search_member.grid(row=0, column=4, sticky="ew", padx=(4, 8), pady=6)

member_tree_frame = ctk.CTkFrame(member_frame, corner_radius=8)
member_tree_frame.pack(padx=10, pady=(0, 10), fill=tk.BOTH, expand=True)

member_scrollbar = ctk.CTkScrollbar(member_tree_frame)
member_scrollbar.pack(side=tk.LEFT, fill=tk.Y, padx=(4, 0), pady=4)

member_tree = ttk.Treeview(
    member_tree_frame, yscrollcommand=member_scrollbar.set, columns=member_column, show="headings", height=15
)
member_scrollbar.configure(command=member_tree.yview)
for col in member_column:
    member_tree.heading(col, text=tr(col), anchor=tk.CENTER)
    member_tree.column(col, anchor=tk.CENTER)
member_display_cols = (
    ["id", "username", "phone_number"] if "username" in member_column else ["id", "member_id", "phone_number"]
)
member_tree["displaycolumns"] = rtl_display_order(member_column, member_display_cols)
member_tree.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(4, 8), pady=4)


def update_member_filter_indicator():
    is_custom = (
        member_filter_settings["column"] != "all"
        or member_filter_settings["match_mode"] != "contains"
        or member_filter_settings["sort_col"] != "id"
        or member_filter_settings["sort_dir"] != "ASC"
    )
    if is_custom:
        filter_btn_member.configure(text=" فیلترها (فعال) ", fg_color="#2563eb")
    else:
        filter_btn_member.configure(text=" فیلترها ", fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"])


def search_members(event=None):
    search_value = entry_search_member.get().strip()
    member_tree.delete(*member_tree.get_children())

    temp_conn = get_db_connection(db_p)
    try:
        temp_cursor = temp_conn.cursor()

        where_conditions: list[str] = []
        params: list[str] = []

        if search_value:
            selected_col = member_filter_settings.get("column", "all")
            match_mode = member_filter_settings.get("match_mode", "contains")

            if match_mode == "exact":
                pattern = search_value
                op = "="
            elif match_mode == "startswith":
                pattern = f"{search_value}%"
                op = "LIKE"
            else:
                pattern = f"%{search_value}%"
                op = "LIKE"

            if selected_col == "all":
                sub_conds = [f"{col} {op} ?" for col in member_column]
                where_conditions.append("(" + " OR ".join(sub_conds) + ")")
                params.extend([pattern] * len(member_column))
            elif selected_col in member_column:
                where_conditions.append(f"{selected_col} {op} ?")
                params.append(pattern)

        query = f"SELECT {', '.join(member_column)} FROM {member_tabel_name}"
        if where_conditions:
            query += " WHERE " + " AND ".join(where_conditions)

        sort_col = member_filter_settings.get("sort_col", "id")
        if sort_col not in member_column:
            sort_col = "id"
        sort_dir = member_filter_settings.get("sort_dir", "ASC")
        if sort_dir not in ("ASC", "DESC"):
            sort_dir = "ASC"
        query += f" ORDER BY {sort_col} {sort_dir}"

        temp_cursor.execute(query, tuple(params))
        results = temp_cursor.fetchall()

        if results:
            for row in results:
                member_tree.insert("", "end", values=tuple(row))
        else:
            member_tree.insert("", "end", values=("❌ نتیجه‌ای یافت نشد!",) + ("",) * (len(member_column) - 1))

    except Exception as e:
        messagebox.showerror("خطا", f"خطا در جستجوی اعضا: {str(e)}")
    finally:
        temp_conn.close()


sub_btn_member.configure(command=search_members)


def open_member_filter_popup():
    popup = ctk.CTkToplevel(root)
    popup.title("فیلترهای اعضای کتابخانه")
    popup.geometry("420x420")
    popup.resizable(False, False)
    if os.path.exists(icon_p):
        try:
            popup.iconbitmap(icon_p)
        except Exception:
            pass

    popup.transient(root)
    popup.grab_set()

    root.update_idletasks()
    rx = root.winfo_rootx()
    ry = root.winfo_rooty()
    rw = root.winfo_width()
    rh = root.winfo_height()
    px = max(50, rx + (rw - 420) // 2)
    py = max(50, ry + (rh - 420) // 2)
    popup.geometry(f"+{px}+{py}")

    col_var = tk.StringVar(value=member_filter_settings["column"])
    match_var = tk.StringVar(value=member_filter_settings["match_mode"])
    sort_col_var = tk.StringVar(value=member_filter_settings["sort_col"])
    sort_dir_var = tk.StringVar(value=member_filter_settings["sort_dir"])

    group_col = ctk.CTkFrame(popup, corner_radius=8)
    group_col.pack(fill=tk.X, padx=15, pady=(10, 4))
    ctk.CTkLabel(group_col, text="جستجو در ستون", font=FONT_BOLD, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))
    col_frame = ctk.CTkFrame(group_col, fg_color="transparent")
    col_frame.pack(fill=tk.X, padx=6, pady=(0, 6))
    rb_all = ctk.CTkRadioButton(col_frame, text="همه ستون‌ها", variable=col_var, value="all", font=FONT_NORMAL)
    rb_all.pack(side=tk.RIGHT, padx=4)
    for col in member_column:
        rb = ctk.CTkRadioButton(col_frame, text=tr(col), variable=col_var, value=col, font=FONT_NORMAL)
        rb.pack(side=tk.RIGHT, padx=4)

    group_mode = ctk.CTkFrame(popup, corner_radius=8)
    group_mode.pack(fill=tk.X, padx=15, pady=4)
    ctk.CTkLabel(group_mode, text="نوع تطابق جستجو", font=FONT_BOLD, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))
    mode_frame = ctk.CTkFrame(group_mode, fg_color="transparent")
    mode_frame.pack(fill=tk.X, padx=6, pady=(0, 6))
    rb_contains = ctk.CTkRadioButton(
        mode_frame, text="شامل عبارت", variable=match_var, value="contains", font=FONT_NORMAL
    )
    rb_contains.pack(side=tk.RIGHT, padx=8)
    rb_starts = ctk.CTkRadioButton(
        mode_frame, text="شروع با عبارت", variable=match_var, value="startswith", font=FONT_NORMAL
    )
    rb_starts.pack(side=tk.RIGHT, padx=8)
    rb_exact = ctk.CTkRadioButton(mode_frame, text="مطابقت دقیق", variable=match_var, value="exact", font=FONT_NORMAL)
    rb_exact.pack(side=tk.RIGHT, padx=8)

    group_sort = ctk.CTkFrame(popup, corner_radius=8)
    group_sort.pack(fill=tk.X, padx=15, pady=4)
    ctk.CTkLabel(group_sort, text="مرتب‌سازی نتایج", font=FONT_BOLD, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))
    sort_frame = ctk.CTkFrame(group_sort, fg_color="transparent")
    sort_frame.pack(fill=tk.X, padx=6, pady=(0, 6))

    ctk.CTkLabel(sort_frame, text="بر اساس:", font=FONT_NORMAL).pack(side=tk.RIGHT, padx=(5, 0))
    sort_cols_avail = [c for c in ["id", "member_id", "phone_number"] if c in member_column]
    sort_col_cb = ctk.CTkOptionMenu(
        sort_frame,
        width=130,
        font=FONT_NORMAL,
        values=[tr(c) for c in sort_cols_avail],
    )
    sort_col_cb.set(tr(sort_col_var.get()))
    sort_col_cb.pack(side=tk.RIGHT, padx=5)

    ctk.CTkLabel(sort_frame, text="ترتیب:", font=FONT_NORMAL).pack(side=tk.RIGHT, padx=(12, 0))
    sort_dir_cb = ctk.CTkOptionMenu(sort_frame, width=100, font=FONT_NORMAL, values=["صعودی", "نزولی"])
    sort_dir_cb.set("صعودی" if sort_dir_var.get() == "ASC" else "نزولی")
    sort_dir_cb.pack(side=tk.RIGHT, padx=5)

    action_frame = ctk.CTkFrame(popup, fg_color="transparent")
    action_frame.pack(fill=tk.X, padx=15, pady=(15, 10))

    def apply_member_filters():
        member_filter_settings["column"] = col_var.get()
        member_filter_settings["match_mode"] = match_var.get()

        disp_col = sort_col_cb.get()
        disp_map = {tr(c): c for c in member_column}
        member_filter_settings["sort_col"] = disp_map.get(disp_col, "id")
        member_filter_settings["sort_dir"] = "ASC" if sort_dir_cb.get() == "صعودی" else "DESC"

        update_member_filter_indicator()
        popup.destroy()
        search_members()

    def reset_member_filters():
        member_filter_settings["column"] = "all"
        member_filter_settings["match_mode"] = "contains"
        member_filter_settings["sort_col"] = "id"
        member_filter_settings["sort_dir"] = "ASC"

        update_member_filter_indicator()
        popup.destroy()
        search_members()

    btn_apply = create_icon_button(
        action_frame,
        text=" اعمال فیلتر ",
        icon_name="check",
        font=FONT_BOLD,
        fg_color="#2563eb",
        hover_color="#1d4ed8",
        command=apply_member_filters,
    )
    btn_apply.pack(side=tk.RIGHT, padx=4)

    btn_reset = create_icon_button(
        action_frame,
        text=" تنظیم مجدد ",
        icon_name="rotate-ccw",
        font=FONT_NORMAL,
        fg_color="transparent",
        hover_color=("#e2e8f0", "#1e293b"),
        command=reset_member_filters,
    )
    btn_reset.pack(side=tk.RIGHT, padx=4)

    btn_cancel = create_icon_button(
        action_frame,
        text=" انصراف ",
        icon_name="x",
        font=FONT_NORMAL,
        fg_color="transparent",
        hover_color=("#e2e8f0", "#1e293b"),
        command=popup.destroy,
    )
    btn_cancel.pack(side=tk.LEFT, padx=4)


filter_btn_member.configure(command=open_member_filter_popup)


def open_add_member_popup():
    popup = ctk.CTkToplevel(root)
    popup.title("ثبت عضو جدید")
    popup.geometry("400x320")
    popup.resizable(False, False)
    if os.path.exists(icon_p):
        try:
            popup.iconbitmap(icon_p)
        except Exception:
            pass

    popup.transient(root)
    popup.grab_set()

    root.update_idletasks()
    rx = root.winfo_rootx()
    ry = root.winfo_rooty()
    rw = root.winfo_width()
    rh = root.winfo_height()
    px = max(50, rx + (rw - 400) // 2)
    py = max(50, ry + (rh - 320) // 2)
    popup.geometry(f"+{px}+{py}")

    ctk.CTkLabel(popup, text="ثبت عضو جدید", font=FONT_TITLE).pack(pady=(15, 10))

    row_1 = ctk.CTkFrame(popup, fg_color="transparent")
    row_1.pack(fill=tk.X, padx=25, pady=6)
    ctk.CTkLabel(row_1, text="نام کاربر (عضو):", font=FONT_NORMAL, width=110, anchor="e").pack(
        side=tk.RIGHT, padx=(5, 0)
    )
    entry_m_id = ctk.CTkEntry(row_1, font=FONT_NORMAL, justify="right", height=34)
    entry_m_id.pack(side=tk.RIGHT, fill=tk.X, expand=True)

    row_2 = ctk.CTkFrame(popup, fg_color="transparent")
    row_2.pack(fill=tk.X, padx=25, pady=6)
    ctk.CTkLabel(row_2, text="شماره تلفن:", font=FONT_NORMAL, width=110, anchor="e").pack(side=tk.RIGHT, padx=(5, 0))
    entry_m_phone = ctk.CTkEntry(row_2, font=FONT_NORMAL, justify="right", height=34)
    entry_m_phone.pack(side=tk.RIGHT, fill=tk.X, expand=True)

    def do_insert_member():
        m_id = entry_m_id.get().strip()
        m_phone = entry_m_phone.get().strip()

        if not m_id:
            messagebox.showwarning("خطا", "لطفاً نام کاربر را وارد کنید!", parent=popup)
            entry_m_id.focus()
            return
        if not m_phone:
            messagebox.showwarning("خطا", "لطفاً شماره تلفن را وارد کنید!", parent=popup)
            entry_m_phone.focus()
            return

        norm_phone = normalize_phone_number(m_phone)
        if len(norm_phone) != 11 or not norm_phone.startswith("09"):
            messagebox.showerror("خطا", "فرمت شماره تلفن نامعتبر است!\nمثال: 09123456789", parent=popup)
            entry_m_phone.focus()
            return

        temp_conn = get_db_connection(db_p)
        try:
            temp_cursor = temp_conn.cursor()
            temp_cursor.execute("INSERT INTO members (username, phone_number) VALUES (?, ?)", (m_id, norm_phone))
            temp_conn.commit()

            messagebox.showinfo("موفق", f"اطلاعات عضو با نام {m_id} با موفقیت ثبت شد!", parent=popup)
            popup.destroy()
            search_members()

        except sqlite3.IntegrityError:
            messagebox.showerror("خطا", f"نام کاربر '{m_id}' قبلاً ثبت شده است!", parent=popup)
        except sqlite3.Error as e:
            messagebox.showerror("خطا", f"خطا در پایگاه داده: {e}", parent=popup)
        finally:
            temp_conn.close()

    btn_f = ctk.CTkFrame(popup, fg_color="transparent")
    btn_f.pack(pady=20, padx=20, fill=tk.X)
    btn_save = create_icon_button(
        btn_f,
        text=" ثبت اطلاعات ",
        icon_name="check",
        command=do_insert_member,
        font=FONT_BOLD,
        fg_color="#16a34a",
        hover_color="#15803d",
        width=120,
    )
    btn_save.pack(side=tk.RIGHT, padx=5)
    btn_cancel = create_icon_button(
        btn_f,
        text=" انصراف ",
        icon_name="x",
        command=popup.destroy,
        font=FONT_NORMAL,
        fg_color="transparent",
        hover_color=("#e2e8f0", "#1e293b"),
        width=90,
    )
    btn_cancel.pack(side=tk.LEFT, padx=5)


def open_edit_member_popup(member_id: int | None = None):
    if member_id is None:
        selected = member_tree.selection()
        if not selected:
            messagebox.showinfo("راهنما", "لطفاً ابتدا یک عضو را از جدول انتخاب کنید.", parent=root)
            return
        vals = member_tree.item(selected[0], "values")
        if not vals or str(vals[0]).startswith("❌"):
            return
        id_idx = member_column.index("id") if "id" in member_column else 0
        try:
            member_id = int(vals[id_idx])
        except (ValueError, IndexError):
            return

    conn = get_db_connection(db_p)
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM members WHERE id = ?", (member_id,))
        row = cur.fetchone()
        if not row:
            messagebox.showerror("خطا", "اطلاعات عضو در سامانه یافت نشد!", parent=root)
            return
        member_data = dict(row)
    finally:
        conn.close()

    popup = ctk.CTkToplevel(root)
    m_name_curr = str(member_data.get("username") or member_data.get("member_id") or "")
    popup.title(f"ویرایش مشخصات عضو ({m_name_curr})")
    popup.geometry("440x360")
    popup.resizable(False, False)
    if os.path.exists(icon_p):
        try:
            popup.iconbitmap(icon_p)
        except Exception:
            pass

    popup.transient(root)
    popup.grab_set()

    root.update_idletasks()
    rx = root.winfo_rootx()
    ry = root.winfo_rooty()
    rw = root.winfo_width()
    rh = root.winfo_height()
    px = max(50, rx + (rw - 440) // 2)
    py = max(50, ry + (rh - 360) // 2)
    popup.geometry(f"+{px}+{py}")

    header_f = ctk.CTkFrame(popup, fg_color="transparent")
    header_f.pack(fill=tk.X, padx=20, pady=(15, 6))
    ctk.CTkLabel(header_f, text="ویرایش مشخصات عضو کتابخانه", font=FONT_TITLE, anchor="center").pack(fill=tk.X)
    ctk.CTkLabel(
        header_f,
        text=f"شناسه پرونده عضویت: #{member_id}",
        font=FONT_SMALL,
        text_color="#94a3b8",
        anchor="center",
    ).pack(fill=tk.X, pady=(2, 0))

    card_f = ctk.CTkFrame(
        popup,
        corner_radius=10,
        border_width=1,
        border_color=("#cbd5e1", "#334155"),
        fg_color=("#ffffff", "#1e293b"),
    )
    card_f.pack(fill=tk.X, padx=20, pady=(4, 10))

    row_1 = ctk.CTkFrame(card_f, fg_color="transparent")
    row_1.pack(fill=tk.X, padx=14, pady=(12, 6))
    ctk.CTkLabel(row_1, text="نام کاربر (عضو):", font=FONT_NORMAL, width=110, anchor="e").pack(
        side=tk.RIGHT, padx=(4, 0)
    )
    entry_m_id = ctk.CTkEntry(row_1, font=FONT_NORMAL, justify="right", height=34)
    entry_m_id.pack(side=tk.RIGHT, fill=tk.X, expand=True)
    entry_m_id.insert(0, m_name_curr)

    row_2 = ctk.CTkFrame(card_f, fg_color="transparent")
    row_2.pack(fill=tk.X, padx=14, pady=(6, 14))
    ctk.CTkLabel(row_2, text="شماره تلفن:", font=FONT_NORMAL, width=110, anchor="e").pack(side=tk.RIGHT, padx=(4, 0))
    entry_m_phone = ctk.CTkEntry(row_2, font=FONT_NORMAL, justify="right", height=34)
    entry_m_phone.pack(side=tk.RIGHT, fill=tk.X, expand=True)
    entry_m_phone.insert(0, str(member_data.get("phone_number", "")))

    def do_update_member():
        new_name = entry_m_id.get().strip()
        new_phone = entry_m_phone.get().strip()

        if not new_name:
            messagebox.showwarning("خطا", "لطفاً نام کاربر را وارد کنید!", parent=popup)
            entry_m_id.focus()
            return
        if not new_phone:
            messagebox.showwarning("خطا", "لطفاً شماره تلفن را وارد کنید!", parent=popup)
            entry_m_phone.focus()
            return

        norm_phone = normalize_phone_number(new_phone)
        if len(norm_phone) != 11 or not norm_phone.startswith("09"):
            messagebox.showerror("خطا", "فرمت شماره تلفن نامعتبر است!\nمثال: 09123456789", parent=popup)
            entry_m_phone.focus()
            return

        temp_conn = get_db_connection(db_p)
        try:
            temp_cursor = temp_conn.cursor()
            temp_cursor.execute(
                "SELECT id FROM members WHERE (username = ? OR member_id = ?) AND id != ?",
                (new_name, new_name, member_id),
            )
            if temp_cursor.fetchone():
                messagebox.showerror("خطا", f"نام کاربر '{new_name}' قبلاً برای عضو دیگری ثبت شده است!", parent=popup)
                entry_m_id.focus()
                return

            try:
                temp_cursor.execute(
                    "UPDATE members SET username = ?, phone_number = ? WHERE id = ?",
                    (new_name, norm_phone, member_id),
                )
            except sqlite3.OperationalError:
                temp_cursor.execute(
                    "UPDATE members SET member_id = ?, phone_number = ? WHERE id = ?",
                    (new_name, norm_phone, member_id),
                )

            temp_conn.commit()

            messagebox.showinfo("موفق", f"اطلاعات عضو «{new_name}» با موفقیت به‌روزرسانی شد.", parent=popup)
            popup.destroy()
            search_members()
            if "search_loans" in globals():
                try:
                    search_loans()
                except Exception:
                    pass
        except sqlite3.Error as e:
            messagebox.showerror("خطا", f"خطا در به‌روزرسانی عضو: {e}", parent=popup)
        finally:
            temp_conn.close()

    btn_f = ctk.CTkFrame(popup, fg_color="transparent")
    btn_f.pack(fill=tk.X, padx=20, pady=(6, 12))

    btn_save = create_icon_button(
        btn_f,
        text=" ذخیره تغییرات ",
        icon_name="check",
        command=do_update_member,
        font=FONT_BOLD,
        fg_color="#16a34a",
        hover_color="#15803d",
        height=34,
        width=130,
    )
    btn_save.pack(side=tk.RIGHT, padx=5)

    btn_cancel = create_icon_button(
        btn_f,
        text=" انصراف ",
        icon_name="x",
        command=popup.destroy,
        font=FONT_NORMAL,
        fg_color="transparent",
        hover_color=("#e2e8f0", "#1e293b"),
        height=34,
        width=90,
    )
    btn_cancel.pack(side=tk.LEFT, padx=5)


add_member_btn.configure(command=open_add_member_popup)
edit_member_btn.configure(command=open_edit_member_popup)
member_tree.bind("<Double-Button-1>", lambda e: open_edit_member_popup())

member_context_menu = tk.Menu(root, tearoff=0)
member_context_menu.add_command(label="ویرایش مشخصات عضو...", command=open_edit_member_popup)
member_context_menu.add_separator()
member_context_menu.add_command(label="حذف عضو", command=lambda: member_tree.event_generate("<Delete>"))


def show_member_context_menu(event):
    row_id = member_tree.identify_row(event.y)
    if row_id:
        member_tree.selection_set(row_id)
        member_context_menu.tk_popup(event.x_root, event.y_root)


member_tree.bind("<Button-3>", show_member_context_menu)

member_search_after_id = None


def on_member_key_release(event):
    global member_search_after_id
    if member_search_after_id is not None:
        root.after_cancel(member_search_after_id)
    member_search_after_id = root.after(200, search_members)


entry_search_member.bind("<KeyRelease>", on_member_key_release)
entry_search_member.bind("<Return>", search_members)

bind_table_delete(
    member_tree,
    "members",
    id_col_index=member_column.index("id") if "id" in member_column else 0,
    on_deleted=search_members,
)

# ==================== مدیریت کاربران سیستم (System Users) ====================
user_tabel_name = "auth_users"
user_columns = ["id", "username", "phone_number", "role", "telegram_chat_id", "is_active", "created_at"]

user_filter_settings = {
    "column": "all",
    "match_mode": "contains",
    "sort_col": "id",
    "sort_dir": "ASC",
}

search_bar_frame_users = ctk.CTkFrame(auth_users_frame, corner_radius=8, height=48)
search_bar_frame_users.pack(fill=tk.X, padx=10, pady=(10, 6))
search_bar_frame_users.columnconfigure(4, weight=1)

sub_btn_users = create_icon_button(search_bar_frame_users, text=" جستجو ", icon_name="search", font=FONT_BOLD, width=85)
sub_btn_users.grid(row=0, column=0, padx=(8, 4), pady=6)

filter_btn_users = create_icon_button(
    search_bar_frame_users, text=" فیلترها ", icon_name="filter", font=FONT_NORMAL, width=85
)
filter_btn_users.grid(row=0, column=1, padx=4, pady=6)

edit_user_btn = create_icon_button(
    search_bar_frame_users,
    text=" ویرایش کاربر ",
    icon_name="user-cog",
    font=FONT_NORMAL,
    width=100,
)
edit_user_btn.grid(row=0, column=2, padx=4, pady=6)

add_user_btn = create_icon_button(
    search_bar_frame_users,
    text=" افزودن کاربر ",
    icon_name="user-plus",
    font=FONT_NORMAL,
    fg_color="#16a34a",
    hover_color="#15803d",
    width=105,
)
add_user_btn.grid(row=0, column=3, padx=4, pady=6)

entry_search_users = ctk.CTkEntry(
    search_bar_frame_users,
    placeholder_text="جستجو در کاربران سامانه (نام کاربری، شماره تماس، نقش و ...)",
    font=FONT_NORMAL,
    justify="right",
    height=36,
)
entry_search_users.grid(row=0, column=4, sticky="ew", padx=(4, 8), pady=6)

users_tree_frame = ctk.CTkFrame(auth_users_frame, corner_radius=8)
users_tree_frame.pack(padx=10, pady=(0, 10), fill=tk.BOTH, expand=True)

users_scrollbar = ctk.CTkScrollbar(users_tree_frame)
users_scrollbar.pack(side=tk.LEFT, fill=tk.Y, padx=(4, 0), pady=4)

users_tree = ttk.Treeview(
    users_tree_frame, yscrollcommand=users_scrollbar.set, columns=user_columns, show="headings", height=15
)
users_scrollbar.configure(command=users_tree.yview)
for col in user_columns:
    users_tree.heading(col, text=tr(col), anchor=tk.CENTER)
    users_tree.column(col, anchor=tk.CENTER)
users_tree["displaycolumns"] = rtl_display_order(
    user_columns, ["id", "username", "phone_number", "role", "telegram_chat_id", "is_active", "created_at"]
)
users_tree.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(4, 8), pady=4)


def update_user_filter_indicator():
    is_custom = (
        user_filter_settings["column"] != "all"
        or user_filter_settings["match_mode"] != "contains"
        or user_filter_settings["sort_col"] != "id"
        or user_filter_settings["sort_dir"] != "ASC"
    )
    if is_custom:
        filter_btn_users.configure(text=" فیلترها (فعال) ", fg_color="#2563eb")
    else:
        filter_btn_users.configure(text=" فیلترها ", fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"])


def search_users(event=None):
    search_value = entry_search_users.get().strip()
    users_tree.delete(*users_tree.get_children())

    temp_conn = get_db_connection(db_p)
    try:
        temp_cursor = temp_conn.cursor()

        where_conditions: list[str] = []
        params: list[str] = []

        if search_value:
            selected_col = user_filter_settings.get("column", "all")
            match_mode = user_filter_settings.get("match_mode", "contains")

            if match_mode == "exact":
                pattern = search_value
                op = "="
            elif match_mode == "startswith":
                pattern = f"{search_value}%"
                op = "LIKE"
            else:
                pattern = f"%{search_value}%"
                op = "LIKE"

            searchable_cols = ["username", "phone_number", "role", "telegram_chat_id"]
            if selected_col == "all":
                sub_conds = [f"{col} {op} ?" for col in searchable_cols]
                where_conditions.append("(" + " OR ".join(sub_conds) + ")")
                params.extend([pattern] * len(searchable_cols))
            elif selected_col in user_columns:
                where_conditions.append(f"{selected_col} {op} ?")
                params.append(pattern)

        query = f"SELECT {', '.join(user_columns)} FROM {user_tabel_name}"
        if where_conditions:
            query += " WHERE " + " AND ".join(where_conditions)

        sort_col = user_filter_settings.get("sort_col", "id")
        if sort_col not in user_columns:
            sort_col = "id"
        sort_dir = user_filter_settings.get("sort_dir", "ASC")
        if sort_dir not in ("ASC", "DESC"):
            sort_dir = "ASC"
        query += f" ORDER BY {sort_col} {sort_dir}"

        temp_cursor.execute(query, tuple(params))
        results = temp_cursor.fetchall()

        if results:
            for row in results:
                row_list = list(row)
                role_idx = user_columns.index("role")
                if role_idx < len(row_list) and row_list[role_idx]:
                    row_list[role_idx] = tr(row_list[role_idx])
                active_idx = user_columns.index("is_active")
                if active_idx < len(row_list):
                    row_list[active_idx] = "فعال" if row_list[active_idx] in (1, "1", True) else "غیرفعال"
                users_tree.insert("", "end", values=tuple(row_list))
        else:
            users_tree.insert("", "end", values=("❌ نتیجه‌ای یافت نشد!",) + ("",) * (len(user_columns) - 1))

    except Exception as e:
        messagebox.showerror("خطا", f"خطا در جستجوی کاربران: {str(e)}")
    finally:
        temp_conn.close()


sub_btn_users.configure(command=search_users)


def open_users_filter_popup():
    popup = ctk.CTkToplevel(root)
    popup.title("فیلترهای کاربران سامانه")
    popup.geometry("420x420")
    popup.resizable(False, False)
    if os.path.exists(icon_p):
        try:
            popup.iconbitmap(icon_p)
        except Exception:
            pass

    popup.transient(root)
    popup.grab_set()

    root.update_idletasks()
    rx = root.winfo_rootx()
    ry = root.winfo_rooty()
    rw = root.winfo_width()
    rh = root.winfo_height()
    px = max(50, rx + (rw - 420) // 2)
    py = max(50, ry + (rh - 420) // 2)
    popup.geometry(f"+{px}+{py}")

    col_var = tk.StringVar(value=user_filter_settings["column"])
    match_var = tk.StringVar(value=user_filter_settings["match_mode"])
    sort_col_var = tk.StringVar(value=user_filter_settings["sort_col"])
    sort_dir_var = tk.StringVar(value=user_filter_settings["sort_dir"])

    group_col = ctk.CTkFrame(popup, corner_radius=8)
    group_col.pack(fill=tk.X, padx=15, pady=(10, 4))
    ctk.CTkLabel(group_col, text="جستجو در ستون", font=FONT_BOLD, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))
    col_frame = ctk.CTkFrame(group_col, fg_color="transparent")
    col_frame.pack(fill=tk.X, padx=6, pady=(0, 6))
    rb_all = ctk.CTkRadioButton(col_frame, text="همه ستون‌ها", variable=col_var, value="all", font=FONT_NORMAL)
    rb_all.pack(side=tk.RIGHT, padx=4)
    for col in ["username", "phone_number", "role"]:
        rb = ctk.CTkRadioButton(col_frame, text=tr(col), variable=col_var, value=col, font=FONT_NORMAL)
        rb.pack(side=tk.RIGHT, padx=4)

    group_mode = ctk.CTkFrame(popup, corner_radius=8)
    group_mode.pack(fill=tk.X, padx=15, pady=4)
    ctk.CTkLabel(group_mode, text="نوع تطابق جستجو", font=FONT_BOLD, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))
    mode_frame = ctk.CTkFrame(group_mode, fg_color="transparent")
    mode_frame.pack(fill=tk.X, padx=6, pady=(0, 6))
    rb_contains = ctk.CTkRadioButton(
        mode_frame, text="شامل عبارت", variable=match_var, value="contains", font=FONT_NORMAL
    )
    rb_contains.pack(side=tk.RIGHT, padx=8)
    rb_starts = ctk.CTkRadioButton(
        mode_frame, text="شروع با عبارت", variable=match_var, value="startswith", font=FONT_NORMAL
    )
    rb_starts.pack(side=tk.RIGHT, padx=8)
    rb_exact = ctk.CTkRadioButton(mode_frame, text="مطابقت دقیق", variable=match_var, value="exact", font=FONT_NORMAL)
    rb_exact.pack(side=tk.RIGHT, padx=8)

    group_sort = ctk.CTkFrame(popup, corner_radius=8)
    group_sort.pack(fill=tk.X, padx=15, pady=4)
    ctk.CTkLabel(group_sort, text="مرتب‌سازی نتایج", font=FONT_BOLD, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))
    sort_frame = ctk.CTkFrame(group_sort, fg_color="transparent")
    sort_frame.pack(fill=tk.X, padx=6, pady=(0, 6))

    ctk.CTkLabel(sort_frame, text="بر اساس:", font=FONT_NORMAL).pack(side=tk.RIGHT, padx=(5, 0))
    sort_cols_avail = ["id", "username", "role"]
    sort_col_cb = ctk.CTkOptionMenu(
        sort_frame,
        width=130,
        font=FONT_NORMAL,
        values=[tr(c) for c in sort_cols_avail],
    )
    sort_col_cb.set(tr(sort_col_var.get()))
    sort_col_cb.pack(side=tk.RIGHT, padx=5)

    ctk.CTkLabel(sort_frame, text="ترتیب:", font=FONT_NORMAL).pack(side=tk.RIGHT, padx=(12, 0))
    sort_dir_cb = ctk.CTkOptionMenu(sort_frame, width=100, font=FONT_NORMAL, values=["صعودی", "نزولی"])
    sort_dir_cb.set("صعودی" if sort_dir_var.get() == "ASC" else "نزولی")
    sort_dir_cb.pack(side=tk.RIGHT, padx=5)

    action_frame = ctk.CTkFrame(popup, fg_color="transparent")
    action_frame.pack(fill=tk.X, padx=15, pady=(15, 10))

    def apply_user_filters():
        user_filter_settings["column"] = col_var.get()
        user_filter_settings["match_mode"] = match_var.get()

        disp_col = sort_col_cb.get()
        disp_map = {tr(c): c for c in user_columns}
        user_filter_settings["sort_col"] = disp_map.get(disp_col, "id")
        user_filter_settings["sort_dir"] = "ASC" if sort_dir_cb.get() == "صعودی" else "DESC"

        update_user_filter_indicator()
        popup.destroy()
        search_users()

    def reset_user_filters():
        user_filter_settings["column"] = "all"
        user_filter_settings["match_mode"] = "contains"
        user_filter_settings["sort_col"] = "id"
        user_filter_settings["sort_dir"] = "ASC"

        update_user_filter_indicator()
        popup.destroy()
        search_users()

    btn_apply = create_icon_button(
        action_frame,
        text=" اعمال فیلتر ",
        icon_name="check",
        font=FONT_BOLD,
        fg_color="#2563eb",
        hover_color="#1d4ed8",
        command=apply_user_filters,
    )
    btn_apply.pack(side=tk.RIGHT, padx=4)

    btn_reset = create_icon_button(
        action_frame,
        text=" تنظیم مجدد ",
        icon_name="rotate-ccw",
        font=FONT_NORMAL,
        fg_color="transparent",
        hover_color=("#e2e8f0", "#1e293b"),
        command=reset_user_filters,
    )
    btn_reset.pack(side=tk.RIGHT, padx=4)

    btn_cancel = create_icon_button(
        action_frame,
        text=" انصراف ",
        icon_name="x",
        font=FONT_NORMAL,
        fg_color="transparent",
        hover_color=("#e2e8f0", "#1e293b"),
        command=popup.destroy,
    )
    btn_cancel.pack(side=tk.LEFT, padx=4)


filter_btn_users.configure(command=open_users_filter_popup)


def open_create_user_popup():
    if not current_user or str(current_user.get("role", "")).strip().lower() not in (
        "super admin",
        "superadmin",
        "admin",
    ):
        messagebox.showerror("عدم دسترسی", "فقط نقش مدیر یا سرپرست مجاز به ایجاد کاربر جدید است.", parent=root)
        return

    popup = ctk.CTkToplevel(root)
    popup.title("ثبت کاربر جدید در سامانه")
    popup.geometry("420x500")
    popup.resizable(False, False)
    if os.path.exists(icon_p):
        try:
            popup.iconbitmap(icon_p)
        except Exception:
            pass

    popup.transient(root)
    popup.grab_set()

    root.update_idletasks()
    rx = root.winfo_rootx()
    ry = root.winfo_rooty()
    rw = root.winfo_width()
    rh = root.winfo_height()
    px = max(50, rx + (rw - 420) // 2)
    py = max(50, ry + (rh - 500) // 2)
    popup.geometry(f"+{px}+{py}")

    ctk.CTkLabel(popup, text="ثبت کاربر جدید (سامانه)", font=FONT_TITLE).pack(pady=(15, 10))

    r1 = ctk.CTkFrame(popup, fg_color="transparent")
    r1.pack(fill=tk.X, padx=25, pady=4)
    ctk.CTkLabel(r1, text="نام کاربری:", font=FONT_NORMAL, width=130, anchor="e").pack(side=tk.RIGHT, padx=(5, 0))
    u_name_ent = ctk.CTkEntry(r1, font=FONT_NORMAL, justify="right", height=32)
    u_name_ent.pack(side=tk.RIGHT, fill=tk.X, expand=True)

    r2 = ctk.CTkFrame(popup, fg_color="transparent")
    r2.pack(fill=tk.X, padx=25, pady=4)
    ctk.CTkLabel(r2, text="شماره تلفن:", font=FONT_NORMAL, width=130, anchor="e").pack(side=tk.RIGHT, padx=(5, 0))
    u_phone_ent = ctk.CTkEntry(r2, font=FONT_NORMAL, justify="right", height=32)
    u_phone_ent.pack(side=tk.RIGHT, fill=tk.X, expand=True)

    r3 = ctk.CTkFrame(popup, fg_color="transparent")
    r3.pack(fill=tk.X, padx=25, pady=4)
    ctk.CTkLabel(r3, text="شناسه چت تلگرام (اختیاری):", font=FONT_NORMAL, width=130, anchor="e").pack(
        side=tk.RIGHT, padx=(5, 0)
    )
    u_tg_ent = ctk.CTkEntry(r3, font=FONT_NORMAL, justify="right", height=32)
    u_tg_ent.pack(side=tk.RIGHT, fill=tk.X, expand=True)

    r4 = ctk.CTkFrame(popup, fg_color="transparent")
    r4.pack(fill=tk.X, padx=25, pady=4)
    ctk.CTkLabel(r4, text="نقش کاربر:", font=FONT_NORMAL, width=130, anchor="e").pack(side=tk.RIGHT, padx=(5, 0))
    u_role_combo = ctk.CTkOptionMenu(
        r4,
        font=FONT_NORMAL,
        values=["super admin", "admin", "librarian", "user"],
        height=32,
    )
    u_role_combo.set("librarian")
    u_role_combo.pack(side=tk.RIGHT, fill=tk.X, expand=True)

    r5 = ctk.CTkFrame(popup, fg_color="transparent")
    r5.pack(fill=tk.X, padx=25, pady=4)
    ctk.CTkLabel(r5, text="رمز عبور:", font=FONT_NORMAL, width=130, anchor="e").pack(side=tk.RIGHT, padx=(5, 0))
    u_pwd_ent = ctk.CTkEntry(r5, font=FONT_NORMAL, justify="right", height=32, show="*")
    u_pwd_ent.pack(side=tk.RIGHT, fill=tk.X, expand=True)

    def do_create_user():
        uname = u_name_ent.get().strip()
        phone = u_phone_ent.get().strip()
        tg = u_tg_ent.get().strip() or None
        role_val = u_role_combo.get().strip() or "librarian"
        pwd = u_pwd_ent.get().strip() or None

        if not uname:
            messagebox.showwarning("خطا", "لطفاً نام کاربری را وارد کنید!", parent=popup)
            u_name_ent.focus()
            return
        if not phone:
            messagebox.showwarning("خطا", "لطفاً شماره تلفن را وارد کنید!", parent=popup)
            u_phone_ent.focus()
            return

        norm_phone = normalize_phone_number(phone)
        if len(norm_phone) != 11 or not norm_phone.startswith("09"):
            messagebox.showerror("خطا", "فرمت شماره تلفن نامعتبر است!\nمثال: 09123456789", parent=popup)
            u_phone_ent.focus()
            return

        success, msg, _ = create_user(
            username=uname,
            phone_number=norm_phone,
            password=pwd,
            role=role_val,
            telegram_chat_id=tg,
            is_active=True,
            database_path=db_p,
        )

        if success:
            messagebox.showinfo("موفق", msg, parent=popup)
            popup.destroy()
            search_users()
        else:
            messagebox.showerror("خطا", msg, parent=popup)

    btn_f = ctk.CTkFrame(popup, fg_color="transparent")
    btn_f.pack(pady=20, padx=20, fill=tk.X)
    btn_save = create_icon_button(
        btn_f,
        text=" ثبت کاربر ",
        icon_name="check",
        command=do_create_user,
        font=FONT_BOLD,
        fg_color="#16a34a",
        hover_color="#15803d",
        width=120,
    )
    btn_save.pack(side=tk.RIGHT, padx=5)
    btn_cancel = create_icon_button(
        btn_f,
        text=" انصراف ",
        icon_name="x",
        command=popup.destroy,
        font=FONT_NORMAL,
        fg_color="transparent",
        hover_color=("#e2e8f0", "#1e293b"),
        width=90,
    )
    btn_cancel.pack(side=tk.LEFT, padx=5)


def open_edit_user_popup(user_id: int | None = None):
    if not current_user or str(current_user.get("role", "")).strip().lower() not in (
        "super admin",
        "superadmin",
        "admin",
    ):
        messagebox.showerror("عدم دسترسی", "فقط نقش مدیر یا سرپرست مجاز به ویرایش کاربران است.", parent=root)
        return

    if user_id is None:
        selected = users_tree.selection()
        if not selected:
            messagebox.showinfo("راهنما", "لطفاً ابتدا یک کاربر را از جدول انتخاب کنید.", parent=root)
            return
        vals = users_tree.item(selected[0], "values")
        if not vals or str(vals[0]).startswith("❌"):
            return
        id_idx = user_columns.index("id") if "id" in user_columns else 0
        try:
            user_id = int(vals[id_idx])
        except (ValueError, IndexError):
            return

    conn = get_db_connection(db_p)
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM auth_users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            messagebox.showerror("خطا", "کاربر در سامانه یافت نشد.", parent=root)
            return
        u_data = dict(row)
    finally:
        conn.close()

    popup = ctk.CTkToplevel(root)
    curr_uname = str(u_data.get("username", ""))
    popup.title(f"ویرایش کاربر ({curr_uname})")
    popup.geometry("450x570")
    popup.resizable(False, False)
    if os.path.exists(icon_p):
        try:
            popup.iconbitmap(icon_p)
        except Exception:
            pass

    popup.transient(root)
    popup.grab_set()

    root.update_idletasks()
    rx = root.winfo_rootx()
    ry = root.winfo_rooty()
    rw = root.winfo_width()
    rh = root.winfo_height()
    px = max(50, rx + (rw - 450) // 2)
    py = max(50, ry + (rh - 570) // 2)
    popup.geometry(f"+{px}+{py}")

    header_f = ctk.CTkFrame(popup, fg_color="transparent")
    header_f.pack(fill=tk.X, padx=20, pady=(15, 6))
    ctk.CTkLabel(header_f, text="ویرایش مشخصات کاربر سامانه", font=FONT_TITLE, anchor="center").pack(fill=tk.X)
    ctk.CTkLabel(
        header_f,
        text=f"شناسه کاربری: #{user_id}",
        font=FONT_SMALL,
        text_color="#94a3b8",
        anchor="center",
    ).pack(fill=tk.X, pady=(2, 0))

    card_f = ctk.CTkFrame(
        popup,
        corner_radius=10,
        border_width=1,
        border_color=("#cbd5e1", "#334155"),
        fg_color=("#ffffff", "#1e293b"),
    )
    card_f.pack(fill=tk.X, padx=20, pady=(4, 10))

    can_edit_creds = is_super_admin(current_user)

    # Row 1: Username
    r1 = ctk.CTkFrame(card_f, fg_color="transparent")
    r1.pack(fill=tk.X, padx=14, pady=(12, 4))
    ctk.CTkLabel(r1, text="نام کاربری:", font=FONT_NORMAL, width=115, anchor="e").pack(side=tk.RIGHT, padx=(4, 0))
    u_name_ent = ctk.CTkEntry(r1, font=FONT_NORMAL, justify="right", height=32)
    u_name_ent.pack(side=tk.RIGHT, fill=tk.X, expand=True)
    u_name_ent.insert(0, curr_uname)
    if not can_edit_creds:
        u_name_ent.configure(state="disabled")

    # Row 2: Phone
    r2 = ctk.CTkFrame(card_f, fg_color="transparent")
    r2.pack(fill=tk.X, padx=14, pady=4)
    ctk.CTkLabel(r2, text="شماره تلفن:", font=FONT_NORMAL, width=115, anchor="e").pack(side=tk.RIGHT, padx=(4, 0))
    u_phone_ent = ctk.CTkEntry(r2, font=FONT_NORMAL, justify="right", height=32)
    u_phone_ent.pack(side=tk.RIGHT, fill=tk.X, expand=True)
    u_phone_ent.insert(0, str(u_data.get("phone_number", "")))
    if not can_edit_creds:
        u_phone_ent.configure(state="disabled")

    if not can_edit_creds:
        note_cred = ctk.CTkFrame(card_f, fg_color="transparent")
        note_cred.pack(fill=tk.X, padx=14, pady=(0, 6))
        ctk.CTkLabel(note_cred, text="", image=get_icon("lock", size=(13, 13)), width=16).pack(
            side=tk.RIGHT, padx=(2, 0)
        )
        ctk.CTkLabel(
            note_cred,
            text="ویرایش نام کاربری و شماره همراه منحصراً با دسترسی مدیر ارشد امکان‌پذیر است.",
            font=FONT_SMALL,
            text_color=("#64748b", "#94a3b8"),
            anchor="e",
        ).pack(side=tk.RIGHT, fill=tk.X, expand=True)

    # Row 3: Role
    r3 = ctk.CTkFrame(card_f, fg_color="transparent")
    r3.pack(fill=tk.X, padx=14, pady=4)
    ctk.CTkLabel(r3, text="نقش کاربر:", font=FONT_NORMAL, width=115, anchor="e").pack(side=tk.RIGHT, padx=(4, 0))
    available_roles = (
        ["super admin", "admin", "librarian", "user"] if can_edit_creds else ["admin", "librarian", "user"]
    )
    u_role_combo = ctk.CTkOptionMenu(
        r3,
        font=FONT_NORMAL,
        values=available_roles,
        height=32,
    )
    curr_role = str(u_data.get("role", "librarian")).strip().lower()
    u_role_combo.set(curr_role if curr_role in available_roles else "librarian")
    u_role_combo.pack(side=tk.RIGHT, fill=tk.X, expand=True)

    # Row 4: Telegram chat ID
    r4 = ctk.CTkFrame(card_f, fg_color="transparent")
    r4.pack(fill=tk.X, padx=14, pady=4)
    ctk.CTkLabel(r4, text="شناسه تلگرام:", font=FONT_NORMAL, width=115, anchor="e").pack(side=tk.RIGHT, padx=(4, 0))
    u_tg_ent = ctk.CTkEntry(r4, font=FONT_NORMAL, justify="right", height=32, placeholder_text="اختیاری")
    u_tg_ent.pack(side=tk.RIGHT, fill=tk.X, expand=True)
    if u_data.get("telegram_chat_id"):
        u_tg_ent.insert(0, str(u_data.get("telegram_chat_id", "")))

    # Row 5: Active Status Switch
    r5 = ctk.CTkFrame(card_f, fg_color="transparent")
    r5.pack(fill=tk.X, padx=14, pady=4)
    ctk.CTkLabel(r5, text="وضعیت حساب:", font=FONT_NORMAL, width=115, anchor="e").pack(side=tk.RIGHT, padx=(4, 0))
    var_active = tk.BooleanVar(value=bool(u_data.get("is_active", 1)))
    sw_active = ctk.CTkSwitch(
        r5,
        text="حساب کاربری فعال است",
        variable=var_active,
        font=FONT_NORMAL,
    )
    sw_active.pack(side=tk.RIGHT, padx=4)

    # Row 6: Password
    r6 = ctk.CTkFrame(card_f, fg_color="transparent")
    r6.pack(fill=tk.X, padx=14, pady=(4, 12))
    ctk.CTkLabel(r6, text="رمز عبور جدید:", font=FONT_NORMAL, width=115, anchor="e").pack(side=tk.RIGHT, padx=(4, 0))
    pwd_container = ctk.CTkFrame(r6, fg_color="transparent")
    pwd_container.pack(side=tk.RIGHT, fill=tk.X, expand=True)

    u_pwd_ent = ctk.CTkEntry(
        pwd_container,
        font=FONT_NORMAL,
        justify="right",
        height=32,
        show="*",
        placeholder_text="در صورت عدم تغییر خالی بگذارید",
    )
    u_pwd_ent.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0))

    icon_eye = get_icon("eye", size=(16, 16))
    icon_eye_off = get_icon("eye-off", size=(16, 16))

    def toggle_user_pwd_visibility():
        if u_pwd_ent.cget("show") == "*":
            u_pwd_ent.configure(show="")
            btn_pwd_eye.configure(image=icon_eye_off)
        else:
            u_pwd_ent.configure(show="*")
            btn_pwd_eye.configure(image=icon_eye)

    btn_pwd_eye = ctk.CTkButton(
        pwd_container,
        text="",
        image=icon_eye,
        width=34,
        height=32,
        fg_color=("#e2e8f0", "#334155"),
        hover_color=("#cbd5e1", "#475569"),
        command=toggle_user_pwd_visibility,
    )
    btn_pwd_eye.pack(side=tk.LEFT)

    def do_update_user():
        if can_edit_creds:
            uname = u_name_ent.get().strip()
            phone = u_phone_ent.get().strip()
            if not uname:
                messagebox.showwarning("خطا", "لطفاً نام کاربری را وارد کنید!", parent=popup)
                u_name_ent.focus()
                return
            if not phone:
                messagebox.showwarning("خطا", "لطفاً شماره تلفن را وارد کنید!", parent=popup)
                u_phone_ent.focus()
                return

            norm_phone = normalize_phone_number(phone)
            if len(norm_phone) != 11 or not norm_phone.startswith("09"):
                messagebox.showerror("خطا", "فرمت شماره تلفن نامعتبر است!\nمثال: 09123456789", parent=popup)
                u_phone_ent.focus()
                return
        else:
            uname = str(u_data.get("username", ""))
            phone = str(u_data.get("phone_number", ""))
            norm_phone = normalize_phone_number(phone)

        tg = u_tg_ent.get().strip() or None
        role_val = u_role_combo.get().strip() or "librarian"
        pwd = u_pwd_ent.get().strip() or None
        act_val = var_active.get()

        if pwd and len(pwd) < 4:
            messagebox.showwarning("خطا", "رمز عبور جدید باید حداقل ۴ کاراکتر باشد!", parent=popup)
            u_pwd_ent.focus()
            return

        success, msg, updated_user = update_user(
            user_id=user_id,
            username=uname,
            phone_number=norm_phone,
            password=pwd,
            role=role_val,
            telegram_chat_id=tg,
            is_active=act_val,
            database_path=db_p,
        )

        if success:
            global current_user
            if current_user and current_user.get("id") == user_id and updated_user:
                current_user = updated_user
                u_role_str = tr(str(current_user.get("role", "")))
                u_name_str = str(current_user.get("username", ""))
                lbl_user_badge.configure(text=f"{u_name_str} ({u_role_str})")

            messagebox.showinfo("موفق", msg, parent=popup)
            popup.destroy()
            search_users()
        else:
            messagebox.showerror("خطا", msg, parent=popup)

    btn_f = ctk.CTkFrame(popup, fg_color="transparent")
    btn_f.pack(fill=tk.X, padx=20, pady=(6, 12))

    btn_save = create_icon_button(
        btn_f,
        text=" ذخیره تغییرات ",
        icon_name="check",
        command=do_update_user,
        font=FONT_BOLD,
        fg_color="#16a34a",
        hover_color="#15803d",
        height=34,
        width=130,
    )
    btn_save.pack(side=tk.RIGHT, padx=5)

    btn_cancel = create_icon_button(
        btn_f,
        text=" انصراف ",
        icon_name="x",
        command=popup.destroy,
        font=FONT_NORMAL,
        fg_color="transparent",
        hover_color=("#e2e8f0", "#1e293b"),
        height=34,
        width=90,
    )
    btn_cancel.pack(side=tk.LEFT, padx=5)


add_user_btn.configure(command=open_create_user_popup)
edit_user_btn.configure(command=open_edit_user_popup)
users_tree.bind("<Double-Button-1>", lambda e: open_edit_user_popup())

users_context_menu = tk.Menu(root, tearoff=0)
users_context_menu.add_command(label="ویرایش مشخصات کاربر...", command=open_edit_user_popup)
users_context_menu.add_separator()
users_context_menu.add_command(label="حذف کاربر", command=lambda: users_tree.event_generate("<Delete>"))


def show_users_context_menu(event):
    row_id = users_tree.identify_row(event.y)
    if row_id:
        users_tree.selection_set(row_id)
        users_context_menu.tk_popup(event.x_root, event.y_root)


users_tree.bind("<Button-3>", show_users_context_menu)

users_search_after_id = None


def on_users_key_release(event):
    global users_search_after_id
    if users_search_after_id is not None:
        root.after_cancel(users_search_after_id)
    users_search_after_id = root.after(200, search_users)


entry_search_users.bind("<KeyRelease>", on_users_key_release)
entry_search_users.bind("<Return>", search_users)

bind_table_delete(
    users_tree,
    "auth_users",
    id_col_index=user_columns.index("id") if "id" in user_columns else 0,
    on_deleted=search_users,
)

# ==================== جدول امانات (Loans Management) ====================
new_tabel_name = "loans"
cursor_loan = sqlite3.connect(db_p).cursor()
cursor_loan.execute(f'PRAGMA table_info("{new_tabel_name}")')
loan_column: list[str] = [str(row[1]) for row in cursor_loan.fetchall()]
cursor_loan.connection.close()

borrow_date = "borrow_date"
borrow_index = loan_column.index(borrow_date) if borrow_date in loan_column else -1
return_date = "return_date"
return_index = loan_column.index(return_date) if return_date in loan_column else -1
borrowed_index = loan_column.index("borrowed") if "borrowed" in loan_column else -1

loans_filter_settings = {
    "column": "all",
    "match_mode": "contains",
    "status": "all",
    "sort_col": "duration",
    "sort_dir": "ASC",
    "from_date": "",
    "to_date": "",
}

search_bar_frame_loans = ctk.CTkFrame(tabel_frame, corner_radius=8, height=48)
search_bar_frame_loans.pack(fill=tk.X, padx=10, pady=(10, 6))
search_bar_frame_loans.columnconfigure(4, weight=1)

sub_btn_loans = create_icon_button(search_bar_frame_loans, text=" جستجو ", icon_name="search", font=FONT_BOLD, width=85)
sub_btn_loans.grid(row=0, column=0, padx=(8, 4), pady=6)

filter_btn_loans = create_icon_button(
    search_bar_frame_loans, text=" فیلترها ", icon_name="filter", font=FONT_NORMAL, width=85
)
filter_btn_loans.grid(row=0, column=1, padx=4, pady=6)

add_loan_btn = create_icon_button(
    search_bar_frame_loans,
    text=" ثبت امانت جدید ",
    icon_name="arrow-right-left",
    font=FONT_NORMAL,
    fg_color="#2563eb",
    hover_color="#1d4ed8",
    width=125,
)
add_loan_btn.grid(row=0, column=2, padx=4, pady=6)

return_loan_btn = create_icon_button(
    search_bar_frame_loans,
    text=" ثبت بازگشت کتاب ",
    icon_name="check",
    font=FONT_BOLD,
    fg_color="#16a34a",
    hover_color="#15803d",
    width=135,
    command=lambda: do_return_selected_loan(),
)
return_loan_btn.grid(row=0, column=3, padx=4, pady=6)

entry_search_loans = ctk.CTkEntry(
    search_bar_frame_loans,
    placeholder_text="جستجو در امانات (نام عضو، کتاب و ...)",
    font=FONT_NORMAL,
    justify="right",
    height=36,
)
entry_search_loans.grid(row=0, column=4, sticky="ew", padx=(4, 8), pady=6)

loans_tree_frame = ctk.CTkFrame(tabel_frame, corner_radius=8)
loans_tree_frame.pack(padx=10, pady=(0, 10), fill=tk.BOTH, expand=True)

scrollbar_2 = ctk.CTkScrollbar(loans_tree_frame)
scrollbar_2.pack(side=tk.LEFT, fill=tk.Y, padx=(4, 0), pady=4)

loans_tree = ttk.Treeview(
    loans_tree_frame, yscrollcommand=scrollbar_2.set, columns=loan_column, show="headings", height=15
)
scrollbar_2.configure(command=loans_tree.yview)
for col in loan_column:
    loans_tree.heading(col, text=tr(col), anchor=tk.CENTER)
    loans_tree.column(col, anchor=tk.CENTER)
col_mem_display = "member_id" if "member_id" in loan_column else "member_name"
loans_tree["displaycolumns"] = rtl_display_order(
    loan_column, ["id", col_mem_display, "book_id", "borrow_date", "return_date", "borrowed"]
)
loans_tree.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(4, 8), pady=4)


def do_return_selected_loan():
    selected = loans_tree.selection()
    if not selected:
        messagebox.showwarning("هشدار", "لطفاً ابتدا یک رکورد امانت را از جدول انتخاب کنید!", parent=root)
        return

    item_id = selected[0]
    values = loans_tree.item(item_id, "values")
    if not values or str(values[0]).startswith("❌"):
        return

    id_idx = loan_column.index("id") if "id" in loan_column else 0
    loan_id = values[id_idx]

    b_idx = loan_column.index("book_id") if "book_id" in loan_column else -1
    book_title = values[b_idx] if b_idx != -1 and b_idx < len(values) else ""

    m_idx = (
        loan_column.index("member_id")
        if "member_id" in loan_column
        else (loan_column.index("member_name") if "member_name" in loan_column else -1)
    )
    member_name = values[m_idx] if m_idx != -1 and m_idx < len(values) else ""

    borrowed_idx = loan_column.index("borrowed") if "borrowed" in loan_column else -1
    current_status = values[borrowed_idx] if borrowed_idx != -1 and borrowed_idx < len(values) else ""

    if current_status == "بازگردانده شده":
        messagebox.showinfo("اطلاع", "این کتاب قبلاً بازگردانده شده است.", parent=root)
        return

    confirm = messagebox.askyesno(
        "ثبت بازگشت کتاب",
        f"آیا از ثبت بازگشت کتاب «{book_title}» امانت داده شده به «{member_name}» اطمینان دارید؟",
        parent=root,
    )
    if not confirm:
        return

    conn = get_db_connection(db_p)
    try:
        cur = conn.cursor()
        cur.execute("UPDATE loans SET borrowed = 0 WHERE id = ?", (loan_id,))
        conn.commit()
        notification_engine.show("ثبت بازگشت کتاب", f"کتاب «{book_title}» با موفقیت بازگردانده شد.")
        messagebox.showinfo("موفقیت", f"بازگشت کتاب «{book_title}» با موفقیت ثبت شد.", parent=root)
        search_loans()
        search()
    except sqlite3.Error as e:
        messagebox.showerror("خطا", f"خطا در ثبت بازگشت کتاب: {e}", parent=root)
    finally:
        conn.close()


def format_loan_row(row):
    row_list = list(row)
    if return_index != -1 and return_index < len(row_list) and row_list[return_index]:
        try:
            miladi_date_str = str(row_list[return_index])
            g_date = datetime.datetime.strptime(miladi_date_str, "%Y-%m-%d").date()
            shamsi_date = jdatetime.date.fromgregorian(date=g_date)
            row_list[return_index] = shamsi_date.strftime("%Y-%m-%d")
        except ValueError:
            pass
    if borrow_index != -1 and borrow_index < len(row_list) and row_list[borrow_index]:
        try:
            date_str = str(row_list[borrow_index])
            if "-" in date_str:
                parts = [int(p) for p in date_str.split("-")]
                if parts[0] > 1900:
                    g_date = datetime.date(parts[0], parts[1], parts[2])
                    row_list[borrow_index] = jdatetime.date.fromgregorian(date=g_date).strftime("%Y-%m-%d")
        except Exception:
            pass
    if borrowed_index != -1 and borrowed_index < len(row_list):
        val = row_list[borrowed_index]
        if val == 1 or val == "1" or val is True:
            row_list[borrowed_index] = "در امانت"
        elif val == 0 or val == "0" or val is False:
            row_list[borrowed_index] = "بازگردانده شده"
    return tuple(row_list)


def update_loans_filter_indicator():
    is_custom = (
        loans_filter_settings["column"] != "all"
        or loans_filter_settings["match_mode"] != "contains"
        or loans_filter_settings["status"] != "all"
        or loans_filter_settings["sort_col"] != "duration"
        or loans_filter_settings["sort_dir"] != "ASC"
        or bool(loans_filter_settings.get("from_date"))
        or bool(loans_filter_settings.get("to_date"))
    )
    if is_custom:
        filter_btn_loans.configure(text=" فیلترها (فعال) ", fg_color="#2563eb")
    else:
        filter_btn_loans.configure(text=" فیلترها ", fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"])


def search_loans(event=None):
    search_value = entry_search_loans.get().strip()
    loans_tree.delete(*loans_tree.get_children())

    temp_conn = get_db_connection(db_p)
    try:
        temp_cursor = temp_conn.cursor()

        where_conditions: list[str] = []
        params: list[str] = []

        if search_value:
            selected_col = loans_filter_settings.get("column", "all")
            match_mode = loans_filter_settings.get("match_mode", "contains")

            if match_mode == "exact":
                pattern = search_value
                op = "="
            elif match_mode == "startswith":
                pattern = f"{search_value}%"
                op = "LIKE"
            else:
                pattern = f"%{search_value}%"
                op = "LIKE"

            if selected_col == "all":
                where_conditions.append(
                    "(COALESCE(m.username, '') "
                    + op
                    + " ? OR COALESCE(b.title, '') "
                    + op
                    + " ? OR CAST(l.id AS TEXT) "
                    + op
                    + " ?)"
                )
                params.extend([pattern, pattern, pattern])
            elif selected_col in ("member_id", "member_name"):
                where_conditions.append(f"COALESCE(m.username, '') {op} ?")
                params.append(pattern)
            elif selected_col == "book_id":
                where_conditions.append(f"COALESCE(b.title, '') {op} ?")
                params.append(pattern)
            elif selected_col in loan_column:
                where_conditions.append(f"l.`{selected_col}` {op} ?")
                params.append(pattern)

        status = loans_filter_settings.get("status", "all")
        if status == "borrowed":
            where_conditions.append("(l.borrowed = 1 OR l.borrowed = '1')")
        elif status == "returned":
            where_conditions.append("(l.borrowed = 0 OR l.borrowed = '0' OR l.borrowed IS NULL)")

        from_d = loans_filter_settings.get("from_date", "").strip()
        if from_d:
            from_greg = jalali_to_gregorian_str(from_d)
            if from_greg:
                where_conditions.append("l.borrow_date >= ?")
                params.append(from_greg)

        to_d = loans_filter_settings.get("to_date", "").strip()
        if to_d:
            to_greg = jalali_to_gregorian_str(to_d)
            if to_greg:
                where_conditions.append("l.borrow_date <= ?")
                params.append(to_greg)

        cols_select = []
        for col in loan_column:
            if col in ("member_id", "member_name"):
                cols_select.append(f"COALESCE(m.username, CAST(l.`{col}` AS TEXT)) AS `{col}`")
            elif col == "book_id":
                cols_select.append("COALESCE(b.title, CAST(l.book_id AS TEXT)) AS book_id")
            else:
                cols_select.append(f"l.`{col}`")

        mem_join_col = "member_id" if "member_id" in loan_column else "member_name"
        query = (
            f"SELECT {', '.join(cols_select)} FROM loans l "
            f"LEFT JOIN members m ON (l.`{mem_join_col}` = m.id OR CAST(l.`{mem_join_col}` AS TEXT) = m.username) "
            f"LEFT JOIN books b ON (l.book_id = b.id OR l.book_id = b.title)"
        )
        if where_conditions:
            query += " WHERE " + " AND ".join(where_conditions)

        sort_col = loans_filter_settings.get("sort_col", "duration")
        sort_dir = loans_filter_settings.get("sort_dir", "ASC")
        if sort_dir not in ("ASC", "DESC"):
            sort_dir = "ASC"

        if sort_col == "duration":
            query += f" ORDER BY (julianday(l.`return_date`) - julianday(l.`borrow_date`)) {sort_dir}"
        elif sort_col in ("member_id", "member_name"):
            query += f" ORDER BY m.username {sort_dir}"
        elif sort_col == "book_id":
            query += f" ORDER BY b.title {sort_dir}"
        else:
            if sort_col not in loan_column:
                sort_col = "id"
            query += f" ORDER BY l.`{sort_col}` {sort_dir}"

        temp_cursor.execute(query, tuple(params))
        results = temp_cursor.fetchall()

        if results:
            for row in results:
                loans_tree.insert("", tk.END, values=format_loan_row(row))
        else:
            loans_tree.insert("", tk.END, values=("❌ نتیجه‌ای یافت نشد!",) + ("",) * (len(loan_column) - 1))

    except Exception as e:
        messagebox.showerror("خطا", f"خطا در جستجوی امانات: {str(e)}")
    finally:
        temp_conn.close()


refresh_loans_table = search_loans
sub_btn_loans.configure(command=search_loans)


def open_loans_filter_popup():
    popup = ctk.CTkToplevel(root)
    popup.title("فیلترهای جدول امانات")
    popup.geometry("460x500")
    popup.resizable(False, False)
    if os.path.exists(icon_p):
        try:
            popup.iconbitmap(icon_p)
        except Exception:
            pass

    popup.transient(root)
    popup.grab_set()

    root.update_idletasks()
    rx = root.winfo_rootx()
    ry = root.winfo_rooty()
    rw = root.winfo_width()
    rh = root.winfo_height()
    px = max(50, rx + (rw - 460) // 2)
    py = max(50, ry + (rh - 500) // 2)
    popup.geometry(f"+{px}+{py}")

    col_var = tk.StringVar(value=loans_filter_settings["column"])
    match_var = tk.StringVar(value=loans_filter_settings["match_mode"])
    status_var = tk.StringVar(value=loans_filter_settings["status"])
    sort_col_var = tk.StringVar(value=loans_filter_settings["sort_col"])
    sort_dir_var = tk.StringVar(value=loans_filter_settings["sort_dir"])

    group_col = ctk.CTkFrame(popup, corner_radius=8)
    group_col.pack(fill=tk.X, padx=15, pady=(10, 4))
    ctk.CTkLabel(group_col, text="جستجو در ستون", font=FONT_BOLD, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))
    col_frame = ctk.CTkFrame(group_col, fg_color="transparent")
    col_frame.pack(fill=tk.X, padx=6, pady=(0, 6))
    rb_all = ctk.CTkRadioButton(col_frame, text="همه ستون‌ها", variable=col_var, value="all", font=FONT_NORMAL)
    rb_all.pack(side=tk.RIGHT, padx=4)
    mem_filter_col = "member_id" if "member_id" in loan_column else "member_name"
    for col in [mem_filter_col, "book_id", "id"]:
        rb = ctk.CTkRadioButton(col_frame, text=tr(col), variable=col_var, value=col, font=FONT_NORMAL)
        rb.pack(side=tk.RIGHT, padx=4)

    group_mode = ctk.CTkFrame(popup, corner_radius=8)
    group_mode.pack(fill=tk.X, padx=15, pady=4)
    ctk.CTkLabel(group_mode, text="نوع تطابق جستجو", font=FONT_BOLD, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))
    mode_frame = ctk.CTkFrame(group_mode, fg_color="transparent")
    mode_frame.pack(fill=tk.X, padx=6, pady=(0, 6))
    rb_contains = ctk.CTkRadioButton(
        mode_frame, text="شامل عبارت", variable=match_var, value="contains", font=FONT_NORMAL
    )
    rb_contains.pack(side=tk.RIGHT, padx=8)
    rb_starts = ctk.CTkRadioButton(
        mode_frame, text="شروع با عبارت", variable=match_var, value="startswith", font=FONT_NORMAL
    )
    rb_starts.pack(side=tk.RIGHT, padx=8)
    rb_exact = ctk.CTkRadioButton(mode_frame, text="مطابقت دقیق", variable=match_var, value="exact", font=FONT_NORMAL)
    rb_exact.pack(side=tk.RIGHT, padx=8)

    group_status = ctk.CTkFrame(popup, corner_radius=8)
    group_status.pack(fill=tk.X, padx=15, pady=4)
    ctk.CTkLabel(group_status, text="وضعیت امانت", font=FONT_BOLD, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))
    status_frame = ctk.CTkFrame(group_status, fg_color="transparent")
    status_frame.pack(fill=tk.X, padx=6, pady=(0, 6))
    rb_st_all = ctk.CTkRadioButton(status_frame, text="همه امانات", variable=status_var, value="all", font=FONT_NORMAL)
    rb_st_all.pack(side=tk.RIGHT, padx=6)
    rb_st_borrowed = ctk.CTkRadioButton(
        status_frame, text="فقط در امانت", variable=status_var, value="borrowed", font=FONT_NORMAL
    )
    rb_st_borrowed.pack(side=tk.RIGHT, padx=6)
    rb_st_returned = ctk.CTkRadioButton(
        status_frame, text="فقط بازگردانده شده", variable=status_var, value="returned", font=FONT_NORMAL
    )
    rb_st_returned.pack(side=tk.RIGHT, padx=6)

    # Date range filter card
    group_date = ctk.CTkFrame(popup, corner_radius=8)
    group_date.pack(fill=tk.X, padx=15, pady=4)
    ctk.CTkLabel(group_date, text="بازه تاریخ امانت (شمسی)", font=FONT_BOLD, anchor="e").pack(
        fill=tk.X, padx=10, pady=(6, 2)
    )
    date_frame = ctk.CTkFrame(group_date, fg_color="transparent")
    date_frame.pack(fill=tk.X, padx=6, pady=(0, 6))

    ctk.CTkLabel(date_frame, text="از:", font=FONT_NORMAL).pack(side=tk.RIGHT, padx=(4, 2))
    ent_from_date = ctk.CTkEntry(
        date_frame, width=110, height=30, font=FONT_NORMAL, justify="center", placeholder_text="YYYY-MM-DD"
    )
    ent_from_date.insert(0, loans_filter_settings.get("from_date", ""))
    btn_from_cal = create_date_picker_button(
        date_frame,
        entry_widget=ent_from_date,
        title="انتخاب تاریخ شروع امانت",
        icon_path=icon_p,
        width=30,
        height=30,
    )
    btn_from_cal.pack(side=tk.RIGHT, padx=2)
    ent_from_date.pack(side=tk.RIGHT, padx=(2, 10))

    ctk.CTkLabel(date_frame, text="تا:", font=FONT_NORMAL).pack(side=tk.RIGHT, padx=(4, 2))
    ent_to_date = ctk.CTkEntry(
        date_frame, width=110, height=30, font=FONT_NORMAL, justify="center", placeholder_text="YYYY-MM-DD"
    )
    ent_to_date.insert(0, loans_filter_settings.get("to_date", ""))
    btn_to_cal = create_date_picker_button(
        date_frame,
        entry_widget=ent_to_date,
        title="انتخاب تاریخ پایان امانت",
        icon_path=icon_p,
        width=30,
        height=30,
    )
    btn_to_cal.pack(side=tk.RIGHT, padx=2)
    ent_to_date.pack(side=tk.RIGHT, padx=2)

    group_sort = ctk.CTkFrame(popup, corner_radius=8)
    group_sort.pack(fill=tk.X, padx=15, pady=4)
    ctk.CTkLabel(group_sort, text="مرتب‌سازی نتایج", font=FONT_BOLD, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))
    sort_frame = ctk.CTkFrame(group_sort, fg_color="transparent")
    sort_frame.pack(fill=tk.X, padx=6, pady=(0, 6))

    ctk.CTkLabel(sort_frame, text="بر اساس:", font=FONT_NORMAL).pack(side=tk.RIGHT, padx=(5, 0))
    sort_options = {
        "مدت امانت": "duration",
        "تاریخ بازگشت": "return_date",
        "تاریخ امانت": "borrow_date",
        "نام کاربر": mem_filter_col,
        "نام کتاب": "book_id",
        "شناسه": "id",
    }
    rev_sort_options = {v: k for k, v in sort_options.items()}

    sort_col_cb = ctk.CTkOptionMenu(
        sort_frame,
        width=130,
        font=FONT_NORMAL,
        values=list(sort_options.keys()),
    )
    current_sort_label = rev_sort_options.get(sort_col_var.get(), "مدت امانت")
    sort_col_cb.set(current_sort_label)
    sort_col_cb.pack(side=tk.RIGHT, padx=5)

    ctk.CTkLabel(sort_frame, text="ترتیب:", font=FONT_NORMAL).pack(side=tk.RIGHT, padx=(12, 0))
    sort_dir_cb = ctk.CTkOptionMenu(sort_frame, width=100, font=FONT_NORMAL, values=["صعودی", "نزولی"])
    sort_dir_cb.set("صعودی" if sort_dir_var.get() == "ASC" else "نزولی")
    sort_dir_cb.pack(side=tk.RIGHT, padx=5)

    action_frame = ctk.CTkFrame(popup, fg_color="transparent")
    action_frame.pack(fill=tk.X, padx=15, pady=(10, 8))

    def apply_loans_filters():
        loans_filter_settings["column"] = col_var.get()
        loans_filter_settings["match_mode"] = match_var.get()
        loans_filter_settings["status"] = status_var.get()
        loans_filter_settings["sort_col"] = sort_options.get(sort_col_cb.get(), "duration")
        loans_filter_settings["sort_dir"] = "ASC" if sort_dir_cb.get() == "صعودی" else "DESC"
        loans_filter_settings["from_date"] = ent_from_date.get().strip()
        loans_filter_settings["to_date"] = ent_to_date.get().strip()

        update_loans_filter_indicator()
        popup.destroy()
        search_loans()

    def reset_loans_filters():
        loans_filter_settings["column"] = "all"
        loans_filter_settings["match_mode"] = "contains"
        loans_filter_settings["status"] = "all"
        loans_filter_settings["sort_col"] = "duration"
        loans_filter_settings["sort_dir"] = "ASC"
        loans_filter_settings["from_date"] = ""
        loans_filter_settings["to_date"] = ""

        update_loans_filter_indicator()
        popup.destroy()
        search_loans()

    btn_apply = create_icon_button(
        action_frame,
        text=" اعمال فیلتر ",
        icon_name="check",
        font=FONT_BOLD,
        fg_color="#2563eb",
        hover_color="#1d4ed8",
        command=apply_loans_filters,
    )
    btn_apply.pack(side=tk.RIGHT, padx=4)

    btn_reset = create_icon_button(
        action_frame,
        text=" تنظیم مجدد ",
        icon_name="rotate-ccw",
        font=FONT_NORMAL,
        fg_color="transparent",
        hover_color=("#e2e8f0", "#1e293b"),
        command=reset_loans_filters,
    )
    btn_reset.pack(side=tk.RIGHT, padx=4)

    btn_cancel = create_icon_button(
        action_frame,
        text=" انصراف ",
        icon_name="x",
        font=FONT_NORMAL,
        fg_color="transparent",
        hover_color=("#e2e8f0", "#1e293b"),
        command=popup.destroy,
    )
    btn_cancel.pack(side=tk.LEFT, padx=4)


filter_btn_loans.configure(command=open_loans_filter_popup)


def open_add_loan_popup(initial_book_title=""):
    popup = ctk.CTkToplevel(root)
    popup.title("ثبت امانت کتاب")
    popup.geometry("480x640")
    popup.resizable(False, False)
    if os.path.exists(icon_p):
        try:
            popup.iconbitmap(icon_p)
        except Exception:
            pass

    popup.transient(root)
    popup.grab_set()

    root.update_idletasks()
    rx = root.winfo_rootx()
    ry = root.winfo_rooty()
    rw = root.winfo_width()
    rh = root.winfo_height()
    px = max(50, rx + (rw - 480) // 2)
    py = max(50, ry + (rh - 640) // 2)
    popup.geometry(f"+{px}+{py}")

    ctk.CTkLabel(popup, text="ثبت اطلاعات امانت کتاب", font=FONT_TITLE).pack(pady=(12, 6))

    # 1. Member selection
    ctk.CTkLabel(popup, text="نام کاربر (عضو):", font=FONT_NORMAL, anchor="e").pack(fill=tk.X, padx=25, pady=(2, 0))
    member_entry = ctk.CTkEntry(popup, font=FONT_NORMAL, justify="right", height=32)
    member_entry.pack(fill=tk.X, padx=25, pady=2)

    mem_conn = get_db_connection(db_p)
    try:
        mem_cur = mem_conn.cursor()
        try:
            mem_cur.execute("SELECT username FROM members ORDER BY username ASC")
        except sqlite3.OperationalError:
            mem_cur.execute("SELECT member_id FROM members ORDER BY member_id ASC")
        members_data = [row[0] for row in mem_cur.fetchall()]
    finally:
        mem_conn.close()

    mem_listbox = tk.Listbox(
        popup,
        height=3,
        font=(FONT_FAMILY, 9),
        justify="right",
        bg="#242424",
        fg="#f8fafc",
        selectbackground="#1f538d",
        selectforeground="#ffffff",
        relief="flat",
        highlightthickness=1,
        highlightbackground="#374151",
    )
    mem_listbox.pack(fill=tk.X, padx=25, pady=2)
    for item in members_data[:10]:
        mem_listbox.insert(tk.END, item)

    def search_member(e):
        mem_listbox.delete(0, tk.END)
        q = member_entry.get().strip().lower()
        for item in members_data:
            if q in item.lower():
                mem_listbox.insert(tk.END, item)

    def select_member(e):
        if mem_listbox.curselection():
            member_entry.delete(0, tk.END)
            member_entry.insert(0, mem_listbox.get(mem_listbox.curselection()[0]))
            mem_listbox.delete(0, tk.END)

    member_entry.bind("<KeyRelease>", search_member)
    mem_listbox.bind("<Double-Button-1>", select_member)

    # 2. Book selection
    ctk.CTkLabel(popup, text="عنوان کتاب:", font=FONT_NORMAL, anchor="e").pack(fill=tk.X, padx=25, pady=(4, 0))
    book_entry = ctk.CTkEntry(popup, font=FONT_NORMAL, justify="right", height=32)
    book_entry.pack(fill=tk.X, padx=25, pady=2)

    if initial_book_title:
        book_entry.insert(0, initial_book_title)
        book_entry.configure(state="readonly")
    else:
        bk_conn = get_db_connection(db_p)
        try:
            bk_cur = bk_conn.cursor()
            bk_cur.execute("""
                SELECT title FROM books
                WHERE title IS NOT NULL AND title != ''
                  AND id NOT IN (SELECT book_id FROM loans WHERE (borrowed = 1 OR borrowed = '1') AND book_id IS NOT NULL)
                  AND title NOT IN (SELECT book_id FROM loans WHERE (borrowed = 1 OR borrowed = '1') AND book_id IS NOT NULL)
                ORDER BY title ASC
            """)
            books_data = [row[0] for row in bk_cur.fetchall() if row[0]]
        finally:
            bk_conn.close()

        bk_listbox = tk.Listbox(
            popup,
            height=3,
            font=(FONT_FAMILY, 9),
            justify="right",
            bg="#242424",
            fg="#f8fafc",
            selectbackground="#1f538d",
            selectforeground="#ffffff",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#374151",
        )
        bk_listbox.pack(fill=tk.X, padx=25, pady=2)
        for item in books_data[:10]:
            bk_listbox.insert(tk.END, item)

        def search_book(e):
            bk_listbox.delete(0, tk.END)
            q = book_entry.get().strip().lower()
            for item in books_data:
                if q in item.lower():
                    bk_listbox.insert(tk.END, item)

        def select_book(e):
            if bk_listbox.curselection():
                book_entry.delete(0, tk.END)
                book_entry.insert(0, bk_listbox.get(bk_listbox.curselection()[0]))
                bk_listbox.delete(0, tk.END)

        book_entry.bind("<KeyRelease>", search_book)
        bk_listbox.bind("<Double-Button-1>", select_book)

    # 3. Borrow Date
    cur_today = get_today_jalali()
    c_days_10 = cur_today + jdatetime.timedelta(days=10)
    c_days_20 = cur_today + jdatetime.timedelta(days=20)
    c_days_30 = cur_today + jdatetime.timedelta(days=30)

    ctk.CTkLabel(popup, text="تاریخ امانت کتاب (YYYY-MM-DD):", font=FONT_NORMAL, anchor="e").pack(
        fill=tk.X, padx=25, pady=(4, 0)
    )
    row_borrow = ctk.CTkFrame(popup, fg_color="transparent")
    row_borrow.pack(fill=tk.X, padx=25, pady=2)

    borrow_entry = ctk.CTkEntry(row_borrow, font=FONT_NORMAL, justify="right", height=32)
    btn_cal_borrow = create_date_picker_button(
        row_borrow,
        entry_widget=borrow_entry,
        title="انتخاب تاریخ امانت (تقویم شمسی)",
        icon_path=icon_p,
    )
    btn_cal_borrow.pack(side=tk.LEFT, padx=(0, 4))
    borrow_entry.pack(side=tk.RIGHT, fill=tk.X, expand=True)

    var_auto_date = tk.IntVar(value=1)
    borrow_entry.insert(0, str(cur_today))

    def toggle_borrow_date():
        if var_auto_date.get() == 1:
            borrow_entry.delete(0, tk.END)
            borrow_entry.insert(0, str(cur_today))
        else:
            borrow_entry.delete(0, tk.END)

    chk_f = ctk.CTkFrame(popup, fg_color="transparent")
    chk_f.pack(fill=tk.X, padx=25, pady=2)
    ctk.CTkCheckBox(
        chk_f, text="ثبت خودکار تاریخ امروز", variable=var_auto_date, command=toggle_borrow_date, font=FONT_NORMAL
    ).pack(side=tk.RIGHT)

    # 4. Return Date
    ctk.CTkLabel(popup, text="تاریخ بازگشت کتاب (YYYY-MM-DD):", font=FONT_NORMAL, anchor="e").pack(
        fill=tk.X, padx=25, pady=(4, 0)
    )
    row_return = ctk.CTkFrame(popup, fg_color="transparent")
    row_return.pack(fill=tk.X, padx=25, pady=2)

    return_entry = ctk.CTkEntry(row_return, font=FONT_NORMAL, justify="right", height=32)
    btn_cal_return = create_date_picker_button(
        row_return,
        entry_widget=return_entry,
        title="انتخاب تاریخ بازگشت (تقویم شمسی)",
        icon_path=icon_p,
        on_select=lambda d: selected_days.set(""),
    )
    btn_cal_return.pack(side=tk.LEFT, padx=(0, 4))
    return_entry.pack(side=tk.RIGHT, fill=tk.X, expand=True)

    selected_days = tk.StringVar(value="option1")
    return_entry.insert(0, str(c_days_10))

    def on_select_days():
        choice = selected_days.get()
        return_entry.delete(0, tk.END)
        if choice == "option1":
            return_entry.insert(0, str(c_days_10))
        elif choice == "option2":
            return_entry.insert(0, str(c_days_20))
        elif choice == "option3":
            return_entry.insert(0, str(c_days_30))

    days_frame = ctk.CTkFrame(popup, fg_color="transparent")
    days_frame.pack(pady=4)

    rb1 = ctk.CTkRadioButton(
        days_frame, text="10 روز", variable=selected_days, value="option1", command=on_select_days, font=FONT_NORMAL
    )
    rb2 = ctk.CTkRadioButton(
        days_frame, text="20 روز", variable=selected_days, value="option2", command=on_select_days, font=FONT_NORMAL
    )
    rb3 = ctk.CTkRadioButton(
        days_frame, text="30 روز", variable=selected_days, value="option3", command=on_select_days, font=FONT_NORMAL
    )
    rb1.pack(side=tk.RIGHT, padx=10)
    rb2.pack(side=tk.RIGHT, padx=10)
    rb3.pack(side=tk.RIGHT, padx=10)

    def do_insert_loan():
        m_name = member_entry.get().strip()
        b_title = book_entry.get().strip()
        borrow_shamsi = borrow_entry.get().strip()
        return_shamsi = return_entry.get().strip()

        if not m_name:
            messagebox.showwarning("هشدار", "لطفاً نام کاربر را وارد کنید!", parent=popup)
            member_entry.focus()
            return
        if not b_title:
            messagebox.showwarning("هشدار", "لطفاً عنوان کتاب را وارد کنید!", parent=popup)
            book_entry.focus()
            return
        if not borrow_shamsi:
            messagebox.showwarning("هشدار", "لطفاً تاریخ امانت را وارد کنید!", parent=popup)
            borrow_entry.focus()
            return
        if not return_shamsi:
            messagebox.showwarning("هشدار", "لطفاً تاریخ بازگشت را وارد کنید!", parent=popup)
            return_entry.focus()
            return

        j_borrow = parse_jalali_date(borrow_shamsi)
        if not j_borrow:
            messagebox.showerror("خطا", "فرمت تاریخ امانت وارد شده صحیح نیست!\nمثال: 1403-06-20", parent=popup)
            return
        borrow_gregorian = j_borrow.togregorian().strftime("%Y-%m-%d")

        j_return = parse_jalali_date(return_shamsi)
        if not j_return:
            messagebox.showerror("خطا", "فرمت تاریخ بازگشت وارد شده صحیح نیست!\nمثال: 1403-06-30", parent=popup)
            return
        return_gregorian = j_return.togregorian().strftime("%Y-%m-%d")

        if return_gregorian < borrow_gregorian:
            messagebox.showerror("خطا", "تاریخ بازگشت نمی‌تواند پیش از تاریخ امانت باشد!", parent=popup)
            return

        with get_db_connection(db_p) as conn:
            settings = get_all_settings(conn)
        mln = int(settings.get("max_loans", "3"))
        try:
            with get_db_connection(db_p) as conn:
                ins_cur = conn.cursor()

                # 1. Resolve member_id
                try:
                    ins_cur.execute("SELECT id, username FROM members WHERE username = ?", (m_name,))
                except sqlite3.OperationalError:
                    ins_cur.execute("SELECT id, member_id FROM members WHERE member_id = ?", (m_name,))
                m_row = ins_cur.fetchone()
                if not m_row and m_name.isdigit():
                    try:
                        ins_cur.execute("SELECT id, username FROM members WHERE id = ?", (int(m_name),))
                    except sqlite3.OperationalError:
                        ins_cur.execute("SELECT id, member_id FROM members WHERE id = ?", (int(m_name),))
                    m_row = ins_cur.fetchone()

                if not m_row:
                    messagebox.showerror(
                        "خطا",
                        f"عضوی با نام «{m_name}» در فهرست اعضای کتابخانه یافت نشد.\nلطفاً ابتدا از تب «اعضای کتابخانه» او را ثبت کنید.",
                        parent=popup,
                    )
                    member_entry.focus()
                    return

                actual_member_id = m_row[0]
                actual_member_name = m_row[1]

                # 2. Check book_id is actual ID from books table
                actual_book_id = None
                actual_book_title = b_title

                ins_cur.execute("SELECT id, title FROM books WHERE title = ?", (b_title,))
                b_row = ins_cur.fetchone()
                if b_row:
                    actual_book_id = b_row[0]
                    actual_book_title = b_row[1]
                elif b_title.isdigit():
                    ins_cur.execute("SELECT id, title FROM books WHERE id = ?", (int(b_title),))
                    b_row = ins_cur.fetchone()
                    if b_row:
                        actual_book_id = b_row[0]
                        actual_book_title = b_row[1]

                if actual_book_id is None:
                    messagebox.showerror(
                        "خطا",
                        f"کتابی با عنوان یا شناسه «{b_title}» در پایگاه داده کتاب‌ها یافت نشد.",
                        parent=popup,
                    )
                    book_entry.focus()
                    return

                # 3. Check member's active borrowed loans limit
                ins_cur.execute(
                    "SELECT COUNT(*) FROM loans WHERE (member_id = ? OR member_id = ?) AND (borrowed = 1 OR borrowed = '1')",
                    (actual_member_id, str(actual_member_id)),
                )
                current_borrowed = ins_cur.fetchone()[0]
                if current_borrowed >= mln:
                    messagebox.showerror(
                        "خطا",
                        f"کاربر «{actual_member_name}» در حال حاضر {current_borrowed} کتاب به امانت برده.\n"
                        f"حداکثر سقف مجاز امانت همزمان: {mln} کتاب می‌باشد.",
                        parent=popup,
                    )
                    return

                # 4. Check if book is already borrowed
                ins_cur.execute(
                    "SELECT COUNT(*) FROM loans WHERE (book_id = ? OR book_id = ?) AND (borrowed = 1 OR borrowed = '1')",
                    (actual_book_id, str(actual_book_id)),
                )
                if ins_cur.fetchone()[0] > 0:
                    messagebox.showwarning(
                        "امانت کتاب",
                        f"کتاب «{actual_book_title}» در حال حاضر در امانت است و امکان امانت مجدد آن وجود ندارد.",
                        parent=popup,
                    )
                    return

                # 5. Insert loan with actual member_id and actual book_id
                ins_cur.execute(
                    "INSERT INTO loans (member_id, book_id, return_date, borrow_date, borrowed) VALUES (?, ?, ?, ?, 1)",
                    (actual_member_id, actual_book_id, return_gregorian, borrow_gregorian),
                )
                conn.commit()

            notification_engine.show(
                "ثبت موفق امانت", f"کتاب «{actual_book_title}» با موفقیت برای {actual_member_name} ثبت شد."
            )

            messagebox.showinfo("موفقیت", "اطلاعات امانت با موفقیت ذخیره شد!", parent=popup)
            popup.destroy()
            search_loans()
            search()
        except sqlite3.Error as e:
            messagebox.showerror("خطا در پایگاه داده", f"خطا در ذخیره اطلاعات: {e}", parent=popup)

    btn_f = ctk.CTkFrame(popup, fg_color="transparent")
    btn_f.pack(pady=16, padx=25, fill=tk.X)
    btn_save = create_icon_button(
        btn_f,
        text=" ثبت امانت ",
        icon_name="arrow-right-left",
        font=FONT_BOLD,
        fg_color="#2563eb",
        hover_color="#1d4ed8",
        width=120,
        command=do_insert_loan,
    )
    btn_save.pack(side=tk.RIGHT, padx=5)
    btn_cancel = create_icon_button(
        btn_f,
        text=" انصراف ",
        icon_name="x",
        font=FONT_NORMAL,
        fg_color="transparent",
        hover_color=("#e2e8f0", "#1e293b"),
        width=90,
        command=popup.destroy,
    )
    btn_cancel.pack(side=tk.LEFT, padx=5)


add_loan_btn.configure(command=open_add_loan_popup)


def on_double_click(event):
    selected = tree.selection()
    if not selected:
        return
    item = selected[0]
    values = tree.item(item, "values")
    if not values or str(values[0]).startswith("❌"):
        return

    try:
        title_index = columns.index("title")
        title_value = values[title_index] if title_index < len(values) else ""
    except ValueError:
        title_value = ""

    id_index = columns.index("id") if "id" in columns else -1
    book_db_id = None
    if id_index != -1 and id_index < len(values):
        try:
            book_db_id = int(values[id_index])
        except (ValueError, TypeError):
            pass

    conn = get_db_connection(db_p)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM loans WHERE (book_id = ? OR book_id = ?) AND (borrowed = 1 OR borrowed = '1')",
            (book_db_id, title_value),
        )
        if cur.fetchone()[0] > 0:
            messagebox.showwarning(
                "امانت کتاب",
                f"کتاب «{title_value}» در حال حاضر در امانت است و امکان امانت مجدد آن وجود ندارد.",
                parent=root,
            )
            return
    finally:
        conn.close()

    open_add_loan_popup(initial_book_title=title_value)


loans_search_after_id = None


def on_loans_key_release(event):
    global loans_search_after_id
    if loans_search_after_id is not None:
        root.after_cancel(loans_search_after_id)
    loans_search_after_id = root.after(200, search_loans)


entry_search_loans.bind("<KeyRelease>", on_loans_key_release)
entry_search_loans.bind("<Return>", search_loans)

loans_tree.bind("<Double-Button-1>", lambda event: do_return_selected_loan())


def open_extend_loan_popup():
    selected = loans_tree.selection()
    if not selected:
        messagebox.showwarning("هشدار", "لطفاً ابتدا یک رکورد امانت را از جدول انتخاب کنید!", parent=root)
        return

    item_id = selected[0]
    values = loans_tree.item(item_id, "values")
    if not values or str(values[0]).startswith("❌"):
        return

    id_idx = loan_column.index("id") if "id" in loan_column else 0
    loan_id = values[id_idx]

    b_idx = loan_column.index("book_id") if "book_id" in loan_column else -1
    book_title = values[b_idx] if b_idx != -1 and b_idx < len(values) else ""

    m_idx = (
        loan_column.index("member_id")
        if "member_id" in loan_column
        else (loan_column.index("member_name") if "member_name" in loan_column else -1)
    )
    member_name = values[m_idx] if m_idx != -1 and m_idx < len(values) else ""

    r_idx = loan_column.index("return_date") if "return_date" in loan_column else -1
    cur_return_shamsi = values[r_idx] if r_idx != -1 and r_idx < len(values) else ""

    borrowed_idx = loan_column.index("borrowed") if "borrowed" in loan_column else -1
    current_status = values[borrowed_idx] if borrowed_idx != -1 and borrowed_idx < len(values) else ""

    if current_status == "بازگردانده شده":
        messagebox.showinfo("اطلاع", "این کتاب قبلاً بازگردانده شده است و امکان تمدید ندارد.", parent=root)
        return

    popup = ctk.CTkToplevel(root)
    popup.title("تمدید و تغییر تاریخ بازگشت امانت")
    popup.geometry("420x360")
    popup.resizable(False, False)
    if os.path.exists(icon_p):
        try:
            popup.iconbitmap(icon_p)
        except Exception:
            pass

    popup.transient(root)
    popup.grab_set()

    root.update_idletasks()
    rx = root.winfo_rootx()
    ry = root.winfo_rooty()
    rw = root.winfo_width()
    rh = root.winfo_height()
    popup.geometry(f"+{max(50, rx + (rw - 420) // 2)}+{max(50, ry + (rh - 360) // 2)}")

    ctk.CTkLabel(popup, text="تمدید یا تغییر تاریخ بازگشت", font=FONT_TITLE).pack(pady=(14, 8))

    info_card = ctk.CTkFrame(popup, corner_radius=8, fg_color=("#f1f5f9", "#1e293b"))
    info_card.pack(fill=tk.X, padx=20, pady=(0, 10))

    ctk.CTkLabel(
        info_card,
        text=f"کتاب: {book_title}   |   عضو: {member_name}",
        font=FONT_NORMAL,
        anchor="e",
    ).pack(fill=tk.X, padx=10, pady=(6, 2))

    ctk.CTkLabel(
        info_card,
        text=f"تاریخ بازگشت فعلی: {cur_return_shamsi or 'نامشخص'}",
        font=FONT_SMALL,
        text_color=("#64748b", "#94a3b8"),
        anchor="e",
    ).pack(fill=tk.X, padx=10, pady=(0, 6))

    ctk.CTkLabel(popup, text="تاریخ بازگشت جدید (YYYY-MM-DD):", font=FONT_NORMAL, anchor="e").pack(
        fill=tk.X, padx=20, pady=(4, 2)
    )

    row_new_date = ctk.CTkFrame(popup, fg_color="transparent")
    row_new_date.pack(fill=tk.X, padx=20, pady=2)

    cur_jdate = parse_jalali_date(cur_return_shamsi) or get_today_jalali()
    default_new_date = format_jalali_date(cur_jdate + jdatetime.timedelta(days=7))

    ent_new_date = ctk.CTkEntry(row_new_date, font=FONT_NORMAL, justify="right", height=32)
    ent_new_date.insert(0, default_new_date)

    btn_cal = create_date_picker_button(
        row_new_date,
        entry_widget=ent_new_date,
        title="انتخاب تاریخ بازگشت جدید (تقویم شمسی)",
        icon_path=icon_p,
    )
    btn_cal.pack(side=tk.LEFT, padx=(0, 4))
    ent_new_date.pack(side=tk.RIGHT, fill=tk.X, expand=True)

    quick_frame = ctk.CTkFrame(popup, fg_color="transparent")
    quick_frame.pack(fill=tk.X, padx=20, pady=6)

    def _add_days(d_cnt: int):
        base = parse_jalali_date(ent_new_date.get()) or get_today_jalali()
        new_d = base + jdatetime.timedelta(days=d_cnt)
        ent_new_date.delete(0, tk.END)
        ent_new_date.insert(0, format_jalali_date(new_d))

    btn_q7 = ctk.CTkButton(
        quick_frame,
        text="+۷ روز",
        font=FONT_SMALL,
        width=65,
        height=26,
        fg_color=("#cbd5e1", "#334155"),
        text_color=("#0f172a", "#f8fafc"),
        command=lambda: _add_days(7),
    )
    btn_q7.pack(side=tk.RIGHT, padx=2)

    btn_q14 = ctk.CTkButton(
        quick_frame,
        text="+۱۴ روز",
        font=FONT_SMALL,
        width=65,
        height=26,
        fg_color=("#cbd5e1", "#334155"),
        text_color=("#0f172a", "#f8fafc"),
        command=lambda: _add_days(14),
    )
    btn_q14.pack(side=tk.RIGHT, padx=2)

    btn_q30 = ctk.CTkButton(
        quick_frame,
        text="+۳۰ روز",
        font=FONT_SMALL,
        width=65,
        height=26,
        fg_color=("#cbd5e1", "#334155"),
        text_color=("#0f172a", "#f8fafc"),
        command=lambda: _add_days(30),
    )
    btn_q30.pack(side=tk.RIGHT, padx=2)

    btn_save = create_icon_button(
        popup,
        text=" ثبت تمدید امانت ",
        icon_name="check",
        font=FONT_BOLD,
        fg_color="#16a34a",
        hover_color="#15803d",
        height=34,
    )
    btn_save.pack(fill=tk.X, padx=20, pady=(12, 6))

    def _do_save_extend():
        val = ent_new_date.get().strip()
        parsed = parse_jalali_date(val)
        if not parsed:
            messagebox.showerror("خطا", "فرمت تاریخ بازگشت معتبر نیست!\nمثال: 1403-07-15", parent=popup)
            return

        greg_str = parsed.togregorian().strftime("%Y-%m-%d")
        conn = get_db_connection(db_p)
        try:
            cur = conn.cursor()
            cur.execute("UPDATE loans SET return_date = ? WHERE id = ?", (greg_str, loan_id))
            conn.commit()
            popup.destroy()
            notification_engine.show(
                "تمدید امانت",
                f"مهلت بازگشت کتاب «{book_title}» تا تاریخ {format_jalali_date(parsed)} تمدید شد.",
            )
            messagebox.showinfo(
                "موفقیت",
                f"تاریخ بازگشت کتاب با موفقیت به {format_jalali_date(parsed)} تغییر یافت.",
                parent=root,
            )
            search_loans()
        except sqlite3.Error as ex:
            messagebox.showerror("خطا", f"خطا در ثبت تمدید: {ex}", parent=popup)
        finally:
            conn.close()

    btn_save.configure(command=_do_save_extend)


loans_menu = tk.Menu(root, tearoff=0)
loans_menu.add_command(label="تمدید یا ویرایش تاریخ بازگشت", command=open_extend_loan_popup)
loans_menu.add_command(label="ثبت بازگشت کتاب", command=do_return_selected_loan)
loans_menu.add_separator()
loans_menu.add_command(label="حذف رکورد امانت", command=lambda: loans_tree.event_generate("<Delete>"))


def show_loans_context_menu(event):
    row_id = loans_tree.identify_row(event.y)
    if row_id:
        loans_tree.selection_set(row_id)
        loans_menu.post(event.x_root, event.y_root)


loans_tree.bind("<Button-3>", show_loans_context_menu)

bind_table_delete(
    loans_tree,
    new_tabel_name,
    id_col_index=loan_column.index("id") if "id" in loan_column else 0,
    on_deleted=search_loans,
)

# ==================== راهنما و درباره نرم‌افزار (Help & About) ====================
help_scroll = ctk.CTkScrollableFrame(help_frame, corner_radius=10, fg_color="transparent")
help_scroll.pack(fill=tk.BOTH, expand=True, padx=12, pady=(8, 8))


def open_url(url: str):
    try:
        webbrowser.open(url)
    except Exception as e:
        messagebox.showerror("خطا", f"امکان باز کردن پیوند در مرورگر وجود ندارد:\n{e}", parent=root)


app_info = load_app_info()
app_version = app_info.get("version", "0.1.0")
update_checker = UpdateChecker(
    repo=app_info.get("github_repo", "amirkabir18/bager_library"),
    current_version=app_version,
)
download_manager = DownloadManager()
latest_update_info: dict = {}

# --- 1. Hero Identity Banner ---
hero_banner = ctk.CTkFrame(
    help_scroll,
    corner_radius=12,
    border_width=1,
    border_color=("#e2e8f0", "#334155"),
    fg_color=("#f8fafc", "#1e293b"),
)
hero_banner.pack(fill=tk.X, pady=(0, 12), padx=2)

hero_content = ctk.CTkFrame(hero_banner, fg_color="transparent")
hero_content.pack(fill=tk.X, padx=20, pady=16)

ctk.CTkLabel(
    hero_content,
    text="کتابخانه باقر العلوم (ع)",
    font=ctk.CTkFont(family=FONT_FAMILY, size=18, weight="bold"),
    text_color=("#0f172a", "#f8fafc"),
    anchor="e",
).pack(fill=tk.X)

ctk.CTkLabel(
    hero_content,
    text="سامانه یکپارچه مدیریت مخزن کتاب، رده‌بندی دهدهی دیویی (DDC)، گردش امانات و اعلان‌های رومیزی",
    font=FONT_NORMAL,
    text_color=("#475569", "#94a3b8"),
    anchor="e",
).pack(fill=tk.X, pady=(4, 12))

badges_row = ctk.CTkFrame(hero_content, fg_color="transparent")
badges_row.pack(fill=tk.X)


def make_badge(parent, text, bg_color, text_color):
    return ctk.CTkLabel(
        parent,
        text=f"  {text}  ",
        font=FONT_SMALL,
        fg_color=bg_color,
        text_color=text_color,
        corner_radius=6,
        height=24,
    )


make_badge(badges_row, f"نسخه {app_version}", ("#dbeafe", "#1e3a8a"), ("#1d4ed8", "#93c5fd")).pack(
    side=tk.RIGHT, padx=(0, 6)
)
make_badge(badges_row, "🟢 سیستم آماده به کار", ("#dcfce7", "#064e3b"), ("#15803d", "#6ee7b7")).pack(
    side=tk.RIGHT, padx=6
)
make_badge(badges_row, "⚡ پایگاه داده محلی SQLite", ("#f3e8ff", "#581c87"), ("#7e22ce", "#d8b4fe")).pack(
    side=tk.RIGHT, padx=6
)
make_badge(badges_row, "🔔 موتور اعلان ویندوز", ("#fef3c7", "#78350f"), ("#b45309", "#fde68a")).pack(
    side=tk.RIGHT, padx=6
)

# --- 2. Guide Cards Section ---
guide_box = ctk.CTkFrame(
    help_scroll,
    corner_radius=12,
    border_width=1,
    border_color=("#e2e8f0", "#334155"),
    fg_color=("#ffffff", "#1e293b"),
)
guide_box.pack(fill=tk.X, pady=(0, 12), padx=2)

guide_header = ctk.CTkFrame(guide_box, fg_color="transparent")
guide_header.pack(fill=tk.X, padx=18, pady=(12, 6))
ctk.CTkLabel(
    guide_header,
    text=" راهنمای بخش‌های سامانه ",
    font=FONT_HEADER,
    text_color=("#0f172a", "#f8fafc"),
    anchor="e",
).pack(side=tk.RIGHT)

cards_container = ctk.CTkFrame(guide_box, fg_color="transparent")
cards_container.pack(fill=tk.X, padx=12, pady=(0, 12))
cards_container.columnconfigure((0, 1), weight=1, uniform="guide")

guide_features = [
    (
        "📚 مخزن کتاب و رده‌بندی دیویی (DDC)",
        "• استعلام برخط شابک (ISBN) از پایگاه‌های Open Library و Google Books.\n"
        "• طبقه‌بندی خودکار در رده‌های ده‌گانه دیویی (۰۰۰ تا ۹۰۰) با خط لوله هوشمند.\n"
        "• پشتیبانی از رده دستی (Manual) بدون تغییر در رده‌بندی خودکار دسته‌ای.\n"
        "• محاسبه خودکار و پیشنهاد دقیق محل فیزیکی کتاب در قفسه‌های کتابخانه.",
        0,
        0,
    ),
    (
        "🔄 میز امانت و گردش کتاب (Circulation)",
        "• ثبت سریع امانت با جستجوی هوشمند و تکمیل خودکار نام عضو و عنوان کتاب.\n"
        "• پشتیبانی کامل از تقویم خورشیدی (جلالی) و محاسبه موعد بازگشت و دیرکرد.\n"
        "• تسویه و ثبت بازگشت فوری کتاب تنها با دابل‌کلیک روی ردیف در جدول امانات.\n"
        "• قابلیت تمدید امانت، ثبت یادداشت و فیلتر کتاب‌های در امانت یا موجود.",
        0,
        1,
    ),
    (
        "👥 مدیریت اعضا و کاربران سامانه",
        "• تشکیل پرونده اعضا با شناسه یکتا و نرمال‌سازی شماره همراه ایران (+98 / 09).\n"
        "• کنترل سطح دسترسی با نقش‌های: سرپرست کل (Super Admin)، مدیر و کتابدار.\n"
        "• رمزنگاری امن کلمات عبور با استاندارد PBKDF2 با ۱۰۰٬۰۰۰ دور تکرار.\n"
        "• احراز هویت دومرحله‌ای با رمز عبور و ارسال کد یکبار مصرف (OTP) با تلگرام.",
        1,
        0,
    ),
    (
        "🔔 سامانه اعلان‌ها و هشدارهای رومیزی",
        "• موتور اعلان ۱۰۰٪ محلی و بدون نیاز به اینترنت برای ویندوز ۱۰ و ۱۱.\n"
        "• پایش خودکار با دیمن پس‌زمینه در بازه‌های ۱۵، ۳۰، ۶۰ یا ۱۲۰ دقیقه‌ای.\n"
        "• تفکیک هشدارهای پیش از موعد (Due Soon) و تاخیر (Overdue) با صدای زنگ.\n"
        "• پنجره شناور اختصاصی (Toast) و ثبت دقیق تاریخچه در دفتر لاگ اعلان‌ها.",
        1,
        1,
    ),
]

for title, desc, r, c in guide_features:
    f_card = ctk.CTkFrame(
        cards_container,
        corner_radius=10,
        fg_color=("#f8fafc", "#0f172a"),
        border_width=1,
        border_color=("#e2e8f0", "#334155"),
    )
    f_card.grid(row=r, column=c, padx=6, pady=6, sticky="nsew")

    ctk.CTkLabel(
        f_card,
        text=title,
        font=FONT_BOLD,
        text_color=("#2563eb", "#38bdf8"),
        anchor="e",
    ).pack(fill=tk.X, padx=12, pady=(10, 4))

    ctk.CTkLabel(
        f_card,
        text=desc,
        font=FONT_SMALL,
        text_color=("#334155", "#cbd5e1"),
        justify="right",
        anchor="e",
    ).pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 10))

# --- 3. Keyboard Shortcuts Ribbon ---
shortcut_box = ctk.CTkFrame(
    help_scroll,
    corner_radius=12,
    border_width=1,
    border_color=("#e2e8f0", "#334155"),
    fg_color=("#ffffff", "#1e293b"),
)
shortcut_box.pack(fill=tk.X, pady=(0, 12), padx=2)

shortcut_header = ctk.CTkFrame(shortcut_box, fg_color="transparent")
shortcut_header.pack(fill=tk.X, padx=18, pady=(12, 6))
ctk.CTkLabel(
    shortcut_header,
    text=" کلیدهای میانبر و ترفندهای کاربری سریع ",
    font=FONT_HEADER,
    text_color=("#0f172a", "#f8fafc"),
    anchor="e",
).pack(side=tk.RIGHT)

shortcuts_row = ctk.CTkFrame(shortcut_box, fg_color="transparent")
shortcuts_row.pack(fill=tk.X, padx=12, pady=(0, 12))
shortcuts_row.columnconfigure((0, 1, 2, 3, 4), weight=1, uniform="sc")

shortcut_items = [
    ("Enter", "جستجوی فوری در جدول"),
    ("Delete", "حذف ردیف انتخاب‌شده"),
    ("دابل‌کلیک", "امانت / ثبت برگشت"),
    ("کلیک راست", "منوی عملیات ویژه"),
    ("Esc", "بستن پنجره‌ها و دیالوگ‌ها"),
]

for idx, (key_label, desc_label) in enumerate(shortcut_items):
    sc_item = ctk.CTkFrame(
        shortcuts_row,
        corner_radius=8,
        fg_color=("#f8fafc", "#0f172a"),
        border_width=1,
        border_color=("#e2e8f0", "#334155"),
    )
    sc_item.grid(row=0, column=idx, padx=4, pady=4, sticky="nsew")

    key_badge = ctk.CTkLabel(
        sc_item,
        text=f" {key_label} ",
        font=FONT_BOLD,
        fg_color=("#e2e8f0", "#334155"),
        text_color=("#0f172a", "#f8fafc"),
        corner_radius=6,
        height=26,
    )
    key_badge.pack(pady=(8, 4), padx=6)

    ctk.CTkLabel(
        sc_item,
        text=desc_label,
        font=FONT_SMALL,
        text_color=("#475569", "#94a3b8"),
        justify="center",
    ).pack(pady=(0, 8), padx=4)

# --- 4. Software Update Center ---
update_group = ctk.CTkFrame(
    help_scroll,
    corner_radius=12,
    border_width=1,
    border_color=("#e2e8f0", "#334155"),
    fg_color=("#ffffff", "#1e293b"),
)
update_group.pack(fill=tk.X, pady=(0, 12), padx=2)

update_title = ctk.CTkLabel(
    update_group,
    text=" مرکز بروزرسانی نرم‌افزار ",
    font=FONT_HEADER,
    text_color=("#0f172a", "#f8fafc"),
    anchor="e",
)
update_title.pack(fill=tk.X, padx=18, pady=(12, 6))

info_row = ctk.CTkFrame(update_group, fg_color="transparent")
info_row.pack(fill=tk.X, padx=18, pady=4)

lbl_current_ver = ctk.CTkLabel(
    info_row,
    text=f"نسخه فعلی: {app_version}",
    font=FONT_BOLD,
    text_color=("#2563eb", "#38bdf8"),
    anchor="e",
)
lbl_current_ver.pack(side=tk.RIGHT, padx=(0, 15))

lbl_update_status = ctk.CTkLabel(
    info_row,
    text="وضعیت: در حال بررسی...",
    font=FONT_NORMAL,
    text_color="#38bdf8",
    anchor="e",
)
lbl_update_status.pack(side=tk.RIGHT, padx=5)

progress_row = ctk.CTkFrame(update_group, fg_color="transparent")

update_progress = ctk.CTkProgressBar(progress_row, mode="determinate", height=10, corner_radius=5)
update_progress.set(0.0)
update_progress.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10, 0))

lbl_progress_text = ctk.CTkLabel(
    progress_row,
    text="",
    font=FONT_SMALL,
    text_color="#94a3b8",
    width=180,
    anchor="w",
)
lbl_progress_text.pack(side=tk.LEFT, padx=(0, 5))

actions_row = ctk.CTkFrame(update_group, fg_color="transparent")
actions_row.pack(fill=tk.X, padx=18, pady=(6, 12))


def on_check_finished(res: dict, interactive: bool):
    latest_update_info.clear()
    latest_update_info.update(res)

    if res.get("update_available"):
        latest_ver = res.get("latest_version", "")
        lbl_update_status.configure(
            text=f"وضعیت: نسخه جدید {latest_ver} موجود است!",
            text_color="#16a34a",
        )
        btn_update_action.configure(
            state="normal",
            text=f" دریافت و نصب نسخه {latest_ver} ",
            command=start_update_download,
        )
        btn_update_action.pack(side=tk.RIGHT, padx=5)
        if interactive:
            messagebox.showinfo(
                "بروزرسانی جدید",
                f"نسخه جدید «{latest_ver}» در دسترس است.\nبرای دریافت و نصب، روی دکمه «دریافت و نصب» کلیک کنید.",
                parent=root,
            )
    else:
        lbl_update_status.configure(
            text="وضعیت: نرم‌افزار به‌روز است.",
            text_color="#16a34a",
        )
        progress_row.pack_forget()
        btn_update_action.pack_forget()
        btn_cancel_update.pack_forget()
        if interactive:
            messagebox.showinfo("بروزرسانی", "نرم‌افزار شما به‌روز است.", parent=root)


def on_check_failed(error_msg: str, interactive: bool):
    progress_row.pack_forget()
    btn_cancel_update.pack_forget()
    if interactive:
        btn_update_action.configure(
            state="normal",
            text=" تلاش مجدد برای بررسی ",
            command=lambda: perform_check(interactive=True),
        )
        btn_update_action.pack(side=tk.RIGHT, padx=5)
        lbl_update_status.configure(text="وضعیت: خطا در بررسی بروزرسانی", text_color="#dc2626")
        messagebox.showerror("خطا در بررسی بروزرسانی", f"خطا در ارتباط با سرور بروزرسانی:\n{error_msg}", parent=root)
    else:
        btn_update_action.pack_forget()
        lbl_update_status.configure(text="وضعیت: نرم‌افزار به‌روز است.", text_color="#16a34a")


def perform_check(interactive: bool = True):
    if not is_internet_access_enabled(db_p):
        if interactive:
            messagebox.showwarning(
                "دسترسی به اینترنت",
                "دسترسی به اینترنت در تنظیمات برنامه غیرفعال شده است.",
                parent=root,
            )
        lbl_update_status.configure(text="وضعیت: دسترسی به اینترنت در تنظیمات غیرفعال است.", text_color="#dc2626")
        return

    lbl_update_status.configure(text="وضعیت: در حال بررسی آخرین نسخه...", text_color="#38bdf8")
    btn_update_action.configure(state="disabled")

    def _worker():
        try:
            res = update_checker.check()
            root.after(0, lambda: on_check_finished(res, interactive))
        except Exception as ex:
            err_str = str(ex)
            root.after(0, lambda: on_check_failed(err_str, interactive))

    threading.Thread(target=_worker, daemon=True).start()


def start_update_download():
    download_url = latest_update_info.get("download_url")
    if not download_url:
        messagebox.showerror("خطا", "آدرس دانلود فایل بروزرسانی یافت نشد.", parent=root)
        return

    dest_path = os.path.join(tempfile.gettempdir(), "bager_library_new.exe")
    btn_update_action.configure(state="disabled")
    btn_cancel_update.pack(side=tk.RIGHT, padx=5)
    lbl_update_status.configure(text="وضعیت: در حال دانلود فایل بروزرسانی...", text_color="#38bdf8")
    progress_row.pack(fill=tk.X, padx=18, pady=4, before=actions_row)
    update_progress.set(0.0)

    def _update_prog_ui(downloaded, total, pct, speed):
        update_progress.set(min(1.0, max(0.0, pct / 100.0)))
        speed_str = format_speed(speed)
        down_str = format_size(downloaded)
        total_str = format_size(total) if total > 0 else "نامشخص"
        lbl_progress_text.configure(text=f"{pct:.0f}% ({down_str} / {total_str}) {speed_str}")

    def _prompt_install(path):
        confirm = messagebox.askyesno(
            "نصب بروزرسانی", "دانلود نسخه جدید کامل شد.\nآیا مایلید برنامه بسته شده و نسخه جدید اجرا شود؟", parent=root
        )
        if confirm:
            try:
                applied = apply_update(path)
                if applied:
                    root.destroy()
                    sys.exit(0)
                else:
                    messagebox.showinfo(
                        "اطلاع",
                        f"برنامه در محیط توسعه پایتون در حال اجراست.\nفایل نصبی جدید در مسیر زیر ذخیره شد:\n{path}",
                        parent=root,
                    )
            except Exception as e:
                messagebox.showerror("خطا در نصب بروزرسانی", f"خطا در جایگزینی فایل:\n{e}", parent=root)

    def _finish_download_ui(path):
        btn_cancel_update.pack_forget()
        btn_update_action.configure(
            state="normal",
            text=" نصب بروزرسانی ",
            command=lambda: _prompt_install(path),
        )
        btn_update_action.pack(side=tk.RIGHT, padx=5)
        update_progress.set(1.0)
        lbl_update_status.configure(text="وضعیت: دانلود با موفقیت انجام شد.", text_color="#16a34a")
        lbl_progress_text.configure(text="دانلود کامل شد")
        _prompt_install(path)

    def _error_download_ui(err):
        btn_cancel_update.pack_forget()
        btn_update_action.configure(
            state="normal",
            text=" تلاش مجدد برای دریافت ",
            command=start_update_download,
        )
        btn_update_action.pack(side=tk.RIGHT, padx=5)
        lbl_update_status.configure(text="وضعیت: خطا در دانلود بروزرسانی", text_color="#dc2626")
        messagebox.showerror("خطا در دانلود", f"خطا در حین دانلود فایل بروزرسانی:\n{err}", parent=root)

    def _cancelled_download_ui():
        btn_cancel_update.pack_forget()
        btn_update_action.configure(
            state="normal",
            text=" دریافت و نصب نسخه جدید ",
            command=start_update_download,
        )
        btn_update_action.pack(side=tk.RIGHT, padx=5)
        progress_row.pack_forget()
        update_progress.set(0.0)
        lbl_progress_text.configure(text="")
        lbl_update_status.configure(text="وضعیت: دانلود لغو شد.", text_color="#64748b")

    download_manager.download_async(
        url=download_url,
        dest_path=dest_path,
        on_progress=lambda d, t, p, s: root.after(0, lambda: _update_prog_ui(d, t, p, s)),
        on_finished=lambda p: root.after(0, lambda: _finish_download_ui(p)),
        on_error=lambda err: root.after(0, lambda: _error_download_ui(err)),
        on_cancelled=lambda: root.after(0, _cancelled_download_ui),
    )


btn_update_action = create_icon_button(
    actions_row,
    text=" بررسی بروزرسانی ",
    icon_name="refresh-cw",
    font=FONT_BOLD,
    fg_color="#2563eb",
    hover_color="#1d4ed8",
    command=lambda: perform_check(interactive=True),
    width=150,
    height=34,
)
btn_update_action.pack(side=tk.RIGHT, padx=5)

btn_cancel_update = create_icon_button(
    actions_row,
    text=" لغو دانلود ",
    icon_name="x",
    font=FONT_NORMAL,
    fg_color="transparent",
    hover_color=("#e2e8f0", "#1e293b"),
    command=download_manager.cancel,
    width=110,
    height=34,
)

# --- 5. Team & Community Section ---
dev_box = ctk.CTkFrame(
    help_scroll,
    corner_radius=12,
    border_width=1,
    border_color=("#e2e8f0", "#334155"),
    fg_color=("#ffffff", "#1e293b"),
)
dev_box.pack(fill=tk.X, pady=(0, 10), padx=2)

dev_box_header = ctk.CTkFrame(dev_box, fg_color="transparent")
dev_box_header.pack(fill=tk.X, padx=18, pady=(12, 6))
ctk.CTkLabel(
    dev_box_header,
    text=" تیم توسعه و پشتیبانی متن‌باز ",
    font=FONT_HEADER,
    text_color=("#0f172a", "#f8fafc"),
    anchor="e",
).pack(side=tk.RIGHT)

devs_container = ctk.CTkFrame(dev_box, fg_color="transparent")
devs_container.pack(fill=tk.X, padx=14, pady=(2, 10))
devs_container.columnconfigure((0, 1, 2), weight=1, uniform="devs")

developers_info = [
    ("امیرحسین اسدی", "@amirkabir18", "https://github.com/amirkabir18"),
    ("سید محمد حسن موسوی", "@Aliomosavi", "https://github.com/Aliomosavi"),
    ("امیررضا یونس‌زاده شیرازی", "@ARUSH221617", "https://github.com/ARUSH221617"),
]

for idx, (name, handle, profile_url) in enumerate(developers_info):
    d_card = ctk.CTkFrame(
        devs_container,
        corner_radius=8,
        fg_color=("#f8fafc", "#0f172a"),
        border_width=1,
        border_color=("#e2e8f0", "#334155"),
    )
    d_card.grid(row=0, column=idx, padx=4, pady=4, sticky="nsew")

    ctk.CTkLabel(
        d_card,
        text=f"👤 {name}",
        font=FONT_BOLD,
        text_color=("#0f172a", "#f8fafc"),
        anchor="center",
    ).pack(pady=(10, 4), padx=6)

    ctk.CTkButton(
        d_card,
        text=handle,
        font=FONT_SMALL,
        fg_color="transparent",
        text_color=("#2563eb", "#38bdf8"),
        hover_color=("#e2e8f0", "#1e293b"),
        height=26,
        command=lambda u=profile_url: open_url(u),
    ).pack(pady=(0, 8), padx=6)

links_row = ctk.CTkFrame(dev_box, fg_color="transparent")
links_row.pack(fill=tk.X, padx=18, pady=(4, 14))

btn_repo = create_icon_button(
    links_row,
    text=" مشاهده مخزن گیت‌هاب ",
    icon_name="bookmark",
    font=FONT_NORMAL,
    command=lambda: open_url("https://github.com/amirkabir18/bager_library"),
    width=175,
    height=32,
)
btn_repo.pack(side=tk.RIGHT, padx=5)

btn_issue = create_icon_button(
    links_row,
    text=" ثبت باگ یا پیشنهاد (Issue) ",
    icon_name="filter",
    font=FONT_NORMAL,
    command=lambda: open_url("https://github.com/amirkabir18/bager_library/issues/new"),
    width=185,
    height=32,
)
btn_issue.pack(side=tk.RIGHT, padx=5)

# ==================== تنظیمات و اعلان‌ها (Settings & Notifications) ====================
title_label_settings = ctk.CTkLabel(settings_frame, text="تنظیمات سیستم و اعلان‌ها", font=FONT_TITLE)
title_label_settings.pack(pady=(16, 4))

subtitle_label_settings = ctk.CTkLabel(
    settings_frame,
    text="مدیریت ترجیحات یادآوری، هشدارهای سررسید و مشاهده تاریخچه اعلان‌ها",
    font=FONT_NORMAL,
    text_color="#94a3b8",
)
subtitle_label_settings.pack(pady=(0, 8))

settings_container = ctk.CTkScrollableFrame(settings_frame, corner_radius=10, fg_color="transparent")
settings_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

# --- Preferences Card ---
pref_card = ctk.CTkFrame(settings_container, corner_radius=10)
pref_card.pack(fill=tk.X, pady=(0, 12))

ctk.CTkLabel(pref_card, text=" ترجیحات اعلان‌ها و یادآوری ", font=FONT_HEADER, anchor="e").pack(
    fill=tk.X, padx=16, pady=(12, 6)
)

var_notif_enabled = tk.BooleanVar(value=True)
var_notif_sound = tk.BooleanVar(value=True)
var_internet_enabled = tk.BooleanVar(value=True)
var_ai_enabled = tk.BooleanVar(value=True)

pref_row1 = ctk.CTkFrame(pref_card, fg_color="transparent")
pref_row1.pack(fill=tk.X, padx=16, pady=4)

chk_enable_notif = ctk.CTkSwitch(
    pref_row1,
    text="فعال‌سازی اعلان‌های دسکتاپ سیستم",
    variable=var_notif_enabled,
    font=FONT_NORMAL,
)
chk_enable_notif.pack(side=tk.RIGHT, padx=10)

chk_enable_sound = ctk.CTkSwitch(
    pref_row1,
    text="پخش صدای هشدار هنگام نمایش اعلان",
    variable=var_notif_sound,
    font=FONT_NORMAL,
)
chk_enable_sound.pack(side=tk.RIGHT, padx=10)

pref_row_net = ctk.CTkFrame(pref_card, fg_color="transparent")
pref_row_net.pack(fill=tk.X, padx=16, pady=4)

chk_enable_internet = ctk.CTkSwitch(
    pref_row_net,
    text="فعال‌سازی دسترسی به اینترنت",
    variable=var_internet_enabled,
    font=FONT_NORMAL,
    command=lambda: on_toggle_internet_setting(),
)
chk_enable_internet.pack(side=tk.RIGHT, padx=10)

chk_enable_ai = ctk.CTkSwitch(
    pref_row_net,
    text="فعال‌سازی قابلیت‌های هوش مصنوعی",
    variable=var_ai_enabled,
    font=FONT_NORMAL,
    command=lambda: on_toggle_ai_setting(),
)
chk_enable_ai.pack(side=tk.RIGHT, padx=10)

btn_recheck_net = create_icon_button(
    pref_row_net,
    text=" بررسی مجدد اتصال ",
    icon_name="rotate-ccw",
    font=FONT_SMALL,
    command=lambda: manual_recheck_internet(),
    width=135,
    height=28,
)
btn_recheck_net.pack(side=tk.LEFT, padx=5)

lbl_boot_net_status = ctk.CTkLabel(
    pref_row_net,
    text="",
    font=FONT_SMALL,
    anchor="w",
)
lbl_boot_net_status.pack(side=tk.LEFT, padx=10)

var_otp_cleanup_enabled = tk.BooleanVar(value=True)

pref_row_otp = ctk.CTkFrame(pref_card, fg_color="transparent")
pref_row_otp.pack(fill=tk.X, padx=16, pady=4)

chk_enable_otp_cleanup = ctk.CTkSwitch(
    pref_row_otp,
    text="پاک‌سازی خودکار کدهای یک‌بارمصرف (OTP)",
    variable=var_otp_cleanup_enabled,
    font=FONT_NORMAL,
)
chk_enable_otp_cleanup.pack(side=tk.RIGHT, padx=10)

ctk.CTkLabel(pref_row_otp, text="بازه پاک‌سازی (ساعت):", font=FONT_NORMAL).pack(side=tk.RIGHT, padx=(15, 5))

combo_otp_interval = ctk.CTkOptionMenu(
    pref_row_otp,
    values=["1", "3", "6", "12", "24", "48"],
    width=80,
    font=FONT_NORMAL,
    dropdown_font=FONT_NORMAL,
)
combo_otp_interval.set("12")
combo_otp_interval.pack(side=tk.RIGHT, padx=5)


def trigger_clean_otp_now():
    try:
        deleted = otp_cleanup_manager.clean_now()
        messagebox.showinfo(
            "پاک‌سازی کدهای OTP",
            f"عملیات پاک‌سازی انجام شد. {deleted} رکورد کد/نشست منقضی از پایگاه داده پاک شد.",
            parent=root,
        )
    except Exception as e:
        messagebox.showerror("خطا", f"خطا در پاک‌سازی کدهای OTP:\n{e}", parent=root)


btn_clean_otp = create_icon_button(
    pref_row_otp,
    text=" پاک‌سازی فوری کدهای OTP ",
    icon_name="rotate-ccw",
    font=FONT_SMALL,
    command=trigger_clean_otp_now,
    width=175,
    height=28,
)
btn_clean_otp.pack(side=tk.LEFT, padx=5)

pref_row2 = ctk.CTkFrame(pref_card, fg_color="transparent")
pref_row2.pack(fill=tk.X, padx=16, pady=6)

ctk.CTkLabel(pref_row2, text="ارسال یادآوری سررسید (چند روز قبل):", font=FONT_NORMAL).pack(side=tk.RIGHT, padx=5)

combo_advance_days = ctk.CTkOptionMenu(
    pref_row2,
    values=["1", "2", "3", "5", "7"],
    width=80,
    font=FONT_NORMAL,
    dropdown_font=FONT_NORMAL,
)
combo_advance_days.set("2")
combo_advance_days.pack(side=tk.RIGHT, padx=10)

ctk.CTkLabel(pref_row2, text="حداکثر تعداد امانت برای هر کاربر", font=FONT_NORMAL).pack(side=tk.RIGHT, padx=5)

combo_max_loans = ctk.CTkOptionMenu(
    pref_row2,
    values=["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
    width=80,
)
combo_max_loans.set("4")
combo_max_loans.pack(side=tk.RIGHT, padx=10)


ctk.CTkLabel(pref_row2, text="فاصله بررسی خودکار (دقیقه):", font=FONT_NORMAL).pack(side=tk.RIGHT, padx=(20, 5))

combo_interval = ctk.CTkOptionMenu(
    pref_row2,
    values=["15", "30", "60", "120", "360"],
    width=80,
    font=FONT_NORMAL,
    dropdown_font=FONT_NORMAL,
)
combo_interval.set("30")
combo_interval.pack(side=tk.RIGHT, padx=10)

ctk.CTkLabel(pref_row2, text="حالت تم:", font=FONT_NORMAL).pack(side=tk.RIGHT, padx=(20, 5))


def change_theme_mode(choice):
    if "روشن" in choice:
        ctk.set_appearance_mode("light")
        apply_treeview_styling("light")
    elif "سیستم" in choice:
        ctk.set_appearance_mode("system")
        apply_treeview_styling("dark")
    else:
        ctk.set_appearance_mode("dark")
        apply_treeview_styling("dark")


combo_theme = ctk.CTkOptionMenu(
    pref_row2,
    values=["تیره (Dark)", "روشن (Light)", "سیستم (System)"],
    width=130,
    command=change_theme_mode,
    font=FONT_NORMAL,
    dropdown_font=FONT_NORMAL,
)
combo_theme.set("تیره (Dark)")
combo_theme.pack(side=tk.RIGHT, padx=5)


def update_boot_net_status_label():
    try:
        if not var_internet_enabled.get():
            lbl_boot_net_status.configure(text="🔴 دسترسی اینترنت غیرفعال است", text_color="#dc2626")
            return
        net_ok = get_boot_internet_status(db_p)
        if net_ok:
            lbl_boot_net_status.configure(text="🟢 اینترنت متصل است", text_color="#16a34a")
        else:
            lbl_boot_net_status.configure(text="🔴 اینترنت قطع است", text_color="#dc2626")
    except Exception:
        pass


def update_ai_card_inputs_state(enabled: bool):
    try:
        state = "normal" if enabled else "disabled"
        entry_ai_url.configure(state=state)
        entry_ai_key.configure(state=state)
        entry_ai_model.configure(state=state)
        btn_test_ai.configure(state=state)
        if not enabled:
            if not var_internet_enabled.get():
                lbl_ai_status.configure(text="🔴 دسترسی اینترنت و هوش مصنوعی غیرفعال است", text_color="#dc2626")
            else:
                lbl_ai_status.configure(text="🟡 قابلیت‌های هوش مصنوعی غیرفعال است", text_color="#f59e0b")
        else:
            lbl_ai_status.configure(text="")
    except Exception:
        pass


def on_toggle_internet_setting():
    if not var_internet_enabled.get():
        # If internet access is disabled, AI features are also disabled
        var_ai_enabled.set(False)
        chk_enable_ai.configure(state="disabled")
        update_boot_net_status_label()
        update_ai_card_inputs_state(enabled=False)
    else:
        chk_enable_ai.configure(state="normal")
        update_boot_net_status_label()
        update_ai_card_inputs_state(enabled=var_ai_enabled.get())


def on_toggle_ai_setting():
    if not var_internet_enabled.get():
        var_ai_enabled.set(False)
        chk_enable_ai.configure(state="disabled")
        update_ai_card_inputs_state(enabled=False)
        return
    update_ai_card_inputs_state(enabled=var_ai_enabled.get())


def manual_recheck_internet():
    if not var_internet_enabled.get():
        messagebox.showinfo(
            "وضعیت اینترنت",
            "دسترسی به اینترنت در تنظیمات برنامه غیرفعال شده است. ابتدا آن را فعال نمایید.",
            parent=root,
        )
        return

    lbl_boot_net_status.configure(text="در حال بررسی اتصال به اینترنت...", text_color="#38bdf8")

    def _worker():
        ok = probe_internet_connectivity(timeout=2.0)
        set_boot_internet_status(ok)

        def _done():
            update_boot_net_status_label()
            if ok:
                messagebox.showinfo("بررسی اتصال", "اتصال به اینترنت برقرار و با موفقیت تأیید شد.", parent=root)
            else:
                messagebox.showwarning("بررسی اتصال", "اتصال به اینترنت برقرار نشد. شبکه را بررسی کنید.", parent=root)

        root.after(0, _done)

    threading.Thread(target=_worker, daemon=True).start()


pref_row3 = ctk.CTkFrame(pref_card, fg_color="transparent")
pref_row3.pack(fill=tk.X, padx=16, pady=(10, 14))


def save_settings_ui():
    notif_val = "true" if var_notif_enabled.get() else "false"
    sound_val = "true" if var_notif_sound.get() else "false"
    adv_days = str(combo_advance_days.get()).strip() or "2"
    max_loans = str(combo_max_loans.get()).strip() or "4"
    interval = str(combo_interval.get()).strip() or "30"

    internet_val = "true" if var_internet_enabled.get() else "false"
    # If internet access is disabled, AI features are strictly disabled
    if internet_val == "false":
        ai_val = "false"
        var_ai_enabled.set(False)
    else:
        ai_val = "true" if var_ai_enabled.get() else "false"

    otp_cleanup_val = "true" if var_otp_cleanup_enabled.get() else "false"
    otp_interval_val = str(combo_otp_interval.get()).strip() or "12"

    try:
        with get_db_connection(db_p) as conn:
            set_setting(conn, "max_loans", max_loans)
            set_setting(conn, "notifications_enabled", notif_val)
            set_setting(conn, "notification_sound", sound_val)
            set_setting(conn, "notification_advance_days", adv_days)
            set_setting(conn, "notification_check_interval_mins", interval)
            set_setting(conn, "internet_access_enabled", internet_val)
            set_setting(conn, "ai_features_enabled", ai_val)
            set_setting(conn, "otp_cleanup_enabled", otp_cleanup_val)
            set_setting(conn, "otp_cleanup_interval_hours", otp_interval_val)
            set_setting(conn, "openai_url", entry_ai_url.get().strip())
            set_setting(conn, "openai_key", entry_ai_key.get().strip())
            set_setting(conn, "openai_model", entry_ai_model.get().strip())

        if internet_val == "false":
            set_boot_internet_status(False)
        else:
            threading.Thread(
                target=lambda: (
                    init_boot_internet_check(database_path=db_p, timeout=1.2),
                    root.after(0, update_boot_net_status_label),
                ),
                daemon=True,
            ).start()

        update_boot_net_status_label()
        on_toggle_internet_setting()

        try:
            reminder_manager.reschedule()
        except Exception:
            pass

        try:
            otp_cleanup_manager.reschedule()
        except Exception:
            pass

        messagebox.showinfo("موفقیت", "تنظیمات با موفقیت ذخیره و اعمال شد.", parent=root)
    except Exception as e:
        messagebox.showerror("خطا", f"خطا در ذخیره تنظیمات:\n{e}", parent=root)


def trigger_test_notification():
    try:
        notification_engine.show(
            "اعلان آزمایشی کتابخانه",
            "سیستم اعلان‌ها و هشدارهای نرم‌افزار به درستی فعال و در حال کار است.",
        )
        try:
            log_notification(db_p, notification_type="test", loan_id=None)
        except Exception:
            pass
        refresh_notification_logs()
        messagebox.showinfo("اعلان آزمایشی", "اعلان آزمایشی ارسال و در تاریخچه ثبت شد.", parent=root)
    except Exception as e:
        messagebox.showerror("خطا", f"خطا در ارسال اعلان آزمایشی:\n{e}", parent=root)


def trigger_check_now():
    try:
        found_count = reminder_manager.check_loans()
        refresh_notification_logs()
        if found_count > 0:
            messagebox.showinfo("بررسی امانات", f"بررسی انجام شد. {found_count} اعلان جدید صادر شد.", parent=root)
        else:
            messagebox.showinfo("بررسی امانات", "بررسی انجام شد. مورد جدیدی برای ارسال اعلان یافت نشد.", parent=root)
    except Exception as e:
        messagebox.showerror("خطا", f"خطا در بررسی امانات:\n{e}", parent=root)


btn_save_settings = create_icon_button(
    pref_row3,
    text=" ذخیره تنظیمات ",
    icon_name="check",
    font=FONT_BOLD,
    fg_color="#16a34a",
    hover_color="#15803d",
    command=save_settings_ui,
    width=130,
    height=34,
)
btn_save_settings.pack(side=tk.RIGHT, padx=5)

btn_test_notif = create_icon_button(
    pref_row3,
    text=" ارسال اعلان آزمایشی ",
    font=FONT_NORMAL,
    command=trigger_test_notification,
    width=150,
    height=34,
)
btn_test_notif.pack(side=tk.RIGHT, padx=5)

btn_check_now = create_icon_button(
    pref_row3,
    text=" بررسی فوری امانات ",
    icon_name="rotate-ccw",
    font=FONT_NORMAL,
    fg_color="transparent",
    hover_color=("#e2e8f0", "#1e293b"),
    command=trigger_check_now,
    width=150,
    height=34,
)
btn_check_now.pack(side=tk.RIGHT, padx=5)

# --- AI Provider Settings Card ---
ai_card = ctk.CTkFrame(settings_container, corner_radius=10)
ai_card.pack(fill=tk.X, pady=(0, 12))

ai_header_row = ctk.CTkFrame(ai_card, fg_color="transparent")
ai_header_row.pack(fill=tk.X, padx=16, pady=(12, 6))

ctk.CTkLabel(
    ai_header_row,
    text=" تنظیمات ارائه‌دهنده هوش مصنوعی (AI Provider) ",
    font=FONT_HEADER,
    anchor="e",
).pack(side=tk.RIGHT)

lbl_ai_status = ctk.CTkLabel(
    ai_header_row,
    text="",
    font=FONT_SMALL,
    text_color="#38bdf8",
    anchor="w",
)
lbl_ai_status.pack(side=tk.LEFT)

ai_row1 = ctk.CTkFrame(ai_card, fg_color="transparent")
ai_row1.pack(fill=tk.X, padx=16, pady=4)

ctk.CTkLabel(ai_row1, text="آدرس سرور (Base URL):", font=FONT_NORMAL, width=145, anchor="e").pack(
    side=tk.RIGHT, padx=(5, 0)
)
entry_ai_url = ctk.CTkEntry(
    ai_row1, font=FONT_NORMAL, justify="left", height=32, placeholder_text="مثال: http://localhost:20128/v1"
)
entry_ai_url.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=5)

ai_row2 = ctk.CTkFrame(ai_card, fg_color="transparent")
ai_row2.pack(fill=tk.X, padx=16, pady=4)

ctk.CTkLabel(ai_row2, text="کلید API (اختیاری):", font=FONT_NORMAL, width=145, anchor="e").pack(
    side=tk.RIGHT, padx=(5, 0)
)
entry_ai_key = ctk.CTkEntry(
    ai_row2, font=FONT_NORMAL, justify="left", height=32, show="*", placeholder_text="sk-... (در صورت نیاز به کلید)"
)
entry_ai_key.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=5)

ai_row3 = ctk.CTkFrame(ai_card, fg_color="transparent")
ai_row3.pack(fill=tk.X, padx=16, pady=4)

ctk.CTkLabel(ai_row3, text="مدل زبانی (Model):", font=FONT_NORMAL, width=145, anchor="e").pack(
    side=tk.RIGHT, padx=(5, 0)
)
entry_ai_model = ctk.CTkEntry(
    ai_row3,
    font=FONT_NORMAL,
    justify="left",
    height=32,
    placeholder_text="مثال: claude-flash-3.6 یا openai/gpt-4o-mini",
)
entry_ai_model.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=5)

ai_row4 = ctk.CTkFrame(ai_card, fg_color="transparent")
ai_row4.pack(fill=tk.X, padx=16, pady=(6, 12))


def test_ai_connection_ui():
    if not is_internet_access_enabled(db_p):
        messagebox.showwarning(
            "دسترسی به اینترنت",
            "دسترسی به اینترنت در تنظیمات برنامه غیرفعال شده است. لطفاً ابتدا دسترسی به اینترنت را فعال کنید.",
            parent=root,
        )
        return

    if not is_ai_features_enabled(db_p):
        messagebox.showwarning(
            "هوش مصنوعی",
            "قابلیت‌های هوش مصنوعی در تنظیمات برنامه غیرفعال شده است. لطفاً ابتدا آن را در تنظیمات فعال کنید.",
            parent=root,
        )
        return

    url = entry_ai_url.get().strip() or "http://localhost:20128"
    key = entry_ai_key.get().strip()
    lbl_ai_status.configure(text="در حال بررسی اتصال به سرویس هوش مصنوعی...", text_color="#38bdf8")

    def _test():
        try:
            from services.dewey_ai_agent import DeweyAIAgent

            net_ok = get_boot_internet_status(db_p)
            agent = DeweyAIAgent(base_url=url, api_key=key, database_path=db_p)
            is_alive = agent.is_available()
            if is_alive:
                msg = "اتصال به سرویس هوش مصنوعی برقرار و سرور فعال است."
                if net_ok:
                    msg += " (اینترنت متصل است)"
                root.after(
                    0,
                    lambda: (
                        lbl_ai_status.configure(text=f"🟢 {msg}", text_color="#16a34a"),
                        messagebox.showinfo("تست اتصال هوش مصنوعی", msg, parent=root),
                    ),
                )
            else:
                root.after(
                    0,
                    lambda: (
                        lbl_ai_status.configure(text="🔴 سرور هوش مصنوعی در این آدرس پاسخ نداد.", text_color="#dc2626"),
                        messagebox.showwarning(
                            "تست اتصال هوش مصنوعی",
                            "سرور هوش مصنوعی در این آدرس پاسخ نداد. لطفاً از روشن بودن سرور هوش مصنوعی اطمینان حاصل کنید.",
                            parent=root,
                        ),
                    ),
                )
        except Exception as ex:
            err_text = str(ex)
            root.after(
                0,
                lambda msg=err_text: (
                    lbl_ai_status.configure(text=f"🔴 خطا: {msg}", text_color="#dc2626"),
                    messagebox.showerror("خطا در تست هوش مصنوعی", msg, parent=root),
                ),
            )

    threading.Thread(target=_test, daemon=True).start()


btn_test_ai = create_icon_button(
    ai_row4,
    text=" تست اتصال به هوش مصنوعی ",
    icon_name="zap",
    font=FONT_NORMAL,
    command=test_ai_connection_ui,
    width=180,
    height=32,
)
btn_test_ai.pack(side=tk.RIGHT, padx=5)


# --- Audit Log Viewer Card ---
log_card = ctk.CTkFrame(settings_container, corner_radius=10)
log_card.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

ctk.CTkLabel(log_card, text=" تاریخچه و لاگ اعلان‌ها ", font=FONT_HEADER, anchor="e").pack(
    fill=tk.X, padx=16, pady=(12, 6)
)

filter_row = ctk.CTkFrame(log_card, fg_color="transparent")
filter_row.pack(fill=tk.X, padx=16, pady=(0, 8))

entry_log_search = ctk.CTkEntry(
    filter_row, placeholder_text="جستجو در لاگ‌ها...", font=FONT_NORMAL, width=170, height=32
)
entry_log_search.pack(side=tk.RIGHT, padx=5)

btn_search_logs = create_icon_button(
    filter_row,
    text=" جستجو ",
    icon_name="search",
    font=FONT_BOLD,
    command=lambda: load_notification_logs_ui(),
    width=85,
    height=32,
)
btn_search_logs.pack(side=tk.RIGHT, padx=4)

ctk.CTkLabel(filter_row, text="نوع اعلان:", font=FONT_NORMAL).pack(side=tk.RIGHT, padx=(10, 4))


def on_combo_log_type_changed(choice=None):
    sel_type = combo_log_type.get().strip()
    type_code_map = {
        "همه": "all",
        "یادآوری سررسید": "due_reminder",
        "هشدار دیرکرد": "overdue",
        "اعلان آزمایشی": "test",
    }
    audit_log_filter_settings["notification_type"] = type_code_map.get(sel_type, "all")
    update_audit_log_filter_indicator()
    load_notification_logs_ui()


combo_log_type = ctk.CTkOptionMenu(
    filter_row,
    values=["همه", "یادآوری سررسید", "هشدار دیرکرد", "اعلان آزمایشی"],
    width=140,
    command=on_combo_log_type_changed,
    font=FONT_NORMAL,
    dropdown_font=FONT_NORMAL,
)
combo_log_type.set("همه")
combo_log_type.pack(side=tk.RIGHT, padx=5)

btn_filter_logs = create_icon_button(
    filter_row,
    text=" فیلترها ",
    icon_name="filter",
    font=FONT_NORMAL,
    command=lambda: open_audit_log_filter_popup(),
    width=85,
    height=32,
)
btn_filter_logs.pack(side=tk.RIGHT, padx=4)

btn_refresh_logs = create_icon_button(
    filter_row,
    text=" تازه‌سازی ",
    icon_name="rotate-ccw",
    font=FONT_NORMAL,
    fg_color="transparent",
    hover_color=("#e2e8f0", "#1e293b"),
    command=lambda: refresh_notification_logs(),
    width=90,
    height=32,
)
btn_refresh_logs.pack(side=tk.RIGHT, padx=4)

btn_clear_logs = create_icon_button(
    filter_row,
    text=" پاک‌سازی تاریخچه ",
    icon_name="x",
    font=FONT_NORMAL,
    fg_color="#dc2626",
    hover_color="#b91c1c",
    command=lambda: clear_logs_ui(),
    width=130,
    height=32,
)
btn_clear_logs.pack(side=tk.LEFT, padx=5)

log_columns = ["id", "notification_type", "book_title", "member_name", "loan_id", "sent_date", "created_at"]

log_tree_frame = ctk.CTkFrame(log_card, corner_radius=8)
log_tree_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 12))

log_scrollbar = ctk.CTkScrollbar(log_tree_frame)
log_scrollbar.pack(side=tk.LEFT, fill=tk.Y, padx=(4, 0), pady=4)

log_tree = ttk.Treeview(
    log_tree_frame,
    yscrollcommand=log_scrollbar.set,
    columns=log_columns,
    show="headings",
    height=9,
)
log_scrollbar.configure(command=log_tree.yview)

for col in log_columns:
    log_tree.heading(col, text=tr(col), anchor=tk.CENTER)
    log_tree.column(col, anchor=tk.CENTER)

log_tree.column("id", width=50, stretch=False)
log_tree.column("notification_type", width=120)
log_tree.column("book_title", width=160)
log_tree.column("member_name", width=130)
log_tree.column("loan_id", width=70, stretch=False)
log_tree.column("sent_date", width=95)
log_tree.column("created_at", width=135)

log_tree["displaycolumns"] = rtl_display_order(
    log_columns, ["id", "notification_type", "book_title", "member_name", "loan_id", "sent_date", "created_at"]
)
log_tree.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(4, 8), pady=4)


def _format_shamsi_date(date_str: str) -> str:
    if not date_str:
        return ""
    try:
        date_str = str(date_str).strip()
        if " " in date_str:
            dt_part, tm_part = date_str.split(" ", 1)
            parts = [int(p) for p in dt_part.split("-")]
            if parts[0] > 1900:
                g_date = datetime.date(parts[0], parts[1], parts[2])
                s_date = jdatetime.date.fromgregorian(date=g_date).strftime("%Y-%m-%d")
                tm_clean = tm_part.split(".")[0]
                return f"{s_date} {tm_clean}"
        elif "-" in date_str:
            parts = [int(p) for p in date_str.split("-")]
            if parts[0] > 1900:
                g_date = datetime.date(parts[0], parts[1], parts[2])
                return jdatetime.date.fromgregorian(date=g_date).strftime("%Y-%m-%d")
    except Exception:
        pass
    return str(date_str)


audit_log_filter_settings = {
    "column": "all",
    "match_mode": "contains",
    "notification_type": "all",
    "sort_col": "id",
    "sort_dir": "DESC",
    "start_date": "",
    "end_date": "",
}


def update_audit_log_filter_indicator():
    is_custom = (
        audit_log_filter_settings["column"] != "all"
        or audit_log_filter_settings["match_mode"] != "contains"
        or audit_log_filter_settings["notification_type"] != "all"
        or audit_log_filter_settings["sort_col"] != "id"
        or audit_log_filter_settings["sort_dir"] != "DESC"
        or bool(audit_log_filter_settings.get("start_date"))
        or bool(audit_log_filter_settings.get("end_date"))
    )
    if is_custom:
        btn_filter_logs.configure(text=" فیلترها (فعال) ", fg_color="#2563eb")
    else:
        btn_filter_logs.configure(text=" فیلترها ", fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"])


def load_notification_logs_ui():
    for item in log_tree.get_children():
        log_tree.delete(item)

    search_kw = entry_log_search.get().strip()
    raw_type = audit_log_filter_settings.get("notification_type", "all")
    type_filter = None if raw_type == "all" else raw_type

    col_filter = audit_log_filter_settings.get("column", "all")
    mode_filter = audit_log_filter_settings.get("match_mode", "contains")
    s_col = audit_log_filter_settings.get("sort_col", "id")
    s_dir = audit_log_filter_settings.get("sort_dir", "DESC")
    start_d = audit_log_filter_settings.get("start_date", "").strip() or None
    end_d = audit_log_filter_settings.get("end_date", "").strip() or None

    try:
        logs = get_notification_logs(
            conn_or_path=db_p,
            notification_type=type_filter,
            start_date=start_d,
            end_date=end_d,
            search_query=search_kw if search_kw else None,
            column=col_filter,
            match_mode=mode_filter,
            sort_col=s_col,
            sort_dir=s_dir,
            limit=200,
        )
        if not logs:
            log_tree.insert("", tk.END, values=("❌ هیچ رکوردی یافت نشد", "", "", "", "", "", ""))
            return

        type_map = {
            "due_reminder": "یادآوری سررسید",
            "due_soon": "یادآوری سررسید",
            "due_today": "یادآوری سررسید",
            "overdue": "هشدار دیرکرد",
            "test": "اعلان آزمایشی",
        }

        for row in logs:
            raw_type = row.get("notification_type", "")
            type_text = type_map.get(raw_type, tr(raw_type))
            loan_id_val = str(row.get("loan_id") or "-")
            book_val = str(row.get("book_title") or "-")
            member_val = str(row.get("member_name") or "-")
            sent_val = _format_shamsi_date(row.get("sent_date", ""))
            created_val = _format_shamsi_date(row.get("created_at", ""))

            vals = (
                row.get("id"),
                type_text,
                book_val,
                member_val,
                loan_id_val,
                sent_val,
                created_val,
            )
            log_tree.insert("", tk.END, values=vals)
    except Exception as e:
        log_tree.insert("", tk.END, values=(f"❌ خطا: {e}", "", "", "", "", "", ""))


def open_audit_log_filter_popup():
    popup = ctk.CTkToplevel(root)
    popup.title("فیلترهای تاریخچه اعلان‌ها")
    popup.geometry("460x520")
    popup.resizable(False, False)
    if os.path.exists(icon_p):
        try:
            popup.iconbitmap(icon_p)
        except Exception:
            pass

    popup.transient(root)
    popup.grab_set()

    root.update_idletasks()
    rx = root.winfo_rootx()
    ry = root.winfo_rooty()
    rw = root.winfo_width()
    rh = root.winfo_height()
    px = max(50, rx + (rw - 460) // 2)
    py = max(50, ry + (rh - 520) // 2)
    popup.geometry(f"+{px}+{py}")

    col_var = tk.StringVar(value=audit_log_filter_settings["column"])
    match_var = tk.StringVar(value=audit_log_filter_settings["match_mode"])
    type_var = tk.StringVar(value=audit_log_filter_settings["notification_type"])
    sort_col_var = tk.StringVar(value=audit_log_filter_settings["sort_col"])
    sort_dir_var = tk.StringVar(value=audit_log_filter_settings["sort_dir"])

    group_col = ctk.CTkFrame(popup, corner_radius=8)
    group_col.pack(fill=tk.X, padx=15, pady=(10, 4))
    ctk.CTkLabel(group_col, text="جستجو در ستون", font=FONT_BOLD, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))

    col_frame_1 = ctk.CTkFrame(group_col, fg_color="transparent")
    col_frame_1.pack(fill=tk.X, padx=6, pady=2)
    rb_all = ctk.CTkRadioButton(col_frame_1, text="همه", variable=col_var, value="all", font=FONT_NORMAL)
    rb_all.pack(side=tk.RIGHT, padx=4)
    rb_bt = ctk.CTkRadioButton(col_frame_1, text="کتاب", variable=col_var, value="book_title", font=FONT_NORMAL)
    rb_bt.pack(side=tk.RIGHT, padx=4)
    rb_mn = ctk.CTkRadioButton(col_frame_1, text="کاربر", variable=col_var, value="member_name", font=FONT_NORMAL)
    rb_mn.pack(side=tk.RIGHT, padx=4)

    col_frame_2 = ctk.CTkFrame(group_col, fg_color="transparent")
    col_frame_2.pack(fill=tk.X, padx=6, pady=(0, 6))
    rb_lid = ctk.CTkRadioButton(col_frame_2, text="شناسه امانت", variable=col_var, value="loan_id", font=FONT_NORMAL)
    rb_lid.pack(side=tk.RIGHT, padx=4)
    rb_sd = ctk.CTkRadioButton(col_frame_2, text="تاریخ ارسال", variable=col_var, value="sent_date", font=FONT_NORMAL)
    rb_sd.pack(side=tk.RIGHT, padx=4)
    rb_id = ctk.CTkRadioButton(col_frame_2, text="شناسه", variable=col_var, value="id", font=FONT_NORMAL)
    rb_id.pack(side=tk.RIGHT, padx=4)

    group_mode = ctk.CTkFrame(popup, corner_radius=8)
    group_mode.pack(fill=tk.X, padx=15, pady=4)
    ctk.CTkLabel(group_mode, text="نوع تطابق جستجو", font=FONT_BOLD, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))
    mode_frame = ctk.CTkFrame(group_mode, fg_color="transparent")
    mode_frame.pack(fill=tk.X, padx=6, pady=(0, 6))
    rb_contains = ctk.CTkRadioButton(
        mode_frame, text="شامل عبارت", variable=match_var, value="contains", font=FONT_NORMAL
    )
    rb_contains.pack(side=tk.RIGHT, padx=8)
    rb_starts = ctk.CTkRadioButton(
        mode_frame, text="شروع با عبارت", variable=match_var, value="startswith", font=FONT_NORMAL
    )
    rb_starts.pack(side=tk.RIGHT, padx=8)
    rb_exact = ctk.CTkRadioButton(mode_frame, text="مطابقت دقیق", variable=match_var, value="exact", font=FONT_NORMAL)
    rb_exact.pack(side=tk.RIGHT, padx=8)

    group_type = ctk.CTkFrame(popup, corner_radius=8)
    group_type.pack(fill=tk.X, padx=15, pady=4)
    ctk.CTkLabel(group_type, text="نوع اعلان", font=FONT_BOLD, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))
    type_frame = ctk.CTkFrame(group_type, fg_color="transparent")
    type_frame.pack(fill=tk.X, padx=6, pady=(0, 6))
    rb_t_all = ctk.CTkRadioButton(type_frame, text="همه", variable=type_var, value="all", font=FONT_NORMAL)
    rb_t_all.pack(side=tk.RIGHT, padx=6)
    rb_t_due = ctk.CTkRadioButton(
        type_frame, text="یادآوری سررسید", variable=type_var, value="due_reminder", font=FONT_NORMAL
    )
    rb_t_due.pack(side=tk.RIGHT, padx=6)
    rb_t_overdue = ctk.CTkRadioButton(
        type_frame, text="هشدار دیرکرد", variable=type_var, value="overdue", font=FONT_NORMAL
    )
    rb_t_overdue.pack(side=tk.RIGHT, padx=6)
    rb_t_test = ctk.CTkRadioButton(type_frame, text="اعلان آزمایشی", variable=type_var, value="test", font=FONT_NORMAL)
    rb_t_test.pack(side=tk.RIGHT, padx=6)

    # Date range filter card
    group_log_date = ctk.CTkFrame(popup, corner_radius=8)
    group_log_date.pack(fill=tk.X, padx=15, pady=4)
    ctk.CTkLabel(group_log_date, text="بازه تاریخ ارسال اعلان (شمسی)", font=FONT_BOLD, anchor="e").pack(
        fill=tk.X, padx=10, pady=(6, 2)
    )
    date_log_frame = ctk.CTkFrame(group_log_date, fg_color="transparent")
    date_log_frame.pack(fill=tk.X, padx=6, pady=(0, 6))

    ctk.CTkLabel(date_log_frame, text="از:", font=FONT_NORMAL).pack(side=tk.RIGHT, padx=(4, 2))
    ent_log_start = ctk.CTkEntry(
        date_log_frame, width=110, height=30, font=FONT_NORMAL, justify="center", placeholder_text="YYYY-MM-DD"
    )
    ent_log_start.insert(0, audit_log_filter_settings.get("start_date", ""))
    btn_start_cal = create_date_picker_button(
        date_log_frame,
        entry_widget=ent_log_start,
        title="انتخاب تاریخ شروع ارسال",
        icon_path=icon_p,
        width=30,
        height=30,
    )
    btn_start_cal.pack(side=tk.RIGHT, padx=2)
    ent_log_start.pack(side=tk.RIGHT, padx=(2, 10))

    ctk.CTkLabel(date_log_frame, text="تا:", font=FONT_NORMAL).pack(side=tk.RIGHT, padx=(4, 2))
    ent_log_end = ctk.CTkEntry(
        date_log_frame, width=110, height=30, font=FONT_NORMAL, justify="center", placeholder_text="YYYY-MM-DD"
    )
    ent_log_end.insert(0, audit_log_filter_settings.get("end_date", ""))
    btn_end_cal = create_date_picker_button(
        date_log_frame,
        entry_widget=ent_log_end,
        title="انتخاب تاریخ پایان ارسال",
        icon_path=icon_p,
        width=30,
        height=30,
    )
    btn_end_cal.pack(side=tk.RIGHT, padx=2)
    ent_log_end.pack(side=tk.RIGHT, padx=2)

    group_sort = ctk.CTkFrame(popup, corner_radius=8)
    group_sort.pack(fill=tk.X, padx=15, pady=4)
    ctk.CTkLabel(group_sort, text="مرتب‌سازی نتایج", font=FONT_BOLD, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))
    sort_frame = ctk.CTkFrame(group_sort, fg_color="transparent")
    sort_frame.pack(fill=tk.X, padx=6, pady=(0, 6))

    ctk.CTkLabel(sort_frame, text="بر اساس:", font=FONT_NORMAL).pack(side=tk.RIGHT, padx=(5, 0))
    sort_options = {
        "شناسه": "id",
        "تاریخ ارسال": "sent_date",
        "تاریخ ثبت": "created_at",
        "عنوان کتاب": "book_title",
        "نام کاربر": "member_name",
        "شناسه امانت": "loan_id",
    }
    rev_sort_options = {v: k for k, v in sort_options.items()}

    sort_col_cb = ctk.CTkOptionMenu(
        sort_frame,
        width=130,
        font=FONT_NORMAL,
        dropdown_font=FONT_NORMAL,
        values=list(sort_options.keys()),
    )
    current_sort_label = rev_sort_options.get(sort_col_var.get(), "شناسه")
    sort_col_cb.set(current_sort_label)
    sort_col_cb.pack(side=tk.RIGHT, padx=5)

    ctk.CTkLabel(sort_frame, text="ترتیب:", font=FONT_NORMAL).pack(side=tk.RIGHT, padx=(12, 0))
    sort_dir_cb = ctk.CTkOptionMenu(
        sort_frame,
        width=140,
        font=FONT_NORMAL,
        dropdown_font=FONT_NORMAL,
        values=["نزولی (جدیدترین)", "صعودی (قدیمی‌ترین)"],
    )
    sort_dir_cb.set("نزولی (جدیدترین)" if sort_dir_var.get() == "DESC" else "صعودی (قدیمی‌ترین)")
    sort_dir_cb.pack(side=tk.RIGHT, padx=5)

    action_frame = ctk.CTkFrame(popup, fg_color="transparent")
    action_frame.pack(fill=tk.X, padx=15, pady=(15, 10))

    def apply_audit_log_filters():
        audit_log_filter_settings["column"] = col_var.get()
        audit_log_filter_settings["match_mode"] = match_var.get()
        audit_log_filter_settings["notification_type"] = type_var.get()
        audit_log_filter_settings["sort_col"] = sort_options.get(sort_col_cb.get(), "id")
        audit_log_filter_settings["sort_dir"] = "DESC" if "نزولی" in sort_dir_cb.get() else "ASC"
        audit_log_filter_settings["start_date"] = ent_log_start.get().strip()
        audit_log_filter_settings["end_date"] = ent_log_end.get().strip()

        type_display_map = {
            "all": "همه",
            "due_reminder": "یادآوری سررسید",
            "overdue": "هشدار دیرکرد",
            "test": "اعلان آزمایشی",
        }
        combo_log_type.set(type_display_map.get(audit_log_filter_settings["notification_type"], "همه"))

        update_audit_log_filter_indicator()
        popup.destroy()
        load_notification_logs_ui()

    def reset_audit_log_filters():
        audit_log_filter_settings["column"] = "all"
        audit_log_filter_settings["match_mode"] = "contains"
        audit_log_filter_settings["notification_type"] = "all"
        audit_log_filter_settings["sort_col"] = "id"
        audit_log_filter_settings["sort_dir"] = "DESC"
        audit_log_filter_settings["start_date"] = ""
        audit_log_filter_settings["end_date"] = ""

        combo_log_type.set("همه")
        update_audit_log_filter_indicator()
        popup.destroy()
        load_notification_logs_ui()

    btn_apply = create_icon_button(
        action_frame,
        text=" اعمال فیلتر ",
        icon_name="check",
        font=FONT_BOLD,
        fg_color="#2563eb",
        hover_color="#1d4ed8",
        command=apply_audit_log_filters,
    )
    btn_apply.pack(side=tk.RIGHT, padx=4)

    btn_reset = create_icon_button(
        action_frame,
        text=" تنظیم مجدد ",
        icon_name="rotate-ccw",
        font=FONT_NORMAL,
        fg_color="transparent",
        hover_color=("#e2e8f0", "#1e293b"),
        command=reset_audit_log_filters,
    )
    btn_reset.pack(side=tk.RIGHT, padx=4)

    btn_cancel = create_icon_button(
        action_frame,
        text=" انصراف ",
        icon_name="x",
        font=FONT_NORMAL,
        fg_color="transparent",
        hover_color=("#e2e8f0", "#1e293b"),
        command=popup.destroy,
    )
    btn_cancel.pack(side=tk.LEFT, padx=4)


def refresh_notification_logs():
    entry_log_search.delete(0, tk.END)
    combo_log_type.set("همه")
    audit_log_filter_settings["column"] = "all"
    audit_log_filter_settings["match_mode"] = "contains"
    audit_log_filter_settings["notification_type"] = "all"
    audit_log_filter_settings["sort_col"] = "id"
    audit_log_filter_settings["sort_dir"] = "DESC"
    audit_log_filter_settings["start_date"] = ""
    audit_log_filter_settings["end_date"] = ""
    update_audit_log_filter_indicator()
    load_notification_logs_ui()


def clear_logs_ui():
    confirm = messagebox.askyesno(
        "تأیید پاک‌سازی",
        "آیا از پاک‌سازی تمام تاریخچه اعلان‌ها اطمینان دارید؟ این عملیات غیرقابل بازگشت است.",
        parent=root,
    )
    if not confirm:
        return
    try:
        deleted = clear_notification_logs(db_p)
        refresh_notification_logs()
        messagebox.showinfo("موفقیت", f"تعداد {deleted} رکورد از تاریخچه اعلان‌ها پاک شد.", parent=root)
    except Exception as e:
        messagebox.showerror("خطا", f"خطا در پاک‌سازی تاریخچه:\n{e}", parent=root)


audit_log_search_after_id = None


def on_log_search_key_release(event=None):
    global audit_log_search_after_id
    if event and event.keysym in ("Up", "Down", "Left", "Right", "Return", "Escape"):
        return
    if audit_log_search_after_id is not None:
        try:
            root.after_cancel(audit_log_search_after_id)
        except Exception:
            pass
    audit_log_search_after_id = root.after(200, load_notification_logs_ui)


entry_log_search.bind("<KeyRelease>", on_log_search_key_release)
entry_log_search.bind("<Return>", lambda e: load_notification_logs_ui())
btn_filter_logs.configure(command=open_audit_log_filter_popup)


def load_settings_into_ui():
    try:
        with get_db_connection(db_p) as conn:
            settings = get_all_settings(conn)

        n_en = settings.get("notifications_enabled", "true").lower() == "true"
        s_en = settings.get("notification_sound", "true").lower() == "true"
        net_en = settings.get("internet_access_enabled", "true").lower() == "true"
        ai_en = settings.get("ai_features_enabled", "true").lower() == "true"
        adv = settings.get("notification_advance_days", "2")
        inv = settings.get("notification_check_interval_mins", "30")
        mln = int(settings.get("max_loans", "2"))
        combo_max_loans.set(str(mln))

        var_notif_enabled.set(n_en)
        var_notif_sound.set(s_en)
        var_internet_enabled.set(net_en)
        if not net_en:
            var_ai_enabled.set(False)
            chk_enable_ai.configure(state="disabled")
        else:
            var_ai_enabled.set(ai_en)
            chk_enable_ai.configure(state="normal")

        otp_en = settings.get("otp_cleanup_enabled", "true").lower() == "true"
        otp_int = settings.get("otp_cleanup_interval_hours", "12")
        var_otp_cleanup_enabled.set(otp_en)
        if otp_int in ["1", "3", "6", "12", "24", "48"]:
            combo_otp_interval.set(otp_int)
        else:
            combo_otp_interval.set("12")

        update_boot_net_status_label()
        update_ai_card_inputs_state(enabled=(net_en and ai_en))

        if adv in ["1", "2", "3", "5", "7"]:
            combo_advance_days.set(adv)
        else:
            combo_advance_days.set("2")

        if inv in ["15", "30", "60", "120", "360"]:
            combo_interval.set(inv)
        else:
            combo_interval.set("30")

        r_url = settings.get("openai_url") or "http://localhost:20128"
        r_key = settings.get("openai_key") or ""
        r_model = settings.get("openai_model") or "gemini-3.8-flash"

        entry_ai_url.delete(0, tk.END)
        entry_ai_url.insert(0, r_url)

        entry_ai_key.delete(0, tk.END)
        entry_ai_key.insert(0, r_key)

        entry_ai_model.delete(0, tk.END)
        entry_ai_model.insert(0, r_model)
    except Exception:
        pass


load_settings_into_ui()
load_notification_logs_ui()


def on_startup_update_detected(res: dict):
    latest_ver = res.get("latest_version", "")
    notification_engine.show(
        "بروزرسانی جدید در دسترس است",
        f"نسخه جدید {latest_ver} منتشر شده است.",
    )
    on_check_finished(res, interactive=False)
    confirm = messagebox.askyesno(
        "بروزرسانی جدید",
        f"نسخه جدید «{latest_ver}» نرم‌افزار در دسترس است.\nآیا مایلید به تب راهنما بروید و بروزرسانی را دریافت کنید؟",
        parent=root,
    )
    if confirm:
        notebook.select(help_frame)


def check_startup_updates():
    try:
        if not is_internet_access_enabled(db_p):
            return
        res = update_checker.check()
        if res.get("update_available"):
            root.after(1500, lambda: on_startup_update_detected(res))
        else:
            root.after(0, lambda: on_check_finished(res, interactive=False))
    except Exception:
        root.after(0, lambda: on_check_failed("", interactive=False))


threading.Thread(target=check_startup_updates, daemon=True).start()

root.bind("<Escape>", lambda event: root.destroy())
entry_serch.bind("<KeyRelease>", on_key_release)
entry_serch.bind("<Return>", search)
tree.bind("<Double-Button-1>", on_double_click)

show_login_view()
root.geometry("1080x720")

root.mainloop()
