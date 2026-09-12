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
db_p = os.path.join(base_dir, "bager_library.db")
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
    OTPService,
    authenticate,
    create_user,
    delete_user,
    ensure_bootstrap_admin,
    get_user_by_identifier,
    mask_phone_number,
    normalize_phone_number,
)
from database import (
    clear_notification_logs,
    get_all_settings,
    get_db_connection,
    get_notification_logs,
    init_database,
    log_notification,
    rtl_display_order,
    set_setting,
    tr,
)

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

if os.path.exists(icon_p):
    try:
        root.iconbitmap(icon_p)
    except Exception:
        pass

available_families = tkfont.families(root)
FONT_FAMILY = "IRANSansWeb(FaNum)" if "IRANSansWeb(FaNum)" in available_families else "Tahoma"

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
title_box.pack(side=tk.RIGHT, padx=12, pady=6)

logo_icon = get_icon("book-open", size=(22, 22))
lbl_app_logo = ctk.CTkLabel(
    title_box,
    text=" کتابخانه باقر العلوم ",
    image=logo_icon,
    compound="right",
    font=FONT_TITLE,
)
lbl_app_logo.pack(side=tk.RIGHT)

nav_bar = ctk.CTkFrame(header_frame, fg_color="transparent")
nav_bar.pack(side=tk.RIGHT, padx=8, fill=tk.Y)

left_actions = ctk.CTkFrame(header_frame, fg_color="transparent")
left_actions.pack(side=tk.LEFT, padx=12, pady=6)

lbl_user_badge = ctk.CTkLabel(left_actions, text="", font=FONT_NORMAL, text_color="#10b981")
lbl_user_badge.pack(side=tk.LEFT, padx=6)

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
    "sort_col": "id",
    "sort_dir": "ASC",
}

current_active_tab = "login"
nav_buttons: dict[str, ctk.CTkButton] = {}


def switch_tab(tab_name: str):
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
    for w in nav_bar.winfo_children():
        w.destroy()
    nav_buttons.clear()

    if current_user is None:
        lbl_user_badge.configure(text="")
        tabs = [
            ("login", "ورود به سامانه", "user-plus"),
            ("help", "راهنما", "bookmark"),
        ]
        default_tab = "login"
    else:
        u_role = tr(str(current_user.get("role", "")))
        u_name = str(current_user.get("username", ""))
        lbl_user_badge.configure(text=f"👤 {u_name} ({u_role})")

        user_role = str(current_user.get("role", "")).strip().lower()
        tabs = [
            ("books", "جستجوی کتاب", "book-open"),
            ("loans", "جدول امانات", "arrow-right-left"),
            ("members", "اعضای کتابخانه", "user-plus"),
        ]
        if user_role in ("super admin", "superadmin", "admin"):
            tabs.append(("users", "مدیریت کاربران", "user-plus"))
            try:
                search_users()
            except Exception:
                pass
        tabs.extend(
            [
                ("settings", "تنظیمات و اعلان‌ها", "filter"),
                ("help", "راهنما", "bookmark"),
                ("login", "حساب کاربری", "check"),
            ]
        )
        default_tab = "books"
        try:
            load_settings_into_ui()
            load_notification_logs_ui()
        except Exception:
            pass

    for tab_id, tab_label, tab_icon in tabs:
        btn = ctk.CTkButton(
            nav_bar,
            text=f" {tab_label} ",
            image=get_icon(tab_icon),
            compound="right",
            font=FONT_NORMAL,
            height=34,
            corner_radius=8,
            fg_color="transparent",
            text_color=("#334155", "#94a3b8"),
            hover_color=("#e2e8f0", "#2d3748"),
            command=lambda tid=tab_id: switch_tab(tid),
        )
        btn.pack(side=tk.RIGHT, padx=4)
        nav_buttons[tab_id] = btn

    switch_tab(default_tab)


rebuild_tabs()


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

    logout_btn = create_icon_button(
        login_frame,
        text=" خروج از حساب کاربری ",
        icon_name="x",
        font=FONT_BOLD,
        fg_color="#dc2626",
        hover_color="#b91c1c",
        height=38,
        command=logout,
    )
    logout_btn.pack(pady=20)


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
search_bar_frame.columnconfigure(3, weight=1)

sub_btn = create_icon_button(search_bar_frame, text=" جستجو ", icon_name="search", font=FONT_BOLD, width=90)
sub_btn.grid(row=0, column=0, padx=(8, 4), pady=6)

filter_btn = create_icon_button(search_bar_frame, text=" فیلترها ", icon_name="filter", font=FONT_NORMAL, width=90)
filter_btn.grid(row=0, column=1, padx=4, pady=6)

add_book_btn = create_icon_button(
    search_bar_frame,
    text=" افزودن کتاب ",
    icon_name="book-plus",
    font=FONT_NORMAL,
    fg_color="#16a34a",
    hover_color="#15803d",
    width=110,
)
add_book_btn.grid(row=0, column=2, padx=4, pady=6)

