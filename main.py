import sqlite3,os,sys,re
import tkinter as tk
from tkinter import ttk,messagebox
import tkinter.font as tkfont
import jdatetime
import datetime

base_dir = getattr(sys, '_MEIPASS', os.path.dirname(__file__))
db_p = os.path.join(base_dir, 'bager_library.db')
icon_p = os.path.join(base_dir, 'logo.ico')
fonts_dir = os.path.join(base_dir, 'assets', 'fonts', 'iransans', 'ttf')

def load_fonts():
    if sys.platform == 'win32':
        try:
            import ctypes
            import glob
            if os.path.exists(fonts_dir):
                for font_file in glob.glob(os.path.join(fonts_dir, "*.ttf")):
                    ctypes.windll.gdi32.AddFontResourceExW(os.path.abspath(font_file), 0x10, 0)
        except Exception:
            pass

load_fonts()

from database import (
    db_p,
    init_database,
    get_db_connection,
    get_setting,
    set_setting,
    get_all_settings,
    TRANSLATIONS,
    tr,
    rtl_display_order,
)
from auth import ensure_bootstrap_admin
from notifications import NotificationEngine, LoanReminderManager

conn = sqlite3.connect(db_p)
init_database(conn)
ensure_bootstrap_admin(database_path=db_p)
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables_data = cursor.fetchall()
table_names = [str(r[0]) for r in tables_data]
tabel_name = 'books'
cursor.execute(f'PRAGMA table_info("{tabel_name}")')
columns: list[str] = [str(row[1]) for row in cursor.fetchall()]

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

for font_name in ("TkDefaultFont", "TkTextFont", "TkFixedFont", "TkMenuFont", "TkHeadingFont", "TkCaptionFont", "TkSmallCaptionFont", "TkTooltipFont"):
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
    icon_path = os.path.join(base_dir, 'assets', 'icons', 'lucide', f"{name}.png")
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
            setattr(btn, 'image', img)
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

notebook = ttk.Notebook(root)
notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

filter_settings = {
    'column': 'all',
    'match_mode': 'contains',
    'availability': 'all',
    'sort_col': 'id',
    'sort_dir': 'ASC',
}

books_frame = ttk.Frame(notebook)
notebook.add(books_frame, text=" جستجوی کتاب ")

search_bar_frame = ttk.Frame(books_frame)
search_bar_frame.pack(fill=tk.X, padx=10, pady=10)
search_bar_frame.columnconfigure(2, weight=1)

sub_btn = create_icon_button(search_bar_frame, text=' جستجو ', icon_name='search', font=FONT_BOLD, padx=6)
sub_btn.grid(row=0, column=0, padx=(0, 6))

filter_btn = create_icon_button(search_bar_frame, text=' فیلترها ', icon_name='filter', font=FONT_NORMAL, padx=6)
filter_btn.grid(row=0, column=1, padx=(0, 6))

entry_serch = tk.Entry(search_bar_frame, font=FONT_NORMAL, justify='right')
entry_serch.grid(row=0, column=2, sticky="ew")

tree_frame = tk.Frame(books_frame)
tree_frame.pack(padx=10, pady=(0, 10), fill=tk.BOTH, expand=True)

scrollbar = tk.Scrollbar(tree_frame)
scrollbar.pack(side=tk.LEFT, fill=tk.Y)

tree = ttk.Treeview(tree_frame, yscrollcommand=scrollbar.set, columns=columns, show="headings", height=15) 
scrollbar.config(command=tree.yview)
for col in columns: 
    tree.heading(col, text=tr(col), anchor=tk.CENTER)
    tree.column(col, anchor=tk.CENTER)
tree['displaycolumns'] = rtl_display_order(columns, ['id', 'title', 'author', 'isbn'])
cursor.execute(f"SELECT {', '.join(columns)} FROM {tabel_name}")
rows = cursor.fetchall()
tree.pack(side=tk.RIGHT, fill="both", expand=True, padx=10, pady=10)

conn.close()

