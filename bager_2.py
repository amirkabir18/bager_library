import sqlite3,os,sys
import tkinter as tk
from tkinter import ttk
from tkinter import scrolledtext

root = tk.Tk()
root.geometry("600x300")
root.title("کتابخانه باقر العلوم")
conn = sqlite3.connect(os.path.join(getattr(sys, '_MEIPASS', os.path.dirname(__file__)), 'example.db'))
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

        conn = sqlite3.connect(os.path.join(getattr(sys, '_MEIPASS', os.path.dirname(__file__)), 'example.db'))
        cursor = conn.cursor()
        
        query = f"SELECT * FROM bager WHERE {column} LIKE ?"
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

def persspn_id():
    conn.execute("UPDATE bager SET id =  WHERE id = 1;")


sub_btn=tk.Button(root,text ='تایید',command=search)
sub_btn.pack(pady=12)

root.mainloop()
#--onefile --noconsole --add-data "example.db;." --name "bager_2" bager.py