entry_serch = ctk.CTkEntry(
    search_bar_frame,
    placeholder_text="جستجو در بین کتاب‌ها (عنوان، نویسنده، شابک و ...)",
    font=FONT_NORMAL,
    justify="right",
    height=36,
)
entry_serch.grid(row=0, column=3, sticky="ew", padx=(4, 8), pady=6)

tree_frame = ctk.CTkFrame(books_frame, corner_radius=8)
tree_frame.pack(padx=10, pady=(0, 10), fill=tk.BOTH, expand=True)

scrollbar = ctk.CTkScrollbar(tree_frame)
scrollbar.pack(side=tk.LEFT, fill=tk.Y, padx=(4, 0), pady=4)

tree = ttk.Treeview(tree_frame, yscrollcommand=scrollbar.set, columns=columns, show="headings", height=15)
scrollbar.configure(command=tree.yview)
for col in columns:
    tree.heading(col, text=tr(col), anchor=tk.CENTER)
    tree.column(col, anchor=tk.CENTER)
tree["displaycolumns"] = rtl_display_order(columns, ["id", "title", "author", "isbn"])
tree.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(4, 8), pady=4)


def update_filter_button_indicator():
    is_custom = (
        filter_settings["column"] != "all"
        or filter_settings["match_mode"] != "contains"
        or filter_settings["availability"] != "all"
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
                sub_conds = [f"{col} {op} ?" for col in columns]
                where_conditions.append("(" + " OR ".join(sub_conds) + ")")
                params.extend([pattern] * len(columns))
            elif selected_col in columns:
                where_conditions.append(f"{selected_col} {op} ?")
                params.append(pattern)

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
    popup.geometry("460x530")
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
    py = max(50, ry + (rh - 530) // 2)
    popup.geometry(f"+{px}+{py}")

    col_var = tk.StringVar(value=filter_settings["column"])
    match_var = tk.StringVar(value=filter_settings["match_mode"])
    avail_var = tk.StringVar(value=filter_settings["availability"])
    sort_col_var = tk.StringVar(value=filter_settings["sort_col"])
    sort_dir_var = tk.StringVar(value=filter_settings["sort_dir"])

    group_col = ctk.CTkFrame(popup, corner_radius=8)
    group_col.pack(fill=tk.X, padx=15, pady=(12, 5))
    ctk.CTkLabel(group_col, text="جستجو در ستون:", font=FONT_BOLD, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))
    col_frame = ctk.CTkFrame(group_col, fg_color="transparent")
    col_frame.pack(fill=tk.X, padx=6, pady=(0, 6))
    rb_all = ctk.CTkRadioButton(col_frame, text="همه ستون‌ها", variable=col_var, value="all", font=FONT_NORMAL)
    rb_all.pack(side=tk.RIGHT, padx=4)
    for col in ["title", "author", "isbn", "id"]:
        if col in columns:
            rb = ctk.CTkRadioButton(col_frame, text=tr(col), variable=col_var, value=col, font=FONT_NORMAL)
            rb.pack(side=tk.RIGHT, padx=4)

    group_mode = ctk.CTkFrame(popup, corner_radius=8)
    group_mode.pack(fill=tk.X, padx=15, pady=5)
    ctk.CTkLabel(group_mode, text="نوع تطابق جستجو:", font=FONT_BOLD, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))
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
    group_avail.pack(fill=tk.X, padx=15, pady=5)
    ctk.CTkLabel(group_avail, text="وضعیت امانت کتاب:", font=FONT_BOLD, anchor="e").pack(
        fill=tk.X, padx=10, pady=(6, 2)
    )
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
    group_sort.pack(fill=tk.X, padx=15, pady=5)
    ctk.CTkLabel(group_sort, text="مرتب‌سازی نتایج:", font=FONT_BOLD, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))
    sort_frame = ctk.CTkFrame(group_sort, fg_color="transparent")
    sort_frame.pack(fill=tk.X, padx=6, pady=(0, 6))

    ctk.CTkLabel(sort_frame, text="بر اساس:", font=FONT_NORMAL).pack(side=tk.RIGHT, padx=(5, 0))
    sort_cols_available = [c for c in ["title", "author", "id"] if c in columns]
    sort_col_cb = ctk.CTkOptionMenu(
        sort_frame,
        width=130,
        font=FONT_NORMAL,
        values=[tr(c) for c in sort_cols_available],
    )
    sort_col_cb.set(tr(sort_col_var.get()))
    sort_col_cb.pack(side=tk.RIGHT, padx=5)

    ctk.CTkLabel(sort_frame, text="ترتیب:", font=FONT_NORMAL).pack(side=tk.RIGHT, padx=(12, 0))
    sort_dir_cb = ctk.CTkOptionMenu(sort_frame, width=100, font=FONT_NORMAL, values=["صعودی", "نزولی"])
    sort_dir_cb.set("صعودی" if sort_dir_var.get() == "ASC" else "نزولی")
    sort_dir_cb.pack(side=tk.RIGHT, padx=5)

    action_frame = ctk.CTkFrame(popup, fg_color="transparent")
    action_frame.pack(fill=tk.X, padx=15, pady=(15, 10))

    def apply_filters():
        filter_settings["column"] = col_var.get()
        filter_settings["match_mode"] = match_var.get()
        filter_settings["availability"] = avail_var.get()

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
    popup.title("ثبت کتاب جدید")
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

    ctk.CTkLabel(popup, text="ثبت کتاب جدید", font=FONT_TITLE).pack(pady=(15, 10))

    book_cols = [c for c in ["title", "author", "isbn"] if c in columns] + [
        c for c in columns if c not in ["id", "title", "author", "isbn"]
    ]
    popup_entries = {}
    for col in book_cols:
        col_fa = tr(col)
        row_f = ctk.CTkFrame(popup, fg_color="transparent")
        row_f.pack(fill=tk.X, padx=25, pady=4)
        ctk.CTkLabel(row_f, text=f"{col_fa}:", font=FONT_NORMAL, width=90, anchor="e").pack(side=tk.RIGHT, padx=(5, 0))
        ent = ctk.CTkEntry(row_f, font=FONT_NORMAL, justify="right", height=32)
        ent.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        popup_entries[col] = ent

    def do_insert_book():
        vals = []
        for col in book_cols:
            v = popup_entries[col].get().strip()
            if col == "title" and not v:
                messagebox.showwarning("خطا", "لطفاً عنوان کتاب را وارد کنید!", parent=popup)
                popup_entries[col].focus()
                return
            vals.append(v if v else None)

        temp_conn = get_db_connection(db_p)
        try:
            temp_cursor = temp_conn.cursor()

            placeholders = ", ".join(["?"] * len(book_cols))
            col_names = ", ".join(book_cols)
            query = f"INSERT INTO {tabel_name} ({col_names}) VALUES ({placeholders})"
            temp_cursor.execute(query, tuple(vals))

            temp_conn.commit()

            messagebox.showinfo("موفق", "اطلاعات کتاب با موفقیت ثبت شد!", parent=popup)
            popup.destroy()
            search()

        except sqlite3.IntegrityError:
            messagebox.showerror("خطا", "این کتاب (شابک تکراری) قبلاً ثبت شده است!", parent=popup)
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
        command=do_insert_book,
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
search_bar_frame_member.columnconfigure(3, weight=1)