def update_filter_button_indicator():
    is_custom = (
        filter_settings['column'] != 'all' or
        filter_settings['match_mode'] != 'contains' or
        filter_settings['availability'] != 'all' or
        filter_settings['sort_col'] != 'id' or
        filter_settings['sort_dir'] != 'ASC'
    )
    if is_custom:
        filter_btn.config(text=' فیلترها (فعال) ', fg='#0d6efd')
    else:
        filter_btn.config(text=' فیلترها ', fg='black')

def search(event=None):
    search_value = entry_serch.get().strip()

    tree.delete(*tree.get_children())

    try:
        temp_conn = sqlite3.connect(db_p)
        temp_cursor = temp_conn.cursor()

        where_conditions: list[str] = []
        params: list[str] = []

        if search_value:
            selected_col = filter_settings.get('column', 'all')
            match_mode = filter_settings.get('match_mode', 'contains')

            if match_mode == 'exact':
                pattern = search_value
                op = "="
            elif match_mode == 'startswith':
                pattern = f"{search_value}%"
                op = "LIKE"
            else:
                pattern = f"%{search_value}%"
                op = "LIKE"

            if selected_col == 'all':
                sub_conds = [f"{col} {op} ?" for col in columns]
                where_conditions.append("(" + " OR ".join(sub_conds) + ")")
                params.extend([pattern] * len(columns))
            elif selected_col in columns:
                where_conditions.append(f"{selected_col} {op} ?")
                params.append(pattern)

        avail = filter_settings.get('availability', 'all')
        if avail == 'borrowed':
            where_conditions.append("title IN (SELECT book_id FROM loans WHERE borrowed = 1)")
        elif avail == 'available':
            where_conditions.append("title NOT IN (SELECT book_id FROM loans WHERE borrowed = 1)")

        query = f"SELECT {', '.join(columns)} FROM {tabel_name}"
        if where_conditions:
            query += " WHERE " + " AND ".join(where_conditions)

        sort_col = filter_settings.get('sort_col', 'id')
        if sort_col not in columns:
            sort_col = 'id'
        sort_dir = filter_settings.get('sort_dir', 'ASC')
        if sort_dir not in ('ASC', 'DESC'):
            sort_dir = 'ASC'
        query += f" ORDER BY {sort_col} {sort_dir}"

        temp_cursor.execute(query, tuple(params))
        results = temp_cursor.fetchall()
        temp_conn.close()

        if results:
            for row in results:
                tree.insert("", "end", values=row)
        else:
            tree.insert("", "end", values=("❌ نتیجه‌ای یافت نشد!",) + ("",) * (len(columns)-1))

    except Exception as e:
        messagebox.showerror("خطا", f"خطا در جستجو: {str(e)}")

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

    col_var = tk.StringVar(value=filter_settings['column'])
    match_var = tk.StringVar(value=filter_settings['match_mode'])
    avail_var = tk.StringVar(value=filter_settings['availability'])
    sort_col_var = tk.StringVar(value=filter_settings['sort_col'])
    sort_dir_var = tk.StringVar(value=filter_settings['sort_dir'])

    group_col = tk.LabelFrame(popup, text="جستجو در ستون", font=FONT_BOLD, padx=10, pady=5)
    group_col.pack(fill=tk.X, padx=15, pady=(10, 5))
    col_frame = tk.Frame(group_col)
    col_frame.pack(fill=tk.X)
    rb_all = tk.Radiobutton(col_frame, text="همه ستون‌ها", variable=col_var, value="all", font=FONT_NORMAL, anchor='e')
    rb_all.pack(side=tk.RIGHT, padx=4)
    for col in ['title', 'author', 'isbn', 'id']:
        if col in columns:
            rb = tk.Radiobutton(col_frame, text=tr(col), variable=col_var, value=col, font=FONT_NORMAL, anchor='e')
            rb.pack(side=tk.RIGHT, padx=4)

    group_mode = tk.LabelFrame(popup, text="نوع تطابق جستجو", font=FONT_BOLD, padx=10, pady=5)
    group_mode.pack(fill=tk.X, padx=15, pady=5)
    mode_frame = tk.Frame(group_mode)
    mode_frame.pack(fill=tk.X)
    rb_contains = tk.Radiobutton(mode_frame, text="شامل عبارت", variable=match_var, value="contains", font=FONT_NORMAL, anchor='e')
    rb_contains.pack(side=tk.RIGHT, padx=8)
    rb_starts = tk.Radiobutton(mode_frame, text="شروع با عبارت", variable=match_var, value="startswith", font=FONT_NORMAL, anchor='e')
    rb_starts.pack(side=tk.RIGHT, padx=8)
    rb_exact = tk.Radiobutton(mode_frame, text="مطابقت دقیق", variable=match_var, value="exact", font=FONT_NORMAL, anchor='e')
    rb_exact.pack(side=tk.RIGHT, padx=8)

    group_avail = tk.LabelFrame(popup, text="وضعیت امانت کتاب", font=FONT_BOLD, padx=10, pady=5)
    group_avail.pack(fill=tk.X, padx=15, pady=5)
    avail_frame = tk.Frame(group_avail)
    avail_frame.pack(fill=tk.X)
    rb_av_all = tk.Radiobutton(avail_frame, text="همه کتاب‌ها", variable=avail_var, value="all", font=FONT_NORMAL, anchor='e')
    rb_av_all.pack(side=tk.RIGHT, padx=8)
    rb_av_avail = tk.Radiobutton(avail_frame, text="فقط کتاب‌های موجود", variable=avail_var, value="available", font=FONT_NORMAL, anchor='e')
    rb_av_avail.pack(side=tk.RIGHT, padx=8)
    rb_av_borrowed = tk.Radiobutton(avail_frame, text="فقط در امانت", variable=avail_var, value="borrowed", font=FONT_NORMAL, anchor='e')
    rb_av_borrowed.pack(side=tk.RIGHT, padx=8)

    group_sort = tk.LabelFrame(popup, text="مرتب‌سازی نتایج", font=FONT_BOLD, padx=10, pady=5)
    group_sort.pack(fill=tk.X, padx=15, pady=5)
    sort_frame = tk.Frame(group_sort)
    sort_frame.pack(fill=tk.X, pady=3)

    tk.Label(sort_frame, text="بر اساس:", font=FONT_NORMAL).pack(side=tk.RIGHT, padx=(5, 0))
    sort_cols_available = [c for c in ['title', 'author', 'id'] if c in columns]
    sort_col_cb = ttk.Combobox(sort_frame, state="readonly", width=12, font=FONT_NORMAL, justify='right',
                               values=[tr(c) for c in sort_cols_available])
    sort_col_cb.set(tr(sort_col_var.get()))
    sort_col_cb.pack(side=tk.RIGHT, padx=5)

    tk.Label(sort_frame, text="ترتیب:", font=FONT_NORMAL).pack(side=tk.RIGHT, padx=(12, 0))
    sort_dir_cb = ttk.Combobox(sort_frame, state="readonly", width=9, font=FONT_NORMAL, justify='right',
                               values=["صعودی", "نزولی"])
    sort_dir_cb.set("صعودی" if sort_dir_var.get() == "ASC" else "نزولی")
    sort_dir_cb.pack(side=tk.RIGHT, padx=5)

    action_frame = tk.Frame(popup)
    action_frame.pack(fill=tk.X, padx=15, pady=(15, 10))

    def apply_filters():
        filter_settings['column'] = col_var.get()
        filter_settings['match_mode'] = match_var.get()
        filter_settings['availability'] = avail_var.get()

        disp_col = sort_col_cb.get()
        disp_map = {tr(c): c for c in columns}
        filter_settings['sort_col'] = disp_map.get(disp_col, 'id')
        filter_settings['sort_dir'] = 'ASC' if sort_dir_cb.get() == "صعودی" else 'DESC'

        update_filter_button_indicator()
        popup.destroy()
        search()

    def reset_filters():
        filter_settings['column'] = 'all'
        filter_settings['match_mode'] = 'contains'
        filter_settings['availability'] = 'all'
        filter_settings['sort_col'] = 'id'
        filter_settings['sort_dir'] = 'ASC'

        update_filter_button_indicator()
        popup.destroy()
        search()

    btn_apply = create_icon_button(action_frame, text=" اعمال فیلتر ", icon_name='check', font=FONT_BOLD, padx=6, pady=2, command=apply_filters)
    btn_apply.pack(side=tk.RIGHT, padx=4)

    btn_reset = create_icon_button(action_frame, text=" تنظیم مجدد ", icon_name='rotate-ccw', font=FONT_NORMAL, padx=6, pady=2, command=reset_filters)
    btn_reset.pack(side=tk.RIGHT, padx=4)

    btn_cancel = create_icon_button(action_frame, text=" انصراف ", icon_name='x', font=FONT_NORMAL, padx=6, pady=2, command=popup.destroy)
    btn_cancel.pack(side=tk.LEFT, padx=4)

