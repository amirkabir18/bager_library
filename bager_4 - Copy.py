import sqlite3,os,sys,re
import tkinter as tk
import ttkbootstrap as tb
from tkinter import ttk,messagebox
import jdatetime

db_p = os.path.join(getattr(sys, '_MEIPASS', os.path.dirname(__file__)), 'bager_library.db')

conn = sqlite3.connect(db_p)
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
data = cursor.fetchall()
tabel_name = data[0][0]
cursor.execute(f'PRAGMA table_info("{tabel_name}")')
columns = [row[1] for row in cursor.fetchall()]

root = tk.Tk()
root.title("کتابخانه باقر العلوم")
style = tb.Style(theme="darkly")
st = ttk.Style()

notebook = ttk.Notebook(root)
notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

books_frame = ttk.Frame(notebook)
notebook.add(books_frame, text="جستجوی کتاب")

label_1 = tk.Label(books_frame, text="یک گزینه انتخاب کن",font=("B Titr", 14, "bold"))
label_1.pack(pady=8)

entry_serch=tk.Entry(books_frame, font=('calibre',10,'normal'))
entry_serch.pack(pady=5)

combo_column = ttk.Combobox(books_frame,state="readonly",values=columns)
combo_column.pack(pady=5)

tree_frame = tk.Frame(books_frame)
tree_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

scrollbar = tk.Scrollbar(tree_frame)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

tree = ttk.Treeview(tree_frame,yscrollcommand=scrollbar, columns=columns, show="headings", height=15)
for col in columns: 
    tree.heading(col, text=col)
cursor.execute(f"SELECT {', '.join(columns)} FROM {tabel_name}")
rows = cursor.fetchall()
tree.pack(fill="both", expand=True, padx=10, pady=10)

st.configure("Treeview", font=(None, 13), rowheight=30)
conn.close()

def search(event=None):
    column = combo_column.get()
    search_value = entry_serch.get()

    
    if not column:
        label_1.config(text="لطفاً همه فیلدها را پر کنید!")
        return

    tree.delete(*tree.get_children())
    
    try:
        temp_conn = sqlite3.connect(db_p)
        temp_cursor = temp_conn.cursor()

        if not search_value:
            query = f"SELECT * FROM {tabel_name}"
            temp_cursor.execute(query)
        else:
            query = f"SELECT * FROM {tabel_name} WHERE {column} LIKE ?"
            temp_cursor.execute(query, (f"%{search_value}%",))
            
        results = temp_cursor.fetchall()
        temp_conn.close()

        if results:
            for row in results:
                tree.insert("", "end", values=row)
        else:
            tree.insert("", "end", values=("❌ نتیجه‌ای یافت نشد!",) + ("",) * (len(columns)-1))
        
    except Exception as e:
        label_1.config(text=f"خطا: {str(e)}")

def on_key_release(event):
    if hasattr(root, 'after_id'):
        root.after_cancel(root.after_id)
    root.after_id = root.after(200, search)
    
sub_btn = tk.Button(books_frame,text = 'تایید',width=50,command=search)
sub_btn.pack(pady=12)

member_frame = ttk.Frame(notebook)
notebook.add(member_frame, text="اضافه کردن کاربر")

def validate_phone(phone):
    pattern = r'^09[0-9]{9}$'
    return re.match(pattern, phone) is not None