sub_btn_member = create_icon_button(
    search_bar_frame_member, text=" جستجو ", icon_name="search", font=FONT_BOLD, width=90
)
sub_btn_member.grid(row=0, column=0, padx=(8, 4), pady=6)

filter_btn_member = create_icon_button(
    search_bar_frame_member, text=" فیلترها ", icon_name="filter", font=FONT_NORMAL, width=90
)
filter_btn_member.grid(row=0, column=1, padx=4, pady=6)

add_member_btn = create_icon_button(
    search_bar_frame_member,
    text=" افزودن عضو ",
    icon_name="user-plus",
    font=FONT_NORMAL,
    fg_color="#16a34a",
    hover_color="#15803d",
    width=110,
)
add_member_btn.grid(row=0, column=2, padx=4, pady=6)

entry_search_member = ctk.CTkEntry(
    search_bar_frame_member,
    placeholder_text="جستجو در اعضا (نام، شماره تماس و ...)",
    font=FONT_NORMAL,
    justify="right",
    height=36,
)
entry_search_member.grid(row=0, column=3, sticky="ew", padx=(4, 8), pady=6)

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
member_tree["displaycolumns"] = rtl_display_order(member_column, ["id", "member_id", "phone_number"])
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
    group_col.pack(fill=tk.X, padx=15, pady=(12, 5))
    ctk.CTkLabel(group_col, text="جستجو در ستون:", font=FONT_BOLD, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))
    col_frame = ctk.CTkFrame(group_col, fg_color="transparent")
    col_frame.pack(fill=tk.X, padx=6, pady=(0, 6))
    rb_all = ctk.CTkRadioButton(col_frame, text="همه ستون‌ها", variable=col_var, value="all", font=FONT_NORMAL)
    rb_all.pack(side=tk.RIGHT, padx=4)
    for col in member_column:
        rb = ctk.CTkRadioButton(col_frame, text=tr(col), variable=col_var, value=col, font=FONT_NORMAL)
        rb.pack(side=tk.RIGHT, padx=4)

    group_mode = ctk.CTkFrame(popup, corner_radius=8)
    group_mode.pack(fill=tk.X, padx=15, pady=5)
    ctk.CTkLabel(group_mode, text="نوع تطابق جستجو:", font=FONT_BOLD, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))
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
    group_sort.pack(fill=tk.X, padx=15, pady=5)
    ctk.CTkLabel(group_sort, text="مرتب‌سازی نتایج:", font=FONT_BOLD, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))
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
            temp_cursor.execute("INSERT INTO members (member_id, phone_number) VALUES (?, ?)", (m_id, norm_phone))
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


