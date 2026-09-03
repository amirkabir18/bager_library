import sqlite3,os,sys
import tkinter as tk
from tkinter import ttk,messagebox,scrolledtext

root = tk.Tk()
root.geometry("800x550")
root.title("کتابخانه باقر العلوم")

conn = sqlite3.connect(os.path.join(getattr(sys, '_MEIPASS', os.path.dirname(__file__)), 'bager_library.db'))
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
data = cursor.fetchall()
tabel_name = data[0][0]
cursor.execute(f'PRAGMA table_info("{tabel_name}")')
columns = [row[1] for row in cursor.fetchall()]

entry_serch=tk.Entry(root, font=('calibre',10,'normal'))
entry_serch.pack(pady=5)

combo_column = ttk.Combobox(root,state="readonly",values=columns)
combo_column.pack(pady=5)

label_1 = tk.Label(root, text="یک گزینه انتخاب کن")
label_1.pack(pady=8)

text_widget = scrolledtext.ScrolledText(root,wrap=tk.WORD,width=50,height=10,font=("Arial", 12))
text_widget.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
 
def search():

    column = combo_column.get()
    search_value = entry_serch.get()
    
    if column == "انتخاب ستون" or not search_value:
        label_1.config(text="لطفاً همه فیلدها را پر کنید!")
        return
    
    try:
        text_widget.config(state=tk.NORMAL)
        text_widget.delete("1.0", tk.END)

        conn = sqlite3.connect(os.path.join(getattr(sys, '_MEIPASS', os.path.dirname(__file__)), 'bager_library.db'))
        cursor = conn.cursor()
        
        query = f"SELECT * FROM books WHERE {column} LIKE ?"
        cursor.execute(query, (f"%{search_value}%",))
        results = cursor.fetchall()
        
        cursor.execute(f'PRAGMA table_info("{tabel_name}")')
        column_names = [row[1] for row in cursor.fetchall()]
        
        if results:
            text = f"📊 {len(results)} نتیجه پیدا شد:\n\n" 
            for i, row in enumerate(results, 1):
                text += f"🔹 ردیف {i}:\n"
                for col_name, value in zip(column_names, row):
                    text += f"   {col_name}: {value}\n"
                text += "\n"
        else:
            text = "❌ نتیجه‌ای یافت نشد!"
        
        text_widget.insert(tk.END, text)
        text_widget.config(state=tk.DISABLED)
        conn.close()
        
    except Exception as e:
        label_1.config(text=f"خطا: {str(e)}")

class UpdateApp: 
    def __init__(self, root):
        self.root = root
        self.root.title("ویرایش کاربر")
        self.root.geometry("700x450")
        
        self.conn = sqlite3.connect('bager_library.db')
        self.cursor = self.conn.cursor()
        
        self.create_widgets()
        self.load_users()
        
    def create_widgets(self):
        tk.Label(self.root, text="انتخاب کاربر:").pack(pady=5)
        # self.user_combo = ttk.Combobox(self.root, width=40)
        # self.user_combo.pack(pady=5)
        
        self.combo = ttk.Combobox(self.root, font=("Arial", 12),width=50)
        self.combo.pack(pady=50, padx=20, fill='x')
        self.combo.bind('<KeyRelease>',self.filter_items)
        self.combo.bind('<<ComboboxSelected>>', self.load_user_data)

        tk.Label(self.root, text="مقدار جدید برای user_id:").pack(pady=5)
        self.value_entry = tk.Entry(self.root, width=40)
        self.value_entry.pack(pady=5)
        
        tk.Button(self.root, text="به‌روزرسانی", 
                  command=self.update_record,
                bg="green", fg="white", width=20).pack(pady=20)
        
    def load_users(self):
        self.cursor.execute("SELECT rowid, name FROM users")
        users = self.cursor.fetchall()
        self.combo['values'] = [f"{rowid} - {name}" for rowid, name in users]

    def filter_items(self, event):
            self.cursor.execute("SELECT rowid, name FROM users")
            text = self.combo.get().strip().lower()
            if text:
                filtered = [item for item in self.combo if text in item.lower()]
                self.combo['values'] = filtered
            else:
                self.combo['values'] = self.text
    
    def load_user_data(self, event):
        selected = self.combo.get()
        if not selected:
            return
        
        rowid = int(selected.split(' - ')[0])
        self.cursor.execute("SELECT name FROM users WHERE rowid = ?", (rowid,))
        user = self.cursor.fetchone()
        
        if user:
            self.value_entry.delete(0, tk.END)
            self.value_entry.insert(0, user[0])
            self.current_rowid = rowid
    
    def update_record(self):
        if not hasattr(self, 'current_rowid'):
            messagebox.showerror("خطا", "لطفاً یک کاربر را انتخاب کنید") 
            return
        
        new_value = self.value_entry.get().strip()
        
        if not new_value:
            messagebox.showerror("خطا", "مقدار نمی‌تواند خالی باشد")
            return
        
        try:
            self.cursor.execute(
                "UPDATE users SET name = ? WHERE rowid = ?", 
                (new_value, self.current_rowid)
            )
            self.conn.commit()
            
            if self.cursor.rowcount > 0:
                messagebox.showinfo("موفقیت", "با موفقیت به‌روزرسانی شد")
                self.load_users()
                
                self.value_entry.delete(0, tk.END)
            else:
                messagebox.showerror("خطا", "رکورد پیدا نشد")
                
        except sqlite3.Error as e:
            messagebox.showerror("خطا", f"خطای دیتابیس: {e}")
    
menubar = tk.Menu(root)
tools = tk.Menu(menubar,tearoff=0)
menubar.add_cascade(label ='ابزار ها', menu = tools)
tools.add_command(label='قرض دادن', command=lambda: UpdateApp(tk.Toplevel(root)))
# tools.add_separator()

sub_btn=tk.Button(root,text = 'تایید',width=50,bg="green",fg="white",command=search)
sub_btn.pack(pady=12)

root.bind('<Return>',lambda event:search())
root.bind('<Escape>',lambda event:root.destroy())
root.bind('<Control-c>',lambda event:())
root.bind('<Control-v>',lambda event:())

root.config(menu = menubar)

root.mainloop()

# pyinstaller --onefile --noconsole --add-data "example.db;." --name "bager_3" bager_3.py