import re
import tkinter as tk
import pandas as pd
from tkinter import ttk
root=tk.Tk()
root.geometry("600x300")
root.title("کتابخانه باقر العلوم")
file_path = r"project\Book1.xlsx" 
df = pd.read_excel(file_path, sheet_name=0)
matches = []
def select():
    label_1.config(text="")
    matches.clear()
    selected_item = combo_box.get()
    row_value = serch.get()
    column_data = df[selected_item].astype(str)
    for idx, value in column_data.items():
        if row_value:
            if row_value.lower() in value.lower():
                matches.append((idx + 2, df.iloc[idx].to_dict()))
    matches_txt = ""
    for match in matches:
        matches_txt +=  f"ردیف {match[0]}: {match[1]}\n"
    label_1.config(text=matches_txt)
#GUI
label_1 = tk.Label(root, text="یک گزینه انتخاب کن")
label_1.pack(pady=8)

combo_box = ttk.Combobox(root,values=df.columns.to_list(),state="readonly")
combo_box.pack(pady=5)

serch=tk.Entry(root, font=('calibre',10,'normal'))
serch.pack(pady=5)

label_2 = tk.Label()

sub_btn=tk.Button(root,text = 'تایید', command=select)
sub_btn.pack(pady=12)
root.mainloop()