add_member_btn.configure(command=open_add_member_popup)

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
search_bar_frame_users.columnconfigure(3, weight=1)

sub_btn_users = create_icon_button(search_bar_frame_users, text=" جستجو ", icon_name="search", font=FONT_BOLD, width=90)
sub_btn_users.grid(row=0, column=0, padx=(8, 4), pady=6)

filter_btn_users = create_icon_button(
    search_bar_frame_users, text=" فیلترها ", icon_name="filter", font=FONT_NORMAL, width=90
)
filter_btn_users.grid(row=0, column=1, padx=4, pady=6)

add_user_btn = create_icon_button(
    search_bar_frame_users,
    text=" افزودن کاربر ",
    icon_name="user-plus",
    font=FONT_NORMAL,
    fg_color="#16a34a",
    hover_color="#15803d",
    width=110,
)
add_user_btn.grid(row=0, column=2, padx=4, pady=6)

entry_search_users = ctk.CTkEntry(
    search_bar_frame_users,
    placeholder_text="جستجو در کاربران سامانه (نام کاربری، شماره تماس، نقش و ...)",
    font=FONT_NORMAL,
    justify="right",
    height=36,
)
entry_search_users.grid(row=0, column=3, sticky="ew", padx=(4, 8), pady=6)

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
    group_col.pack(fill=tk.X, padx=15, pady=(12, 5))
    ctk.CTkLabel(group_col, text="جستجو در ستون:", font=FONT_BOLD, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))
    col_frame = ctk.CTkFrame(group_col, fg_color="transparent")
    col_frame.pack(fill=tk.X, padx=6, pady=(0, 6))
    rb_all = ctk.CTkRadioButton(col_frame, text="همه ستون‌ها", variable=col_var, value="all", font=FONT_NORMAL)
    rb_all.pack(side=tk.RIGHT, padx=4)
    for col in ["username", "phone_number", "role"]:
        rb = ctk.CTkRadioButton(col_frame, text=tr(col), variable=col_var, value=col, font=FONT_NORMAL)
        rb.pack(side=tk.RIGHT, padx=4)

    group_mode = ctk.CTkFrame(popup, corner_radius=8)
    group_mode.pack(fill=tk.X, padx=15, pady=5)
    ctk.CTkLabel(group_mode, text="نوع تطابق جستجو:", font=FONT_BOLD, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))
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
    group_sort.pack(fill=tk.X, padx=15, pady=5)
    ctk.CTkLabel(group_sort, text="مرتب‌سازی نتایج:", font=FONT_BOLD, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))
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