filter_btn.config(command=open_filter_popup)

search_after_id = None

def on_key_release(event):
    global search_after_id
    if search_after_id is not None:
        root.after_cancel(search_after_id)
    search_after_id = root.after(200, search)

member_frame = ttk.Frame(notebook)
notebook.add(member_frame, text=" اضافه کردن کاربر ")

def validate_phone(phone):
    pattern = r'^09[0-9]{9}$'
    return re.match(pattern, phone) is not None

def insert_member_data():
    member_id = entry_member_id.get().strip()
    phone_number = entry_phone.get().strip()
    
    if not member_id:
        messagebox.showwarning("خطا", "لطفاً نام کاربر را وارد کنید!")
        entry_member_id.focus()
        return
    
    if not phone_number:
        messagebox.showwarning("خطا", "لطفاً شماره تلفن را وارد کنید!")
        entry_phone.focus()
        return
    
    if not validate_phone(phone_number):
        messagebox.showerror("خطا", "فرمت شماره تلفن نامعتبر است!\nمثال: 09123456789")
        entry_phone.delete(0, tk.END)
        entry_phone.focus()
        return
    
    try:
        temp_conn = sqlite3.connect(db_p)
        temp_cursor = temp_conn.cursor()
        
        temp_cursor.execute("INSERT INTO members (member_id, phone_number) VALUES (?, ?)",(member_id, phone_number))
        
        temp_conn.commit()
        temp_conn.close()
        
        messagebox.showinfo("موفق", f"اطلاعات عضو با نام {member_id} با موفقیت ثبت شد!")
        
        entry_member_id.delete(0, tk.END)
        entry_phone.delete(0, tk.END)
        entry_member_id.focus()
        
    except sqlite3.IntegrityError:
        messagebox.showerror("خطا", f"نام کاربر {member_id} قبلاً ثبت شده است!")
        entry_member_id.delete(0, tk.END)
        entry_member_id.focus()
        
    except sqlite3.Error as e:
        messagebox.showerror("خطا", f"خطا در پایگاه داده: {e}")

