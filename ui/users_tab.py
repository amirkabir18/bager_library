import os
import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

import customtkinter as ctk

from auth import create_user, is_super_admin, normalize_phone_number, update_user
from database import get_db_connection, rtl_display_order, tr
from ui.common import export_tree_to_csv_ui


def build_users_tab(
    parent: Any,
    root: Any,
    fonts: dict[str, Any],
    get_icon_fn: Callable[..., Any],
    create_icon_button_fn: Callable[..., Any],
    bind_table_delete_fn: Callable[..., Any],
    db_path: str,
    get_current_user_fn: Callable[[], dict[str, Any] | None],
    on_user_updated: Callable[[dict[str, Any]], None] | None = None,
    icon_path: str = "",
) -> dict[str, Any]:
    font_title = fonts.get("title")
    font_normal = fonts.get("normal")
    font_bold = fonts.get("bold")
    font_small = fonts.get("small")

    user_tabel_name = "auth_users"
    user_columns = ["id", "username", "phone_number", "role", "telegram_chat_id", "is_active", "created_at"]

    user_filter_settings = {
        "column": "all",
        "match_mode": "contains",
        "sort_col": "id",
        "sort_dir": "ASC",
    }

    search_bar_frame_users = ctk.CTkFrame(parent, corner_radius=8, height=48)
    search_bar_frame_users.pack(fill=tk.X, padx=10, pady=(10, 6))
    search_bar_frame_users.columnconfigure(5, weight=1)

    sub_btn_users = create_icon_button_fn(
        search_bar_frame_users, text=" جستجو ", icon_name="search", font=font_bold, width=85
    )
    sub_btn_users.grid(row=0, column=0, padx=(8, 4), pady=6)

    filter_btn_users = create_icon_button_fn(
        search_bar_frame_users, text=" فیلترها ", icon_name="filter", font=font_normal, width=85
    )
    filter_btn_users.grid(row=0, column=1, padx=4, pady=6)

    export_users_btn = create_icon_button_fn(
        search_bar_frame_users,
        text=" خروجی اکسل ",
        icon_name="file-spreadsheet",
        font=font_normal,
        width=100,
        command=lambda: export_tree_to_csv_ui(users_tree, "users_export", root=root),
    )
    export_users_btn.grid(row=0, column=2, padx=4, pady=6)

    edit_user_btn = create_icon_button_fn(
        search_bar_frame_users,
        text=" ویرایش کاربر ",
        icon_name="user-cog",
        font=font_normal,
        width=100,
    )
    edit_user_btn.grid(row=0, column=3, padx=4, pady=6)

    add_user_btn = create_icon_button_fn(
        search_bar_frame_users,
        text=" افزودن کاربر ",
        icon_name="user-plus",
        font=font_normal,
        fg_color="#16a34a",
        hover_color="#15803d",
        width=105,
    )
    add_user_btn.grid(row=0, column=4, padx=4, pady=6)

    entry_search_users = ctk.CTkEntry(
        search_bar_frame_users,
        placeholder_text="جستجو در کاربران سامانه (نام کاربری، شماره تماس، نقش و ...)",
        font=font_normal,
        justify="right",
        height=36,
    )
    entry_search_users.grid(row=0, column=5, sticky="ew", padx=(4, 8), pady=6)

    users_tree_frame = ctk.CTkFrame(parent, corner_radius=8)
    users_tree_frame.pack(padx=10, pady=(0, 10), fill=tk.BOTH, expand=True)

    users_scrollbar = ctk.CTkScrollbar(users_tree_frame)
    users_scrollbar.pack(side=tk.LEFT, fill=tk.Y, padx=(4, 0), pady=4)

    users_tree = ttk.Treeview(
        users_tree_frame, yscrollcommand=users_scrollbar.set, columns=user_columns, show="headings", height=15
    )
    users_scrollbar.configure(command=users_tree.yview)
    for col in user_columns:
        users_tree.heading(col, text=tr(col), anchor=tk.CENTER)
        users_tree.column(col, anchor=tk.CENTER)
    users_tree["displaycolumns"] = rtl_display_order(
        user_columns, ["id", "username", "phone_number", "role", "telegram_chat_id", "is_active", "created_at"]
    )
    users_tree.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(4, 8), pady=4)

    def update_user_filter_indicator():
        is_custom = (
            user_filter_settings["column"] != "all"
            or user_filter_settings["match_mode"] != "contains"
            or user_filter_settings["sort_col"] != "id"
            or user_filter_settings["sort_dir"] != "ASC"
        )
        if is_custom:
            filter_btn_users.configure(text=" فیلترها (فعال) ", fg_color="#2563eb")
        else:
            filter_btn_users.configure(text=" فیلترها ", fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"])

    def search_users(event=None):
        search_value = entry_search_users.get().strip()
        users_tree.delete(*users_tree.get_children())

        temp_conn = get_db_connection(db_path)
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
            messagebox.showerror("خطا", f"خطا در جستجوی کاربران: {str(e)}", parent=root)
        finally:
            temp_conn.close()

    sub_btn_users.configure(command=search_users)

    def open_users_filter_popup():
        popup = ctk.CTkToplevel(root)
        popup.title("فیلترهای کاربران سامانه")
        popup.geometry("420x420")
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
        px = max(50, rx + (rw - 420) // 2)
        py = max(50, ry + (rh - 420) // 2)
        popup.geometry(f"+{px}+{py}")

        col_var = tk.StringVar(value=user_filter_settings["column"])
        match_var = tk.StringVar(value=user_filter_settings["match_mode"])
        sort_col_var = tk.StringVar(value=user_filter_settings["sort_col"])
        sort_dir_var = tk.StringVar(value=user_filter_settings["sort_dir"])

        group_col = ctk.CTkFrame(popup, corner_radius=8)
        group_col.pack(fill=tk.X, padx=15, pady=(10, 4))
        ctk.CTkLabel(group_col, text="جستجو در ستون", font=font_bold, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))
        col_frame = ctk.CTkFrame(group_col, fg_color="transparent")
        col_frame.pack(fill=tk.X, padx=6, pady=(0, 6))
        rb_all = ctk.CTkRadioButton(col_frame, text="همه ستون‌ها", variable=col_var, value="all", font=font_normal)
        rb_all.pack(side=tk.RIGHT, padx=4)
        for col in ["username", "phone_number", "role"]:
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

        group_sort = ctk.CTkFrame(popup, corner_radius=8)
        group_sort.pack(fill=tk.X, padx=15, pady=4)
        ctk.CTkLabel(group_sort, text="مرتب‌سازی نتایج", font=font_bold, anchor="e").pack(
            fill=tk.X, padx=10, pady=(6, 2)
        )
        sort_frame = ctk.CTkFrame(group_sort, fg_color="transparent")
        sort_frame.pack(fill=tk.X, padx=6, pady=(0, 6))

        ctk.CTkLabel(sort_frame, text="بر اساس:", font=font_normal).pack(side=tk.RIGHT, padx=(5, 0))
        sort_cols_avail = ["id", "username", "role"]
        sort_col_cb = ctk.CTkOptionMenu(
            sort_frame,
            width=130,
            font=font_normal,
            values=[tr(c) for c in sort_cols_avail],
        )
        sort_col_cb.set(tr(sort_col_var.get()))
        sort_col_cb.pack(side=tk.RIGHT, padx=5)

        ctk.CTkLabel(sort_frame, text="ترتیب:", font=font_normal).pack(side=tk.RIGHT, padx=(12, 0))
        sort_dir_cb = ctk.CTkOptionMenu(sort_frame, width=100, font=font_normal, values=["صعودی", "نزولی"])
        sort_dir_cb.set("صعودی" if sort_dir_var.get() == "ASC" else "نزولی")
        sort_dir_cb.pack(side=tk.RIGHT, padx=5)

        action_frame = ctk.CTkFrame(popup, fg_color="transparent")
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

        btn_apply = create_icon_button_fn(
            action_frame,
            text=" اعمال فیلتر ",
            icon_name="check",
            font=font_bold,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            command=apply_user_filters,
        )
        btn_apply.pack(side=tk.RIGHT, padx=4)

        btn_reset = create_icon_button_fn(
            action_frame,
            text=" تنظیم مجدد ",
            icon_name="rotate-ccw",
            font=font_normal,
            fg_color="transparent",
            hover_color=("#e2e8f0", "#1e293b"),
            command=reset_user_filters,
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

    filter_btn_users.configure(command=open_users_filter_popup)

    def open_create_user_popup():
        cur_user = get_current_user_fn()
        if not cur_user or str(cur_user.get("role", "")).strip().lower() not in (
            "super admin",
            "superadmin",
            "admin",
        ):
            messagebox.showerror("عدم دسترسی", "فقط نقش مدیر یا سرپرست مجاز به ایجاد کاربر جدید است.", parent=root)
            return

        popup = ctk.CTkToplevel(root)
        popup.title("ثبت کاربر جدید در سامانه")
        popup.geometry("420x500")
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
        px = max(50, rx + (rw - 420) // 2)
        py = max(50, ry + (rh - 500) // 2)
        popup.geometry(f"+{px}+{py}")

        ctk.CTkLabel(popup, text="ثبت کاربر جدید (سامانه)", font=font_title).pack(pady=(15, 10))

        r1 = ctk.CTkFrame(popup, fg_color="transparent")
        r1.pack(fill=tk.X, padx=25, pady=4)
        ctk.CTkLabel(r1, text="نام کاربری:", font=font_normal, width=130, anchor="e").pack(side=tk.RIGHT, padx=(5, 0))
        u_name_ent = ctk.CTkEntry(r1, font=font_normal, justify="right", height=32)
        u_name_ent.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        r2 = ctk.CTkFrame(popup, fg_color="transparent")
        r2.pack(fill=tk.X, padx=25, pady=4)
        ctk.CTkLabel(r2, text="شماره تلفن:", font=font_normal, width=130, anchor="e").pack(side=tk.RIGHT, padx=(5, 0))
        u_phone_ent = ctk.CTkEntry(r2, font=font_normal, justify="right", height=32)
        u_phone_ent.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        r3 = ctk.CTkFrame(popup, fg_color="transparent")
        r3.pack(fill=tk.X, padx=25, pady=4)
        ctk.CTkLabel(r3, text="شناسه چت تلگرام (اختیاری):", font=font_normal, width=130, anchor="e").pack(
            side=tk.RIGHT, padx=(5, 0)
        )
        u_tg_ent = ctk.CTkEntry(r3, font=font_normal, justify="right", height=32)
        u_tg_ent.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        r4 = ctk.CTkFrame(popup, fg_color="transparent")
        r4.pack(fill=tk.X, padx=25, pady=4)
        ctk.CTkLabel(r4, text="نقش کاربر:", font=font_normal, width=130, anchor="e").pack(side=tk.RIGHT, padx=(5, 0))
        u_role_combo = ctk.CTkOptionMenu(
            r4,
            font=font_normal,
            values=["super admin", "admin", "librarian", "user"],
            height=32,
        )
        u_role_combo.set("librarian")
        u_role_combo.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        r5 = ctk.CTkFrame(popup, fg_color="transparent")
        r5.pack(fill=tk.X, padx=25, pady=4)
        ctk.CTkLabel(r5, text="رمز عبور:", font=font_normal, width=130, anchor="e").pack(side=tk.RIGHT, padx=(5, 0))
        u_pwd_ent = ctk.CTkEntry(r5, font=font_normal, justify="right", height=32, show="*")
        u_pwd_ent.pack(side=tk.RIGHT, fill=tk.X, expand=True)

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
                database_path=db_path,
            )

            if success:
                messagebox.showinfo("موفق", msg, parent=popup)
                popup.destroy()
                search_users()
            else:
                messagebox.showerror("خطا", msg, parent=popup)

        btn_f = ctk.CTkFrame(popup, fg_color="transparent")
        btn_f.pack(pady=20, padx=20, fill=tk.X)
        btn_save = create_icon_button_fn(
            btn_f,
            text=" ثبت کاربر ",
            icon_name="check",
            command=do_create_user,
            font=font_bold,
            fg_color="#16a34a",
            hover_color="#15803d",
            width=120,
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

    def open_edit_user_popup(user_id: int | None = None):
        cur_user = get_current_user_fn()
        if not cur_user or str(cur_user.get("role", "")).strip().lower() not in (
            "super admin",
            "superadmin",
            "admin",
        ):
            messagebox.showerror("عدم دسترسی", "فقط نقش مدیر یا سرپرست مجاز به ویرایش کاربران است.", parent=root)
            return

        if user_id is None:
            selected = users_tree.selection()
            if not selected:
                messagebox.showinfo("راهنما", "لطفاً ابتدا یک کاربر را از جدول انتخاب کنید.", parent=root)
                return
            vals = users_tree.item(selected[0], "values")
            if not vals or str(vals[0]).startswith("❌"):
                return
            id_idx = user_columns.index("id") if "id" in user_columns else 0
            try:
                user_id = int(vals[id_idx])
            except (ValueError, IndexError):
                return

        conn = get_db_connection(db_path)
        try:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM auth_users WHERE id = ?", (user_id,))
            row = cur.fetchone()
            if not row:
                messagebox.showerror("خطا", "کاربر در سامانه یافت نشد.", parent=root)
                return
            u_data = dict(row)
        finally:
            conn.close()

        popup = ctk.CTkToplevel(root)
        curr_uname = str(u_data.get("username", ""))
        popup.title(f"ویرایش کاربر ({curr_uname})")
        popup.geometry("450x570")
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
        px = max(50, rx + (rw - 450) // 2)
        py = max(50, ry + (rh - 570) // 2)
        popup.geometry(f"+{px}+{py}")

        header_f = ctk.CTkFrame(popup, fg_color="transparent")
        header_f.pack(fill=tk.X, padx=20, pady=(15, 6))
        ctk.CTkLabel(header_f, text="ویرایش مشخصات کاربر سامانه", font=font_title, anchor="center").pack(fill=tk.X)
        ctk.CTkLabel(
            header_f,
            text=f"شناسه کاربری: #{user_id}",
            font=font_small,
            text_color="#94a3b8",
            anchor="center",
        ).pack(fill=tk.X, pady=(2, 0))

        card_f = ctk.CTkFrame(
            popup,
            corner_radius=10,
            border_width=1,
            border_color=("#cbd5e1", "#334155"),
            fg_color=("#ffffff", "#1e293b"),
        )
        card_f.pack(fill=tk.X, padx=20, pady=(4, 10))

        can_edit_creds = is_super_admin(cur_user)

        r1 = ctk.CTkFrame(card_f, fg_color="transparent")
        r1.pack(fill=tk.X, padx=14, pady=(12, 4))
        ctk.CTkLabel(r1, text="نام کاربری:", font=font_normal, width=115, anchor="e").pack(side=tk.RIGHT, padx=(4, 0))
        u_name_ent = ctk.CTkEntry(r1, font=font_normal, justify="right", height=32)
        u_name_ent.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        u_name_ent.insert(0, curr_uname)
        if not can_edit_creds:
            u_name_ent.configure(state="disabled")

        r2 = ctk.CTkFrame(card_f, fg_color="transparent")
        r2.pack(fill=tk.X, padx=14, pady=4)
        ctk.CTkLabel(r2, text="شماره تلفن:", font=font_normal, width=115, anchor="e").pack(side=tk.RIGHT, padx=(4, 0))
        u_phone_ent = ctk.CTkEntry(r2, font=font_normal, justify="right", height=32)
        u_phone_ent.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        u_phone_ent.insert(0, str(u_data.get("phone_number", "")))
        if not can_edit_creds:
            u_phone_ent.configure(state="disabled")

        if not can_edit_creds:
            note_cred = ctk.CTkFrame(card_f, fg_color="transparent")
            note_cred.pack(fill=tk.X, padx=14, pady=(0, 6))
            ctk.CTkLabel(note_cred, text="", image=get_icon_fn("lock", size=(13, 13)), width=16).pack(
                side=tk.RIGHT, padx=(2, 0)
            )
            ctk.CTkLabel(
                note_cred,
                text="ویرایش نام کاربری و شماره همراه منحصراً با دسترسی مدیر ارشد امکان‌پذیر است.",
                font=font_small,
                text_color=("#64748b", "#94a3b8"),
                anchor="e",
            ).pack(side=tk.RIGHT, fill=tk.X, expand=True)

        r3 = ctk.CTkFrame(card_f, fg_color="transparent")
        r3.pack(fill=tk.X, padx=14, pady=4)
        ctk.CTkLabel(r3, text="نقش کاربر:", font=font_normal, width=115, anchor="e").pack(side=tk.RIGHT, padx=(4, 0))
        available_roles = (
            ["super admin", "admin", "librarian", "user"] if can_edit_creds else ["admin", "librarian", "user"]
        )
        u_role_combo = ctk.CTkOptionMenu(
            r3,
            font=font_normal,
            values=available_roles,
            height=32,
        )
        curr_role = str(u_data.get("role", "librarian")).strip().lower()
        u_role_combo.set(curr_role if curr_role in available_roles else "librarian")
        u_role_combo.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        r4 = ctk.CTkFrame(card_f, fg_color="transparent")
        r4.pack(fill=tk.X, padx=14, pady=4)
        ctk.CTkLabel(r4, text="شناسه تلگرام:", font=font_normal, width=115, anchor="e").pack(side=tk.RIGHT, padx=(4, 0))
        u_tg_ent = ctk.CTkEntry(r4, font=font_normal, justify="right", height=32, placeholder_text="اختیاری")
        u_tg_ent.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        if u_data.get("telegram_chat_id"):
            u_tg_ent.insert(0, str(u_data.get("telegram_chat_id", "")))

        r5 = ctk.CTkFrame(card_f, fg_color="transparent")
        r5.pack(fill=tk.X, padx=14, pady=4)
        ctk.CTkLabel(r5, text="وضعیت حساب:", font=font_normal, width=115, anchor="e").pack(side=tk.RIGHT, padx=(4, 0))
        var_active = tk.BooleanVar(value=bool(u_data.get("is_active", 1)))
        sw_active = ctk.CTkSwitch(
            r5,
            text="حساب کاربری فعال است",
            variable=var_active,
            font=font_normal,
        )
        sw_active.pack(side=tk.RIGHT, padx=4)

        r6 = ctk.CTkFrame(card_f, fg_color="transparent")
        r6.pack(fill=tk.X, padx=14, pady=(4, 12))
        ctk.CTkLabel(r6, text="رمز عبور جدید:", font=font_normal, width=115, anchor="e").pack(
            side=tk.RIGHT, padx=(4, 0)
        )
        pwd_container = ctk.CTkFrame(r6, fg_color="transparent")
        pwd_container.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        u_pwd_ent = ctk.CTkEntry(
            pwd_container,
            font=font_normal,
            justify="right",
            height=32,
            show="*",
            placeholder_text="در صورت عدم تغییر خالی بگذارید",
        )
        u_pwd_ent.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0))

        icon_eye = get_icon_fn("eye", size=(16, 16))
        icon_eye_off = get_icon_fn("eye-off", size=(16, 16))

        def toggle_user_pwd_visibility():
            if u_pwd_ent.cget("show") == "*":
                u_pwd_ent.configure(show="")
                btn_pwd_eye.configure(image=icon_eye_off)
            else:
                u_pwd_ent.configure(show="*")
                btn_pwd_eye.configure(image=icon_eye)

        btn_pwd_eye = ctk.CTkButton(
            pwd_container,
            text="",
            image=icon_eye,
            width=34,
            height=32,
            fg_color=("#e2e8f0", "#334155"),
            hover_color=("#cbd5e1", "#475569"),
            command=toggle_user_pwd_visibility,
        )
        btn_pwd_eye.pack(side=tk.LEFT)

        def do_update_user():
            if can_edit_creds:
                uname = u_name_ent.get().strip()
                phone = u_phone_ent.get().strip()
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
            else:
                uname = str(u_data.get("username", ""))
                phone = str(u_data.get("phone_number", ""))
                norm_phone = normalize_phone_number(phone)

            tg = u_tg_ent.get().strip() or None
            role_val = u_role_combo.get().strip() or "librarian"
            pwd = u_pwd_ent.get().strip() or None
            act_val = var_active.get()

            if pwd and len(pwd) < 4:
                messagebox.showwarning("خطا", "رمز عبور جدید باید حداقل ۴ کاراکتر باشد!", parent=popup)
                u_pwd_ent.focus()
                return

            success, msg, updated_user = update_user(
                user_id=user_id,
                username=uname,
                phone_number=norm_phone,
                password=pwd,
                role=role_val,
                telegram_chat_id=tg,
                is_active=act_val,
                database_path=db_path,
            )

            if success:
                if on_user_updated and updated_user:
                    try:
                        on_user_updated(updated_user)
                    except Exception:
                        pass

                messagebox.showinfo("موفق", msg, parent=popup)
                popup.destroy()
                search_users()
            else:
                messagebox.showerror("خطا", msg, parent=popup)

        btn_f = ctk.CTkFrame(popup, fg_color="transparent")
        btn_f.pack(fill=tk.X, padx=20, pady=(6, 12))

        btn_save = create_icon_button_fn(
            btn_f,
            text=" ذخیره تغییرات ",
            icon_name="check",
            command=do_update_user,
            font=font_bold,
            fg_color="#16a34a",
            hover_color="#15803d",
            height=34,
            width=130,
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
            height=34,
            width=90,
        )
        btn_cancel.pack(side=tk.LEFT, padx=5)

    add_user_btn.configure(command=open_create_user_popup)
    edit_user_btn.configure(command=open_edit_user_popup)
    users_tree.bind("<Double-Button-1>", lambda e: open_edit_user_popup())

    users_context_menu = tk.Menu(root, tearoff=0)
    users_context_menu.add_command(label="ویرایش مشخصات کاربر...", command=open_edit_user_popup)
    users_context_menu.add_separator()
    users_context_menu.add_command(label="حذف کاربر", command=lambda: users_tree.event_generate("<Delete>"))

    def show_users_context_menu(event):
        row_id = users_tree.identify_row(event.y)
        if row_id:
            users_tree.selection_set(row_id)
            users_context_menu.tk_popup(event.x_root, event.y_root)

    users_tree.bind("<Button-3>", show_users_context_menu)

    users_search_after_id = [None]

    def on_users_key_release(event):
        if users_search_after_id[0] is not None:
            root.after_cancel(users_search_after_id[0])
        users_search_after_id[0] = root.after(200, search_users)

    entry_search_users.bind("<KeyRelease>", on_users_key_release)
    entry_search_users.bind("<Return>", search_users)

    bind_table_delete_fn(
        users_tree,
        "auth_users",
        id_col_index=user_columns.index("id") if "id" in user_columns else 0,
        on_deleted=search_users,
    )

    return {
        "search_users": search_users,
        "open_create_user_popup": open_create_user_popup,
        "open_edit_user_popup": open_edit_user_popup,
        "tree": users_tree,
    }
