import tkinter as tk
from tkinter import ttk
def select():
    selected_item = combo_box.get()
    label.config(text="Selected Item: " + selected_item)
root = tk.Tk()
root.geometry("600x400")
root.title("Combobox Example")
label = tk.Label(root, text="Selected Item:")
label.pack(pady=10)
combo_box = ttk.Combobox(root,values=["اسم کتاب", "نویسنده", "ناشر", "رده بندی دیویی", "مترجم"],state="readonly")
combo_box.pack(pady=5)
combo_box.set("اسم کتاب")
#combo_box.bind("<<ComboboxSelected>>", select)
sub_btn=tk.Button(root,width=70,text = 'Submit', command=select)
sub_btn.pack(pady=12)
root.mainloop()