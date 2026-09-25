"""
Shared UI helper functions.
"""

from __future__ import annotations

import datetime
from tkinter import filedialog, messagebox, ttk
from typing import Any

from database import write_csv_file


def export_tree_to_csv_ui(tree_widget: ttk.Treeview, default_name: str, root: Any = None) -> None:
    """
    Exports items from a ttk.Treeview to a UTF-8 BOM CSV file.
    """
    # ponytail: basic csv dump of treeview items; upgrade to async export if 100k+ rows
    try:
        items = tree_widget.get_children()
        rows = []
        for item in items:
            vals = tree_widget.item(item, "values")
            if vals and str(vals[0]).startswith("❌"):
                continue
            rows.append(vals)

        if not rows:
            messagebox.showinfo("خروجی CSV", "هیچ داده‌ای برای صدور یافت نشد.", parent=root)
            return

        cols = list(tree_widget["columns"])
        headers = [tree_widget.heading(c).get("text", c) for c in cols]

        default_file = f"{default_name}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        dest_path = filedialog.asksaveasfilename(
            parent=root,
            title="ذخیره خروجی اکسل / CSV",
            defaultextension=".csv",
            initialfile=default_file,
            filetypes=[("فایل CSV", "*.csv"), ("تمام فایل‌ها", "*.*")],
        )
        if not dest_path:
            return

        write_csv_file(dest_path, headers, rows)
        messagebox.showinfo(
            "خروجی موفق",
            f"تعداد {len(rows)} رکورد با موفقیت در فایل زیر ذخیره شد:\n{dest_path}",
            parent=root,
        )
    except Exception as e:
        messagebox.showerror("خطا در خروجی CSV", f"خطا در ایجاد فایل:\n{e}", parent=root)