title_label = tk.Label(member_frame, text="ثبت عضو جدید", font=FONT_TITLE)
title_label.pack(pady=10)

tk.Label(member_frame, text="نام کاربر:", font=FONT_NORMAL).pack(pady=5)
entry_member_id = tk.Entry(member_frame, width=25, font=FONT_NORMAL, justify='right')
entry_member_id.pack(pady=5)

tk.Label(member_frame, text="شماره تلفن:", font=FONT_NORMAL).pack(pady=5)
entry_phone = tk.Entry(member_frame, width=25, font=FONT_NORMAL, justify='right')
entry_phone.pack(pady=5)

btn_register = create_icon_button(member_frame, text=" ثبت اطلاعات ", icon_name='check', command=insert_member_data, font=FONT_BOLD, padx=12, pady=4)
btn_register.pack(pady=10)

member_conn = sqlite3.connect(db_p)
member_cursor = member_conn.cursor()

member_tabel_name = 'members'
member_cursor.execute(f'PRAGMA table_info("{member_tabel_name}")')
member_column: list[str] = [str(row[1]) for row in member_cursor.fetchall()]

member_tree_frame = ttk.Frame(member_frame)
member_tree_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

member_scrollbar = tk.Scrollbar(member_tree_frame)
member_scrollbar.pack(side=tk.LEFT, fill=tk.Y)