add_user_btn.configure(command=open_create_user_popup)

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
loans_tree["displaycolumns"] = rtl_display_order(
    loan_column, ["id", "member_name", "book_id", "borrow_date", "return_date", "borrowed"]
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

    m_idx = loan_column.index("member_name") if "member_name" in loan_column else -1
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

            searchable_cols = ["member_name", "book_id", "id"]
            if selected_col == "all":
                sub_conds = [f"{col} {op} ?" for col in searchable_cols]
                where_conditions.append("(" + " OR ".join(sub_conds) + ")")
                params.extend([pattern] * len(searchable_cols))
            elif selected_col in loan_column:
                where_conditions.append(f"{selected_col} {op} ?")
                params.append(pattern)

        status = loans_filter_settings.get("status", "all")
        if status == "borrowed":
            where_conditions.append("(borrowed = 1 OR borrowed = '1')")
        elif status == "returned":
            where_conditions.append("(borrowed = 0 OR borrowed = '0' OR borrowed IS NULL)")

        query = f"SELECT {', '.join(loan_column)} FROM `{new_tabel_name}`"
        if where_conditions:
            query += " WHERE " + " AND ".join(where_conditions)

        sort_col = loans_filter_settings.get("sort_col", "duration")
        sort_dir = loans_filter_settings.get("sort_dir", "ASC")
        if sort_dir not in ("ASC", "DESC"):
            sort_dir = "ASC"

        if sort_col == "duration":
            query += f" ORDER BY (julianday(`return_date`) - julianday(`borrow_date`)) {sort_dir}"
        else:
            if sort_col not in loan_column:
                sort_col = "id"
            query += f" ORDER BY `{sort_col}` {sort_dir}"

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
    popup.geometry("460x530")
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
    py = max(50, ry + (rh - 530) // 2)
    popup.geometry(f"+{px}+{py}")

    col_var = tk.StringVar(value=loans_filter_settings["column"])
    match_var = tk.StringVar(value=loans_filter_settings["match_mode"])
    status_var = tk.StringVar(value=loans_filter_settings["status"])
    sort_col_var = tk.StringVar(value=loans_filter_settings["sort_col"])
    sort_dir_var = tk.StringVar(value=loans_filter_settings["sort_dir"])

    group_col = ctk.CTkFrame(popup, corner_radius=8)
    group_col.pack(fill=tk.X, padx=15, pady=(12, 5))
    ctk.CTkLabel(group_col, text="جستجو در ستون:", font=FONT_BOLD, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))
    col_frame = ctk.CTkFrame(group_col, fg_color="transparent")
    col_frame.pack(fill=tk.X, padx=6, pady=(0, 6))
    rb_all = ctk.CTkRadioButton(col_frame, text="همه ستون‌ها", variable=col_var, value="all", font=FONT_NORMAL)
    rb_all.pack(side=tk.RIGHT, padx=4)
    for col in ["member_name", "book_id", "id"]:
        rb = ctk.CTkRadioButton(col_frame, text=tr(col), variable=col_var, value=col, font=FONT_NORMAL)
        rb.pack(side=tk.RIGHT, padx=4)

    group_mode = ctk.CTkFrame(popup, corner_radius=8)
    group_mode.pack(fill=tk.X, padx=15, pady=5)
    ctk.CTkLabel(group_mode, text="نوع تطابق جستجو:", font=FONT_BOLD, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))
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
    group_status.pack(fill=tk.X, padx=15, pady=5)
    ctk.CTkLabel(group_status, text="وضعیت امانت:", font=FONT_BOLD, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))
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

    group_sort = ctk.CTkFrame(popup, corner_radius=8)
    group_sort.pack(fill=tk.X, padx=15, pady=5)
    ctk.CTkLabel(group_sort, text="مرتب‌سازی نتایج:", font=FONT_BOLD, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))
    sort_frame = ctk.CTkFrame(group_sort, fg_color="transparent")
    sort_frame.pack(fill=tk.X, padx=6, pady=(0, 6))

    ctk.CTkLabel(sort_frame, text="بر اساس:", font=FONT_NORMAL).pack(side=tk.RIGHT, padx=(5, 0))
    sort_options = {
        "مدت امانت": "duration",
        "تاریخ بازگشت": "return_date",
        "تاریخ امانت": "borrow_date",
        "نام کاربر": "member_name",
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

    tk.Label(sort_frame, text="ترتیب:", font=FONT_NORMAL).pack(side=tk.RIGHT, padx=(12, 0))
    sort_dir_cb = ctk.CTkOptionMenu(sort_frame, width=100, font=FONT_NORMAL, values=["صعودی", "نزولی"])
    sort_dir_cb.set("صعودی" if sort_dir_var.get() == "ASC" else "نزولی")
    sort_dir_cb.pack(side=tk.RIGHT, padx=5)

    action_frame = ctk.CTkFrame(popup, fg_color="transparent")
    action_frame.pack(fill=tk.X, padx=15, pady=(15, 10))

    def apply_loans_filters():
        loans_filter_settings["column"] = col_var.get()
        loans_filter_settings["match_mode"] = match_var.get()
        loans_filter_settings["status"] = status_var.get()
        loans_filter_settings["sort_col"] = sort_options.get(sort_col_cb.get(), "duration")
        loans_filter_settings["sort_dir"] = "ASC" if sort_dir_cb.get() == "صعودی" else "DESC"

        update_loans_filter_indicator()
        popup.destroy()
        search_loans()

    def reset_loans_filters():
        loans_filter_settings["column"] = "all"
        loans_filter_settings["match_mode"] = "contains"
        loans_filter_settings["status"] = "all"
        loans_filter_settings["sort_col"] = "duration"
        loans_filter_settings["sort_dir"] = "ASC"

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
                  AND title NOT IN (SELECT book_id FROM loans WHERE borrowed = 1 OR borrowed = '1')
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
    cur_today = jdatetime.date.today()
    c_days_10 = cur_today + jdatetime.timedelta(days=10)
    c_days_20 = cur_today + jdatetime.timedelta(days=20)
    c_days_30 = cur_today + jdatetime.timedelta(days=30)

    ctk.CTkLabel(popup, text="تاریخ امانت کتاب (YYYY-MM-DD):", font=FONT_NORMAL, anchor="e").pack(
        fill=tk.X, padx=25, pady=(4, 0)
    )
    borrow_entry = ctk.CTkEntry(popup, font=FONT_NORMAL, justify="right", height=32)
    borrow_entry.pack(fill=tk.X, padx=25, pady=2)

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
    return_entry = ctk.CTkEntry(popup, font=FONT_NORMAL, justify="right", height=32)
    return_entry.pack(fill=tk.X, padx=25, pady=2)

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

        try:
            j_date = jdatetime.datetime.strptime(borrow_shamsi, "%Y-%m-%d")
            borrow_gregorian = j_date.togregorian().strftime("%Y-%m-%d")
        except ValueError:
            messagebox.showerror("خطا", "فرمت تاریخ امانت وارد شده صحیح نیست!\nمثال: 1403-06-20", parent=popup)
            return

        try:
            j_date = jdatetime.datetime.strptime(return_shamsi, "%Y-%m-%d")
            return_gregorian = j_date.togregorian().strftime("%Y-%m-%d")
        except ValueError:
            messagebox.showerror("خطا", "فرمت تاریخ بازگشت وارد شده صحیح نیست!\nمثال: 1403-06-30", parent=popup)
            return

        if return_gregorian < borrow_gregorian:
            messagebox.showerror("خطا", "تاریخ بازگشت نمی‌تواند پیش از تاریخ امانت باشد!", parent=popup)
            return

        ins_conn = get_db_connection(db_p)
        try:
            ins_cur = ins_conn.cursor()
            ins_cur.execute(
                "SELECT COUNT(*) FROM loans WHERE book_id = ? AND (borrowed = 1 OR borrowed = '1')", (b_title,)
            )
            if ins_cur.fetchone()[0] > 0:
                messagebox.showerror(
                    "خطا", f"کتاب «{b_title}» در حال حاضر در امانت است و امکان امانت مجدد آن وجود ندارد!", parent=popup
                )
                return

            ins_cur.execute(
                "INSERT INTO loans (member_name, book_id, return_date, borrow_date, borrowed) VALUES (?, ?, ?, ?, 1)",
                (m_name, b_title, return_gregorian, borrow_gregorian),
            )
            ins_conn.commit()
            notification_engine.show("ثبت موفق امانت", f"کتاب «{b_title}» با موفقیت برای {m_name} ثبت شد.")

            messagebox.showinfo("موفقیت", "اطلاعات امانت با موفقیت ذخیره شد!", parent=popup)
            popup.destroy()
            search_loans()
            search()
        except sqlite3.Error as e:
            messagebox.showerror("خطا در پایگاه داده", f"خطا در ذخیره اطلاعات: {e}", parent=popup)
        finally:
            ins_conn.close()

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

    conn = get_db_connection(db_p)
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM loans WHERE book_id = ? AND (borrowed = 1 OR borrowed = '1')", (title_value,))
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

loans_menu = tk.Menu(root, tearoff=0)
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
title_label_help = ctk.CTkLabel(help_frame, text="راهنما و درباره نرم‌افزار", font=FONT_TITLE)
title_label_help.pack(pady=(16, 4))

subtitle_label_help = ctk.CTkLabel(
    help_frame,
    text="سیستم مدیریت کتابخانه باقرالعلوم",
    font=FONT_NORMAL,
    text_color="#94a3b8",
)
subtitle_label_help.pack(pady=(0, 10))

help_content = ctk.CTkScrollableFrame(help_frame, corner_radius=10, fg_color="transparent")
help_content.pack(fill=tk.BOTH, expand=True, padx=25, pady=5)


def open_url(url: str):
    try:
        webbrowser.open(url)
    except Exception as e:
        messagebox.showerror("خطا", f"امکان باز کردن پیوند در مرورگر وجود ندارد:\n{e}", parent=root)


dev_group = ctk.CTkFrame(help_content, corner_radius=10)
dev_group.pack(fill=tk.X, pady=(0, 10))

dev_title = ctk.CTkLabel(dev_group, text=" توسعه‌دهندگان سامانه ", font=FONT_HEADER, anchor="e")
dev_title.pack(fill=tk.X, padx=16, pady=(12, 6))

developers_info = [
    ("امیرحسین اسدی", "@amirkabir18", "https://github.com/amirkabir18"),
    ("سید محمد حسن موسوی", "@Aliomosavi", "https://github.com/Aliomosavi"),
    ("امیررضا یونس‌زاده شیرازی", "@ARUSH221617", "https://github.com/ARUSH221617"),
]

for name, handle, profile_url in developers_info:
    row = ctk.CTkFrame(dev_group, fg_color="transparent")
    row.pack(fill=tk.X, padx=16, pady=3)

    lbl_name = ctk.CTkLabel(row, text=f"• {name}", font=FONT_NORMAL, anchor="e")
    lbl_name.pack(side=tk.RIGHT, padx=5)

    btn_h = ctk.CTkButton(
        row,
        text=handle,
        font=FONT_NORMAL,
        fg_color="transparent",
        text_color=("#2563eb", "#38bdf8"),
        hover_color=("#e2e8f0", "#1e293b"),
        height=26,
        width=110,
        command=lambda u=profile_url: open_url(u),
    )
    btn_h.pack(side=tk.LEFT, padx=5)

dev_spacer = ctk.CTkLabel(dev_group, text="", font=FONT_SMALL)
dev_spacer.pack(pady=2)

repo_url = "https://github.com/amirkabir18/bager_library"
repo_group = ctk.CTkFrame(help_content, corner_radius=10)
repo_group.pack(fill=tk.X, pady=(0, 10))

repo_title = ctk.CTkLabel(repo_group, text=" مخزن گیت‌هاب پروژه ", font=FONT_HEADER, anchor="e")
repo_title.pack(fill=tk.X, padx=16, pady=(12, 4))

repo_desc = ctk.CTkLabel(
    repo_group,
    text="سورس‌کد و مستندات پروژه در گیت‌هاب:",
    font=FONT_NORMAL,
    anchor="e",
)
repo_desc.pack(fill=tk.X, padx=16, pady=(0, 6))

repo_row = ctk.CTkFrame(repo_group, fg_color="transparent")
repo_row.pack(fill=tk.X, padx=16, pady=(0, 12))

btn_repo = create_icon_button(
    repo_row,
    text=" مشاهده مخزن در گیت‌هاب ",
    icon_name="bookmark",
    font=FONT_NORMAL,
    command=lambda: open_url(repo_url),
    width=160,
    height=32,
)
btn_repo.pack(side=tk.RIGHT, padx=5)

lbl_repo_url = ctk.CTkButton(
    repo_row,
    text=repo_url,
    font=FONT_NORMAL,
    fg_color="transparent",
    text_color=("#2563eb", "#38bdf8"),
    hover_color=("#e2e8f0", "#1e293b"),
    height=28,
    command=lambda: open_url(repo_url),
)
lbl_repo_url.pack(side=tk.LEFT, padx=5)

issue_url = "https://github.com/amirkabir18/bager_library/issues/new"
issue_group = ctk.CTkFrame(help_content, corner_radius=10)
issue_group.pack(fill=tk.X, pady=(0, 10))

issue_title = ctk.CTkLabel(issue_group, text=" ثبت گزارش خطا یا پیشنهاد (New Issue) ", font=FONT_HEADER, anchor="e")
issue_title.pack(fill=tk.X, padx=16, pady=(12, 4))

issue_desc = ctk.CTkLabel(
    issue_group,
    text="برای گزارش باگ‌ها، مشکلات یا ثبت پیشنهادات، یک Issue جدید در گیت‌هاب باز کنید:",
    font=FONT_NORMAL,
    anchor="e",
)
issue_desc.pack(fill=tk.X, padx=16, pady=(0, 6))

issue_row = ctk.CTkFrame(issue_group, fg_color="transparent")
issue_row.pack(fill=tk.X, padx=16, pady=(0, 12))

btn_issue = create_icon_button(
    issue_row,
    text=" ثبت Issue جدید در گیت‌هاب ",
    font=FONT_BOLD,
    fg_color="#2563eb",
    hover_color="#1d4ed8",
    command=lambda: open_url(issue_url),
    width=170,
    height=32,
)
btn_issue.pack(side=tk.RIGHT, padx=5)

lbl_issue_url = ctk.CTkButton(
    issue_row,
    text=issue_url,
    font=FONT_NORMAL,
    fg_color="transparent",
    text_color=("#2563eb", "#38bdf8"),
    hover_color=("#e2e8f0", "#1e293b"),
    height=28,
    command=lambda: open_url(issue_url),
)
lbl_issue_url.pack(side=tk.LEFT, padx=5)

app_info = load_app_info()
app_version = app_info.get("version", "0.1.0")
update_checker = UpdateChecker(
    repo=app_info.get("github_repo", "amirkabir18/bager_library"),
    current_version=app_version,
)
download_manager = DownloadManager()

update_group = ctk.CTkFrame(help_content, corner_radius=10)
update_group.pack(fill=tk.X, pady=(0, 10))

update_title = ctk.CTkLabel(update_group, text=" بروزرسانی نرم‌افزار ", font=FONT_HEADER, anchor="e")
update_title.pack(fill=tk.X, padx=16, pady=(12, 4))

info_row = ctk.CTkFrame(update_group, fg_color="transparent")
info_row.pack(fill=tk.X, padx=16, pady=4)

lbl_current_ver = ctk.CTkLabel(info_row, text=f"نسخه فعلی: {app_version}", font=FONT_NORMAL, anchor="e")
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

update_progress = ctk.CTkProgressBar(progress_row, mode="determinate")
update_progress.set(0.0)
update_progress.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10, 0))

