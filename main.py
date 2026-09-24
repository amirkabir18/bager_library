import datetime
import os
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, ttk
from typing import Any

import customtkinter as ctk
import jdatetime
from PIL import Image

from notifications import LoanReminderManager, NotificationEngine

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
    delete_user,
    ensure_bootstrap_admin,
    get_user_by_identifier,
    is_super_admin,
    mask_phone_number,
    normalize_phone_number,
    update_user,
)
from database import (
    db_p,
    get_db_connection,
    init_database,
    is_ai_features_enabled,
    is_internet_access_enabled,
    tr,
)
from services.book_service import BookService
from services.dewey_ai_agent import (
    get_boot_internet_status,
    init_boot_internet_check,
)
from services.dewey_service import DeweyService
from ui.books_tab import build_books_tab
from ui.help_tab import build_help_tab
from ui.loans_tab import build_loans_tab
from ui.members_tab import build_members_tab
from ui.settings_tab import build_settings_tab
from ui.users_tab import build_users_tab

dewey_service = DeweyService()
book_service = BookService(dewey_service=dewey_service)

with get_db_connection(db_p) as _init_conn:
    init_database(_init_conn)
    ensure_bootstrap_admin(database_path=db_p)

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
            fn = globals().get("update_boot_net_status_label")
            if fn:
                root.after(0, fn)
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

FONTS = {
    "family": FONT_FAMILY,
    "header": FONT_HEADER,
    "normal": FONT_NORMAL,
    "bold": FONT_BOLD,
    "small": FONT_SMALL,
    "title": FONT_TITLE,
}

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

books_tab_controllers: dict[str, Any] = {}
loans_tab_controllers: dict[str, Any] = {}
members_tab_controllers: dict[str, Any] = {}
users_tab_controllers: dict[str, Any] = {}
settings_tab_controllers: dict[str, Any] = {}
help_tab_controllers: dict[str, Any] = {}


def search(event=None):
    if "search" in books_tab_controllers:
        return books_tab_controllers["search"](event)


def search_members(event=None):
    if "search_members" in members_tab_controllers:
        return members_tab_controllers["search_members"](event)


def search_users(event=None):
    if "search_users" in users_tab_controllers:
        return users_tab_controllers["search_users"](event)


def search_loans(event=None):
    if "search_loans" in loans_tab_controllers:
        return loans_tab_controllers["search_loans"](event)


refresh_loans_table = search_loans


def load_settings_into_ui():
    if "load_settings_into_ui" in settings_tab_controllers:
        return settings_tab_controllers["load_settings_into_ui"]()


def load_notification_logs_ui():
    if "load_notification_logs_ui" in settings_tab_controllers:
        return settings_tab_controllers["load_notification_logs_ui"]()


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


# ==================== کتاب‌ها (Books Management) ====================
def handle_borrow_book(book_title: str):
    switch_tab("loans")
    if "open_add_loan_popup" in loans_tab_controllers:
        loans_tab_controllers["open_add_loan_popup"](book_title)


books_tab_controllers.update(
    build_books_tab(
        parent=books_frame,
        root=root,
        fonts=FONTS,
        get_icon_fn=get_icon,
        create_icon_button_fn=create_icon_button,
        bind_table_delete_fn=bind_table_delete,
        db_path=db_p,
        book_service=book_service,
        is_ai_available_fn=is_ai_available,
        is_internet_access_enabled_fn=is_internet_access_enabled,
        on_borrow_book=handle_borrow_book,
        icon_path=icon_p,
    )
)


# ==================== اعضای کتابخانه (Library Members) ====================
members_tab_controllers.update(
    build_members_tab(
        parent=member_frame,
        root=root,
        fonts=FONTS,
        get_icon_fn=get_icon,
        create_icon_button_fn=create_icon_button,
        bind_table_delete_fn=bind_table_delete,
        db_path=db_p,
        icon_path=icon_p,
        on_member_updated=lambda: search_loans(),
    )
)


# ==================== مدیریت کاربران سیستم (System Users) ====================
def handle_user_updated(updated_user):
    global current_user
    if current_user and current_user.get("id") == updated_user.get("id"):
        current_user = updated_user
        u_role_str = tr(str(updated_user.get("role", "")))
        u_name_str = str(updated_user.get("username", ""))
        lbl_user_badge.configure(text=f"{u_name_str} ({u_role_str})")


users_tab_controllers.update(
    build_users_tab(
        parent=auth_users_frame,
        root=root,
        fonts=FONTS,
        get_icon_fn=get_icon,
        create_icon_button_fn=create_icon_button,
        bind_table_delete_fn=bind_table_delete,
        db_path=db_p,
        get_current_user_fn=lambda: current_user,
        on_user_updated=handle_user_updated,
        icon_path=icon_p,
    )
)

# ==================== جدول امانات (Loans Management) ====================
loans_tab_controllers.update(
    build_loans_tab(
        parent=tabel_frame,
        root=root,
        fonts=FONTS,
        get_icon_fn=get_icon,
        create_icon_button_fn=create_icon_button,
        bind_table_delete_fn=bind_table_delete,
        db_path=db_p,
        icon_path=icon_p,
        notification_engine=notification_engine,
        on_loan_changed=lambda: search(),
    )
)

# ==================== راهنما و درباره نرم‌افزار (Help & About) ====================
help_tab_controllers = build_help_tab(
    parent=help_frame,
    root=root,
    fonts={
        "family": FONT_FAMILY,
        "header": FONT_HEADER,
        "normal": FONT_NORMAL,
        "bold": FONT_BOLD,
        "small": FONT_SMALL,
    },
    get_icon_fn=get_icon,
    create_icon_button_fn=create_icon_button,
    is_internet_access_enabled_fn=is_internet_access_enabled,
    db_path=db_p,
)
update_checker = help_tab_controllers["update_checker"]
on_check_finished = help_tab_controllers["on_check_finished"]
on_check_failed = help_tab_controllers["on_check_failed"]

# ==================== تنظیمات و اعلان‌ها (Settings & Notifications) ====================
settings_tab_controllers.update(
    build_settings_tab(
        parent=settings_frame,
        root=root,
        fonts=FONTS,
        get_icon_fn=get_icon,
        create_icon_button_fn=create_icon_button,
        apply_treeview_styling_fn=apply_treeview_styling,
        notification_engine=notification_engine,
        reminder_manager=reminder_manager,
        otp_cleanup_manager=otp_cleanup_manager,
        db_path=db_p,
        icon_path=icon_p,
        on_data_restored=[search, search_members, search_loans, load_notification_logs_ui],
    )
)


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

show_login_view()
root.geometry("1080x720")

root.mainloop()