member_tree = ttk.Treeview(member_tree_frame, yscrollcommand=member_scrollbar.set, columns=member_column, show="headings", height=15) 
member_scrollbar.config(command=member_tree.yview)
for col in member_column: 
    member_tree.heading(col, text=tr(col), anchor=tk.CENTER)
    member_tree.column(col, anchor=tk.CENTER)
member_tree['displaycolumns'] = rtl_display_order(member_column, ['id', 'member_id', 'phone_number'])
member_cursor.execute(f"SELECT {', '.join(member_column)} FROM {member_tabel_name}")
member_row = member_cursor.fetchall()
member_tree.pack(side=tk.RIGHT, fill="both", expand=True, padx=10, pady=10)
for row in member_row:
    member_tree.insert("",tk.END, values=row)

member_conn.commit()
member_conn.close()
date_object = jdatetime.date.today()
days_10 = date_object + jdatetime.timedelta(days=10)
days_20 = date_object + jdatetime.timedelta(days=20)
days_30 = date_object + jdatetime.timedelta(days=30)

def on_double_click(event):
    selected = tree.selection()
    if not selected:
        return
    item = selected[0]
    values = tree.item(item, "values")

    try:
        title_index = columns.index("title")
        title_value = values[title_index] if title_index < len(values) else ""
    except ValueError:
        title_value = ""
    
    new_panel = tk.Toplevel(root)
    new_panel.geometry("600x600")
    new_panel.title("امانت دادن")
    if os.path.exists(icon_p):
        try:
            new_panel.iconbitmap(icon_p)
        except Exception:
            pass

    def toggle_state():
        if var.get() == 1:
            borrow_entry.insert(0, str(date_object))
        else:
            borrow_entry.delete(0, tk.END)

    var = tk.IntVar(value=0)

    def refresh_treeview():
        temp_conn = sqlite3.connect(db_p)
        temp_cursor = temp_conn.cursor()
        
        for item in loans_tree.get_children():
            loans_tree.delete(item)
        
        temp_cursor.execute(f"SELECT {', '.join(loan_column)} FROM {new_tabel_name}")
        new_rows = temp_cursor.fetchall()
        
        for row in new_rows:
            loans_tree.insert("", tk.END, values=format_loan_row(row))

        temp_conn.close()

    def insert_data():
        return_shamsi_str = return_entry.get().strip()
        
        if not return_shamsi_str:
            messagebox.showwarning("هشدار", "لطفاً تاریخ بازگشت را وارد کنید!")
            return

        try:
            j_date = jdatetime.datetime.strptime(return_shamsi_str, '%Y-%m-%d')
            g_date = j_date.togregorian()
            return_date_val = g_date.strftime('%Y-%m-%d')
        except ValueError:
            messagebox.showerror("خطا", "فرمت تاریخ بازگشت وارد شده صحیح نیست!\nلطفاً به صورت YYYY-MM-DD وارد کنید.")
            return

        borrow_shamsi_str = borrow_entry.get().strip()

        if not borrow_shamsi_str:
            messagebox.showwarning("هشدار", "لطفاً تاریخ امانت را وارد کنید!")
            return

        try:
            j_date = jdatetime.datetime.strptime(borrow_shamsi_str, '%Y-%m-%d')
            g_date = j_date.togregorian()
            borrow_date_val = g_date.strftime('%Y-%m-%d')
        except ValueError:
            messagebox.showerror("خطا", "فرمت تاریخ امانت وارد شده صحیح نیست!\nلطفاً به صورت YYYY-MM-DD وارد کنید.")
            return

        book_id = book_entry.get()
        member_name = member_entry.get()
        
        if not member_name:
            messagebox.showerror("خطا", "لطفاً نام کاربر را وارد کنید")
            return

        try:
            temp_conn = sqlite3.connect(db_p)
            temp_cursor = temp_conn.cursor()

            temp_cursor.execute("INSERT INTO loans (member_name, book_id, return_date, borrow_date) VALUES (?, ?, ?, ?)", (member_name, book_id if book_id else None, return_date_val, borrow_date_val))
            temp_conn.commit()
            temp_conn.close()

            messagebox.showinfo("موفقیت", "اطلاعات امانت با موفقیت ذخیره شد")
            notification_engine.show("ثبت موفق امانت", f"کتاب «{book_id}» با موفقیت برای {member_name} ثبت شد.")
            refresh_treeview()
            new_panel.destroy()
            
        except sqlite3.Error as e:
            messagebox.showerror("خطای پایگاه داده", f"خطا در ذخیره اطلاعات: {e}")

    def on_panel_close():
        refresh_treeview()
        new_panel.destroy()
    new_panel.protocol("WM_DELETE_WINDOW", on_panel_close)

    tk.Label(new_panel, text="نام کاربر:", font=FONT_NORMAL).pack(pady=3)
    member_entry = tk.Entry(new_panel, width=50, font=FONT_NORMAL, justify='right')
    member_entry.pack(pady=3)

    temp_conn = sqlite3.connect(db_p)
    temp_cursor = temp_conn.cursor()
    temp_cursor.execute("SELECT member_id FROM members")
    members_data = [row[0] for row in temp_cursor.fetchall()]
    temp_conn.close()

    listbox = tk.Listbox(new_panel, width=50, font=FONT_NORMAL, justify='right')
    listbox.pack(pady=3)

    def search_member(e):
        listbox.delete(0, tk.END)
        for item in members_data:
            if member_entry.get().lower() in item.lower():
                listbox.insert(tk.END, item)

    def select_member(e):
        if listbox.curselection():
            member_entry.delete(0, tk.END)
            member_entry.insert(0, listbox.get(listbox.curselection()[0]))
            listbox.delete(0, tk.END)

    member_entry.bind('<KeyRelease>', search_member)
    listbox.bind('<Double-Button-1>', select_member)
    
    tk.Label(new_panel, text="عنوان کتاب:", font=FONT_NORMAL).pack(pady=3)
    book_entry = tk.Entry(new_panel, width=50, font=FONT_NORMAL, justify='right')
    book_entry.pack(pady=3)

    book_entry.insert(0, title_value)
    book_entry.config(state="readonly")

    tk.Label(new_panel, text="تاریخ امانت کتاب:", font=FONT_NORMAL).pack(pady=3)
    borrow_entry = tk.Entry(new_panel, width=50, font=FONT_NORMAL, justify='right')
    borrow_entry.pack(pady=3)

    toggle = tk.Checkbutton(new_panel, text="ثبت خودکار تاریخ", variable=var, command=toggle_state, font=FONT_NORMAL, indicatoron=True, width=15, height=2)
    toggle.pack(pady=3)

    tk.Label(new_panel, text="تاریخ بازگشت کتاب:", font=FONT_NORMAL).pack(pady=3)
    return_entry = tk.Entry(new_panel, width=50, font=FONT_NORMAL, justify='right')
    return_entry.pack(pady=3)

    selected = tk.StringVar(value="none")

    def on_select():
        choice = selected.get()
        return_entry.delete(0, tk.END)
        if choice == "option1":
            return_entry.insert(0, str(days_10))
        elif choice == "option2":
            return_entry.insert(0, str(days_20))
        elif choice == "option3":
            return_entry.insert(0, str(days_30))

    btn_frame = ttk.Frame(new_panel)
    btn_frame.pack(pady=10)

    rb1 = ttk.Radiobutton(btn_frame, text="10 روز", variable=selected, value="option1", command=on_select, style="Modern.TRadiobutton")
    rb2 = ttk.Radiobutton(btn_frame, text="20 روز", variable=selected, value="option2", command=on_select, style="Modern.TRadiobutton")
    rb3 = ttk.Radiobutton(btn_frame, text="30 روز", variable=selected, value="option3", command=on_select, style="Modern.TRadiobutton")
    rb1.pack(side=tk.RIGHT, padx=20)
    rb2.pack(side=tk.RIGHT, padx=20)
    rb3.pack(side=tk.RIGHT, padx=20)

    sub_button = create_icon_button(new_panel, text=" ثبت امانت ", icon_name='arrow-right-left', font=FONT_BOLD, padx=12, pady=4, command=insert_data)
    sub_button.pack(pady=10)

