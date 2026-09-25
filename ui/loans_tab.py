import datetime
import os
import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

import customtkinter as ctk
import jdatetime

from database import check_member_loan_eligibility, get_db_connection, rtl_display_order, tr
from persian_calendar import (
    create_date_picker_button,
    format_jalali_date,
    get_today_jalali,
    jalali_to_gregorian_str,
    parse_jalali_date,
)
from ui.common import export_tree_to_csv_ui


def build_loans_tab(
    parent: Any,
    root: Any,
    fonts: dict[str, Any],
    get_icon_fn: Callable[..., Any],
    create_icon_button_fn: Callable[..., Any],
    bind_table_delete_fn: Callable[..., Any],
    db_path: str,
    icon_path: str = "",
    notification_engine: Any = None,
    on_loan_changed: Callable[[], None] | None = None,
) -> dict[str, Any]:
    font_title = fonts.get("title")
    font_normal = fonts.get("normal")
    font_bold = fonts.get("bold")
    font_small = fonts.get("small")
    font_family = fonts.get("family", "IRANSansWeb(FaNum)")

    loans_table_name = "loans"
    with get_db_connection(db_path) as conn_loan:
        cur_loan = conn_loan.cursor()
        cur_loan.execute(f'PRAGMA table_info("{loans_table_name}")')
        loan_column: list[str] = [str(row[1]) for row in cur_loan.fetchall()]

    borrow_date_col = "borrow_date"
    borrow_index = loan_column.index(borrow_date_col) if borrow_date_col in loan_column else -1
    return_date_col = "return_date"
    return_index = loan_column.index(return_date_col) if return_date_col in loan_column else -1
    borrowed_index = loan_column.index("borrowed") if "borrowed" in loan_column else -1

    loans_filter_settings = {
        "column": "all",
        "match_mode": "contains",
        "status": "all",
        "sort_col": "duration",
        "sort_dir": "ASC",
        "from_date": "",
        "to_date": "",
    }

    search_bar_frame_loans = ctk.CTkFrame(parent, corner_radius=8, height=48)
    search_bar_frame_loans.pack(fill=tk.X, padx=10, pady=(10, 6))
    search_bar_frame_loans.columnconfigure(5, weight=1)

    sub_btn_loans = create_icon_button_fn(
        search_bar_frame_loans, text=" جستجو ", icon_name="search", font=font_bold, width=85
    )
    sub_btn_loans.grid(row=0, column=0, padx=(8, 4), pady=6)

    filter_btn_loans = create_icon_button_fn(
        search_bar_frame_loans, text=" فیلترها ", icon_name="filter", font=font_normal, width=85
    )
    filter_btn_loans.grid(row=0, column=1, padx=4, pady=6)

    loans_tree_frame = ctk.CTkFrame(parent, corner_radius=8)
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
    col_mem_display = "member_id" if "member_id" in loan_column else "member_name"
    loans_tree["displaycolumns"] = rtl_display_order(
        loan_column, ["id", col_mem_display, "book_id", "borrow_date", "return_date", "borrowed"]
    )
    loans_tree.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(4, 8), pady=4)

    add_loan_btn = create_icon_button_fn(
        search_bar_frame_loans,
        text=" ثبت امانت جدید ",
        icon_name="arrow-right-left",
        font=font_normal,
        fg_color="#2563eb",
        hover_color="#1d4ed8",
        width=125,
    )
    add_loan_btn.grid(row=0, column=3, padx=4, pady=6)

    return_loan_btn = create_icon_button_fn(
        search_bar_frame_loans,
        text=" ثبت بازگشت کتاب ",
        icon_name="check",
        font=font_bold,
        fg_color="#16a34a",
        hover_color="#15803d",
        width=135,
        command=lambda: do_return_selected_loan(),
    )
    return_loan_btn.grid(row=0, column=4, padx=4, pady=6)

    entry_search_loans = ctk.CTkEntry(
        search_bar_frame_loans,
        placeholder_text="جستجو در امانات (نام عضو، کتاب و ...)",
        font=font_normal,
        justify="right",
        height=36,
    )
    entry_search_loans.grid(row=0, column=5, sticky="ew", padx=(4, 8), pady=6)

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

        m_idx = (
            loan_column.index("member_id")
            if "member_id" in loan_column
            else (loan_column.index("member_name") if "member_name" in loan_column else -1)
        )
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

        conn = get_db_connection(db_path)
        try:
            cur = conn.cursor()
            cur.execute("UPDATE loans SET borrowed = 0 WHERE id = ?", (loan_id,))
            conn.commit()
            if notification_engine:
                notification_engine.show("ثبت بازگشت کتاب", f"کتاب «{book_title}» با موفقیت بازگردانده شد.")
            messagebox.showinfo("موفقیت", f"بازگشت کتاب «{book_title}» با موفقیت ثبت شد.", parent=root)
            search_loans()
            if on_loan_changed:
                on_loan_changed()
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
            or bool(loans_filter_settings.get("from_date"))
            or bool(loans_filter_settings.get("to_date"))
        )
        if is_custom:
            filter_btn_loans.configure(text=" فیلترها (فعال) ", fg_color="#2563eb")
        else:
            filter_btn_loans.configure(text=" فیلترها ", fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"])

    def search_loans(event=None):
        search_value = entry_search_loans.get().strip()
        loans_tree.delete(*loans_tree.get_children())

        temp_conn = get_db_connection(db_path)
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

                if selected_col == "all":
                    where_conditions.append(
                        "(COALESCE(m.username, '') "
                        + op
                        + " ? OR COALESCE(b.title, '') "
                        + op
                        + " ? OR CAST(l.id AS TEXT) "
                        + op
                        + " ?)"
                    )
                    params.extend([pattern, pattern, pattern])
                elif selected_col in ("member_id", "member_name"):
                    where_conditions.append(f"COALESCE(m.username, '') {op} ?")
                    params.append(pattern)
                elif selected_col == "book_id":
                    where_conditions.append(f"COALESCE(b.title, '') {op} ?")
                    params.append(pattern)
                elif selected_col in loan_column:
                    where_conditions.append(f"l.`{selected_col}` {op} ?")
                    params.append(pattern)

            status = loans_filter_settings.get("status", "all")
            if status == "borrowed":
                where_conditions.append("(l.borrowed = 1 OR l.borrowed = '1')")
            elif status == "returned":
                where_conditions.append("(l.borrowed = 0 OR l.borrowed = '0' OR l.borrowed IS NULL)")

            from_d = loans_filter_settings.get("from_date", "").strip()
            if from_d:
                from_greg = jalali_to_gregorian_str(from_d)
                if from_greg:
                    where_conditions.append("l.borrow_date >= ?")
                    params.append(from_greg)

            to_d = loans_filter_settings.get("to_date", "").strip()
            if to_d:
                to_greg = jalali_to_gregorian_str(to_d)
                if to_greg:
                    where_conditions.append("l.borrow_date <= ?")
                    params.append(to_greg)

            cols_select = []
            for col in loan_column:
                if col in ("member_id", "member_name"):
                    cols_select.append(f"COALESCE(m.username, CAST(l.`{col}` AS TEXT)) AS `{col}`")
                elif col == "book_id":
                    cols_select.append("COALESCE(b.title, CAST(l.book_id AS TEXT)) AS book_id")
                else:
                    cols_select.append(f"l.`{col}`")

            mem_join_col = "member_id" if "member_id" in loan_column else "member_name"
            query = (
                f"SELECT {', '.join(cols_select)} FROM loans l "
                f"LEFT JOIN members m ON (l.`{mem_join_col}` = m.id OR CAST(l.`{mem_join_col}` AS TEXT) = m.username) "
                f"LEFT JOIN books b ON (l.book_id = b.id OR l.book_id = b.title)"
            )
            if where_conditions:
                query += " WHERE " + " AND ".join(where_conditions)

            sort_col = loans_filter_settings.get("sort_col", "duration")
            sort_dir = loans_filter_settings.get("sort_dir", "ASC")
            if sort_dir not in ("ASC", "DESC"):
                sort_dir = "ASC"

            if sort_col == "duration":
                query += f" ORDER BY (julianday(l.`return_date`) - julianday(l.`borrow_date`)) {sort_dir}"
            elif sort_col in ("member_id", "member_name"):
                query += f" ORDER BY m.username {sort_dir}"
            elif sort_col == "book_id":
                query += f" ORDER BY b.title {sort_dir}"
            else:
                if sort_col not in loan_column:
                    sort_col = "id"
                query += f" ORDER BY l.`{sort_col}` {sort_dir}"

            temp_cursor.execute(query, tuple(params))
            results = temp_cursor.fetchall()

            if results:
                for row in results:
                    loans_tree.insert("", tk.END, values=format_loan_row(row))
            else:
                loans_tree.insert("", tk.END, values=("❌ نتیجه‌ای یافت نشد!",) + ("",) * (len(loan_column) - 1))

        except Exception as e:
            messagebox.showerror("خطا", f"خطا در جستجوی امانات: {str(e)}", parent=root)
        finally:
            temp_conn.close()

    sub_btn_loans.configure(command=search_loans)

    def open_loans_filter_popup():
        popup = ctk.CTkToplevel(root)
        popup.title("فیلترهای جدول امانات")
        popup.geometry("460x500")
        popup.resizable(False, False)
        if icon_path and os.path.exists(icon_path):
            try:
                popup.iconbitmap(icon_path)
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
        py = max(50, ry + (rh - 500) // 2)
        popup.geometry(f"+{px}+{py}")

        col_var = tk.StringVar(value=loans_filter_settings["column"])
        match_var = tk.StringVar(value=loans_filter_settings["match_mode"])
        status_var = tk.StringVar(value=loans_filter_settings["status"])
        sort_col_var = tk.StringVar(value=loans_filter_settings["sort_col"])
        sort_dir_var = tk.StringVar(value=loans_filter_settings["sort_dir"])

        group_col = ctk.CTkFrame(popup, corner_radius=8)
        group_col.pack(fill=tk.X, padx=15, pady=(10, 4))
        ctk.CTkLabel(group_col, text="جستجو در ستون", font=font_bold, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))
        col_frame = ctk.CTkFrame(group_col, fg_color="transparent")
        col_frame.pack(fill=tk.X, padx=6, pady=(0, 6))
        rb_all = ctk.CTkRadioButton(col_frame, text="همه ستون‌ها", variable=col_var, value="all", font=font_normal)
        rb_all.pack(side=tk.RIGHT, padx=4)
        mem_filter_col = "member_id" if "member_id" in loan_column else "member_name"
        for col in [mem_filter_col, "book_id", "id"]:
            rb = ctk.CTkRadioButton(col_frame, text=tr(col), variable=col_var, value=col, font=font_normal)
            rb.pack(side=tk.RIGHT, padx=4)

        group_mode = ctk.CTkFrame(popup, corner_radius=8)
        group_mode.pack(fill=tk.X, padx=15, pady=4)
        ctk.CTkLabel(group_mode, text="نوع تطابق جستجو", font=font_bold, anchor="e").pack(
            fill=tk.X, padx=10, pady=(6, 2)
        )
        mode_frame = ctk.CTkFrame(group_mode, fg_color="transparent")
        mode_frame.pack(fill=tk.X, padx=6, pady=(0, 6))
        rb_contains = ctk.CTkRadioButton(
            mode_frame, text="شامل عبارت", variable=match_var, value="contains", font=font_normal
        )
        rb_contains.pack(side=tk.RIGHT, padx=8)
        rb_starts = ctk.CTkRadioButton(
            mode_frame, text="شروع با عبارت", variable=match_var, value="startswith", font=font_normal
        )
        rb_starts.pack(side=tk.RIGHT, padx=8)
        rb_exact = ctk.CTkRadioButton(
            mode_frame, text="مطابقت دقیق", variable=match_var, value="exact", font=font_normal
        )
        rb_exact.pack(side=tk.RIGHT, padx=8)

        group_status = ctk.CTkFrame(popup, corner_radius=8)
        group_status.pack(fill=tk.X, padx=15, pady=4)
        ctk.CTkLabel(group_status, text="وضعیت امانت", font=font_bold, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))
        status_frame = ctk.CTkFrame(group_status, fg_color="transparent")
        status_frame.pack(fill=tk.X, padx=6, pady=(0, 6))
        rb_st_all = ctk.CTkRadioButton(
            status_frame, text="همه امانات", variable=status_var, value="all", font=font_normal
        )
        rb_st_all.pack(side=tk.RIGHT, padx=6)
        rb_st_borrowed = ctk.CTkRadioButton(
            status_frame, text="فقط در امانت", variable=status_var, value="borrowed", font=font_normal
        )
        rb_st_borrowed.pack(side=tk.RIGHT, padx=6)
        rb_st_returned = ctk.CTkRadioButton(
            status_frame, text="فقط بازگردانده شده", variable=status_var, value="returned", font=font_normal
        )
        rb_st_returned.pack(side=tk.RIGHT, padx=6)

        group_date = ctk.CTkFrame(popup, corner_radius=8)
        group_date.pack(fill=tk.X, padx=15, pady=4)
        ctk.CTkLabel(group_date, text="بازه تاریخ امانت (شمسی)", font=font_bold, anchor="e").pack(
            fill=tk.X, padx=10, pady=(6, 2)
        )
        date_frame = ctk.CTkFrame(group_date, fg_color="transparent")
        date_frame.pack(fill=tk.X, padx=6, pady=(0, 6))

        ctk.CTkLabel(date_frame, text="از:", font=font_normal).pack(side=tk.RIGHT, padx=(4, 2))
        ent_from_date = ctk.CTkEntry(
            date_frame, width=110, height=30, font=font_normal, justify="center", placeholder_text="YYYY-MM-DD"
        )
        ent_from_date.insert(0, loans_filter_settings.get("from_date", ""))
        btn_from_cal = create_date_picker_button(
            date_frame,
            entry_widget=ent_from_date,
            title="انتخاب تاریخ شروع امانت",
            icon_path=icon_path,
            width=30,
            height=30,
        )
        btn_from_cal.pack(side=tk.RIGHT, padx=2)
        ent_from_date.pack(side=tk.RIGHT, padx=(2, 10))

        ctk.CTkLabel(date_frame, text="تا:", font=font_normal).pack(side=tk.RIGHT, padx=(4, 2))
        ent_to_date = ctk.CTkEntry(
            date_frame, width=110, height=30, font=font_normal, justify="center", placeholder_text="YYYY-MM-DD"
        )
        ent_to_date.insert(0, loans_filter_settings.get("to_date", ""))
        btn_to_cal = create_date_picker_button(
            date_frame,
            entry_widget=ent_to_date,
            title="انتخاب تاریخ پایان امانت",
            icon_path=icon_path,
            width=30,
            height=30,
        )
        btn_to_cal.pack(side=tk.RIGHT, padx=2)
        ent_to_date.pack(side=tk.RIGHT, padx=2)

        group_sort = ctk.CTkFrame(popup, corner_radius=8)
        group_sort.pack(fill=tk.X, padx=15, pady=4)
        ctk.CTkLabel(group_sort, text="مرتب‌سازی نتایج", font=font_bold, anchor="e").pack(
            fill=tk.X, padx=10, pady=(6, 2)
        )
        sort_frame = ctk.CTkFrame(group_sort, fg_color="transparent")
        sort_frame.pack(fill=tk.X, padx=6, pady=(0, 6))

        ctk.CTkLabel(sort_frame, text="بر اساس:", font=font_normal).pack(side=tk.RIGHT, padx=(5, 0))
        sort_options = {
            "مدت امانت": "duration",
            "تاریخ بازگشت": "return_date",
            "تاریخ امانت": "borrow_date",
            "نام کاربر": mem_filter_col,
            "نام کتاب": "book_id",
            "شناسه": "id",
        }
        rev_sort_options = {v: k for k, v in sort_options.items()}

        sort_col_cb = ctk.CTkOptionMenu(
            sort_frame,
            width=130,
            font=font_normal,
            values=list(sort_options.keys()),
        )
        current_sort_label = rev_sort_options.get(sort_col_var.get(), "مدت امانت")
        sort_col_cb.set(current_sort_label)
        sort_col_cb.pack(side=tk.RIGHT, padx=5)

        ctk.CTkLabel(sort_frame, text="ترتیب:", font=font_normal).pack(side=tk.RIGHT, padx=(12, 0))
        sort_dir_cb = ctk.CTkOptionMenu(sort_frame, width=100, font=font_normal, values=["صعودی", "نزولی"])
        sort_dir_cb.set("صعودی" if sort_dir_var.get() == "ASC" else "نزولی")
        sort_dir_cb.pack(side=tk.RIGHT, padx=5)

        action_frame = ctk.CTkFrame(popup, fg_color="transparent")
        action_frame.pack(fill=tk.X, padx=15, pady=(10, 8))

        def apply_loans_filters():
            loans_filter_settings["column"] = col_var.get()
            loans_filter_settings["match_mode"] = match_var.get()
            loans_filter_settings["status"] = status_var.get()
            loans_filter_settings["sort_col"] = sort_options.get(sort_col_cb.get(), "duration")
            loans_filter_settings["sort_dir"] = "ASC" if sort_dir_cb.get() == "صعودی" else "DESC"
            loans_filter_settings["from_date"] = ent_from_date.get().strip()
            loans_filter_settings["to_date"] = ent_to_date.get().strip()

            update_loans_filter_indicator()
            popup.destroy()
            search_loans()

        def reset_loans_filters():
            loans_filter_settings["column"] = "all"
            loans_filter_settings["match_mode"] = "contains"
            loans_filter_settings["status"] = "all"
            loans_filter_settings["sort_col"] = "duration"
            loans_filter_settings["sort_dir"] = "ASC"
            loans_filter_settings["from_date"] = ""
            loans_filter_settings["to_date"] = ""

            update_loans_filter_indicator()
            popup.destroy()
            search_loans()

        btn_apply = create_icon_button_fn(
            action_frame,
            text=" اعمال فیلتر ",
            icon_name="check",
            font=font_bold,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            command=apply_loans_filters,
        )
        btn_apply.pack(side=tk.RIGHT, padx=4)

        btn_reset = create_icon_button_fn(
            action_frame,
            text=" تنظیم مجدد ",
            icon_name="rotate-ccw",
            font=font_normal,
            fg_color="transparent",
            hover_color=("#e2e8f0", "#1e293b"),
            command=reset_loans_filters,
        )
        btn_reset.pack(side=tk.RIGHT, padx=4)

        btn_cancel = create_icon_button_fn(
            action_frame,
            text=" انصراف ",
            icon_name="x",
            font=font_normal,
            fg_color="transparent",
            hover_color=("#e2e8f0", "#1e293b"),
            command=popup.destroy,
        )
        btn_cancel.pack(side=tk.LEFT, padx=4)

    filter_btn_loans.configure(command=open_loans_filter_popup)

    def open_add_loan_popup(initial_book_title: str = ""):
        popup = ctk.CTkToplevel(root)
        popup.title("ثبت امانت کتاب")
        popup.geometry("480x640")
        popup.resizable(False, False)
        if icon_path and os.path.exists(icon_path):
            try:
                popup.iconbitmap(icon_path)
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

        ctk.CTkLabel(popup, text="ثبت اطلاعات امانت کتاب", font=font_title).pack(pady=(12, 6))

        # 1. Member selection
        ctk.CTkLabel(popup, text="نام کاربر (عضو):", font=font_normal, anchor="e").pack(fill=tk.X, padx=25, pady=(2, 0))
        member_entry = ctk.CTkEntry(popup, font=font_normal, justify="right", height=32)
        member_entry.pack(fill=tk.X, padx=25, pady=2)

        mem_conn = get_db_connection(db_path)
        try:
            mem_cur = mem_conn.cursor()
            try:
                mem_cur.execute("SELECT username FROM members ORDER BY username ASC")
            except sqlite3.OperationalError:
                mem_cur.execute("SELECT member_id FROM members ORDER BY member_id ASC")
            members_data = [row[0] for row in mem_cur.fetchall()]
        finally:
            mem_conn.close()

        mem_listbox = tk.Listbox(
            popup,
            height=3,
            font=(font_family, 9),
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

        lbl_mem_eligibility = ctk.CTkLabel(popup, text="", font=font_small, anchor="e")
        lbl_mem_eligibility.pack(fill=tk.X, padx=25, pady=(0, 2))

        def update_member_eligibility(m_val: str):
            if not m_val:
                lbl_mem_eligibility.configure(text="")
                return
            try:
                with get_db_connection(db_path) as conn:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT id FROM members WHERE username = ? OR CAST(id AS TEXT) = ?",
                        (m_val, m_val),
                    )
                    row = cur.fetchone()
                    if row:
                        ok, msg, stats = check_member_loan_eligibility(row[0], conn_or_path=conn)
                        if not ok:
                            lbl_mem_eligibility.configure(text=f"⚠️ {msg}", text_color="#ef4444")
                        else:
                            lbl_mem_eligibility.configure(
                                text=f"✓ سهمیه امانت: {stats['active_loans']}/{stats['max_quota']}",
                                text_color="#10b981",
                            )
                    else:
                        lbl_mem_eligibility.configure(text="")
            except Exception:
                pass

        def search_member(e):
            mem_listbox.delete(0, tk.END)
            q = member_entry.get().strip().lower()
            for item in members_data:
                if q in item.lower():
                    mem_listbox.insert(tk.END, item)
            update_member_eligibility(member_entry.get().strip())

        def select_member(e):
            if mem_listbox.curselection():
                val = mem_listbox.get(mem_listbox.curselection()[0])
                member_entry.delete(0, tk.END)
                member_entry.insert(0, val)
                mem_listbox.delete(0, tk.END)
                update_member_eligibility(val)

        member_entry.bind("<KeyRelease>", search_member)
        mem_listbox.bind("<Double-Button-1>", select_member)

        # 2. Book selection
        ctk.CTkLabel(popup, text="عنوان کتاب:", font=font_normal, anchor="e").pack(fill=tk.X, padx=25, pady=(4, 0))
        book_entry = ctk.CTkEntry(popup, font=font_normal, justify="right", height=32)
        book_entry.pack(fill=tk.X, padx=25, pady=2)

        if initial_book_title:
            book_entry.insert(0, initial_book_title)
            book_entry.configure(state="readonly")
        else:
            bk_conn = get_db_connection(db_path)
            try:
                bk_cur = bk_conn.cursor()
                bk_cur.execute("""
                    SELECT title FROM books
                    WHERE title IS NOT NULL AND title != ''
                      AND id NOT IN (SELECT book_id FROM loans WHERE (borrowed = 1 OR borrowed = '1') AND book_id IS NOT NULL)
                      AND title NOT IN (SELECT book_id FROM loans WHERE (borrowed = 1 OR borrowed = '1') AND book_id IS NOT NULL)
                    ORDER BY title ASC
                """)
                books_data = [row[0] for row in bk_cur.fetchall() if row[0]]
            finally:
                bk_conn.close()

            bk_listbox = tk.Listbox(
                popup,
                height=3,
                font=(font_family, 9),
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
        cur_today = get_today_jalali()
        c_days_10 = cur_today + jdatetime.timedelta(days=10)
        c_days_20 = cur_today + jdatetime.timedelta(days=20)
        c_days_30 = cur_today + jdatetime.timedelta(days=30)

        ctk.CTkLabel(popup, text="تاریخ امانت کتاب (YYYY-MM-DD):", font=font_normal, anchor="e").pack(
            fill=tk.X, padx=25, pady=(4, 0)
        )
        row_borrow = ctk.CTkFrame(popup, fg_color="transparent")
        row_borrow.pack(fill=tk.X, padx=25, pady=2)

        borrow_entry = ctk.CTkEntry(row_borrow, font=font_normal, justify="right", height=32)
        btn_cal_borrow = create_date_picker_button(
            row_borrow,
            entry_widget=borrow_entry,
            title="انتخاب تاریخ امانت (تقویم شمسی)",
            icon_path=icon_path,
        )
        btn_cal_borrow.pack(side=tk.LEFT, padx=(0, 4))
        borrow_entry.pack(side=tk.RIGHT, fill=tk.X, expand=True)

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
            chk_f,
            text="ثبت خودکار تاریخ امروز",
            variable=var_auto_date,
            command=toggle_borrow_date,
            font=font_normal,
        ).pack(side=tk.RIGHT)

        # 4. Return Date
        ctk.CTkLabel(popup, text="تاریخ بازگشت کتاب (YYYY-MM-DD):", font=font_normal, anchor="e").pack(
            fill=tk.X, padx=25, pady=(4, 0)
        )
        row_return = ctk.CTkFrame(popup, fg_color="transparent")
        row_return.pack(fill=tk.X, padx=25, pady=2)

        return_entry = ctk.CTkEntry(row_return, font=font_normal, justify="right", height=32)
        btn_cal_return = create_date_picker_button(
            row_return,
            entry_widget=return_entry,
            title="انتخاب تاریخ بازگشت (تقویم شمسی)",
            icon_path=icon_path,
            on_select=lambda d: selected_days.set(""),
        )
        btn_cal_return.pack(side=tk.LEFT, padx=(0, 4))
        return_entry.pack(side=tk.RIGHT, fill=tk.X, expand=True)

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
            days_frame,
            text="10 روز",
            variable=selected_days,
            value="option1",
            command=on_select_days,
            font=font_normal,
        )
        rb2 = ctk.CTkRadioButton(
            days_frame,
            text="20 روز",
            variable=selected_days,
            value="option2",
            command=on_select_days,
            font=font_normal,
        )
        rb3 = ctk.CTkRadioButton(
            days_frame,
            text="30 روز",
            variable=selected_days,
            value="option3",
            command=on_select_days,
            font=font_normal,
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

            j_borrow = parse_jalali_date(borrow_shamsi)
            if not j_borrow:
                messagebox.showerror("خطا", "فرمت تاریخ امانت وارد شده صحیح نیست!\nمثال: 1403-06-20", parent=popup)
                return
            borrow_gregorian = j_borrow.togregorian().strftime("%Y-%m-%d")

            j_return = parse_jalali_date(return_shamsi)
            if not j_return:
                messagebox.showerror("خطا", "فرمت تاریخ بازگشت وارد شده صحیح نیست!\nمثال: 1403-06-30", parent=popup)
                return
            return_gregorian = j_return.togregorian().strftime("%Y-%m-%d")

            if return_gregorian < borrow_gregorian:
                messagebox.showerror("خطا", "تاریخ بازگشت نمی‌تواند پیش از تاریخ امانت باشد!", parent=popup)
                return

            try:
                with get_db_connection(db_path) as conn:
                    ins_cur = conn.cursor()

                    # 1. Resolve member_id
                    try:
                        ins_cur.execute("SELECT id, username FROM members WHERE username = ?", (m_name,))
                    except sqlite3.OperationalError:
                        ins_cur.execute("SELECT id, member_id FROM members WHERE member_id = ?", (m_name,))
                    m_row = ins_cur.fetchone()
                    if not m_row and m_name.isdigit():
                        try:
                            ins_cur.execute("SELECT id, username FROM members WHERE id = ?", (int(m_name),))
                        except sqlite3.OperationalError:
                            ins_cur.execute("SELECT id, member_id FROM members WHERE id = ?", (int(m_name),))
                        m_row = ins_cur.fetchone()

                    if not m_row:
                        messagebox.showerror(
                            "خطا",
                            f"عضوی با نام «{m_name}» در فهرست اعضای کتابخانه یافت نشد.\nلطفاً ابتدا از تب «اعضای کتابخانه» او را ثبت کنید.",
                            parent=popup,
                        )
                        member_entry.focus()
                        return

                    actual_member_id = m_row[0]
                    actual_member_name = m_row[1]

                    # 2. Check book_id is actual ID from books table
                    actual_book_id = None
                    actual_book_title = b_title

                    ins_cur.execute("SELECT id, title FROM books WHERE title = ?", (b_title,))
                    b_row = ins_cur.fetchone()
                    if b_row:
                        actual_book_id = b_row[0]
                        actual_book_title = b_row[1]
                    elif b_title.isdigit():
                        ins_cur.execute("SELECT id, title FROM books WHERE id = ?", (int(b_title),))
                        b_row = ins_cur.fetchone()
                        if b_row:
                            actual_book_id = b_row[0]
                            actual_book_title = b_row[1]

                    if actual_book_id is None:
                        messagebox.showerror(
                            "خطا",
                            f"کتابی با عنوان یا شناسه «{b_title}» در پایگاه داده کتاب‌ها یافت نشد.",
                            parent=popup,
                        )
                        book_entry.focus()
                        return

                    # 3. Check member loan eligibility (quota & overdue check)
                    is_eligible, reason_msg, stats = check_member_loan_eligibility(
                        actual_member_id, conn_or_path=conn, current_date=borrow_gregorian
                    )
                    if not is_eligible:
                        messagebox.showerror(
                            "عدم امکان امانت کتاب",
                            f"کاربر «{actual_member_name}» شرایط دریافت امانت جدید را ندارد:\n\n{reason_msg}",
                            parent=popup,
                        )
                        return

                    # 4. Check if book is already borrowed
                    ins_cur.execute(
                        "SELECT COUNT(*) FROM loans WHERE (book_id = ? OR book_id = ?) AND (borrowed = 1 OR borrowed = '1')",
                        (actual_book_id, str(actual_book_id)),
                    )
                    if ins_cur.fetchone()[0] > 0:
                        messagebox.showwarning(
                            "امانت کتاب",
                            f"کتاب «{actual_book_title}» در حال حاضر در امانت است و امکان امانت مجدد آن وجود ندارد.",
                            parent=popup,
                        )
                        return

                    # 5. Insert loan
                    ins_cur.execute(
                        "INSERT INTO loans (member_id, book_id, return_date, borrow_date, borrowed) VALUES (?, ?, ?, ?, 1)",
                        (actual_member_id, actual_book_id, return_gregorian, borrow_gregorian),
                    )
                    conn.commit()

                if notification_engine:
                    notification_engine.show(
                        "ثبت موفق امانت", f"کتاب «{actual_book_title}» با موفقیت برای {actual_member_name} ثبت شد."
                    )

                messagebox.showinfo("موفقیت", "اطلاعات امانت با موفقیت ذخیره شد!", parent=popup)
                popup.destroy()
                search_loans()
                if on_loan_changed:
                    on_loan_changed()
            except sqlite3.Error as e:
                messagebox.showerror("خطا در پایگاه داده", f"خطا در ذخیره اطلاعات: {e}", parent=popup)

        btn_f = ctk.CTkFrame(popup, fg_color="transparent")
        btn_f.pack(pady=16, padx=25, fill=tk.X)
        btn_save = create_icon_button_fn(
            btn_f,
            text=" ثبت امانت ",
            icon_name="arrow-right-left",
            font=font_bold,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            width=120,
            command=do_insert_loan,
        )
        btn_save.pack(side=tk.RIGHT, padx=5)
        btn_cancel = create_icon_button_fn(
            btn_f,
            text=" انصراف ",
            icon_name="x",
            font=font_normal,
            fg_color="transparent",
            hover_color=("#e2e8f0", "#1e293b"),
            width=90,
            command=popup.destroy,
        )
        btn_cancel.pack(side=tk.LEFT, padx=5)

    add_loan_btn.configure(command=open_add_loan_popup)

    def open_extend_loan_popup():
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

        m_idx = (
            loan_column.index("member_id")
            if "member_id" in loan_column
            else (loan_column.index("member_name") if "member_name" in loan_column else -1)
        )
        member_name = values[m_idx] if m_idx != -1 and m_idx < len(values) else ""

        r_idx = loan_column.index("return_date") if "return_date" in loan_column else -1
        cur_return_shamsi = values[r_idx] if r_idx != -1 and r_idx < len(values) else ""

        borrowed_idx = loan_column.index("borrowed") if "borrowed" in loan_column else -1
        current_status = values[borrowed_idx] if borrowed_idx != -1 and borrowed_idx < len(values) else ""

        if current_status == "بازگردانده شده":
            messagebox.showinfo("اطلاع", "این کتاب قبلاً بازگردانده شده است و امکان تمدید ندارد.", parent=root)
            return

        popup = ctk.CTkToplevel(root)
        popup.title("تمدید و تغییر تاریخ بازگشت امانت")
        popup.geometry("420x360")
        popup.resizable(False, False)
        if icon_path and os.path.exists(icon_path):
            try:
                popup.iconbitmap(icon_path)
            except Exception:
                pass

        popup.transient(root)
        popup.grab_set()

        root.update_idletasks()
        rx = root.winfo_rootx()
        ry = root.winfo_rooty()
        rw = root.winfo_width()
        rh = root.winfo_height()
        popup.geometry(f"+{max(50, rx + (rw - 420) // 2)}+{max(50, ry + (rh - 360) // 2)}")

        ctk.CTkLabel(popup, text="تمدید یا تغییر تاریخ بازگشت", font=font_title).pack(pady=(14, 8))

        info_card = ctk.CTkFrame(popup, corner_radius=8, fg_color=("#f1f5f9", "#1e293b"))
        info_card.pack(fill=tk.X, padx=20, pady=(0, 10))

        ctk.CTkLabel(
            info_card,
            text=f"کتاب: {book_title}   |   عضو: {member_name}",
            font=font_normal,
            anchor="e",
        ).pack(fill=tk.X, padx=10, pady=(6, 2))

        ctk.CTkLabel(
            info_card,
            text=f"تاریخ بازگشت فعلی: {cur_return_shamsi or 'نامشخص'}",
            font=font_small,
            text_color=("#64748b", "#94a3b8"),
            anchor="e",
        ).pack(fill=tk.X, padx=10, pady=(0, 6))

        ctk.CTkLabel(popup, text="تاریخ بازگشت جدید (YYYY-MM-DD):", font=font_normal, anchor="e").pack(
            fill=tk.X, padx=20, pady=(4, 2)
        )

        row_new_date = ctk.CTkFrame(popup, fg_color="transparent")
        row_new_date.pack(fill=tk.X, padx=20, pady=2)

        cur_jdate = parse_jalali_date(cur_return_shamsi) or get_today_jalali()
        default_new_date = format_jalali_date(cur_jdate + jdatetime.timedelta(days=7))

        ent_new_date = ctk.CTkEntry(row_new_date, font=font_normal, justify="right", height=32)
        ent_new_date.insert(0, default_new_date)

        btn_cal = create_date_picker_button(
            row_new_date,
            entry_widget=ent_new_date,
            title="انتخاب تاریخ بازگشت جدید (تقویم شمسی)",
            icon_path=icon_path,
        )
        btn_cal.pack(side=tk.LEFT, padx=(0, 4))
        ent_new_date.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        quick_frame = ctk.CTkFrame(popup, fg_color="transparent")
        quick_frame.pack(fill=tk.X, padx=20, pady=6)

        def _add_days(d_cnt: int):
            base = parse_jalali_date(ent_new_date.get()) or get_today_jalali()
            new_d = base + jdatetime.timedelta(days=d_cnt)
            ent_new_date.delete(0, tk.END)
            ent_new_date.insert(0, format_jalali_date(new_d))

        btn_q7 = ctk.CTkButton(
            quick_frame,
            text="+۷ روز",
            font=font_small,
            width=65,
            height=26,
            fg_color=("#cbd5e1", "#334155"),
            text_color=("#0f172a", "#f8fafc"),
            command=lambda: _add_days(7),
        )
        btn_q7.pack(side=tk.RIGHT, padx=2)

        btn_q14 = ctk.CTkButton(
            quick_frame,
            text="+۱۴ روز",
            font=font_small,
            width=65,
            height=26,
            fg_color=("#cbd5e1", "#334155"),
            text_color=("#0f172a", "#f8fafc"),
            command=lambda: _add_days(14),
        )
        btn_q14.pack(side=tk.RIGHT, padx=2)

        btn_q30 = ctk.CTkButton(
            quick_frame,
            text="+۳۰ روز",
            font=font_small,
            width=65,
            height=26,
            fg_color=("#cbd5e1", "#334155"),
            text_color=("#0f172a", "#f8fafc"),
            command=lambda: _add_days(30),
        )
        btn_q30.pack(side=tk.RIGHT, padx=2)

        btn_save = create_icon_button_fn(
            popup,
            text=" ثبت تمدید امانت ",
            icon_name="check",
            font=font_bold,
            fg_color="#16a34a",
            hover_color="#15803d",
            height=34,
        )
        btn_save.pack(fill=tk.X, padx=20, pady=(12, 6))

        def _do_save_extend():
            val = ent_new_date.get().strip()
            parsed = parse_jalali_date(val)
            if not parsed:
                messagebox.showerror("خطا", "فرمت تاریخ بازگشت معتبر نیست!\nمثال: 1403-07-15", parent=popup)
                return

            greg_str = parsed.togregorian().strftime("%Y-%m-%d")
            conn = get_db_connection(db_path)
            try:
                cur = conn.cursor()
                cur.execute("UPDATE loans SET return_date = ? WHERE id = ?", (greg_str, loan_id))
                conn.commit()
                popup.destroy()
                if notification_engine:
                    notification_engine.show(
                        "تمدید امانت",
                        f"مهلت بازگشت کتاب «{book_title}» تا تاریخ {format_jalali_date(parsed)} تمدید شد.",
                    )
                messagebox.showinfo(
                    "موفقیت",
                    f"تاریخ بازگشت کتاب با موفقیت به {format_jalali_date(parsed)} تغییر یافت.",
                    parent=root,
                )
                search_loans()
            except sqlite3.Error as ex:
                messagebox.showerror("خطا", f"خطا در ثبت تمدید: {ex}", parent=popup)
            finally:
                conn.close()

        btn_save.configure(command=_do_save_extend)

    loans_menu = tk.Menu(root, tearoff=0)
    loans_menu.add_command(label="تمدید یا ویرایش تاریخ بازگشت", command=open_extend_loan_popup)
    loans_menu.add_command(label="ثبت بازگشت کتاب", command=do_return_selected_loan)
    loans_menu.add_separator()
    loans_menu.add_command(label="حذف رکورد امانت", command=lambda: loans_tree.event_generate("<Delete>"))

    def show_loans_context_menu(event):
        row_id = loans_tree.identify_row(event.y)
        if row_id:
            loans_tree.selection_set(row_id)
            loans_menu.post(event.x_root, event.y_root)

    loans_tree.bind("<Button-3>", show_loans_context_menu)
    loans_tree.bind("<Double-Button-1>", lambda event: do_return_selected_loan())

    loans_search_after_id = [None]

    def on_loans_key_release(event):
        if loans_search_after_id[0] is not None:
            root.after_cancel(loans_search_after_id[0])
        loans_search_after_id[0] = root.after(200, search_loans)

    entry_search_loans.bind("<KeyRelease>", on_loans_key_release)
    entry_search_loans.bind("<Return>", search_loans)

    def handle_deleted():
        search_loans()
        if on_loan_changed:
            on_loan_changed()

    bind_table_delete_fn(
        loans_tree,
        loans_table_name,
        id_col_index=loan_column.index("id") if "id" in loan_column else 0,
        on_deleted=handle_deleted,
    )

    return {
        "search_loans": search_loans,
        "refresh_loans_table": search_loans,
        "open_add_loan_popup": open_add_loan_popup,
        "open_extend_loan_popup": open_extend_loan_popup,
        "do_return_selected_loan": do_return_selected_loan,
        "tree": loans_tree,
    }