lbl_progress_text = ctk.CTkLabel(progress_row, text="", font=FONT_NORMAL, text_color="#94a3b8", width=180, anchor="w")
lbl_progress_text.pack(side=tk.LEFT, padx=(0, 5))

actions_row = ctk.CTkFrame(update_group, fg_color="transparent")
actions_row.pack(fill=tk.X, padx=16, pady=(6, 12))

latest_update_info: dict = {}


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
    progress_row.pack(fill=tk.X, padx=16, pady=4, before=actions_row)
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
    font=FONT_BOLD,
    command=lambda: perform_check(interactive=True),
    width=140,
    height=32,
)
btn_update_action.pack(side=tk.RIGHT, padx=5)

btn_cancel_update = create_icon_button(
    actions_row,
    text=" لغو دانلود ",
    font=FONT_NORMAL,
    fg_color="transparent",
    hover_color=("#e2e8f0", "#1e293b"),
    command=download_manager.cancel,
    width=100,
    height=32,
)

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

pref_row2 = ctk.CTkFrame(pref_card, fg_color="transparent")
pref_row2.pack(fill=tk.X, padx=16, pady=6)

ctk.CTkLabel(pref_row2, text="ارسال یادآوری سررسید (چند روز قبل):", font=FONT_NORMAL).pack(side=tk.RIGHT, padx=5)