book_frame = ttk.Frame(notebook)
notebook.add(book_frame, text=" اضافه کردن کتاب ")

title_label_book = tk.Label(book_frame, text="ثبت کتاب جدید", font=FONT_TITLE)
title_label_book.pack(pady=10)

form_cols = [c for c in ['id', 'title', 'author', 'isbn'] if c in columns] + [c for c in columns if c not in ['id', 'title', 'author', 'isbn']]
book_entries = {}
for col in form_cols:
    col_fa = tr(col)
    tk.Label(book_frame, text=f"{col_fa}:", font=FONT_NORMAL).pack(pady=5)
    ent = tk.Entry(book_frame, width=25, font=FONT_NORMAL, justify='right')
    ent.pack(pady=5)
    book_entries[col] = ent

def insert_book_data():
    vals = []
    for col in columns:
        v = book_entries[col].get().strip()
        if not v:
            col_fa = tr(col)
            messagebox.showwarning("خطا", f"لطفاً فیلد {col_fa} را پر کنید!")
            book_entries[col].focus()
            return
        vals.append(v)

    try:
        temp_conn = sqlite3.connect(db_p)
        temp_cursor = temp_conn.cursor()

        placeholders = ", ".join(["?"] * len(columns))
        col_names = ", ".join(columns)
        query = f"INSERT INTO {tabel_name} ({col_names}) VALUES ({placeholders})"
        temp_cursor.execute(query, tuple(vals))

        temp_conn.commit()
        temp_conn.close()

        messagebox.showinfo("موفق", "اطلاعات کتاب با موفقیت ثبت شد!")

        for col in columns:
            book_entries[col].delete(0, tk.END)
        book_entries[columns[0]].focus()

    except sqlite3.IntegrityError:
        messagebox.showerror("خطا", "این کتاب قبلاً ثبت شده است!")

    except sqlite3.Error as e:
        messagebox.showerror("خطا", f"خطا در پایگاه داده: {e}")

