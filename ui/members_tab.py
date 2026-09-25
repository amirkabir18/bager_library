import os
import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

import customtkinter as ctk

from auth import normalize_phone_number
from database import get_db_connection, rtl_display_order, tr
from ui.common import export_tree_to_csv_ui


def build_members_tab(
    parent: Any,
    root: Any,
    fonts: dict[str, Any],
    get_icon_fn: Callable[..., Any],
    create_icon_button_fn: Callable[..., Any],
    bind_table_delete_fn: Callable[..., Any],
    db_path: str,
    icon_path: str = "",
    on_member_updated: Callable[[], None] | None = None,
) -> dict[str, Any]:
    font_title = fonts.get("title")
    font_normal = fonts.get("normal")
    font_bold = fonts.get("bold")
    font_small = fonts.get("small")

    member_tabel_name = "members"
    with get_db_connection(db_path) as conn_mem:
        cur_mem = conn_mem.cursor()
        cur_mem.execute(f'PRAGMA table_info("{member_tabel_name}")')
        member_column: list[str] = [str(row[1]) for row in cur_mem.fetchall()]

    member_filter_settings = {
        "column": "all",
        "match_mode": "contains",
        "sort_col": "id",
        "sort_dir": "ASC",
    }

    search_bar_frame_member = ctk.CTkFrame(parent, corner_radius=8, height=48)
    search_bar_frame_member.pack(fill=tk.X, padx=10, pady=(10, 6))
    search_bar_frame_member.columnconfigure(5, weight=1)

    sub_btn_member = create_icon_button_fn(
        search_bar_frame_member, text=" جستجو ", icon_name="search", font=font_bold, width=85
    )
    sub_btn_member.grid(row=0, column=0, padx=(8, 4), pady=6)

    filter_btn_member = create_icon_button_fn(
        search_bar_frame_member, text=" فیلترها ", icon_name="filter", font=font_normal, width=85
    )
    filter_btn_member.grid(row=0, column=1, padx=4, pady=6)

    export_member_btn = create_icon_button_fn(
        search_bar_frame_member,
        text=" خروجی اکسل ",
        icon_name="file-spreadsheet",
        font=font_normal,
        width=100,
        command=lambda: export_tree_to_csv_ui(member_tree, "members_export", root=root),
    )
    export_member_btn.grid(row=0, column=2, padx=4, pady=6)

    edit_member_btn = create_icon_button_fn(
        search_bar_frame_member,
        text=" ویرایش عضو ",
        icon_name="edit",
        font=font_normal,
        width=100,
    )
    edit_member_btn.grid(row=0, column=3, padx=4, pady=6)

    add_member_btn = create_icon_button_fn(
        search_bar_frame_member,
        text=" افزودن عضو ",
        icon_name="user-plus",
        font=font_normal,
        fg_color="#16a34a",
        hover_color="#15803d",
        width=105,
    )
    add_member_btn.grid(row=0, column=4, padx=4, pady=6)

    entry_search_member = ctk.CTkEntry(
        search_bar_frame_member,
        placeholder_text="جستجو در اعضا (نام، شماره تماس و ...)",
        font=font_normal,
        justify="right",
        height=36,
    )
    entry_search_member.grid(row=0, column=5, sticky="ew", padx=(4, 8), pady=6)

    member_tree_frame = ctk.CTkFrame(parent, corner_radius=8)
    member_tree_frame.pack(padx=10, pady=(0, 10), fill=tk.BOTH, expand=True)

    member_scrollbar = ctk.CTkScrollbar(member_tree_frame)
    member_scrollbar.pack(side=tk.LEFT, fill=tk.Y, padx=(4, 0), pady=4)

    member_tree = ttk.Treeview(
        member_tree_frame, yscrollcommand=member_scrollbar.set, columns=member_column, show="headings", height=15
    )
    member_scrollbar.configure(command=member_tree.yview)
    for col in member_column:
        member_tree.heading(col, text=tr(col), anchor=tk.CENTER)
        member_tree.column(col, anchor=tk.CENTER)
    member_display_cols = (
        ["id", "username", "phone_number"] if "username" in member_column else ["id", "member_id", "phone_number"]
    )
    member_tree["displaycolumns"] = rtl_display_order(member_column, member_display_cols)
    member_tree.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(4, 8), pady=4)

    def update_member_filter_indicator():
        is_custom = (
            member_filter_settings["column"] != "all"
            or member_filter_settings["match_mode"] != "contains"
            or member_filter_settings["sort_col"] != "id"
            or member_filter_settings["sort_dir"] != "ASC"
        )
        if is_custom:
            filter_btn_member.configure(text=" فیلترها (فعال) ", fg_color="#2563eb")
        else:
            filter_btn_member.configure(text=" فیلترها ", fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"])

    def search_members(event=None):
        search_value = entry_search_member.get().strip()
        member_tree.delete(*member_tree.get_children())

        temp_conn = get_db_connection(db_path)
        try:
            temp_cursor = temp_conn.cursor()

            where_conditions: list[str] = []
            params: list[str] = []

            if search_value:
                selected_col = member_filter_settings.get("column", "all")
                match_mode = member_filter_settings.get("match_mode", "contains")

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
                    sub_conds = [f"{col} {op} ?" for col in member_column]
                    where_conditions.append("(" + " OR ".join(sub_conds) + ")")
                    params.extend([pattern] * len(member_column))
                elif selected_col in member_column:
                    where_conditions.append(f"{selected_col} {op} ?")
                    params.append(pattern)

            query = f"SELECT {', '.join(member_column)} FROM {member_tabel_name}"
            if where_conditions:
                query += " WHERE " + " AND ".join(where_conditions)

            sort_col = member_filter_settings.get("sort_col", "id")
            if sort_col not in member_column:
                sort_col = "id"
            sort_dir = member_filter_settings.get("sort_dir", "ASC")
            if sort_dir not in ("ASC", "DESC"):
                sort_dir = "ASC"
            query += f" ORDER BY {sort_col} {sort_dir}"

            temp_cursor.execute(query, tuple(params))
            results = temp_cursor.fetchall()

            if results:
                for row in results:
                    member_tree.insert("", "end", values=tuple(row))
            else:
                member_tree.insert("", "end", values=("❌ نتیجه‌ای یافت نشد!",) + ("",) * (len(member_column) - 1))

        except Exception as e:
            messagebox.showerror("خطا", f"خطا در جستجوی اعضا: {str(e)}", parent=root)
        finally:
            temp_conn.close()

    sub_btn_member.configure(command=search_members)

    def open_member_filter_popup():
        popup = ctk.CTkToplevel(root)
        popup.title("فیلترهای اعضای کتابخانه")
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

        col_var = tk.StringVar(value=member_filter_settings["column"])
        match_var = tk.StringVar(value=member_filter_settings["match_mode"])
        sort_col_var = tk.StringVar(value=member_filter_settings["sort_col"])
        sort_dir_var = tk.StringVar(value=member_filter_settings["sort_dir"])

        group_col = ctk.CTkFrame(popup, corner_radius=8)
        group_col.pack(fill=tk.X, padx=15, pady=(10, 4))
        ctk.CTkLabel(group_col, text="جستجو در ستون", font=font_bold, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))
        col_frame = ctk.CTkFrame(group_col, fg_color="transparent")
        col_frame.pack(fill=tk.X, padx=6, pady=(0, 6))
        rb_all = ctk.CTkRadioButton(col_frame, text="همه ستون‌ها", variable=col_var, value="all", font=font_normal)
        rb_all.pack(side=tk.RIGHT, padx=4)
        for col in member_column:
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
        sort_cols_avail = [c for c in ["id", "member_id", "phone_number"] if c in member_column]
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

        def apply_member_filters():
            member_filter_settings["column"] = col_var.get()
            member_filter_settings["match_mode"] = match_var.get()

            disp_col = sort_col_cb.get()
            disp_map = {tr(c): c for c in member_column}
            member_filter_settings["sort_col"] = disp_map.get(disp_col, "id")
            member_filter_settings["sort_dir"] = "ASC" if sort_dir_cb.get() == "صعودی" else "DESC"

            update_member_filter_indicator()
            popup.destroy()
            search_members()

        def reset_member_filters():
            member_filter_settings["column"] = "all"
            member_filter_settings["match_mode"] = "contains"
            member_filter_settings["sort_col"] = "id"
            member_filter_settings["sort_dir"] = "ASC"

            update_member_filter_indicator()
            popup.destroy()
            search_members()

        btn_apply = create_icon_button_fn(
            action_frame,
            text=" اعمال فیلتر ",
            icon_name="check",
            font=font_bold,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            command=apply_member_filters,
        )
        btn_apply.pack(side=tk.RIGHT, padx=4)

        btn_reset = create_icon_button_fn(
            action_frame,
            text=" تنظیم مجدد ",
            icon_name="rotate-ccw",
            font=font_normal,
            fg_color="transparent",
            hover_color=("#e2e8f0", "#1e293b"),
            command=reset_member_filters,
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

    filter_btn_member.configure(command=open_member_filter_popup)

    def open_add_member_popup():
        popup = ctk.CTkToplevel(root)
        popup.title("ثبت عضو جدید")
        popup.geometry("400x320")
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
        px = max(50, rx + (rw - 400) // 2)
        py = max(50, ry + (rh - 320) // 2)
        popup.geometry(f"+{px}+{py}")

        ctk.CTkLabel(popup, text="ثبت عضو جدید", font=font_title).pack(pady=(15, 10))

        row_1 = ctk.CTkFrame(popup, fg_color="transparent")
        row_1.pack(fill=tk.X, padx=25, pady=6)
        ctk.CTkLabel(row_1, text="نام کاربر (عضو):", font=font_normal, width=110, anchor="e").pack(
            side=tk.RIGHT, padx=(5, 0)
        )
        entry_m_id = ctk.CTkEntry(row_1, font=font_normal, justify="right", height=34)
        entry_m_id.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        row_2 = ctk.CTkFrame(popup, fg_color="transparent")
        row_2.pack(fill=tk.X, padx=25, pady=6)
        ctk.CTkLabel(row_2, text="شماره تلفن:", font=font_normal, width=110, anchor="e").pack(
            side=tk.RIGHT, padx=(5, 0)
        )
        entry_m_phone = ctk.CTkEntry(row_2, font=font_normal, justify="right", height=34)
        entry_m_phone.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        def do_insert_member():
            m_id = entry_m_id.get().strip()
            m_phone = entry_m_phone.get().strip()

            if not m_id:
                messagebox.showwarning("خطا", "لطفاً نام کاربر را وارد کنید!", parent=popup)
                entry_m_id.focus()
                return
            if not m_phone:
                messagebox.showwarning("خطا", "لطفاً شماره تلفن را وارد کنید!", parent=popup)
                entry_m_phone.focus()
                return

            norm_phone = normalize_phone_number(m_phone)
            if len(norm_phone) != 11 or not norm_phone.startswith("09"):
                messagebox.showerror("خطا", "فرمت شماره تلفن نامعتبر است!\nمثال: 09123456789", parent=popup)
                entry_m_phone.focus()
                return

            temp_conn = get_db_connection(db_path)
            try:
                temp_cursor = temp_conn.cursor()
                temp_cursor.execute("INSERT INTO members (username, phone_number) VALUES (?, ?)", (m_id, norm_phone))
                temp_conn.commit()

                messagebox.showinfo("موفق", f"اطلاعات عضو با نام {m_id} با موفقیت ثبت شد!", parent=popup)
                popup.destroy()
                search_members()

            except sqlite3.IntegrityError:
                messagebox.showerror("خطا", f"نام کاربر '{m_id}' قبلاً ثبت شده است!", parent=popup)
            except sqlite3.Error as e:
                messagebox.showerror("خطا", f"خطا در پایگاه داده: {e}", parent=popup)
            finally:
                temp_conn.close()

        btn_f = ctk.CTkFrame(popup, fg_color="transparent")
        btn_f.pack(pady=20, padx=20, fill=tk.X)
        btn_save = create_icon_button_fn(
            btn_f,
            text=" ثبت اطلاعات ",
            icon_name="check",
            command=do_insert_member,
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

    def open_edit_member_popup(member_id: int | None = None):
        if member_id is None:
            selected = member_tree.selection()
            if not selected:
                messagebox.showinfo("راهنما", "لطفاً ابتدا یک عضو را از جدول انتخاب کنید.", parent=root)
                return
            vals = member_tree.item(selected[0], "values")
            if not vals or str(vals[0]).startswith("❌"):
                return
            id_idx = member_column.index("id") if "id" in member_column else 0
            try:
                member_id = int(vals[id_idx])
            except (ValueError, IndexError):
                return

        conn = get_db_connection(db_path)
        try:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM members WHERE id = ?", (member_id,))
            row = cur.fetchone()
            if not row:
                messagebox.showerror("خطا", "اطلاعات عضو در سامانه یافت نشد!", parent=root)
                return
            member_data = dict(row)
        finally:
            conn.close()

        popup = ctk.CTkToplevel(root)
        m_name_curr = str(member_data.get("username") or member_data.get("member_id") or "")
        popup.title(f"ویرایش مشخصات عضو ({m_name_curr})")
        popup.geometry("440x360")
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
        px = max(50, rx + (rw - 440) // 2)
        py = max(50, ry + (rh - 360) // 2)
        popup.geometry(f"+{px}+{py}")

        header_f = ctk.CTkFrame(popup, fg_color="transparent")
        header_f.pack(fill=tk.X, padx=20, pady=(15, 6))
        ctk.CTkLabel(header_f, text="ویرایش مشخصات عضو کتابخانه", font=font_title, anchor="center").pack(fill=tk.X)
        ctk.CTkLabel(
            header_f,
            text=f"شناسه پرونده عضویت: #{member_id}",
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

        row_1 = ctk.CTkFrame(card_f, fg_color="transparent")
        row_1.pack(fill=tk.X, padx=14, pady=(12, 6))
        ctk.CTkLabel(row_1, text="نام کاربر (عضو):", font=font_normal, width=110, anchor="e").pack(
            side=tk.RIGHT, padx=(4, 0)
        )
        entry_m_id = ctk.CTkEntry(row_1, font=font_normal, justify="right", height=34)
        entry_m_id.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        entry_m_id.insert(0, m_name_curr)

        row_2 = ctk.CTkFrame(card_f, fg_color="transparent")
        row_2.pack(fill=tk.X, padx=14, pady=(6, 14))
        ctk.CTkLabel(row_2, text="شماره تلفن:", font=font_normal, width=110, anchor="e").pack(
            side=tk.RIGHT, padx=(4, 0)
        )
        entry_m_phone = ctk.CTkEntry(row_2, font=font_normal, justify="right", height=34)
        entry_m_phone.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        entry_m_phone.insert(0, str(member_data.get("phone_number", "")))

        def do_update_member():
            new_name = entry_m_id.get().strip()
            new_phone = entry_m_phone.get().strip()

            if not new_name:
                messagebox.showwarning("خطا", "لطفاً نام کاربر را وارد کنید!", parent=popup)
                entry_m_id.focus()
                return
            if not new_phone:
                messagebox.showwarning("خطا", "لطفاً شماره تلفن را وارد کنید!", parent=popup)
                entry_m_phone.focus()
                return

            norm_phone = normalize_phone_number(new_phone)
            if len(norm_phone) != 11 or not norm_phone.startswith("09"):
                messagebox.showerror("خطا", "فرمت شماره تلفن نامعتبر است!\nمثال: 09123456789", parent=popup)
                entry_m_phone.focus()
                return

            temp_conn = get_db_connection(db_path)
            try:
                temp_cursor = temp_conn.cursor()
                temp_cursor.execute(
                    "SELECT id FROM members WHERE (username = ? OR member_id = ?) AND id != ?",
                    (new_name, new_name, member_id),
                )
                if temp_cursor.fetchone():
                    messagebox.showerror(
                        "خطا", f"نام کاربر '{new_name}' قبلاً برای عضو دیگری ثبت شده است!", parent=popup
                    )
                    entry_m_id.focus()
                    return

                try:
                    temp_cursor.execute(
                        "UPDATE members SET username = ?, phone_number = ? WHERE id = ?",
                        (new_name, norm_phone, member_id),
                    )
                except sqlite3.OperationalError:
                    temp_cursor.execute(
                        "UPDATE members SET member_id = ?, phone_number = ? WHERE id = ?",
                        (new_name, norm_phone, member_id),
                    )

                temp_conn.commit()

                messagebox.showinfo("موفق", f"اطلاعات عضو «{new_name}» با موفقیت به‌روزرسانی شد.", parent=popup)
                popup.destroy()
                search_members()
                if on_member_updated:
                    try:
                        on_member_updated()
                    except Exception:
                        pass
            except sqlite3.Error as e:
                messagebox.showerror("خطا", f"خطا در به‌روزرسانی عضو: {e}", parent=popup)
            finally:
                temp_conn.close()

        btn_f = ctk.CTkFrame(popup, fg_color="transparent")
        btn_f.pack(fill=tk.X, padx=20, pady=(6, 12))

        btn_save = create_icon_button_fn(
            btn_f,
            text=" ذخیره تغییرات ",
            icon_name="check",
            command=do_update_member,
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

    add_member_btn.configure(command=open_add_member_popup)
    edit_member_btn.configure(command=open_edit_member_popup)
    member_tree.bind("<Double-Button-1>", lambda e: open_edit_member_popup())

    member_context_menu = tk.Menu(root, tearoff=0)
    member_context_menu.add_command(label="ویرایش مشخصات عضو...", command=open_edit_member_popup)
    member_context_menu.add_separator()
    member_context_menu.add_command(label="حذف عضو", command=lambda: member_tree.event_generate("<Delete>"))

    def show_member_context_menu(event):
        row_id = member_tree.identify_row(event.y)
        if row_id:
            member_tree.selection_set(row_id)
            member_context_menu.tk_popup(event.x_root, event.y_root)

    member_tree.bind("<Button-3>", show_member_context_menu)

    member_search_after_id = [None]

    def on_member_key_release(event):
        if member_search_after_id[0] is not None:
            root.after_cancel(member_search_after_id[0])
        member_search_after_id[0] = root.after(200, search_members)

    entry_search_member.bind("<KeyRelease>", on_member_key_release)
    entry_search_member.bind("<Return>", search_members)

    bind_table_delete_fn(
        member_tree,
        "members",
        id_col_index=member_column.index("id") if "id" in member_column else 0,
        on_deleted=search_members,
    )

    return {
        "search_members": search_members,
        "open_add_member_popup": open_add_member_popup,
        "open_edit_member_popup": open_edit_member_popup,
        "tree": member_tree,
    }