combo_advance_days = ctk.CTkOptionMenu(
    pref_row2,
    values=["1", "2", "3", "5", "7"],
    width=80,
)
combo_advance_days.set("2")
combo_advance_days.pack(side=tk.RIGHT, padx=10)

ctk.CTkLabel(pref_row2, text="فاصله بررسی خودکار (دقیقه):", font=FONT_NORMAL).pack(side=tk.RIGHT, padx=(20, 5))

combo_interval = ctk.CTkOptionMenu(
    pref_row2,
    values=["15", "30", "60", "120", "360"],
    width=80,
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
)
combo_theme.set("تیره (Dark)")
combo_theme.pack(side=tk.RIGHT, padx=5)

pref_row3 = ctk.CTkFrame(pref_card, fg_color="transparent")
pref_row3.pack(fill=tk.X, padx=16, pady=(10, 14))


def save_settings_ui():
    notif_val = "true" if var_notif_enabled.get() else "false"
    sound_val = "true" if var_notif_sound.get() else "false"
    adv_days = str(combo_advance_days.get()).strip() or "2"
    interval = str(combo_interval.get()).strip() or "30"

    try:
        with get_db_connection(db_p) as conn:
            set_setting(conn, "notifications_enabled", notif_val)
            set_setting(conn, "notification_sound", sound_val)
            set_setting(conn, "notification_advance_days", adv_days)
            set_setting(conn, "notification_check_interval_mins", interval)

        try:
            reminder_manager.reschedule()
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
}