btn_register_book = create_icon_button(book_frame, text=" ثبت اطلاعات ", icon_name='check', command=insert_book_data, font=FONT_BOLD, padx=12, pady=4)
btn_register_book.pack(pady=10)

tabel_frame = tk.Frame(notebook)
notebook.add(tabel_frame, text=" جدول امانات ")

scrollbar_2 = tk.Scrollbar(tabel_frame)
scrollbar_2.pack(side=tk.LEFT, fill=tk.Y)

new_conn = sqlite3.connect(db_p)
new_cursor = new_conn.cursor()

new_tabel_name = 'loans'
new_cursor.execute(f'PRAGMA table_info("{new_tabel_name}")')
loan_column: list[str] = [str(row[1]) for row in new_cursor.fetchall()]

today = jdatetime.date.today()
loans_tree = ttk.Treeview(tabel_frame, yscrollcommand=scrollbar_2.set, columns=loan_column, show="headings", height=15)
scrollbar_2.config(command=loans_tree.yview)
for col in loan_column: 
    loans_tree.heading(col, text=tr(col), anchor=tk.CENTER)
    loans_tree.column(col, anchor=tk.CENTER)
loans_tree['displaycolumns'] = rtl_display_order(loan_column, ['id', 'member_name', 'book_id', 'borrow_date', 'return_date', 'borrowed'])
loans_tree.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

new_cursor.execute(f"SELECT * FROM `{new_tabel_name}` ORDER BY julianday(`return_date`) - julianday(`borrow_date`) ASC")
loan_rows = new_cursor.fetchall()

borrow_date = 'borrow_date'
borrow_index = loan_column.index(borrow_date) if borrow_date in loan_column else -1
return_date = 'return_date' 
return_index = loan_column.index(return_date) if return_date in loan_column else -1
borrowed_index = loan_column.index('borrowed') if 'borrowed' in loan_column else -1

