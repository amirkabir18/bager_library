import os
import sqlite3
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

import customtkinter as ctk

from database import get_db_connection, tr
from services.dewey_service import is_valid_dewey
from ui.common import export_tree_to_csv_ui


def build_books_tab(
    parent: Any,
    root: Any,
    fonts: dict[str, Any],
    get_icon_fn: Callable[..., Any],
    create_icon_button_fn: Callable[..., Any],
    bind_table_delete_fn: Callable[..., Any],
    db_path: str,
    book_service: Any,
    is_ai_available_fn: Callable[[], bool],
    is_internet_access_enabled_fn: Callable[[str], bool],
    on_borrow_book: Callable[[str], None] | None = None,
    icon_path: str = "",
) -> dict[str, Any]:
    font_title = fonts.get("title")
    font_normal = fonts.get("normal")
    font_bold = fonts.get("bold")
    font_small = fonts.get("small")

    tabel_name = "books"
    with get_db_connection(db_path) as _init_conn:
        _init_cur = _init_conn.cursor()
        _init_cur.execute(f'PRAGMA table_info("{tabel_name}")')
        columns: list[str] = [str(row[1]) for row in _init_cur.fetchall()]

    filter_settings = {
        "column": "all",
        "match_mode": "contains",
        "availability": "all",
        "dewey_class": "all",
        "sort_col": "id",
        "sort_dir": "ASC",
    }

    search_bar_frame = ctk.CTkFrame(parent, corner_radius=8, height=48)
    search_bar_frame.pack(fill=tk.X, padx=10, pady=(10, 6))
    search_bar_frame.columnconfigure(6, weight=1)

    sub_btn = create_icon_button_fn(search_bar_frame, text=" جستجو ", icon_name="search", font=font_bold, width=80)
    sub_btn.grid(row=0, column=0, padx=(8, 4), pady=6)

    filter_btn = create_icon_button_fn(
        search_bar_frame, text=" فیلترها ", icon_name="filter", font=font_normal, width=85
    )
    filter_btn.grid(row=0, column=1, padx=4, pady=6)

    tree_frame = ctk.CTkFrame(parent, corner_radius=8)
    tree_frame.pack(padx=10, pady=(0, 10), fill=tk.BOTH, expand=True)

    scrollbar = ctk.CTkScrollbar(tree_frame)
    scrollbar.pack(side=tk.LEFT, fill=tk.Y, padx=(4, 0), pady=4)

    tree = ttk.Treeview(tree_frame, yscrollcommand=scrollbar.set, columns=columns, show="headings", height=15)
    scrollbar.configure(command=tree.yview)
    for col in columns:
        tree.heading(col, text=tr(col), anchor=tk.CENTER)
        tree.column(col, anchor=tk.CENTER)

    visible_book_cols = [c for c in ["id", "title", "author", "dewey_code", "dewey_subject", "isbn"] if c in columns]
    tree["displaycolumns"] = list(reversed(visible_book_cols))

    if "id" in columns:
        tree.column("id", width=55, minwidth=40, anchor=tk.CENTER)
    if "title" in columns:
        tree.column("title", width=230, minwidth=130, anchor=tk.E)
    if "author" in columns:
        tree.column("author", width=140, minwidth=90, anchor=tk.E)
    if "dewey_code" in columns:
        tree.column("dewey_code", width=85, minwidth=65, anchor=tk.CENTER)
    if "dewey_subject" in columns:
        tree.column("dewey_subject", width=140, minwidth=90, anchor=tk.E)
    if "isbn" in columns:
        tree.column("isbn", width=125, minwidth=85, anchor=tk.CENTER)

    tree.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(4, 8), pady=4)

    reclassify_all_btn = create_icon_button_fn(
        search_bar_frame,
        text=" رده‌بندی دسته‌ای ",
        icon_name="layers",
        font=font_normal,
        width=115,
    )
    reclassify_all_btn.grid(row=0, column=3, padx=4, pady=6)

    edit_book_btn = create_icon_button_fn(
        search_bar_frame,
        text=" ویرایش کتاب ",
        icon_name="pencil",
        font=font_normal,
        width=95,
    )
    edit_book_btn.grid(row=0, column=4, padx=4, pady=6)

    add_book_btn = create_icon_button_fn(
        search_bar_frame,
        text=" افزودن کتاب ",
        icon_name="book-plus",
        font=font_normal,
        fg_color="#16a34a",
        hover_color="#15803d",
        width=105,
    )
    add_book_btn.grid(row=0, column=5, padx=4, pady=6)

    entry_serch = ctk.CTkEntry(
        search_bar_frame,
        placeholder_text="جستجو در بین کتاب‌ها (عنوان، نویسنده، شابک، کد دیویی و ...)",
        font=font_normal,
        justify="right",
        height=36,
    )
    entry_serch.grid(row=0, column=6, sticky="ew", padx=(4, 8), pady=6)

    def update_filter_button_indicator():
        is_custom = (
            filter_settings["column"] != "all"
            or filter_settings["match_mode"] != "contains"
            or filter_settings["availability"] != "all"
            or filter_settings.get("dewey_class", "all") != "all"
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

        temp_conn = get_db_connection(db_path)
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
                    searchable_cols = [
                        c for c in columns if c in ["title", "author", "isbn", "dewey_code", "dewey_subject", "id"]
                    ]
                    sub_conds = [f"{col} {op} ?" for col in searchable_cols]
                    where_conditions.append("(" + " OR ".join(sub_conds) + ")")
                    params.extend([pattern] * len(searchable_cols))
                elif selected_col in columns:
                    where_conditions.append(f"{selected_col} {op} ?")
                    params.append(pattern)

            dewey_cls = filter_settings.get("dewey_class", "all")
            if dewey_cls != "all":
                cls_digit = str(dewey_cls).strip()[:1]
                where_conditions.append("(SUBSTR(COALESCE(dewey_code, ''), 1, 1) = ?)")
                params.append(cls_digit)

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

            if sort_col in ("dewey_code",):
                query += f" ORDER BY {sort_col} COLLATE dewey {sort_dir}"
            else:
                query += f" ORDER BY {sort_col} {sort_dir}"

            temp_cursor.execute(query, tuple(params))
            results = temp_cursor.fetchall()

            if results:
                for row in results:
                    tree.insert("", "end", values=tuple(row))
            else:
                tree.insert("", "end", values=("❌ نتیجه‌ای یافت نشد!",) + ("",) * (len(columns) - 1))

        except Exception as e:
            messagebox.showerror("خطا", f"خطا در جستجو: {str(e)}", parent=root)
        finally:
            temp_conn.close()

    sub_btn.configure(command=search)

    def open_filter_popup():
        popup = ctk.CTkToplevel(root)
        popup.title("فیلترهای پیشرفته جستجو")
        popup.geometry("500x570")
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
        px = max(50, rx + (rw - 500) // 2)
        py = max(50, ry + (rh - 570) // 2)
        popup.geometry(f"+{px}+{py}")

        col_var = tk.StringVar(value=filter_settings["column"])
        match_var = tk.StringVar(value=filter_settings["match_mode"])
        avail_var = tk.StringVar(value=filter_settings["availability"])
        dewey_cls_var = tk.StringVar(value=filter_settings.get("dewey_class", "all"))
        sort_col_var = tk.StringVar(value=filter_settings["sort_col"])
        sort_dir_var = tk.StringVar(value=filter_settings["sort_dir"])

        group_col = ctk.CTkFrame(popup, corner_radius=8)
        group_col.pack(fill=tk.X, padx=15, pady=(10, 4))
        ctk.CTkLabel(group_col, text="جستجو در ستون", font=font_bold, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))

        col_frame_1 = ctk.CTkFrame(group_col, fg_color="transparent")
        col_frame_1.pack(fill=tk.X, padx=6, pady=(0, 2))
        row1_cols = [("همه ستون‌ها", "all"), ("عنوان کتاب", "title"), ("نویسنده", "author"), ("شابک", "isbn")]
        for text_fa, val in row1_cols:
            if val == "all" or val in columns:
                rb = ctk.CTkRadioButton(col_frame_1, text=text_fa, variable=col_var, value=val, font=font_normal)
                rb.pack(side=tk.RIGHT, padx=6)

        col_frame_2 = ctk.CTkFrame(group_col, fg_color="transparent")
        col_frame_2.pack(fill=tk.X, padx=6, pady=(0, 6))
        row2_cols = [("کد دیویی", "dewey_code"), ("موضوع دیویی", "dewey_subject"), ("شناسه", "id")]
        for text_fa, val in row2_cols:
            if val in columns:
                rb = ctk.CTkRadioButton(col_frame_2, text=text_fa, variable=col_var, value=val, font=font_normal)
                rb.pack(side=tk.RIGHT, padx=6)

        group_dewey = ctk.CTkFrame(popup, corner_radius=8)
        group_dewey.pack(fill=tk.X, padx=15, pady=4)
        ctk.CTkLabel(group_dewey, text="فیلتر موضوعی دیویی", font=font_bold, anchor="e").pack(
            fill=tk.X, padx=10, pady=(6, 2)
        )
        dewey_opts = [
            ("همه موضوعات", "all"),
            ("۰۰۰ - کلیات و علوم کامپیوتر", "000"),
            ("۱۰۰ - فلسفه و روان‌شناسی", "100"),
            ("۲۰۰ - دین و الهیات", "200"),
            ("۳۰۰ - علوم اجتماعی", "300"),
            ("۴۰۰ - زبان و زبان‌شناسی", "400"),
            ("۵۰۰ - علوم محض و طبیعی", "500"),
            ("۶۰۰ - فناوری و مهندسی", "600"),
            ("۷۰۰ - هنر و سرگرمی", "700"),
            ("۸۰۰ - ادبیات", "800"),
            ("۹۰۰ - تاریخ و جغرافیا", "900"),
        ]
        dewey_cb = ctk.CTkOptionMenu(
            group_dewey,
            font=font_normal,
            values=[opt[0] for opt in dewey_opts],
        )
        cur_d_val = next((opt[0] for opt in dewey_opts if opt[1] == dewey_cls_var.get()), "همه موضوعات")
        dewey_cb.set(cur_d_val)
        dewey_cb.pack(fill=tk.X, padx=10, pady=(0, 6))

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

        group_avail = ctk.CTkFrame(popup, corner_radius=8)
        group_avail.pack(fill=tk.X, padx=15, pady=4)
        ctk.CTkLabel(group_avail, text="وضعیت امانت کتاب", font=font_bold, anchor="e").pack(
            fill=tk.X, padx=10, pady=(6, 2)
        )
        avail_frame = ctk.CTkFrame(group_avail, fg_color="transparent")
        avail_frame.pack(fill=tk.X, padx=6, pady=(0, 6))
        rb_av_all = ctk.CTkRadioButton(
            avail_frame, text="همه کتاب‌ها", variable=avail_var, value="all", font=font_normal
        )
        rb_av_all.pack(side=tk.RIGHT, padx=6)
        rb_av_avail = ctk.CTkRadioButton(
            avail_frame, text="فقط موجود", variable=avail_var, value="available", font=font_normal
        )
        rb_av_avail.pack(side=tk.RIGHT, padx=6)
        rb_av_borrowed = ctk.CTkRadioButton(
            avail_frame, text="فقط در امانت", variable=avail_var, value="borrowed", font=font_normal
        )
        rb_av_borrowed.pack(side=tk.RIGHT, padx=6)

        group_sort = ctk.CTkFrame(popup, corner_radius=8)
        group_sort.pack(fill=tk.X, padx=15, pady=4)
        ctk.CTkLabel(group_sort, text="مرتب‌سازی نتایج", font=font_bold, anchor="e").pack(
            fill=tk.X, padx=10, pady=(6, 2)
        )
        sort_frame = ctk.CTkFrame(group_sort, fg_color="transparent")
        sort_frame.pack(fill=tk.X, padx=6, pady=(0, 6))

        ctk.CTkLabel(sort_frame, text="بر اساس:", font=font_normal).pack(side=tk.RIGHT, padx=(5, 0))
        sort_cols_available = [c for c in ["title", "author", "dewey_code", "id"] if c in columns]
        sort_col_cb = ctk.CTkOptionMenu(
            sort_frame,
            width=135,
            font=font_normal,
            values=[tr(c) for c in sort_cols_available],
        )
        sort_col_cb.set(tr(sort_col_var.get()))
        sort_col_cb.pack(side=tk.RIGHT, padx=5)

        ctk.CTkLabel(sort_frame, text="ترتیب:", font=font_normal).pack(side=tk.RIGHT, padx=(12, 0))
        sort_dir_cb = ctk.CTkOptionMenu(sort_frame, width=105, font=font_normal, values=["صعودی", "نزولی"])
        sort_dir_cb.set("صعودی" if sort_dir_var.get() == "ASC" else "نزولی")
        sort_dir_cb.pack(side=tk.RIGHT, padx=5)

        action_frame = ctk.CTkFrame(popup, fg_color="transparent")
        action_frame.pack(fill=tk.X, padx=15, pady=(12, 8))

        def apply_filters():
            filter_settings["column"] = col_var.get()
            filter_settings["match_mode"] = match_var.get()
            filter_settings["availability"] = avail_var.get()

            disp_dewey = dewey_cb.get()
            dewey_map = {opt[0]: opt[1] for opt in dewey_opts}
            filter_settings["dewey_class"] = dewey_map.get(disp_dewey, "all")

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
            filter_settings["dewey_class"] = "all"
            filter_settings["sort_col"] = "id"
            filter_settings["sort_dir"] = "ASC"

            update_filter_button_indicator()
            popup.destroy()
            search()

        btn_apply = create_icon_button_fn(
            action_frame,
            text=" اعمال فیلتر ",
            icon_name="check",
            font=font_bold,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            command=apply_filters,
        )
        btn_apply.pack(side=tk.RIGHT, padx=4)

        btn_reset = create_icon_button_fn(
            action_frame,
            text=" تنظیم مجدد ",
            icon_name="rotate-ccw",
            font=font_normal,
            fg_color="transparent",
            hover_color=("#e2e8f0", "#1e293b"),
            command=reset_filters,
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

    filter_btn.configure(command=open_filter_popup)

    def open_add_book_popup():
        popup = ctk.CTkToplevel(root)
        popup.title("ثبت کتاب جدید و رده‌بندی دیویی")
        popup.geometry("500x485")
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
        px = max(50, rx + (rw - 500) // 2)
        py = max(50, ry + (rh - 485) // 2)
        popup.geometry(f"+{px}+{py}")

        ctk.CTkLabel(popup, text="ثبت کتاب جدید و رده‌بندی دیویی", font=font_title).pack(pady=(12, 8))

        form_f = ctk.CTkFrame(popup, fg_color="transparent")
        form_f.pack(fill=tk.BOTH, expand=True, padx=20, pady=0)

        # ISBN row
        row_isbn = ctk.CTkFrame(form_f, fg_color="transparent")
        row_isbn.pack(fill=tk.X, pady=4)
        ctk.CTkLabel(row_isbn, text="شابک:", font=font_normal, width=105, anchor="e").pack(side=tk.RIGHT, padx=(5, 0))
        btn_lookup_isbn = create_icon_button_fn(
            row_isbn,
            text=" استعلام آنلاین ",
            icon_name="search",
            font=font_small,
            width=105,
            height=32,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
        )
        btn_lookup_isbn.pack(side=tk.LEFT, padx=(5, 0))
        ent_isbn = ctk.CTkEntry(
            row_isbn, font=font_normal, justify="right", height=32, placeholder_text="شابک ۱۰ یا ۱۳ رقمی"
        )
        ent_isbn.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        # Title row
        row_title = ctk.CTkFrame(form_f, fg_color="transparent")
        row_title.pack(fill=tk.X, pady=4)
        ctk.CTkLabel(row_title, text="عنوان کتاب:", font=font_bold, width=105, anchor="e").pack(
            side=tk.RIGHT, padx=(5, 0)
        )
        ent_title = ctk.CTkEntry(
            row_title, font=font_normal, justify="right", height=32, placeholder_text="عنوان کتاب (الزامی)"
        )
        ent_title.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        # Author row
        row_author = ctk.CTkFrame(form_f, fg_color="transparent")
        row_author.pack(fill=tk.X, pady=4)
        ctk.CTkLabel(row_author, text="نویسنده:", font=font_normal, width=105, anchor="e").pack(
            side=tk.RIGHT, padx=(5, 0)
        )
        ent_author = ctk.CTkEntry(
            row_author, font=font_normal, justify="right", height=32, placeholder_text="نام نویسنده / پدیدآورنده"
        )
        ent_author.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        # AI row
        row_ai = ctk.CTkFrame(form_f, fg_color="transparent")
        btn_auto_ddc = create_icon_button_fn(
            row_ai,
            text=" پیشنهاد هوشمند رده دیویی با هوش مصنوعی ",
            icon_name="zap",
            font=font_normal,
            height=30,
            fg_color="#0284c7",
            hover_color="#0369a1",
        )
        btn_auto_ddc.pack(fill=tk.X)

        # Dewey Code row
        row_dewey = ctk.CTkFrame(form_f, fg_color="transparent")
        row_dewey.pack(fill=tk.X, pady=4)
        ctk.CTkLabel(row_dewey, text="کد دیویی:", font=font_normal, width=105, anchor="e").pack(
            side=tk.RIGHT, padx=(5, 0)
        )
        ent_dewey = ctk.CTkEntry(
            row_dewey, font=font_normal, justify="center", height=32, placeholder_text="مانند: 510 یا 641.5"
        )
        ent_dewey.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        # Dewey Subject row
        row_subject = ctk.CTkFrame(form_f, fg_color="transparent")
        row_subject.pack(fill=tk.X, pady=4)
        ctk.CTkLabel(row_subject, text="موضوع دیویی:", font=font_normal, width=105, anchor="e").pack(
            side=tk.RIGHT, padx=(5, 0)
        )
        ent_subject = ctk.CTkEntry(
            row_subject,
            font=font_normal,
            justify="right",
            height=32,
            placeholder_text="موضوع رده (مانند ریاضیات، فیزیک)",
        )
        ent_subject.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        shelf_card = ctk.CTkFrame(form_f, corner_radius=6, fg_color=("#f1f5f9", "#1e293b"))
        shelf_card.pack(fill=tk.X, pady=(5, 3), padx=2)
        shelf_lbl = ctk.CTkLabel(
            shelf_card,
            text="محل قفسه: تعیین نشده",
            font=font_small,
            text_color=("#475569", "#94a3b8"),
            anchor="e",
        )
        shelf_lbl.pack(fill=tk.X, padx=10, pady=5)

        status_lbl = ctk.CTkLabel(form_f, text="", font=font_small, anchor="center")
        status_lbl.pack(fill=tk.X, pady=(1, 3))

        classification_meta = {"source": None, "confidence": 0.0}

        if is_ai_available_fn():
            row_ai.pack(fill=tk.X, pady=(3, 5), before=row_dewey)

        def update_shelf_preview(*args):
            code = ent_dewey.get().strip()
            if code and is_valid_dewey(code):
                loc = book_service.dewey_service.get_shelf_location(code)
                shelf_lbl.configure(text=f"📍 {loc.get('shelf_label')}")
            else:
                shelf_lbl.configure(text="محل قفسه: تعیین نشده")

        ent_dewey.bind("<KeyRelease>", update_shelf_preview)

        def on_user_dewey_edit(event):
            classification_meta["source"] = "manual"
            classification_meta["confidence"] = 1.0

        ent_dewey.bind("<Key>", on_user_dewey_edit)
        ent_subject.bind("<Key>", on_user_dewey_edit)

        def do_isbn_lookup():
            if not is_internet_access_enabled_fn(db_path):
                messagebox.showwarning(
                    "دسترسی به اینترنت", "دسترسی به اینترنت در تنظیمات برنامه غیرفعال شده است.", parent=popup
                )
                return
            raw_isbn = ent_isbn.get().strip()
            if not raw_isbn:
                messagebox.showwarning("شابک", "لطفاً ابتدا مقدار شابک را وارد نمایید!", parent=popup)
                ent_isbn.focus()
                return
            status_lbl.configure(text="در حال استعلام اطلاعات شابک...", text_color="#3b82f6")
            popup.update()

            def _fetch_thread():
                try:
                    res = book_service.lookup_isbn_and_classify(raw_isbn)

                    def _apply():
                        if res.get("title"):
                            ent_title.delete(0, tk.END)
                            ent_title.insert(0, res["title"])
                        if res.get("author"):
                            ent_author.delete(0, tk.END)
                            ent_author.insert(0, res["author"])
                        if res.get("dewey_code"):
                            ent_dewey.delete(0, tk.END)
                            ent_dewey.insert(0, res["dewey_code"])
                        if res.get("dewey_subject"):
                            ent_subject.delete(0, tk.END)
                            ent_subject.insert(0, res["dewey_subject"])
                        classification_meta["source"] = res.get("dewey_source", "api")
                        classification_meta["confidence"] = res.get("dewey_confidence", 0.95)
                        update_shelf_preview()
                        if res.get("title"):
                            status_lbl.configure(
                                text=f"اطلاعات کتاب دریافت شد (رده: {res.get('dewey_code') or 'نامشخص'})",
                                text_color="#16a34a",
                            )
                        else:
                            status_lbl.configure(
                                text="اطلاعات آنلاین برای این شابک یافت نشد. می‌توانید اطلاعات را دستی وارد کنید.",
                                text_color="#d97706",
                            )

                    popup.after(0, _apply)
                except Exception as ex:
                    err_text = str(ex)
                    popup.after(
                        0,
                        lambda msg=err_text: status_lbl.configure(text=f"خطا در استعلام: {msg}", text_color="#ef4444"),
                    )

            threading.Thread(target=_fetch_thread, daemon=True).start()

        btn_lookup_isbn.configure(command=do_isbn_lookup)

        def do_auto_classify_title():
            if not is_ai_available_fn():
                messagebox.showwarning(
                    "هوش مصنوعی",
                    "قابلیت‌های هوش مصنوعی یا دسترسی به اینترنت در تنظیمات برنامه غیرفعال است.",
                    parent=popup,
                )
                return
            t = ent_title.get().strip()
            a = ent_author.get().strip()
            if not t:
                messagebox.showwarning("خطا", "لطفاً ابتدا عنوان کتاب را وارد کنید!", parent=popup)
                ent_title.focus()
                return
            status_lbl.configure(text="در حال استعلام رده دیویی با هوش مصنوعی...", text_color="#38bdf8")
            popup.update()

            def _worker():
                try:
                    c_res = book_service.dewey_service.detect_with_ai(title=t, author=a if a else None)

                    def _apply():
                        if c_res and c_res.dewey_code:
                            ent_dewey.delete(0, tk.END)
                            ent_dewey.insert(0, c_res.dewey_code)
                            ent_subject.delete(0, tk.END)
                            ent_subject.insert(0, c_res.dewey_subject or "")
                            classification_meta["source"] = c_res.dewey_source
                            classification_meta["confidence"] = c_res.dewey_confidence
                            update_shelf_preview()
                            status_lbl.configure(
                                text=f"رده پیشنهادی (هوش مصنوعی): {c_res.dewey_code} - {c_res.dewey_subject} ({int(c_res.dewey_confidence * 100)} درصد اطمینان)",
                                text_color="#16a34a",
                            )
                        else:
                            status_lbl.configure(text="رده قطعی بر اساس عنوان یافت نشد.", text_color="#d97706")

                    popup.after(0, _apply)
                except Exception as ex:
                    err_msg = str(ex)
                    popup.after(
                        0,
                        lambda msg=err_msg: status_lbl.configure(
                            text=f"خطا در هوش مصنوعی: {msg}", text_color="#ef4444"
                        ),
                    )

            threading.Thread(target=_worker, daemon=True).start()

        btn_auto_ddc.configure(command=do_auto_classify_title)

        def do_insert_book():
            t = ent_title.get().strip()
            if not t:
                messagebox.showwarning("خطا", "لطفاً عنوان کتاب را وارد کنید!", parent=popup)
                ent_title.focus()
                return
            a = ent_author.get().strip() or None
            i = ent_isbn.get().strip() or None
            d = ent_dewey.get().strip() or None
            s = ent_subject.get().strip() or None

            if d and not is_valid_dewey(d):
                messagebox.showerror(
                    "کد دیویی نامعتبر",
                    "کد دیویی وارد شده معتبر نیست. کد باید عددی بین 000 تا 999 با اعشار اختیاری باشد.",
                    parent=popup,
                )
                ent_dewey.focus()
                return

            try:
                source = classification_meta["source"] or ("manual" if d else None)
                book_service.register_book(
                    title=t,
                    author=a,
                    isbn=i,
                    dewey_code=d,
                    dewey_subject=s,
                    dewey_source=source,
                    auto_classify=True,
                    conn_or_path=db_path,
                )
                messagebox.showinfo("موفق", "اطلاعات کتاب و رده‌بندی دیویی با موفقیت ثبت شد!", parent=popup)
                popup.destroy()
                search()
            except sqlite3.IntegrityError:
                messagebox.showerror("خطا", "این کتاب (شابک تکراری) قبلاً ثبت شده است!", parent=popup)
            except Exception as e:
                messagebox.showerror("خطا", f"خطا در ثبت کتاب: {e}", parent=popup)

        btn_f = ctk.CTkFrame(popup, fg_color="transparent")
        btn_f.pack(pady=(4, 14), padx=20, fill=tk.X)
        btn_save = create_icon_button_fn(
            btn_f,
            text=" ثبت اطلاعات کتاب ",
            icon_name="check",
            command=do_insert_book,
            font=font_bold,
            fg_color="#16a34a",
            hover_color="#15803d",
            width=135,
        )
        btn_save.pack(side=tk.RIGHT, padx=5)
        btn_cancel = create_icon_button_fn(
            btn_f,
            text=" انصراف ",
            icon_name="x",
            command=popup.destroy,
            font=font_normal,
            fg_color="transparent",
            hover_color=("#e2e8f0", "#1e293b"),
            width=90,
        )
        btn_cancel.pack(side=tk.LEFT, padx=5)

    def open_edit_book_popup(book_id: int | None = None):
        if book_id is None:
            selected = tree.selection()
            if not selected:
                messagebox.showinfo("راهنما", "لطفاً ابتدا یک کتاب را از جدول انتخاب کنید.", parent=root)
                return
            vals = tree.item(selected[0], "values")
            if not vals or str(vals[0]).startswith("❌"):
                return
            id_idx = columns.index("id") if "id" in columns else 0
            try:
                book_id = int(vals[id_idx])
            except (ValueError, IndexError):
                return

        book = book_service.get_book(book_id, conn_or_path=db_path)
        if not book:
            messagebox.showerror("خطا", "اطلاعات کتاب یافت نشد!", parent=root)
            return

        popup = ctk.CTkToplevel(root)
        book_title_display = book.get("title") or ""
        popup.title(f"ویرایش کتاب ({book_title_display})")
        popup.geometry("500x485")
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
        px = max(50, rx + (rw - 500) // 2)
        py = max(50, ry + (rh - 485) // 2)
        popup.geometry(f"+{px}+{py}")

        ctk.CTkLabel(popup, text="ویرایش اطلاعات کتاب و رده دیویی", font=font_title).pack(pady=(12, 8))

        form_f = ctk.CTkFrame(popup, fg_color="transparent")
        form_f.pack(fill=tk.BOTH, expand=True, padx=20, pady=0)

        # Title
        row_t = ctk.CTkFrame(form_f, fg_color="transparent")
        row_t.pack(fill=tk.X, pady=4)
        ctk.CTkLabel(row_t, text="عنوان کتاب:", font=font_bold, width=105, anchor="e").pack(side=tk.RIGHT, padx=(5, 0))
        ent_t = ctk.CTkEntry(
            row_t, font=font_normal, justify="right", height=32, placeholder_text="عنوان کتاب (الزامی)"
        )
        ent_t.insert(0, book.get("title") or "")
        ent_t.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        # Author
        row_a = ctk.CTkFrame(form_f, fg_color="transparent")
        row_a.pack(fill=tk.X, pady=4)
        ctk.CTkLabel(row_a, text="نویسنده:", font=font_normal, width=105, anchor="e").pack(side=tk.RIGHT, padx=(5, 0))
        ent_a = ctk.CTkEntry(
            row_a, font=font_normal, justify="right", height=32, placeholder_text="نام پدیدآورنده یا نویسنده"
        )
        ent_a.insert(0, book.get("author") or "")
        ent_a.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        # ISBN
        row_i = ctk.CTkFrame(form_f, fg_color="transparent")
        row_i.pack(fill=tk.X, pady=4)
        ctk.CTkLabel(row_i, text="شابک:", font=font_normal, width=105, anchor="e").pack(side=tk.RIGHT, padx=(5, 0))
        ent_i = ctk.CTkEntry(row_i, font=font_normal, justify="right", height=32, placeholder_text="شابک ۱۰ یا ۱۳ رقمی")
        ent_i.insert(0, book.get("isbn") or "")
        ent_i.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        # Reclassify row
        row_re = ctk.CTkFrame(form_f, fg_color="transparent")
        btn_reclassify_single = create_icon_button_fn(
            row_re,
            text=" پیشنهاد مجدد رده دیویی با هوش مصنوعی ",
            icon_name="zap",
            font=font_normal,
            height=30,
            fg_color="#0284c7",
            hover_color="#0369a1",
        )
        btn_reclassify_single.pack(fill=tk.X)

        if is_ai_available_fn():
            row_re.pack(fill=tk.X, pady=(3, 5))

        # Dewey Code
        row_d = ctk.CTkFrame(form_f, fg_color="transparent")
        row_d.pack(fill=tk.X, pady=4)
        ctk.CTkLabel(row_d, text="کد دیویی:", font=font_normal, width=105, anchor="e").pack(side=tk.RIGHT, padx=(5, 0))
        ent_d = ctk.CTkEntry(
            row_d, font=font_normal, justify="center", height=32, placeholder_text="مانند: 510 یا 641.5"
        )
        ent_d.insert(0, book.get("dewey_code") or "")
        ent_d.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        # Dewey Subject
        row_s = ctk.CTkFrame(form_f, fg_color="transparent")
        row_s.pack(fill=tk.X, pady=4)
        ctk.CTkLabel(row_s, text="موضوع دیویی:", font=font_normal, width=105, anchor="e").pack(
            side=tk.RIGHT, padx=(5, 0)
        )
        ent_s = ctk.CTkEntry(row_s, font=font_normal, justify="right", height=32, placeholder_text="موضوع رده")
        ent_s.insert(0, book.get("dewey_subject") or "")
        ent_s.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        DEWEY_SOURCE_FA = {
            "manual": "دستی",
            "api": "استعلام آنلاین",
            "mapping": "نگاشت موضوعی",
            "keyword": "واژگان کلیدی",
            "rule": "قوانین رده‌بندی",
            "ai": "هوش مصنوعی",
            "unknown": "تعیین‌نشده",
        }
        raw_src = str(book.get("dewey_source") or "unknown").strip().lower()
        src_display = DEWEY_SOURCE_FA.get(raw_src, "تعیین‌نشده")
        conf_val = int((book.get("dewey_confidence") or 0) * 100)

        meta_f = ctk.CTkFrame(form_f, corner_radius=6, fg_color=("#f1f5f9", "#1e293b"))
        meta_f.pack(fill=tk.X, pady=(5, 3), padx=2)
        meta_lbl = ctk.CTkLabel(
            meta_f,
            text=f"منبع رده: {src_display}  |  درجه اطمینان: {conf_val} درصد",
            font=font_small,
            text_color=("#475569", "#94a3b8"),
            anchor="e",
        )
        meta_lbl.pack(fill=tk.X, padx=10, pady=(4, 2))

        shelf_lbl = ctk.CTkLabel(
            meta_f,
            text="",
            font=font_small,
            text_color=("#475569", "#94a3b8"),
            anchor="e",
        )
        shelf_lbl.pack(fill=tk.X, padx=10, pady=(2, 4))

        def update_shelf_lbl():
            code = ent_d.get().strip()
            if code and is_valid_dewey(code):
                loc = book_service.dewey_service.get_shelf_location(code)
                shelf_lbl.configure(text=f"📍 {loc.get('shelf_label')}")
            else:
                shelf_lbl.configure(text="محل قفسه: تعیین نشده")

        update_shelf_lbl()
        ent_d.bind("<KeyRelease>", lambda e: update_shelf_lbl())

        def do_reclassify():
            if not is_ai_available_fn():
                messagebox.showwarning(
                    "هوش مصنوعی",
                    "قابلیت‌های هوش مصنوعی یا دسترسی به اینترنت در تنظیمات برنامه غیرفعال است.",
                    parent=popup,
                )
                return
            t = ent_t.get().strip()
            a = ent_a.get().strip()
            if not t:
                messagebox.showwarning("خطا", "لطفاً ابتدا عنوان کتاب را وارد کنید!", parent=popup)
                return

            def _worker():
                try:
                    c_res = book_service.dewey_service.detect_with_ai(title=t, author=a if a else None)

                    def _apply():
                        if c_res and c_res.dewey_code:
                            ent_d.delete(0, tk.END)
                            ent_d.insert(0, c_res.dewey_code)
                            ent_s.delete(0, tk.END)
                            ent_s.insert(0, c_res.dewey_subject or "")
                            update_shelf_lbl()
                            new_src_fa = DEWEY_SOURCE_FA.get(str(c_res.dewey_source).lower(), "هوش مصنوعی")
                            new_conf = int(c_res.dewey_confidence * 100)
                            meta_lbl.configure(text=f"منبع جدید: {new_src_fa}  |  درجه اطمینان: {new_conf} درصد")
                        else:
                            messagebox.showinfo("رده‌بندی", "رده مشخصی برای این کتاب پیدا نشد.", parent=popup)

                    popup.after(0, _apply)
                except Exception as ex:
                    err_msg = str(ex)
                    popup.after(
                        0,
                        lambda msg=err_msg: messagebox.showerror("خطا", f"خطا در هوش مصنوعی: {msg}", parent=popup),
                    )

            threading.Thread(target=_worker, daemon=True).start()

        btn_reclassify_single.configure(command=do_reclassify)

        def do_save_edit():
            new_title = ent_t.get().strip()
            if not new_title:
                messagebox.showwarning("خطا", "عنوان کتاب نمی‌تواند خالی باشد!", parent=popup)
                return
            new_author = ent_a.get().strip() or None
            new_isbn = ent_i.get().strip() or None
            new_code = ent_d.get().strip() or None
            new_subj = ent_s.get().strip() or None

            if new_code and not is_valid_dewey(new_code):
                messagebox.showerror("خطا", "کد دیویی وارد شده معتبر نیست!", parent=popup)
                return

            temp_conn = get_db_connection(db_path)
            try:
                temp_cur = temp_conn.cursor()
                cls_name = book_service.dewey_service.get_class_name(new_code) if new_code else None
                temp_cur.execute(
                    """
                    UPDATE books SET
                        title = ?,
                        author = ?,
                        isbn = ?,
                        dewey_code = ?,
                        dewey_class = ?,
                        dewey_subject = ?,
                        dewey_confidence = ?,
                        dewey_source = ?
                    WHERE id = ?
                    """,
                    (
                        new_title,
                        new_author,
                        new_isbn,
                        new_code,
                        cls_name,
                        new_subj,
                        1.0 if new_code else 0.0,
                        "manual",
                        book_id,
                    ),
                )
                temp_conn.commit()
                messagebox.showinfo("موفق", "اطلاعات کتاب با موفقیت به‌روزرسانی شد.", parent=popup)
                popup.destroy()
                search()
            except sqlite3.IntegrityError:
                messagebox.showerror("خطا", "شابک وارد شده تکراری است!", parent=popup)
            except Exception as ex:
                messagebox.showerror("خطا", f"خطا در به‌روزرسانی کتاب: {ex}", parent=popup)
            finally:
                temp_conn.close()

        btn_f = ctk.CTkFrame(popup, fg_color="transparent")
        btn_f.pack(pady=(4, 14), padx=20, fill=tk.X)
        btn_save = create_icon_button_fn(
            btn_f,
            text=" ذخیره تغییرات ",
            icon_name="check",
            command=do_save_edit,
            font=font_bold,
            fg_color="#16a34a",
            hover_color="#15803d",
            width=135,
        )
        btn_save.pack(side=tk.RIGHT, padx=5)
        btn_cancel = create_icon_button_fn(
            btn_f,
            text=" انصراف ",
            icon_name="x",
            command=popup.destroy,
            font=font_normal,
            fg_color="transparent",
            hover_color=("#e2e8f0", "#1e293b"),
            width=90,
        )
        btn_cancel.pack(side=tk.LEFT, padx=5)

    def open_reclassify_all_dialog():
        confirm = messagebox.askyesno(
            "رده‌بندی دسته‌ای کتاب‌ها",
            "آیا مایلید تمام کتاب‌های فاقد رده یا رده‌بندی‌شده سیستمی به صورت خودکار رده‌بندی شوند؟\n\n"
            "نکته: رده‌های تنظیم‌شده به صورت دستی (Manual) بدون تغییر حفظ خواهند شد.",
            parent=root,
        )
        if not confirm:
            return

        progress_win = ctk.CTkToplevel(root)
        progress_win.title("در حال رده‌بندی...")
        progress_win.geometry("320x120")
        progress_win.resizable(False, False)
        progress_win.transient(root)
        progress_win.grab_set()
        ctk.CTkLabel(progress_win, text="در حال پردازش و رده‌بندی کتاب‌ها...", font=font_normal).pack(pady=20)
        p_bar = ctk.CTkProgressBar(progress_win, mode="indeterminate")
        p_bar.pack(fill=tk.X, padx=30, pady=5)
        p_bar.start()

        def _worker():
            try:
                res = book_service.reclassify_all_books(force=False, conn_or_path=db_path)

                def _done():
                    progress_win.destroy()
                    messagebox.showinfo(
                        "پایان رده‌بندی",
                        f"رده‌بندی هوشمند به پایان رسید:\n\n"
                        f"• کل کتاب‌ها: {res['total']}\n"
                        f"• رده‌بندی‌شده / به‌روزرسانی‌شده: {res['updated']}\n"
                        f"• حفظ شده (رده دستی): {res['skippedmanual'] if 'skippedmanual' in res else res.get('skipped_manual', 0)}\n"
                        f"• بدون رده مشخص: {res['unclassified']}",
                        parent=root,
                    )
                    search()

                root.after(0, _done)
            except Exception as ex:
                err_msg = str(ex)

                def _err(msg=err_msg):
                    progress_win.destroy()
                    messagebox.showerror("خطا", f"خطا در رده‌بندی: {msg}", parent=root)

                root.after(0, _err)

        threading.Thread(target=_worker, daemon=True).start()

    def do_reclassify_selected_book():
        selected = tree.selection()
        if not selected:
            messagebox.showinfo("راهنما", "لطفاً ابتدا یک کتاب را انتخاب کنید.", parent=root)
            return
        vals = tree.item(selected[0], "values")
        if not vals or str(vals[0]).startswith("❌"):
            return
        id_idx = columns.index("id") if "id" in columns else 0
        try:
            book_id = int(vals[id_idx])
            c_res = book_service.reclassify_book(book_id, force=True, conn_or_path=db_path)
            if c_res and c_res.dewey_code:
                messagebox.showinfo(
                    "رده‌بندی دیویی",
                    f"کتاب با موفقیت رده‌بندی شد:\nکد: {c_res.dewey_code}\nموضوع: {c_res.dewey_subject}",
                    parent=root,
                )
            else:
                messagebox.showinfo("رده‌بندی دیویی", "رده مشخصی برای این کتاب پیدا نشد.", parent=root)
            search()
        except Exception as ex:
            messagebox.showerror("خطا", f"خطا در رده‌بندی: {ex}", parent=root)

    def request_borrow_selected():
        selected = tree.selection()
        if not selected:
            return
        vals = tree.item(selected[0], "values")
        if not vals or str(vals[0]).startswith("❌"):
            return

        title_idx = columns.index("title") if "title" in columns else -1
        title_val = vals[title_idx] if title_idx != -1 and title_idx < len(vals) else ""

        id_idx = columns.index("id") if "id" in columns else -1
        book_db_id = None
        if id_idx != -1 and id_idx < len(vals):
            try:
                book_db_id = int(vals[id_idx])
            except (ValueError, TypeError):
                pass

        with get_db_connection(db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM loans WHERE (book_id = ? OR book_id = ?) AND (borrowed = 1 OR borrowed = '1')",
                (book_db_id, title_val),
            )
            if cur.fetchone()[0] > 0:
                messagebox.showwarning(
                    "امانت کتاب",
                    f"کتاب «{title_val}» در حال حاضر در امانت است و امکان امانت مجدد آن وجود ندارد.",
                    parent=root,
                )
                return

        if on_borrow_book:
            on_borrow_book(title_val)

    book_context_menu = tk.Menu(root, tearoff=0)
    book_context_menu.add_command(label="ویرایش کتاب و رده دیویی...", command=open_edit_book_popup)
    book_context_menu.add_command(label="رده‌بندی خودکار این کتاب", command=do_reclassify_selected_book)
    book_context_menu.add_separator()
    book_context_menu.add_command(label="ثبت امانت این کتاب...", command=request_borrow_selected)

    def show_book_context_menu(event):
        row_id = tree.identify_row(event.y)
        if row_id:
            tree.selection_set(row_id)
            book_context_menu.tk_popup(event.x_root, event.y_root)

    tree.bind("<Button-3>", show_book_context_menu)
    tree.bind("<Double-Button-1>", lambda e: request_borrow_selected())

    reclassify_all_btn.configure(command=open_reclassify_all_dialog)
    edit_book_btn.configure(command=open_edit_book_popup)
    add_book_btn.configure(command=open_add_book_popup)

    bind_table_delete_fn(
        tree,
        tabel_name,
        id_col_index=columns.index("id") if "id" in columns else 0,
        on_deleted=search,
    )

    books_search_after_id = [None]

    def on_key_release(event):
        if books_search_after_id[0] is not None:
            root.after_cancel(books_search_after_id[0])
        books_search_after_id[0] = root.after(200, search)

    entry_serch.bind("<KeyRelease>", on_key_release)
    entry_serch.bind("<Return>", search)

    return {
        "search": search,
        "refresh_books_table": search,
        "open_add_book_popup": open_add_book_popup,
        "open_edit_book_popup": open_edit_book_popup,
        "tree": tree,
    }
