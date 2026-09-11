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

import jdatetime

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
    get_db_connection,
    init_database,
    rtl_display_order,
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

root = tk.Tk()
root.title("کتابخانه باقر العلوم")
notification_engine = NotificationEngine(root, icon_path=icon_p)
reminder_manager = LoanReminderManager(root, db_p, notification_engine)
reminder_manager.start()

if os.path.exists(icon_p):
    try:
        root.iconbitmap(icon_p)
    except Exception:
        pass

available_families = tkfont.families(root)
FONT_FAMILY = "IRANSansWeb(FaNum)" if "IRANSansWeb(FaNum)" in available_families else "Tahoma"

for font_name in (
    "TkDefaultFont",
    "TkTextFont",
    "TkFixedFont",
    "TkMenuFont",
    "TkHeadingFont",
    "TkCaptionFont",
    "TkSmallCaptionFont",
    "TkTooltipFont",
):
    try:
        tkfont.nametofont(font_name).configure(family=FONT_FAMILY, size=10)
    except Exception:
        pass

FONT_TITLE = (FONT_FAMILY, 13, "bold")
FONT_NORMAL = (FONT_FAMILY, 10)
FONT_BOLD = (FONT_FAMILY, 10, "bold")

icons_cache: dict[str, tk.PhotoImage] = {}


def get_icon(name: str) -> tk.PhotoImage | None:
    if name in icons_cache:
        return icons_cache[name]
    icon_path = os.path.join(base_dir, "assets", "icons", "lucide", f"{name}.png")
    if os.path.exists(icon_path):
        try:
            img = tk.PhotoImage(file=icon_path)
            icons_cache[name] = img
            return img
        except Exception:
            return None
    return None


def create_icon_button(parent, text: str, icon_name: str | None = None, command=None, font=None, **kwargs) -> tk.Button:
    btn = tk.Button(parent, text=text, font=font or FONT_NORMAL, **kwargs)
    if command is not None:
        btn.config(command=command)
    if icon_name:
        img = get_icon(icon_name)
        if img:
            btn.config(image=img, compound=tk.RIGHT)
            setattr(btn, "image", img)
    return btn


st = ttk.Style()
st.configure(".", font=FONT_NORMAL)
st.configure("Treeview", font=FONT_NORMAL, rowheight=30)
st.configure("Treeview.Heading", font=FONT_BOLD)
st.configure("TNotebook", tabposition="ne")
st.configure("TNotebook.Tab", font=FONT_NORMAL)
st.configure("TCombobox", font=FONT_NORMAL)
st.configure("TRadiobutton", font=FONT_NORMAL)
st.configure("Modern.TRadiobutton", font=FONT_NORMAL)

current_user: dict | None = None


def bind_table_delete(tree_widget, table_name, id_col_index=0, on_deleted=None):
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
            for item_id, rec_id in valid_items:
                del_ok, msg = delete_user(int(rec_id), database_path=db_p)
                if del_ok:
                    tree_widget.delete(item_id)
                else:
                    all_succeeded = False
                    messagebox.showerror("خطا در حذف کاربر", msg, parent=root)
            if all_succeeded:
                messagebox.showinfo("موفق", "کاربر با موفقیت حذف شد.", parent=root)
            if on_deleted:
                on_deleted()
            return

        del_conn = get_db_connection(db_p)
        try:
            del_cur = del_conn.cursor()
            for item_id, rec_id in valid_items:
                del_cur.execute(f"DELETE FROM `{table_name}` WHERE id = ?", (rec_id,))
                tree_widget.delete(item_id)
            del_conn.commit()
            messagebox.showinfo("موفق", "ردیف با موفقیت حذف شد.", parent=root)
            if on_deleted:
                on_deleted()
        except sqlite3.Error as e:
            messagebox.showerror("خطا", f"خطا در حذف اطلاعات: {e}", parent=root)
        finally:
            del_conn.close()

    tree_widget.bind("<Delete>", on_delete_key)


notebook = ttk.Notebook(root)
notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

filter_settings = {
    "column": "all",
    "match_mode": "contains",
    "availability": "all",
    "sort_col": "id",
    "sort_dir": "ASC",
}

login_frame = ttk.Frame(notebook)
books_frame = ttk.Frame(notebook)
tabel_frame = ttk.Frame(notebook)
member_frame = ttk.Frame(notebook)
auth_users_frame = ttk.Frame(notebook)
help_frame = ttk.Frame(notebook)


def rebuild_tabs():
    for tab in list(notebook.tabs()):
        try:
            notebook.forget(tab)
        except Exception:
            pass

    if current_user is None:
        notebook.add(help_frame, text=" راهنما ")
        notebook.add(login_frame, text=" ورود ")
        notebook.select(login_frame)
    else:
        notebook.add(login_frame, text=" وضعیت حساب ")
        notebook.add(help_frame, text=" راهنما ")

        user_role = str(current_user.get("role", "")).strip().lower()
        if user_role in ("super admin", "superadmin", "admin"):
            notebook.add(auth_users_frame, text=" مدیریت کاربران ")
            try:
                search_users()
            except Exception:
                pass

        notebook.add(member_frame, text=" اعضای کتابخانه ")
        notebook.add(tabel_frame, text=" جدول امانات ")
        notebook.add(books_frame, text=" جستجوی کتاب ")

        notebook.select(books_frame)


rebuild_tabs()


def show_logged_in_view(user):
    for widget in login_frame.winfo_children():
        widget.destroy()

    tk.Label(login_frame, text="وضعیت حساب کاربری", font=FONT_TITLE).pack(pady=15)

    info_card = tk.LabelFrame(login_frame, text="مشخصات حساب کاربری فعال", font=FONT_BOLD, padx=20, pady=15)
    info_card.pack(pady=10, padx=20, fill=tk.X)

    role_val = str(user.get("role", ""))
    role_fa = tr(role_val)
    tk.Label(info_card, text=f"نام کاربری: {user.get('username', '')}", font=FONT_BOLD, anchor="e").pack(
        fill=tk.X, pady=4
    )
    tk.Label(info_card, text=f"شماره تلفن: {user.get('phone_number', '')}", font=FONT_NORMAL, anchor="e").pack(
        fill=tk.X, pady=4
    )
    tk.Label(info_card, text=f"نقش کاربری: {role_fa}", font=FONT_BOLD, fg="#198754", anchor="e").pack(fill=tk.X, pady=4)
    if user.get("telegram_chat_id"):
        tk.Label(info_card, text=f"شناسه چت تلگرام: {user.get('telegram_chat_id')}", font=FONT_NORMAL, anchor="e").pack(
            fill=tk.X, pady=4
        )

    logout_btn = create_icon_button(
        login_frame,
        text=" خروج از حساب کاربری ",
        icon_name="x",
        font=FONT_BOLD,
        fg="red",
        padx=12,
        pady=5,
        command=logout,
    )
    logout_btn.pack(pady=20)