def update_audit_log_filter_indicator():
    is_custom = (
        audit_log_filter_settings["column"] != "all"
        or audit_log_filter_settings["match_mode"] != "contains"
        or audit_log_filter_settings["notification_type"] != "all"
        or audit_log_filter_settings["sort_col"] != "id"
        or audit_log_filter_settings["sort_dir"] != "DESC"
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

    try:
        logs = get_notification_logs(
            conn_or_path=db_p,
            notification_type=type_filter,
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
    popup.geometry("460x530")
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
    py = max(50, ry + (rh - 530) // 2)
    popup.geometry(f"+{px}+{py}")

    col_var = tk.StringVar(value=audit_log_filter_settings["column"])
    match_var = tk.StringVar(value=audit_log_filter_settings["match_mode"])
    type_var = tk.StringVar(value=audit_log_filter_settings["notification_type"])
    sort_col_var = tk.StringVar(value=audit_log_filter_settings["sort_col"])
    sort_dir_var = tk.StringVar(value=audit_log_filter_settings["sort_dir"])

    group_col = ctk.CTkFrame(popup, corner_radius=8)
    group_col.pack(fill=tk.X, padx=15, pady=(12, 5))
    ctk.CTkLabel(group_col, text="جستجو در ستون:", font=FONT_BOLD, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))

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
    group_mode.pack(fill=tk.X, padx=15, pady=5)
    ctk.CTkLabel(group_mode, text="نوع تطابق جستجو:", font=FONT_BOLD, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))
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
    group_type.pack(fill=tk.X, padx=15, pady=5)
    ctk.CTkLabel(group_type, text="نوع اعلان:", font=FONT_BOLD, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))
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

    group_sort = ctk.CTkFrame(popup, corner_radius=8)
    group_sort.pack(fill=tk.X, padx=15, pady=5)
    ctk.CTkLabel(group_sort, text="مرتب‌سازی نتایج:", font=FONT_BOLD, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))
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
        adv = settings.get("notification_advance_days", "2")
        inv = settings.get("notification_check_interval_mins", "30")

        var_notif_enabled.set(n_en)
        var_notif_sound.set(s_en)
        if adv in ["1", "2", "3", "5", "7"]:
            combo_advance_days.set(adv)
        else:
            combo_advance_days.set("2")

        if inv in ["15", "30", "60", "120", "360"]:
            combo_interval.set(inv)
        else:
            combo_interval.set("30")
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