def format_loan_row(row):
    row_list = list(row)
    if return_index != -1 and return_index < len(row_list) and row_list[return_index]:
        try:
            miladi_date_str = str(row_list[return_index])
            g_date = datetime.datetime.strptime(miladi_date_str, '%Y-%m-%d').date()
            shamsi_date = jdatetime.date.fromgregorian(date=g_date)
            row_list[return_index] = shamsi_date.strftime('%Y-%m-%d')
        except ValueError:
            pass 
    if borrow_index != -1 and borrow_index < len(row_list) and row_list[borrow_index]:
        try:
            date_str = str(row_list[borrow_index])
            if '-' in date_str:
                parts = [int(p) for p in date_str.split('-')]
                if parts[0] > 1900:
                    g_date = datetime.date(parts[0], parts[1], parts[2])
                    row_list[borrow_index] = jdatetime.date.fromgregorian(date=g_date).strftime('%Y-%m-%d')
        except Exception:
            pass
    if borrowed_index != -1 and borrowed_index < len(row_list):
        val = row_list[borrowed_index]
        if val == 1 or val == '1' or val is True:
            row_list[borrowed_index] = "در امانت"
        elif val == 0 or val == '0' or val is False:
            row_list[borrowed_index] = "بازگردانده شده"
    return tuple(row_list)

def gregorian():
    for row in loan_rows:
        loans_tree.insert("", tk.END, values=format_loan_row(row))

def refresh_loans_tree():
    temp_conn = sqlite3.connect(db_p)
    temp_cursor = temp_conn.cursor()
    for item in loans_tree.get_children():
        loans_tree.delete(item)
    temp_cursor.execute(f"SELECT * FROM `{new_tabel_name}` ORDER BY julianday(`return_date`) - julianday(`borrow_date`) ASC")
    for row in temp_cursor.fetchall():
        loans_tree.insert("", tk.END, values=format_loan_row(row))
    temp_conn.close()

def on_loan_double_click(event):
    selected = loans_tree.selection()
    if not selected:
        return
    values = loans_tree.item(selected[0], "values")
    id_idx = loan_column.index("id") if "id" in loan_column else -1
    borrowed_idx = loan_column.index("borrowed") if "borrowed" in loan_column else -1
    book_idx = loan_column.index("book_id") if "book_id" in loan_column else -1
    member_idx = loan_column.index("member_name") if "member_name" in loan_column else -1

    if id_idx == -1:
        return
    loan_id = values[id_idx]
    book_name = values[book_idx] if book_idx != -1 else "کتاب"
    member_name = values[member_idx] if member_idx != -1 else "کاربر"
    borrowed_val = values[borrowed_idx] if borrowed_idx != -1 else ""

    if borrowed_val == "بازگردانده شده":
        messagebox.showinfo("اطلاع", "این کتاب قبلاً بازگردانده شده است.")
        return

    confirm = messagebox.askyesno("ثبت بازگشت کتاب", f"آیا بازگشت کتاب «{book_name}» توسط {member_name} تایید می‌شود؟")
    if confirm:
        try:
            conn_ret = sqlite3.connect(db_p)
            c_ret = conn_ret.cursor()
            c_ret.execute("UPDATE loans SET borrowed = 0 WHERE id = ?", (loan_id,))
            conn_ret.commit()
            conn_ret.close()
            refresh_loans_tree()
            notification_engine.show("ثبت بازگشت کتاب", f"کتاب «{book_name}» با موفقیت بازگردانده شد.")
        except sqlite3.Error as e:
            messagebox.showerror("خطا", f"خطا در ثبت بازگشت کتاب: {e}")

root.bind('<Escape>',lambda event:root.destroy())
entry_serch.bind('<KeyRelease>', on_key_release)
entry_serch.bind('<Return>', search)
tree.bind("<Double-Button-1>", on_double_click)
loans_tree.bind("<Double-Button-1>", on_loan_double_click)

root.geometry("800x600")

new_conn.close()
search()
gregorian()
root.mainloop()