def show_login_view():
    for widget in login_frame.winfo_children():
        widget.destroy()

    tk.Label(login_frame, text="ورود به کتابخانه باقر العلوم", font=FONT_TITLE).pack(pady=15)

    card = tk.LabelFrame(login_frame, text=" ورود با رمز یکبار مصرف (OTP) ", font=FONT_BOLD, padx=25, pady=20)
    card.pack(pady=10, padx=20)

    step1_frame = tk.Frame(card)
    step1_frame.pack(fill=tk.BOTH, expand=True)

    status_lbl = tk.Label(
        step1_frame, text="شماره تلفن همراه خود را وارد کنید:", font=FONT_NORMAL, wraplength=380, justify="center"
    )
    status_lbl.pack(pady=8)

    phone_entry = tk.Entry(step1_frame, font=FONT_NORMAL, justify="center", width=26)
    phone_entry.pack(pady=6)
    phone_entry.focus()

    step2_frame = tk.Frame(card)

    otp_info_lbl = tk.Label(step2_frame, text="", font=FONT_NORMAL, fg="#0d6efd", wraplength=380, justify="center")
    otp_info_lbl.pack(pady=6)

    otp_code_lbl = tk.Label(step2_frame, text="کد تأیید ۶ رقمی را وارد کنید:", font=FONT_NORMAL)
    otp_code_lbl.pack(pady=4)

    otp_entry = tk.Entry(step2_frame, font=(FONT_FAMILY, 14, "bold"), justify="center", width=14)
    otp_entry.pack(pady=6)

    pwd_frame = tk.Frame(card)
    pwd_status_lbl = tk.Label(
        pwd_frame,
        text="شماره تلفن یا نام کاربری و رمز عبور را وارد کنید:",
        font=FONT_NORMAL,
        wraplength=380,
        justify="center",
    )
    pwd_status_lbl.pack(pady=6)

    tk.Label(pwd_frame, text="نام کاربری یا شماره تلفن:", font=FONT_NORMAL).pack(pady=2)
    pwd_ident_entry = tk.Entry(pwd_frame, font=FONT_NORMAL, justify="center", width=26)
    pwd_ident_entry.pack(pady=4)

    tk.Label(pwd_frame, text="رمز عبور:", font=FONT_NORMAL).pack(pady=2)
    pwd_val_entry = tk.Entry(pwd_frame, font=FONT_NORMAL, justify="center", width=26, show="*")
    pwd_val_entry.pack(pady=4)

    pending_phone = {"val": ""}

    def switch_to_pwd():
        step1_frame.pack_forget()
        step2_frame.pack_forget()
        card.config(text=" ورود با رمز عبور (آفلاین) ")
        pwd_frame.pack(fill=tk.BOTH, expand=True)
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
        card.config(text=" ورود با رمز یکبار مصرف (OTP) ")
        step1_frame.pack(fill=tk.BOTH, expand=True)
        phone_entry.focus()

    def do_pwd_login(event=None):
        ident = pwd_ident_entry.get().strip()
        pwd = pwd_val_entry.get().strip()
        if not ident or not pwd:
            pwd_status_lbl.config(text="لطفاً نام کاربری و رمز عبور را وارد کنید!", fg="red")
            return
        success, msg, u = authenticate(ident, pwd, mode="password", database_path=db_p)
        if success and u:
            on_login_success(u)
        else:
            pwd_status_lbl.config(text=msg or "اطلاعات ورود نادرست است.", fg="red")

    def reset_to_step1():
        step2_frame.pack_forget()
        pwd_frame.pack_forget()
        card.config(text=" ورود با رمز یکبار مصرف (OTP) ")
        step1_frame.pack(fill=tk.BOTH, expand=True)
        status_lbl.config(text="شماره تلفن همراه خود را وارد کنید:", fg="black")
        phone_entry.delete(0, tk.END)
        phone_entry.insert(0, pending_phone["val"])
        phone_entry.focus()

    def do_request_otp(event=None):
        raw_phone = phone_entry.get().strip()
        norm_phone = normalize_phone_number(raw_phone)
        if len(norm_phone) != 11 or not norm_phone.startswith("09"):
            status_lbl.config(text="شماره تلفن نامعتبر است! مثال: 09123456789", fg="red")
            phone_entry.focus()
            return

        u = get_user_by_identifier(norm_phone, database_path=db_p)
        if not u:
            status_lbl.config(text="کاربری با این شماره تلفن یافت نشد.", fg="red")
            messagebox.showerror("خطا", "کاربری با این شماره تلفن در سامانه یافت نشد.", parent=root)
            return

        otp_s = OTPService(database_path=db_p)
        req_res = otp_s.request_otp(norm_phone)
        if req_res[0]:
            pending_phone["val"] = norm_phone
            step1_frame.pack_forget()
            step2_frame.pack(fill=tk.BOTH, expand=True)
            otp_info_lbl.config(text=f"کد تأیید به شماره {mask_phone_number(norm_phone)} ارسال شد.")
            otp_entry.delete(0, tk.END)
            otp_entry.focus()
        else:
            status_lbl.config(text=f"خطا در ارسال کد:\n{req_res[1]}", fg="red")
            btn_fallback_pwd.config(fg="#dc2626")

    def do_verify_otp(event=None):
        code = otp_entry.get().strip()
        if len(code) != 6 or not code.isdigit():
            otp_code_lbl.config(text="کد OTP باید ۶ رقم عددی باشد.", fg="red")
            otp_entry.focus()
            return

        target_phone = pending_phone["val"]
        otp_s = OTPService(database_path=db_p)
        verify_res = otp_s.verify_otp(target_phone, code)
        if verify_res[0]:
            u = get_user_by_identifier(target_phone, database_path=db_p)
            on_login_success(u)
        else:
            otp_code_lbl.config(text=f"کد اشتباه یا منقضی است: {verify_res[1]}", fg="red")
            otp_entry.focus()

    btn_req_otp = create_icon_button(
        step1_frame,
        text=" درخواست کد OTP ",
        icon_name="arrow-right-left",
        font=FONT_BOLD,
        padx=12,
        pady=4,
        command=do_request_otp,
    )
    btn_req_otp.pack(pady=(10, 4))

    btn_fallback_pwd = create_icon_button(
        step1_frame,
        text=" ورود با رمز عبور (آفلاین) ",
        font=FONT_NORMAL,
        fg="#0d6efd",
        padx=8,
        pady=2,
        command=switch_to_pwd,
    )
    btn_fallback_pwd.pack(pady=4)

    btn_verify = create_icon_button(
        step2_frame, text=" تأیید و ورود ", icon_name="check", font=FONT_BOLD, padx=14, pady=4, command=do_verify_otp
    )
    btn_verify.pack(pady=8)

    btn_back = create_icon_button(
        step2_frame,
        text=" تغییر شماره / ارسال مجدد ",
        icon_name="rotate-ccw",
        font=FONT_NORMAL,
        padx=8,
        pady=3,
        command=reset_to_step1,
    )
    btn_back.pack(pady=3)

    btn_step2_pwd = create_icon_button(
        step2_frame,
        text=" ورود با رمز عبور آفلاین ",
        font=FONT_NORMAL,
        fg="#0d6efd",
        padx=8,
        pady=2,
        command=switch_to_pwd,
    )
    btn_step2_pwd.pack(pady=3)

    btn_do_pwd = create_icon_button(
        pwd_frame, text=" ورود به سامانه ", icon_name="check", font=FONT_BOLD, padx=14, pady=4, command=do_pwd_login
    )
    btn_do_pwd.pack(pady=8)

    btn_back_to_otp = create_icon_button(
        pwd_frame,
        text=" بازگشت به ورود با پیامک/تلگرام (OTP) ",
        icon_name="arrow-right-left",
        font=FONT_NORMAL,
        padx=8,
        pady=3,
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


search_bar_frame = ttk.Frame(books_frame)
search_bar_frame.pack(fill=tk.X, padx=10, pady=10)
search_bar_frame.columnconfigure(3, weight=1)

sub_btn = create_icon_button(search_bar_frame, text=" جستجو ", icon_name="search", font=FONT_BOLD, padx=6)
sub_btn.grid(row=0, column=0, padx=(0, 6))

filter_btn = create_icon_button(search_bar_frame, text=" فیلترها ", icon_name="filter", font=FONT_NORMAL, padx=6)
filter_btn.grid(row=0, column=1, padx=(0, 6))

add_book_btn = create_icon_button(
    search_bar_frame, text=" افزودن کتاب ", icon_name="book-plus", font=FONT_NORMAL, padx=6
)
add_book_btn.grid(row=0, column=2, padx=(0, 6))

entry_serch = tk.Entry(search_bar_frame, font=FONT_NORMAL, justify="right")
entry_serch.grid(row=0, column=3, sticky="ew")

tree_frame = tk.Frame(books_frame)
tree_frame.pack(padx=10, pady=(0, 10), fill=tk.BOTH, expand=True)

scrollbar = tk.Scrollbar(tree_frame)
scrollbar.pack(side=tk.LEFT, fill=tk.Y)

tree = ttk.Treeview(tree_frame, yscrollcommand=scrollbar.set, columns=columns, show="headings", height=15)
scrollbar.config(command=tree.yview)
for col in columns:
    tree.heading(col, text=tr(col), anchor=tk.CENTER)
    tree.column(col, anchor=tk.CENTER)
tree["displaycolumns"] = rtl_display_order(columns, ["id", "title", "author", "isbn"])
tree.pack(side=tk.RIGHT, fill="both", expand=True, padx=10, pady=10)


def update_filter_button_indicator():
    is_custom = (
        filter_settings["column"] != "all"
        or filter_settings["match_mode"] != "contains"
        or filter_settings["availability"] != "all"
        or filter_settings["sort_col"] != "id"
        or filter_settings["sort_dir"] != "ASC"
    )
    if is_custom:
        filter_btn.config(text=" فیلترها (فعال) ", fg="#0d6efd")
    else:
        filter_btn.config(text=" فیلترها ", fg="black")


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
                tree.insert("", "end", values=row)
        else:
            tree.insert("", "end", values=("❌ نتیجه‌ای یافت نشد!",) + ("",) * (len(columns) - 1))

    except Exception as e:
        messagebox.showerror("خطا", f"خطا در جستجو: {str(e)}")
    finally:
        temp_conn.close()


sub_btn.config(command=search)


def open_filter_popup():
    popup = tk.Toplevel(root)
    popup.title("فیلترهای پیشرفته جستجو")
    popup.geometry("440x510")
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
    py = max(50, ry + (rh - 510) // 2)
    popup.geometry(f"+{px}+{py}")

    col_var = tk.StringVar(value=filter_settings["column"])
    match_var = tk.StringVar(value=filter_settings["match_mode"])
    avail_var = tk.StringVar(value=filter_settings["availability"])
    sort_col_var = tk.StringVar(value=filter_settings["sort_col"])
    sort_dir_var = tk.StringVar(value=filter_settings["sort_dir"])

    group_col = tk.LabelFrame(popup, text="جستجو در ستون", font=FONT_BOLD, padx=10, pady=5)
    group_col.pack(fill=tk.X, padx=15, pady=(10, 5))
    col_frame = tk.Frame(group_col)
    col_frame.pack(fill=tk.X)
    rb_all = tk.Radiobutton(col_frame, text="همه ستون‌ها", variable=col_var, value="all", font=FONT_NORMAL, anchor="e")
    rb_all.pack(side=tk.RIGHT, padx=4)
    for col in ["title", "author", "isbn", "id"]:
        if col in columns:
            rb = tk.Radiobutton(col_frame, text=tr(col), variable=col_var, value=col, font=FONT_NORMAL, anchor="e")
            rb.pack(side=tk.RIGHT, padx=4)

    group_mode = tk.LabelFrame(popup, text="نوع تطابق جستجو", font=FONT_BOLD, padx=10, pady=5)
    group_mode.pack(fill=tk.X, padx=15, pady=5)
    mode_frame = tk.Frame(group_mode)
    mode_frame.pack(fill=tk.X)
    rb_contains = tk.Radiobutton(
        mode_frame, text="شامل عبارت", variable=match_var, value="contains", font=FONT_NORMAL, anchor="e"
    )
    rb_contains.pack(side=tk.RIGHT, padx=8)
    rb_starts = tk.Radiobutton(
        mode_frame, text="شروع با عبارت", variable=match_var, value="startswith", font=FONT_NORMAL, anchor="e"
    )
    rb_starts.pack(side=tk.RIGHT, padx=8)
    rb_exact = tk.Radiobutton(
        mode_frame, text="مطابقت دقیق", variable=match_var, value="exact", font=FONT_NORMAL, anchor="e"
    )
    rb_exact.pack(side=tk.RIGHT, padx=8)

    group_avail = tk.LabelFrame(popup, text="وضعیت امانت کتاب", font=FONT_BOLD, padx=10, pady=5)
    group_avail.pack(fill=tk.X, padx=15, pady=5)
    avail_frame = tk.Frame(group_avail)
    avail_frame.pack(fill=tk.X)
    rb_av_all = tk.Radiobutton(
        avail_frame, text="همه کتاب‌ها", variable=avail_var, value="all", font=FONT_NORMAL, anchor="e"
    )
    rb_av_all.pack(side=tk.RIGHT, padx=8)
    rb_av_avail = tk.Radiobutton(
        avail_frame, text="فقط کتاب‌های موجود", variable=avail_var, value="available", font=FONT_NORMAL, anchor="e"
    )
    rb_av_avail.pack(side=tk.RIGHT, padx=8)
    rb_av_borrowed = tk.Radiobutton(
        avail_frame, text="فقط در امانت", variable=avail_var, value="borrowed", font=FONT_NORMAL, anchor="e"
    )
    rb_av_borrowed.pack(side=tk.RIGHT, padx=8)

    group_sort = tk.LabelFrame(popup, text="مرتب‌سازی نتایج", font=FONT_BOLD, padx=10, pady=5)
    group_sort.pack(fill=tk.X, padx=15, pady=5)
    sort_frame = tk.Frame(group_sort)
    sort_frame.pack(fill=tk.X, pady=3)

    tk.Label(sort_frame, text="بر اساس:", font=FONT_NORMAL).pack(side=tk.RIGHT, padx=(5, 0))
    sort_cols_available = [c for c in ["title", "author", "id"] if c in columns]
    sort_col_cb = ttk.Combobox(
        sort_frame,
        state="readonly",
        width=12,
        font=FONT_NORMAL,
        justify="right",
        values=[tr(c) for c in sort_cols_available],
    )
    sort_col_cb.set(tr(sort_col_var.get()))
    sort_col_cb.pack(side=tk.RIGHT, padx=5)

    tk.Label(sort_frame, text="ترتیب:", font=FONT_NORMAL).pack(side=tk.RIGHT, padx=(12, 0))
    sort_dir_cb = ttk.Combobox(
        sort_frame, state="readonly", width=9, font=FONT_NORMAL, justify="right", values=["صعودی", "نزولی"]
    )
    sort_dir_cb.set("صعودی" if sort_dir_var.get() == "ASC" else "نزولی")
    sort_dir_cb.pack(side=tk.RIGHT, padx=5)

    action_frame = tk.Frame(popup)
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
        action_frame, text=" اعمال فیلتر ", icon_name="check", font=FONT_BOLD, padx=6, pady=2, command=apply_filters
    )
    btn_apply.pack(side=tk.RIGHT, padx=4)

    btn_reset = create_icon_button(
        action_frame,
        text=" تنظیم مجدد ",
        icon_name="rotate-ccw",
        font=FONT_NORMAL,
        padx=6,
        pady=2,
        command=reset_filters,
    )
    btn_reset.pack(side=tk.RIGHT, padx=4)

    btn_cancel = create_icon_button(
        action_frame, text=" انصراف ", icon_name="x", font=FONT_NORMAL, padx=6, pady=2, command=popup.destroy
    )
    btn_cancel.pack(side=tk.LEFT, padx=4)


filter_btn.config(command=open_filter_popup)


def open_add_book_popup():
    popup = tk.Toplevel(root)
    popup.title("ثبت کتاب جدید")
    popup.geometry("380x360")
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
    px = max(50, rx + (rw - 380) // 2)
    py = max(50, ry + (rh - 360) // 2)
    popup.geometry(f"+{px}+{py}")

    tk.Label(popup, text="ثبت کتاب جدید", font=FONT_TITLE).pack(pady=10)

    book_cols = [c for c in ["title", "author", "isbn"] if c in columns] + [
        c for c in columns if c not in ["id", "title", "author", "isbn"]
    ]
    popup_entries = {}
    for col in book_cols:
        col_fa = tr(col)
        tk.Label(popup, text=f"{col_fa}:", font=FONT_NORMAL).pack(pady=3)
        ent = tk.Entry(popup, width=28, font=FONT_NORMAL, justify="right")
        ent.pack(pady=3)
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

    btn_f = tk.Frame(popup)
    btn_f.pack(pady=15)
    btn_save = create_icon_button(
        btn_f, text=" ثبت اطلاعات ", icon_name="check", command=do_insert_book, font=FONT_BOLD, padx=10, pady=3
    )
    btn_save.pack(side=tk.RIGHT, padx=5)
    btn_cancel = create_icon_button(
        btn_f, text=" انصراف ", icon_name="x", command=popup.destroy, font=FONT_NORMAL, padx=10, pady=3
    )
    btn_cancel.pack(side=tk.LEFT, padx=5)


add_book_btn.config(command=open_add_book_popup)
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

search_bar_frame_member = ttk.Frame(member_frame)
search_bar_frame_member.pack(fill=tk.X, padx=10, pady=10)
search_bar_frame_member.columnconfigure(3, weight=1)

sub_btn_member = create_icon_button(search_bar_frame_member, text=" جستجو ", icon_name="search", font=FONT_BOLD, padx=6)
sub_btn_member.grid(row=0, column=0, padx=(0, 6))

filter_btn_member = create_icon_button(
    search_bar_frame_member, text=" فیلترها ", icon_name="filter", font=FONT_NORMAL, padx=6
)
filter_btn_member.grid(row=0, column=1, padx=(0, 6))

add_member_btn = create_icon_button(
    search_bar_frame_member, text=" افزودن عضو ", icon_name="user-plus", font=FONT_NORMAL, padx=6
)
add_member_btn.grid(row=0, column=2, padx=(0, 6))

entry_search_member = tk.Entry(search_bar_frame_member, font=FONT_NORMAL, justify="right")
entry_search_member.grid(row=0, column=3, sticky="ew")

member_tree_frame = tk.Frame(member_frame)
member_tree_frame.pack(padx=10, pady=(0, 10), fill=tk.BOTH, expand=True)

member_scrollbar = tk.Scrollbar(member_tree_frame)
member_scrollbar.pack(side=tk.LEFT, fill=tk.Y)

member_tree = ttk.Treeview(
    member_tree_frame, yscrollcommand=member_scrollbar.set, columns=member_column, show="headings", height=15
)
member_scrollbar.config(command=member_tree.yview)
for col in member_column:
    member_tree.heading(col, text=tr(col), anchor=tk.CENTER)
    member_tree.column(col, anchor=tk.CENTER)
member_tree["displaycolumns"] = rtl_display_order(member_column, ["id", "member_id", "phone_number"])
member_tree.pack(side=tk.RIGHT, fill="both", expand=True, padx=10, pady=10)


def update_member_filter_indicator():
    is_custom = (
        member_filter_settings["column"] != "all"
        or member_filter_settings["match_mode"] != "contains"
        or member_filter_settings["sort_col"] != "id"
        or member_filter_settings["sort_dir"] != "ASC"
    )
    if is_custom:
        filter_btn_member.config(text=" فیلترها (فعال) ", fg="#0d6efd")
    else:
        filter_btn_member.config(text=" فیلترها ", fg="black")


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
                member_tree.insert("", "end", values=row)
        else:
            member_tree.insert("", "end", values=("❌ نتیجه‌ای یافت نشد!",) + ("",) * (len(member_column) - 1))

    except Exception as e:
        messagebox.showerror("خطا", f"خطا در جستجوی اعضا: {str(e)}")
    finally:
        temp_conn.close()


sub_btn_member.config(command=search_members)


def open_member_filter_popup():
    popup = tk.Toplevel(root)
    popup.title("فیلترهای اعضای کتابخانه")
    popup.geometry("400x380")
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
    py = max(50, ry + (rh - 380) // 2)
    popup.geometry(f"+{px}+{py}")

    col_var = tk.StringVar(value=member_filter_settings["column"])
    match_var = tk.StringVar(value=member_filter_settings["match_mode"])
    sort_col_var = tk.StringVar(value=member_filter_settings["sort_col"])
    sort_dir_var = tk.StringVar(value=member_filter_settings["sort_dir"])

    group_col = tk.LabelFrame(popup, text="جستجو در ستون", font=FONT_BOLD, padx=10, pady=5)
    group_col.pack(fill=tk.X, padx=15, pady=(10, 5))
    col_frame = tk.Frame(group_col)
    col_frame.pack(fill=tk.X)
    rb_all = tk.Radiobutton(col_frame, text="همه ستون‌ها", variable=col_var, value="all", font=FONT_NORMAL, anchor="e")
    rb_all.pack(side=tk.RIGHT, padx=4)
    for col in member_column:
        rb = tk.Radiobutton(col_frame, text=tr(col), variable=col_var, value=col, font=FONT_NORMAL, anchor="e")
        rb.pack(side=tk.RIGHT, padx=4)

    group_mode = tk.LabelFrame(popup, text="نوع تطابق جستجو", font=FONT_BOLD, padx=10, pady=5)
    group_mode.pack(fill=tk.X, padx=15, pady=5)
    mode_frame = tk.Frame(group_mode)
    mode_frame.pack(fill=tk.X)
    rb_contains = tk.Radiobutton(
        mode_frame, text="شامل عبارت", variable=match_var, value="contains", font=FONT_NORMAL, anchor="e"
    )
    rb_contains.pack(side=tk.RIGHT, padx=8)
    rb_starts = tk.Radiobutton(
        mode_frame, text="شروع با عبارت", variable=match_var, value="startswith", font=FONT_NORMAL, anchor="e"
    )
    rb_starts.pack(side=tk.RIGHT, padx=8)
    rb_exact = tk.Radiobutton(
        mode_frame, text="مطابقت دقیق", variable=match_var, value="exact", font=FONT_NORMAL, anchor="e"
    )
    rb_exact.pack(side=tk.RIGHT, padx=8)

    group_sort = tk.LabelFrame(popup, text="مرتب‌سازی نتایج", font=FONT_BOLD, padx=10, pady=5)
    group_sort.pack(fill=tk.X, padx=15, pady=5)
    sort_frame = tk.Frame(group_sort)
    sort_frame.pack(fill=tk.X, pady=3)

    tk.Label(sort_frame, text="بر اساس:", font=FONT_NORMAL).pack(side=tk.RIGHT, padx=(5, 0))
    sort_cols_avail = [c for c in ["id", "member_id", "phone_number"] if c in member_column]
    sort_col_cb = ttk.Combobox(
        sort_frame,
        state="readonly",
        width=12,
        font=FONT_NORMAL,
        justify="right",
        values=[tr(c) for c in sort_cols_avail],
    )
    sort_col_cb.set(tr(sort_col_var.get()))
    sort_col_cb.pack(side=tk.RIGHT, padx=5)

    tk.Label(sort_frame, text="ترتیب:", font=FONT_NORMAL).pack(side=tk.RIGHT, padx=(12, 0))
    sort_dir_cb = ttk.Combobox(
        sort_frame, state="readonly", width=9, font=FONT_NORMAL, justify="right", values=["صعودی", "نزولی"]
    )
    sort_dir_cb.set("صعودی" if sort_dir_var.get() == "ASC" else "نزولی")
    sort_dir_cb.pack(side=tk.RIGHT, padx=5)

    action_frame = tk.Frame(popup)
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
        padx=6,
        pady=2,
        command=apply_member_filters,
    )
    btn_apply.pack(side=tk.RIGHT, padx=4)

    btn_reset = create_icon_button(
        action_frame,
        text=" تنظیم مجدد ",
        icon_name="rotate-ccw",
        font=FONT_NORMAL,
        padx=6,
        pady=2,
        command=reset_member_filters,
    )
    btn_reset.pack(side=tk.RIGHT, padx=4)

    btn_cancel = create_icon_button(
        action_frame, text=" انصراف ", icon_name="x", font=FONT_NORMAL, padx=6, pady=2, command=popup.destroy
    )
    btn_cancel.pack(side=tk.LEFT, padx=4)


filter_btn_member.config(command=open_member_filter_popup)


def open_add_member_popup():
    popup = tk.Toplevel(root)
    popup.title("ثبت عضو جدید")
    popup.geometry("380x300")
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
    px = max(50, rx + (rw - 380) // 2)
    py = max(50, ry + (rh - 300) // 2)
    popup.geometry(f"+{px}+{py}")

    tk.Label(popup, text="ثبت عضو جدید", font=FONT_TITLE).pack(pady=10)

    tk.Label(popup, text="نام کاربر (عضو):", font=FONT_NORMAL).pack(pady=3)
    entry_m_id = tk.Entry(popup, width=28, font=FONT_NORMAL, justify="right")
    entry_m_id.pack(pady=3)

    tk.Label(popup, text="شماره تلفن:", font=FONT_NORMAL).pack(pady=3)
    entry_m_phone = tk.Entry(popup, width=28, font=FONT_NORMAL, justify="right")
    entry_m_phone.pack(pady=3)

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

    btn_f = tk.Frame(popup)
    btn_f.pack(pady=15)
    btn_save = create_icon_button(
        btn_f, text=" ثبت اطلاعات ", icon_name="check", command=do_insert_member, font=FONT_BOLD, padx=10, pady=3
    )
    btn_save.pack(side=tk.RIGHT, padx=5)
    btn_cancel = create_icon_button(
        btn_f, text=" انصراف ", icon_name="x", command=popup.destroy, font=FONT_NORMAL, padx=10, pady=3
    )
    btn_cancel.pack(side=tk.LEFT, padx=5)


add_member_btn.config(command=open_add_member_popup)

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

search_bar_frame_users = ttk.Frame(auth_users_frame)
search_bar_frame_users.pack(fill=tk.X, padx=10, pady=10)
search_bar_frame_users.columnconfigure(3, weight=1)

sub_btn_users = create_icon_button(search_bar_frame_users, text=" جستجو ", icon_name="search", font=FONT_BOLD, padx=6)
sub_btn_users.grid(row=0, column=0, padx=(0, 6))

filter_btn_users = create_icon_button(
    search_bar_frame_users, text=" فیلترها ", icon_name="filter", font=FONT_NORMAL, padx=6
)
filter_btn_users.grid(row=0, column=1, padx=(0, 6))

add_user_btn = create_icon_button(
    search_bar_frame_users, text=" افزودن کاربر ", icon_name="user-plus", font=FONT_NORMAL, padx=6
)
add_user_btn.grid(row=0, column=2, padx=(0, 6))

entry_search_users = tk.Entry(search_bar_frame_users, font=FONT_NORMAL, justify="right")
entry_search_users.grid(row=0, column=3, sticky="ew")

users_tree_frame = tk.Frame(auth_users_frame)
users_tree_frame.pack(padx=10, pady=(0, 10), fill=tk.BOTH, expand=True)

users_scrollbar = tk.Scrollbar(users_tree_frame)
users_scrollbar.pack(side=tk.LEFT, fill=tk.Y)

users_tree = ttk.Treeview(
    users_tree_frame, yscrollcommand=users_scrollbar.set, columns=user_columns, show="headings", height=15
)
users_scrollbar.config(command=users_tree.yview)
for col in user_columns:
    users_tree.heading(col, text=tr(col), anchor=tk.CENTER)
    users_tree.column(col, anchor=tk.CENTER)
users_tree["displaycolumns"] = rtl_display_order(
    user_columns, ["id", "username", "phone_number", "role", "telegram_chat_id", "is_active", "created_at"]
)
users_tree.pack(side=tk.RIGHT, fill="both", expand=True, padx=10, pady=10)


def update_user_filter_indicator():
    is_custom = (
        user_filter_settings["column"] != "all"
        or user_filter_settings["match_mode"] != "contains"
        or user_filter_settings["sort_col"] != "id"
        or user_filter_settings["sort_dir"] != "ASC"
    )
    if is_custom:
        filter_btn_users.config(text=" فیلترها (فعال) ", fg="#0d6efd")
    else:
        filter_btn_users.config(text=" فیلترها ", fg="black")


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


sub_btn_users.config(command=search_users)


def open_users_filter_popup():
    popup = tk.Toplevel(root)
    popup.title("فیلترهای کاربران سامانه")
    popup.geometry("400x380")
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
    py = max(50, ry + (rh - 380) // 2)
    popup.geometry(f"+{px}+{py}")

    col_var = tk.StringVar(value=user_filter_settings["column"])
    match_var = tk.StringVar(value=user_filter_settings["match_mode"])
    sort_col_var = tk.StringVar(value=user_filter_settings["sort_col"])
    sort_dir_var = tk.StringVar(value=user_filter_settings["sort_dir"])

    group_col = tk.LabelFrame(popup, text="جستجو در ستون", font=FONT_BOLD, padx=10, pady=5)
    group_col.pack(fill=tk.X, padx=15, pady=(10, 5))
    col_frame = tk.Frame(group_col)
    col_frame.pack(fill=tk.X)
    rb_all = tk.Radiobutton(col_frame, text="همه ستون‌ها", variable=col_var, value="all", font=FONT_NORMAL, anchor="e")
    rb_all.pack(side=tk.RIGHT, padx=4)
    for col in ["username", "phone_number", "role"]:
        rb = tk.Radiobutton(col_frame, text=tr(col), variable=col_var, value=col, font=FONT_NORMAL, anchor="e")
        rb.pack(side=tk.RIGHT, padx=4)

    group_mode = tk.LabelFrame(popup, text="نوع تطابق جستجو", font=FONT_BOLD, padx=10, pady=5)
    group_mode.pack(fill=tk.X, padx=15, pady=5)
    mode_frame = tk.Frame(group_mode)
    mode_frame.pack(fill=tk.X)
    rb_contains = tk.Radiobutton(
        mode_frame, text="شامل عبارت", variable=match_var, value="contains", font=FONT_NORMAL, anchor="e"
    )
    rb_contains.pack(side=tk.RIGHT, padx=8)
    rb_starts = tk.Radiobutton(
        mode_frame, text="شروع با عبارت", variable=match_var, value="startswith", font=FONT_NORMAL, anchor="e"
    )
    rb_starts.pack(side=tk.RIGHT, padx=8)
    rb_exact = tk.Radiobutton(
        mode_frame, text="مطابقت دقیق", variable=match_var, value="exact", font=FONT_NORMAL, anchor="e"
    )
    rb_exact.pack(side=tk.RIGHT, padx=8)

    group_sort = tk.LabelFrame(popup, text="مرتب‌سازی نتایج", font=FONT_BOLD, padx=10, pady=5)
    group_sort.pack(fill=tk.X, padx=15, pady=5)
    sort_frame = tk.Frame(group_sort)
    sort_frame.pack(fill=tk.X, pady=3)

    tk.Label(sort_frame, text="بر اساس:", font=FONT_NORMAL).pack(side=tk.RIGHT, padx=(5, 0))
    sort_cols_avail = ["id", "username", "role"]
    sort_col_cb = ttk.Combobox(
        sort_frame,
        state="readonly",
        width=12,
        font=FONT_NORMAL,
        justify="right",
        values=[tr(c) for c in sort_cols_avail],
    )
    sort_col_cb.set(tr(sort_col_var.get()))
    sort_col_cb.pack(side=tk.RIGHT, padx=5)

    tk.Label(sort_frame, text="ترتیب:", font=FONT_NORMAL).pack(side=tk.RIGHT, padx=(12, 0))
    sort_dir_cb = ttk.Combobox(
        sort_frame, state="readonly", width=9, font=FONT_NORMAL, justify="right", values=["صعودی", "نزولی"]
    )
    sort_dir_cb.set("صعودی" if sort_dir_var.get() == "ASC" else "نزولی")
    sort_dir_cb.pack(side=tk.RIGHT, padx=5)

    action_frame = tk.Frame(popup)
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
        padx=6,
        pady=2,
        command=apply_user_filters,
    )
    btn_apply.pack(side=tk.RIGHT, padx=4)

    btn_reset = create_icon_button(
        action_frame,
        text=" تنظیم مجدد ",
        icon_name="rotate-ccw",
        font=FONT_NORMAL,
        padx=6,
        pady=2,
        command=reset_user_filters,
    )
    btn_reset.pack(side=tk.RIGHT, padx=4)

    btn_cancel = create_icon_button(
        action_frame, text=" انصراف ", icon_name="x", font=FONT_NORMAL, padx=6, pady=2, command=popup.destroy
    )
    btn_cancel.pack(side=tk.LEFT, padx=4)


filter_btn_users.config(command=open_users_filter_popup)


def open_create_user_popup():
    if not current_user or str(current_user.get("role", "")).strip().lower() not in (
        "super admin",
        "superadmin",
        "admin",
    ):
        messagebox.showerror("عدم دسترسی", "فقط نقش مدیر یا سرپرست مجاز به ایجاد کاربر جدید است.", parent=root)
        return

    popup = tk.Toplevel(root)
    popup.title("ثبت کاربر جدید در سامانه")
    popup.geometry("400x480")
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
    py = max(50, ry + (rh - 480) // 2)
    popup.geometry(f"+{px}+{py}")

    tk.Label(popup, text="ثبت کاربر جدید (سامانه)", font=FONT_TITLE).pack(pady=10)

    tk.Label(popup, text="نام کاربری:", font=FONT_NORMAL).pack(pady=3)
    u_name_ent = tk.Entry(popup, width=28, font=FONT_NORMAL, justify="right")
    u_name_ent.pack(pady=3)

    tk.Label(popup, text="شماره تلفن:", font=FONT_NORMAL).pack(pady=3)
    u_phone_ent = tk.Entry(popup, width=28, font=FONT_NORMAL, justify="right")
    u_phone_ent.pack(pady=3)

    tk.Label(popup, text="شناسه چت تلگرام (اختیاری):", font=FONT_NORMAL).pack(pady=3)
    u_tg_ent = tk.Entry(popup, width=28, font=FONT_NORMAL, justify="right")
    u_tg_ent.pack(pady=3)

    tk.Label(popup, text="نقش کاربر:", font=FONT_NORMAL).pack(pady=3)
    u_role_combo = ttk.Combobox(
        popup,
        font=FONT_NORMAL,
        justify="right",
        state="readonly",
        values=["super admin", "admin", "librarian", "user"],
        width=26,
    )
    u_role_combo.set("librarian")
    u_role_combo.pack(pady=3)

    tk.Label(popup, text="رمز عبور:", font=FONT_NORMAL).pack(pady=3)
    u_pwd_ent = tk.Entry(popup, width=28, font=FONT_NORMAL, justify="right", show="*")
    u_pwd_ent.pack(pady=3)

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

    btn_f = tk.Frame(popup)
    btn_f.pack(pady=15)
    btn_save = create_icon_button(
        btn_f, text=" ثبت کاربر ", icon_name="check", command=do_create_user, font=FONT_BOLD, padx=10, pady=3
    )
    btn_save.pack(side=tk.RIGHT, padx=5)
    btn_cancel = create_icon_button(
        btn_f, text=" انصراف ", icon_name="x", command=popup.destroy, font=FONT_NORMAL, padx=10, pady=3
    )
    btn_cancel.pack(side=tk.LEFT, padx=5)


add_user_btn.config(command=open_create_user_popup)

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

search_bar_frame_loans = ttk.Frame(tabel_frame)
search_bar_frame_loans.pack(fill=tk.X, padx=10, pady=10)
search_bar_frame_loans.columnconfigure(4, weight=1)

sub_btn_loans = create_icon_button(search_bar_frame_loans, text=" جستجو ", icon_name="search", font=FONT_BOLD, padx=6)
sub_btn_loans.grid(row=0, column=0, padx=(0, 6))

filter_btn_loans = create_icon_button(
    search_bar_frame_loans, text=" فیلترها ", icon_name="filter", font=FONT_NORMAL, padx=6
)
filter_btn_loans.grid(row=0, column=1, padx=(0, 6))

add_loan_btn = create_icon_button(
    search_bar_frame_loans, text=" ثبت امانت جدید ", icon_name="arrow-right-left", font=FONT_NORMAL, padx=6
)
add_loan_btn.grid(row=0, column=2, padx=(0, 6))

return_loan_btn = create_icon_button(
    search_bar_frame_loans,
    text=" ثبت بازگشت کتاب ",
    icon_name="check",
    font=FONT_BOLD,
    padx=6,
    command=lambda: do_return_selected_loan(),
)
return_loan_btn.grid(row=0, column=3, padx=(0, 6))

entry_search_loans = tk.Entry(search_bar_frame_loans, font=FONT_NORMAL, justify="right")
entry_search_loans.grid(row=0, column=4, sticky="ew")

loans_tree_frame = tk.Frame(tabel_frame)
loans_tree_frame.pack(padx=10, pady=(0, 10), fill=tk.BOTH, expand=True)

scrollbar_2 = tk.Scrollbar(loans_tree_frame)
scrollbar_2.pack(side=tk.LEFT, fill=tk.Y)

loans_tree = ttk.Treeview(
    loans_tree_frame, yscrollcommand=scrollbar_2.set, columns=loan_column, show="headings", height=15
)
scrollbar_2.config(command=loans_tree.yview)
for col in loan_column:
    loans_tree.heading(col, text=tr(col), anchor=tk.CENTER)
    loans_tree.column(col, anchor=tk.CENTER)
loans_tree["displaycolumns"] = rtl_display_order(
    loan_column, ["id", "member_name", "book_id", "borrow_date", "return_date", "borrowed"]
)
loans_tree.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)


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
        filter_btn_loans.config(text=" فیلترها (فعال) ", fg="#0d6efd")
    else:
        filter_btn_loans.config(text=" فیلترها ", fg="black")


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
sub_btn_loans.config(command=search_loans)


def open_loans_filter_popup():
    popup = tk.Toplevel(root)
    popup.title("فیلترهای جدول امانات")
    popup.geometry("440x510")
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
    py = max(50, ry + (rh - 510) // 2)
    popup.geometry(f"+{px}+{py}")

    col_var = tk.StringVar(value=loans_filter_settings["column"])
    match_var = tk.StringVar(value=loans_filter_settings["match_mode"])
    status_var = tk.StringVar(value=loans_filter_settings["status"])
    sort_col_var = tk.StringVar(value=loans_filter_settings["sort_col"])
    sort_dir_var = tk.StringVar(value=loans_filter_settings["sort_dir"])

    group_col = tk.LabelFrame(popup, text="جستجو در ستون", font=FONT_BOLD, padx=10, pady=5)
    group_col.pack(fill=tk.X, padx=15, pady=(10, 5))
    col_frame = tk.Frame(group_col)
    col_frame.pack(fill=tk.X)
    rb_all = tk.Radiobutton(col_frame, text="همه ستون‌ها", variable=col_var, value="all", font=FONT_NORMAL, anchor="e")
    rb_all.pack(side=tk.RIGHT, padx=4)
    for col in ["member_name", "book_id", "id"]:
        rb = tk.Radiobutton(col_frame, text=tr(col), variable=col_var, value=col, font=FONT_NORMAL, anchor="e")
        rb.pack(side=tk.RIGHT, padx=4)

    group_mode = tk.LabelFrame(popup, text="نوع تطابق جستجو", font=FONT_BOLD, padx=10, pady=5)
    group_mode.pack(fill=tk.X, padx=15, pady=5)
    mode_frame = tk.Frame(group_mode)
    mode_frame.pack(fill=tk.X)
    rb_contains = tk.Radiobutton(
        mode_frame, text="شامل عبارت", variable=match_var, value="contains", font=FONT_NORMAL, anchor="e"
    )
    rb_contains.pack(side=tk.RIGHT, padx=8)
    rb_starts = tk.Radiobutton(
        mode_frame, text="شروع با عبارت", variable=match_var, value="startswith", font=FONT_NORMAL, anchor="e"
    )
    rb_starts.pack(side=tk.RIGHT, padx=8)
    rb_exact = tk.Radiobutton(
        mode_frame, text="مطابقت دقیق", variable=match_var, value="exact", font=FONT_NORMAL, anchor="e"
    )
    rb_exact.pack(side=tk.RIGHT, padx=8)

    group_status = tk.LabelFrame(popup, text="وضعیت امانت", font=FONT_BOLD, padx=10, pady=5)
    group_status.pack(fill=tk.X, padx=15, pady=5)
    status_frame = tk.Frame(group_status)
    status_frame.pack(fill=tk.X)
    rb_st_all = tk.Radiobutton(
        status_frame, text="همه امانات", variable=status_var, value="all", font=FONT_NORMAL, anchor="e"
    )
    rb_st_all.pack(side=tk.RIGHT, padx=8)
    rb_st_borrowed = tk.Radiobutton(
        status_frame, text="فقط در امانت", variable=status_var, value="borrowed", font=FONT_NORMAL, anchor="e"
    )
    rb_st_borrowed.pack(side=tk.RIGHT, padx=8)
    rb_st_returned = tk.Radiobutton(
        status_frame, text="فقط بازگردانده شده", variable=status_var, value="returned", font=FONT_NORMAL, anchor="e"
    )
    rb_st_returned.pack(side=tk.RIGHT, padx=8)

    group_sort = tk.LabelFrame(popup, text="مرتب‌سازی نتایج", font=FONT_BOLD, padx=10, pady=5)
    group_sort.pack(fill=tk.X, padx=15, pady=5)
    sort_frame = tk.Frame(group_sort)
    sort_frame.pack(fill=tk.X, pady=3)

    tk.Label(sort_frame, text="بر اساس:", font=FONT_NORMAL).pack(side=tk.RIGHT, padx=(5, 0))
    sort_options = {
        "مدت امانت": "duration",
        "تاریخ بازگشت": "return_date",
        "تاریخ امانت": "borrow_date",
        "نام کاربر": "member_name",
        "نام کتاب": "book_id",
        "شناسه": "id",
    }
    rev_sort_options = {v: k for k, v in sort_options.items()}

    sort_col_cb = ttk.Combobox(
        sort_frame, state="readonly", width=14, font=FONT_NORMAL, justify="right", values=list(sort_options.keys())
    )
    current_sort_label = rev_sort_options.get(sort_col_var.get(), "مدت امانت")
    sort_col_cb.set(current_sort_label)
    sort_col_cb.pack(side=tk.RIGHT, padx=5)

    tk.Label(sort_frame, text="ترتیب:", font=FONT_NORMAL).pack(side=tk.RIGHT, padx=(12, 0))
    sort_dir_cb = ttk.Combobox(
        sort_frame, state="readonly", width=9, font=FONT_NORMAL, justify="right", values=["صعودی", "نزولی"]
    )
    sort_dir_cb.set("صعودی" if sort_dir_var.get() == "ASC" else "نزولی")
    sort_dir_cb.pack(side=tk.RIGHT, padx=5)

    action_frame = tk.Frame(popup)
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
        padx=6,
        pady=2,
        command=apply_loans_filters,
    )
    btn_apply.pack(side=tk.RIGHT, padx=4)

    btn_reset = create_icon_button(
        action_frame,
        text=" تنظیم مجدد ",
        icon_name="rotate-ccw",
        font=FONT_NORMAL,
        padx=6,
        pady=2,
        command=reset_loans_filters,
    )
    btn_reset.pack(side=tk.RIGHT, padx=4)

    btn_cancel = create_icon_button(
        action_frame, text=" انصراف ", icon_name="x", font=FONT_NORMAL, padx=6, pady=2, command=popup.destroy
    )
    btn_cancel.pack(side=tk.LEFT, padx=4)


filter_btn_loans.config(command=open_loans_filter_popup)


def open_add_loan_popup(initial_book_title=""):
    popup = tk.Toplevel(root)
    popup.title("ثبت امانت کتاب")
    popup.geometry("460x600")
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
    py = max(50, ry + (rh - 600) // 2)
    popup.geometry(f"+{px}+{py}")

    tk.Label(popup, text="ثبت اطلاعات امانت کتاب", font=FONT_TITLE).pack(pady=8)

    # 1. Member selection
    tk.Label(popup, text="نام کاربر (عضو):", font=FONT_NORMAL).pack(pady=2)
    member_entry = tk.Entry(popup, width=35, font=FONT_NORMAL, justify="right")
    member_entry.pack(pady=2)

    mem_conn = get_db_connection(db_p)
    try:
        mem_cur = mem_conn.cursor()
        mem_cur.execute("SELECT member_id FROM members ORDER BY member_id ASC")
        members_data = [row[0] for row in mem_cur.fetchall()]
    finally:
        mem_conn.close()

    mem_listbox = tk.Listbox(popup, width=35, height=3, font=FONT_NORMAL, justify="right")
    mem_listbox.pack(pady=2)
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
    tk.Label(popup, text="عنوان کتاب:", font=FONT_NORMAL).pack(pady=2)
    book_entry = tk.Entry(popup, width=35, font=FONT_NORMAL, justify="right")
    book_entry.pack(pady=2)

    if initial_book_title:
        book_entry.insert(0, initial_book_title)
        book_entry.config(state="readonly")
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

        bk_listbox = tk.Listbox(popup, width=35, height=3, font=FONT_NORMAL, justify="right")
        bk_listbox.pack(pady=2)
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

    tk.Label(popup, text="تاریخ امانت کتاب (YYYY-MM-DD):", font=FONT_NORMAL).pack(pady=2)
    borrow_entry = tk.Entry(popup, width=35, font=FONT_NORMAL, justify="right")
    borrow_entry.pack(pady=2)

    var_auto_date = tk.IntVar(value=1)
    borrow_entry.insert(0, str(cur_today))

    def toggle_borrow_date():
        if var_auto_date.get() == 1:
            borrow_entry.delete(0, tk.END)
            borrow_entry.insert(0, str(cur_today))
        else:
            borrow_entry.delete(0, tk.END)

    tk.Checkbutton(
        popup, text="ثبت خودکار تاریخ امروز", variable=var_auto_date, command=toggle_borrow_date, font=FONT_NORMAL
    ).pack(pady=2)

    # 4. Return Date
    tk.Label(popup, text="تاریخ بازگشت کتاب (YYYY-MM-DD):", font=FONT_NORMAL).pack(pady=2)
    return_entry = tk.Entry(popup, width=35, font=FONT_NORMAL, justify="right")
    return_entry.pack(pady=2)

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

    days_frame = ttk.Frame(popup)
    days_frame.pack(pady=4)

    rb1 = ttk.Radiobutton(
        days_frame,
        text="10 روز",
        variable=selected_days,
        value="option1",
        command=on_select_days,
        style="Modern.TRadiobutton",
    )
    rb2 = ttk.Radiobutton(
        days_frame,
        text="20 روز",
        variable=selected_days,
        value="option2",
        command=on_select_days,
        style="Modern.TRadiobutton",
    )
    rb3 = ttk.Radiobutton(
        days_frame,
        text="30 روز",
        variable=selected_days,
        value="option3",
        command=on_select_days,
        style="Modern.TRadiobutton",
    )
    rb1.pack(side=tk.RIGHT, padx=12)
    rb2.pack(side=tk.RIGHT, padx=12)
    rb3.pack(side=tk.RIGHT, padx=12)

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

    btn_f = tk.Frame(popup)
    btn_f.pack(pady=12)
    btn_save = create_icon_button(
        btn_f, text=" ثبت امانت ", icon_name="arrow-right-left", font=FONT_BOLD, padx=10, pady=3, command=do_insert_loan
    )
    btn_save.pack(side=tk.RIGHT, padx=5)
    btn_cancel = create_icon_button(
        btn_f, text=" انصراف ", icon_name="x", font=FONT_NORMAL, padx=10, pady=3, command=popup.destroy
    )
    btn_cancel.pack(side=tk.LEFT, padx=5)


add_loan_btn.config(command=open_add_loan_popup)


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
title_label_help = tk.Label(help_frame, text="راهنما و درباره نرم‌افزار", font=FONT_TITLE)
title_label_help.pack(pady=(15, 4))

subtitle_label_help = tk.Label(
    help_frame,
    text="سیستم مدیریت کتابخانه باقرالعلوم",
    font=FONT_NORMAL,
    fg="#666666",
)
subtitle_label_help.pack(pady=(0, 10))

help_content = ttk.Frame(help_frame)
help_content.pack(fill=tk.BOTH, expand=True, padx=25, pady=5)


def open_url(url: str):
    try:
        webbrowser.open(url)
    except Exception as e:
        messagebox.showerror("خطا", f"امکان باز کردن پیوند در مرورگر وجود ندارد:\n{e}", parent=root)


dev_group = tk.LabelFrame(help_content, text=" توسعه‌دهندگان ", font=FONT_BOLD, padx=15, pady=8)
dev_group.pack(fill=tk.X, pady=(0, 8))

developers_info = [
    ("امیرحسین اسدی", "@amirkabir18", "https://github.com/amirkabir18"),
    ("سید محمد حسن موسوی", "@Aliomosavi", "https://github.com/Aliomosavi"),
    ("امیررضا یونس‌زاده شیرازی", "@ARUSH221617", "https://github.com/ARUSH221617"),
]

for name, handle, profile_url in developers_info:
    row = tk.Frame(dev_group)
    row.pack(fill=tk.X, pady=2)

    lbl_name = tk.Label(row, text=f"• {name}", font=FONT_NORMAL, anchor="e")
    lbl_name.pack(side=tk.RIGHT, padx=5)

    lbl_handle = tk.Label(
        row,
        text=handle,
        font=FONT_NORMAL,
        fg="#0d6efd",
        cursor="hand2",
        anchor="w",
    )
    lbl_handle.pack(side=tk.LEFT, padx=5)
    lbl_handle.bind("<Button-1>", lambda event, u=profile_url: open_url(u))

repo_url = "https://github.com/amirkabir18/bager_library"
repo_group = tk.LabelFrame(help_content, text=" مخزن گیت‌هاب پروژه ", font=FONT_BOLD, padx=15, pady=8)
repo_group.pack(fill=tk.X, pady=(0, 8))

repo_desc = tk.Label(
    repo_group,
    text="سورس‌کد و مستندات پروژه در گیت‌هاب:",
    font=FONT_NORMAL,
    anchor="e",
)
repo_desc.pack(anchor="e", pady=(0, 4))

repo_row = tk.Frame(repo_group)
repo_row.pack(fill=tk.X, pady=2)

btn_repo = create_icon_button(
    repo_row,
    text=" مشاهده مخزن در گیت‌هاب ",
    font=FONT_NORMAL,
    command=lambda: open_url(repo_url),
    padx=10,
    pady=3,
)
btn_repo.pack(side=tk.RIGHT, padx=5)

lbl_repo_url = tk.Label(
    repo_row,
    text=repo_url,
    font=FONT_NORMAL,
    fg="#0d6efd",
    cursor="hand2",
    anchor="w",
)
lbl_repo_url.pack(side=tk.LEFT, padx=5)
lbl_repo_url.bind("<Button-1>", lambda event: open_url(repo_url))

issue_url = "https://github.com/amirkabir18/bager_library/issues/new"
issue_group = tk.LabelFrame(
    help_content, text=" ثبت گزارش خطا یا پیشنهاد (New Issue) ", font=FONT_BOLD, padx=15, pady=8
)
issue_group.pack(fill=tk.X, pady=(0, 8))

issue_desc = tk.Label(
    issue_group,
    text="برای گزارش باگ‌ها، مشکلات یا ثبت پیشنهادات، یک Issue جدید در گیت‌هاب باز کنید:",
    font=FONT_NORMAL,
    anchor="e",
)
issue_desc.pack(anchor="e", pady=(0, 4))

issue_row = tk.Frame(issue_group)
issue_row.pack(fill=tk.X, pady=2)

btn_issue = create_icon_button(
    issue_row,
    text=" ثبت Issue جدید در گیت‌هاب ",
    font=FONT_BOLD,
    command=lambda: open_url(issue_url),
    padx=10,
    pady=3,
)
btn_issue.pack(side=tk.RIGHT, padx=5)

lbl_issue_url = tk.Label(
    issue_row,
    text=issue_url,
    font=FONT_NORMAL,
    fg="#0d6efd",
    cursor="hand2",
    anchor="w",
)
lbl_issue_url.pack(side=tk.LEFT, padx=5)
lbl_issue_url.bind("<Button-1>", lambda event: open_url(issue_url))

app_info = load_app_info()
app_version = app_info.get("version", "0.1.0")
update_checker = UpdateChecker(
    repo=app_info.get("github_repo", "amirkabir18/bager_library"),
    current_version=app_version,
)
download_manager = DownloadManager()

update_group = tk.LabelFrame(help_content, text=" بروزرسانی نرم‌افزار ", font=FONT_BOLD, padx=15, pady=8)
update_group.pack(fill=tk.X, pady=(0, 8))

info_row = tk.Frame(update_group)
info_row.pack(fill=tk.X, pady=2)

lbl_current_ver = tk.Label(info_row, text=f"نسخه فعلی: {app_version}", font=FONT_NORMAL, anchor="e")
lbl_current_ver.pack(side=tk.RIGHT, padx=(0, 15))

lbl_update_status = tk.Label(
    info_row,
    text="وضعیت: در حال بررسی...",
    font=FONT_NORMAL,
    fg="#0d6efd",
    anchor="e",
)
lbl_update_status.pack(side=tk.RIGHT, padx=5)

progress_row = tk.Frame(update_group)

update_progress = ttk.Progressbar(progress_row, orient="horizontal", mode="determinate")
update_progress.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10, 0))

lbl_progress_text = tk.Label(progress_row, text="", font=FONT_NORMAL, fg="#475569", width=26, anchor="w")
lbl_progress_text.pack(side=tk.LEFT, padx=(0, 5))

actions_row = tk.Frame(update_group)
actions_row.pack(fill=tk.X, pady=2)

latest_update_info: dict = {}


def on_check_finished(res: dict, interactive: bool):
    latest_update_info.clear()
    latest_update_info.update(res)

    if res.get("update_available"):
        latest_ver = res.get("latest_version", "")
        lbl_update_status.config(
            text=f"وضعیت: نسخه جدید {latest_ver} موجود است!",
            fg="#16a34a",
        )
        btn_update_action.config(
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
        lbl_update_status.config(
            text="وضعیت: نرم‌افزار به‌روز است.",
            fg="#16a34a",
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
        btn_update_action.config(
            state="normal",
            text=" تلاش مجدد برای بررسی ",
            command=lambda: perform_check(interactive=True),
        )
        btn_update_action.pack(side=tk.RIGHT, padx=5)
        lbl_update_status.config(text="وضعیت: خطا در بررسی بروزرسانی", fg="#dc2626")
        messagebox.showerror("خطا در بررسی بروزرسانی", f"خطا در ارتباط با سرور بروزرسانی:\n{error_msg}", parent=root)
    else:
        btn_update_action.pack_forget()
        lbl_update_status.config(text="وضعیت: نرم‌افزار به‌روز است.", fg="#16a34a")


def perform_check(interactive: bool = True):
    lbl_update_status.config(text="وضعیت: در حال بررسی آخرین نسخه...", fg="#0d6efd")
    btn_update_action.config(state="disabled")

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
    btn_update_action.config(state="disabled")
    btn_cancel_update.pack(side=tk.RIGHT, padx=5)
    lbl_update_status.config(text="وضعیت: در حال دانلود فایل بروزرسانی...", fg="#0d6efd")
    progress_row.pack(fill=tk.X, pady=4, before=actions_row)
    update_progress["value"] = 0

    def _update_prog_ui(downloaded, total, pct, speed):
        update_progress["value"] = pct
        speed_str = format_speed(speed)
        down_str = format_size(downloaded)
        total_str = format_size(total) if total > 0 else "نامشخص"
        lbl_progress_text.config(text=f"{pct:.0f}% ({down_str} / {total_str}) {speed_str}")

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
        btn_update_action.config(
            state="normal",
            text=" نصب بروزرسانی ",
            command=lambda: _prompt_install(path),
        )
        btn_update_action.pack(side=tk.RIGHT, padx=5)
        update_progress["value"] = 100
        lbl_update_status.config(text="وضعیت: دانلود با موفقیت انجام شد.", fg="#16a34a")
        lbl_progress_text.config(text="دانلود کامل شد")
        _prompt_install(path)

    def _error_download_ui(err):
        btn_cancel_update.pack_forget()
        btn_update_action.config(
            state="normal",
            text=" تلاش مجدد برای دریافت ",
            command=start_update_download,
        )
        btn_update_action.pack(side=tk.RIGHT, padx=5)
        lbl_update_status.config(text="وضعیت: خطا در دانلود بروزرسانی", fg="#dc2626")
        messagebox.showerror("خطا در دانلود", f"خطا در حین دانلود فایل بروزرسانی:\n{err}", parent=root)

    def _cancelled_download_ui():
        btn_cancel_update.pack_forget()
        btn_update_action.config(
            state="normal",
            text=" دریافت و نصب نسخه جدید ",
            command=start_update_download,
        )
        btn_update_action.pack(side=tk.RIGHT, padx=5)
        progress_row.pack_forget()
        update_progress["value"] = 0
        lbl_progress_text.config(text="")
        lbl_update_status.config(text="وضعیت: دانلود لغو شد.", fg="#64748b")

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
    padx=10,
    pady=3,
)
btn_update_action.pack(side=tk.RIGHT, padx=5)

btn_cancel_update = create_icon_button(
    actions_row,
    text=" لغو دانلود ",
    font=FONT_NORMAL,
    command=download_manager.cancel,
    padx=10,
    pady=3,
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
root.geometry("800x600")

root.mainloop()