def insert_member_data():
    member_id = entry_member_id.get().strip()
    phone_number = entry_phone.get().strip()
    
    if not member_id:
        messagebox.showwarning("خطا", "لطفاً اسم کاربر را وارد کنید!")
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
        
        messagebox.showinfo("موفق", f"اطلاعات عضو با اسم {member_id} با موفقیت ثبت شد!")
        
        entry_member_id.delete(0, tk.END)
        entry_phone.delete(0, tk.END)
        entry_member_id.focus()
        
    except sqlite3.IntegrityError:
        messagebox.showerror("خطا", f"اسم کاربر {member_id} قبلاً ثبت شده است!")
        entry_member_id.delete(0, tk.END)
        entry_member_id.focus()
        
    except sqlite3.Error as e:
        messagebox.showerror("خطا", f"خطا در دیتابیس: {e}")

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
            
            temp_cursor.execute(f"SELECT {', '.join(column)} FROM {new_tabel_name}")
            new_rows = temp_cursor.fetchall()
            
            for row in new_rows:
                loans_tree.insert("", tk.END, values=row)
    
            temp_conn.close()

    def insert_data():
        borrow_date = date_object.togregorian()
        return_date = return_entry.get()
        book_id = book_entry.get()
        member_name = member_entry.get()
        
        if not member_name:
            messagebox.showerror("خطا", "لطفاً نام را وارد کنید")
            return
        
        try:
            temp_conn = sqlite3.connect(db_p)
            temp_cursor = temp_conn.cursor()

            temp_cursor.execute('''INSERT INTO loans (member_name, book_id, return_date, borrow_date) VALUES (?, ?, ?, ?)''', (member_name, book_id if book_id else None, return_date, borrow_date))
            temp_conn.commit()
            temp_conn.close()

            messagebox.showinfo("موفقیت", "اطلاعات با موفقیت ذخیره شد")
            refresh_treeview()
            new_panel.destroy()
            
        except sqlite3.Error as e:
            messagebox.showerror("خطای دیتابیس", f"خطا در ذخیره اطلاعات: {e}")

    def on_panel_close():
            refresh_treeview()
            new_panel.destroy()
    new_panel.protocol("WM_DELETE_WINDOW", on_panel_close)

    tk.Label(new_panel,text="اسم کاربر",font=("B Nazanin", 11)).pack(pady=3)
    member_entry = tk.Entry(new_panel, width=50)
    member_entry.pack(pady=3)

    temp_conn = sqlite3.connect(db_p)
    temp_cursor = temp_conn.cursor()
    temp_cursor.execute("SELECT member_id FROM members")
    data = [row[0] for row in temp_cursor.fetchall()]

    listbox = tk.Listbox(new_panel, width=50)
    listbox.pack(pady=3)

    def search_member(e):
        listbox.delete(0, tk.END)
        for item in data:
            if member_entry.get().lower() in item.lower():
                listbox.insert(tk.END, item)

    def select_member(e):
        if listbox.curselection():
            member_entry.delete(0, tk.END)
            member_entry.insert(0, listbox.get(listbox.curselection()[0]))
            listbox.delete(0, tk.END)

    member_entry.bind('<KeyRelease>', search_member)
    listbox.bind('<Double-Button-1>', select_member)
    
    tk.Label(new_panel,text="اسم کتاب",font=("B Nazanin", 11)).pack(pady=3)
    book_entry = tk.Entry(new_panel, width=50)
    book_entry.pack(pady=3)

    book_entry.insert(0, title_value)
    book_entry.config(state="readonly", readonlybackground="#333333")

    tk.Label(new_panel,text="تاریخ امانت کتاب",font=("B Nazanin", 11)).pack(pady=3)
    borrow_entry = tk.Entry(new_panel, width=50)
    borrow_entry.pack(pady=3)

    toggle = tk.Checkbutton(new_panel, text="ثبت اتومایک تاریخ", variable=var, command=toggle_state, font=("Arial", 11), indicatoron=True, width=15, height=2)
    toggle.pack(pady=3)

    tk.Label(new_panel,text="تاریخ بازگشت کتاب",font=("B Nazanin", 11)).pack(pady=3)
    return_entry = tk.Entry(new_panel, width=50)
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
    rb2 = ttk.Radiobutton(btn_frame, text="20 روز", variable=selected, value="option2", command=on_select,style="Modern.TRadiobutton")
    rb3 = ttk.Radiobutton(btn_frame, text="30 روز", variable=selected, value="option3", command=on_select,style="Modern.TRadiobutton")
    rb1.pack(side=tk.LEFT, padx=20)
    rb2.pack(side=tk.LEFT, padx=20)
    rb3.pack(side=tk.LEFT, padx=20)

    sub_button = tk.Button(new_panel, text="ثبت امانت", command=insert_data)
    sub_button.pack(pady=3)

title_label = tk.Label(member_frame,text="ثبت عضو جدید",font=("B Titr", 14, "bold"),fg="#2c3e50")
title_label.pack(pady=10)

tk.Label(member_frame, text="اسم کاربر:", font=("B Nazanin", 11)).pack(pady=5)
entry_member_id = tk.Entry(member_frame, width=25, font=("B Nazanin", 11))
entry_member_id.pack(pady=5)

tk.Label(member_frame, text="شماره تلفن:", font=("B Nazanin", 11)).pack(pady=5)
entry_phone = tk.Entry(member_frame, width=25, font=("B Nazanin", 11))
entry_phone.pack(pady=5)

btn_register = tk.Button(member_frame,text="ثبت اطلاعات",command=insert_member_data,fg="white",font=("B Nazanin", 11, "bold"),width=15,height=1)
btn_register.pack(pady=10)

member_del = tk.Button(member_frame, text="حذف کاربر", )
member_del.pack(pady=3)

tabel_frame = tk.Frame(notebook)
notebook.add(tabel_frame, text="جدول امانات")

scrollbar_2 = tk.Scrollbar(tabel_frame)
scrollbar_2.pack(side=tk.RIGHT, fill=tk.Y)

new_conn = sqlite3.connect(db_p)
new_cursor = new_conn.cursor()

new_tabel_name = data[2][0]
new_cursor.execute(f'PRAGMA table_info("{new_tabel_name}")')
column = [row[1] for row in new_cursor.fetchall()]

today = jdatetime.date.today()
loans_tree = ttk.Treeview(tabel_frame, yscrollcommand=scrollbar_2, columns=column, show="headings", height=15)
for col in column: 
    loans_tree.heading(col, text=col)
loans_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

st.configure("Treeview", font=(None, 13), rowheight=30)
new_cursor.execute(f"SELECT * FROM {new_tabel_name}")
loan_rows = new_cursor.fetchall()
for row in loan_rows:
    loans_tree.insert("", tk.END, values=row)
new_conn.close()

root.bind('<Escape>',lambda event:root.destroy())
entry_serch.bind('<KeyRelease>', on_key_release)
tree.bind("<Double-Button-1>", on_double_click)

search()
root.mainloop()