import datetime
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable
from ui.common import export_tree_to_csv_ui

import customtkinter as ctk
import jdatetime

from database import (
    backup_database,
    clear_notification_logs,
    get_all_settings,
    get_db_connection,
    get_notification_logs,
    is_ai_features_enabled,
    is_internet_access_enabled,
    log_notification,
    restore_database,
    rtl_display_order,
    set_setting,
    tr,
)
from persian_calendar import create_date_picker_button
from services.dewey_ai_agent import (
    get_boot_internet_status,
    init_boot_internet_check,
    probe_internet_connectivity,
    set_boot_internet_status,
)


def _format_shamsi_date(date_str: str) -> str:
    if not date_str:
        return ""
    try:
        date_str = str(date_str).strip()
        if " " in date_str:
            dt_part, tm_part = date_str.split(" ", 1)
            parts = [int(p) for p in dt_part.split("-")]
            if parts[0] > 1900:
                g_date = datetime.date(parts[0], parts[1], parts[2])
                s_date = jdatetime.date.fromgregorian(date=g_date).strftime("%Y-%m-%d")
                tm_clean = tm_part.split(".")[0]
                return f"{s_date} {tm_clean}"
        elif "-" in date_str:
            parts = [int(p) for p in date_str.split("-")]
            if parts[0] > 1900:
                g_date = datetime.date(parts[0], parts[1], parts[2])
                return jdatetime.date.fromgregorian(date=g_date).strftime("%Y-%m-%d")
    except Exception:
        pass
    return str(date_str)


def build_settings_tab(
    parent: Any,
    root: Any,
    fonts: dict[str, Any],
    get_icon_fn: Callable[..., Any],
    create_icon_button_fn: Callable[..., Any],
    apply_treeview_styling_fn: Callable[[str], None],
    notification_engine: Any,
    reminder_manager: Any,
    otp_cleanup_manager: Any,
    db_path: str,
    icon_path: str = "",
    on_data_restored: list[Callable[[], None]] | None = None,
) -> dict[str, Any]:
    font_title = fonts.get("title")
    font_header = fonts.get("header")
    font_normal = fonts.get("normal")
    font_bold = fonts.get("bold")
    font_small = fonts.get("small")

    title_label = ctk.CTkLabel(parent, text="تنظیمات سیستم و اعلان‌ها", font=font_title)
    title_label.pack(pady=(16, 4))

    subtitle_label = ctk.CTkLabel(
        parent,
        text="مدیریت ترجیحات یادآوری، هشدارهای سررسید و مشاهده تاریخچه اعلان‌ها",
        font=font_normal,
        text_color="#94a3b8",
    )
    subtitle_label.pack(pady=(0, 8))

    settings_container = ctk.CTkScrollableFrame(parent, corner_radius=10, fg_color="transparent")
    settings_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

    # --- Preferences Card ---
    pref_card = ctk.CTkFrame(settings_container, corner_radius=10)
    pref_card.pack(fill=tk.X, pady=(0, 12))

    ctk.CTkLabel(pref_card, text=" ترجیحات اعلان‌ها و یادآوری ", font=font_header, anchor="e").pack(
        fill=tk.X, padx=16, pady=(12, 6)
    )

    var_notif_enabled = tk.BooleanVar(value=True)
    var_notif_sound = tk.BooleanVar(value=True)
    var_internet_enabled = tk.BooleanVar(value=True)
    var_ai_enabled = tk.BooleanVar(value=True)
    var_otp_cleanup_enabled = tk.BooleanVar(value=True)

    pref_row1 = ctk.CTkFrame(pref_card, fg_color="transparent")
    pref_row1.pack(fill=tk.X, padx=16, pady=4)

    chk_enable_notif = ctk.CTkSwitch(
        pref_row1,
        text="فعال‌سازی اعلان‌های دسکتاپ سیستم",
        variable=var_notif_enabled,
        font=font_normal,
    )
    chk_enable_notif.pack(side=tk.RIGHT, padx=10)

    chk_enable_sound = ctk.CTkSwitch(
        pref_row1,
        text="پخش صدای هشدار هنگام نمایش اعلان",
        variable=var_notif_sound,
        font=font_normal,
    )
    chk_enable_sound.pack(side=tk.RIGHT, padx=10)

    pref_row_net = ctk.CTkFrame(pref_card, fg_color="transparent")
    pref_row_net.pack(fill=tk.X, padx=16, pady=4)

    def on_toggle_internet_setting():
        if not var_internet_enabled.get():
            var_ai_enabled.set(False)
            chk_enable_ai.configure(state="disabled")
            update_boot_net_status_label()
            update_ai_card_inputs_state(enabled=False)
        else:
            chk_enable_ai.configure(state="normal")
            update_boot_net_status_label()
            update_ai_card_inputs_state(enabled=var_ai_enabled.get())

    def on_toggle_ai_setting():
        if not var_internet_enabled.get():
            var_ai_enabled.set(False)
            chk_enable_ai.configure(state="disabled")
            update_ai_card_inputs_state(enabled=False)
            return
        update_ai_card_inputs_state(enabled=var_ai_enabled.get())

    chk_enable_internet = ctk.CTkSwitch(
        pref_row_net,
        text="فعال‌سازی دسترسی به اینترنت",
        variable=var_internet_enabled,
        font=font_normal,
        command=on_toggle_internet_setting,
    )
    chk_enable_internet.pack(side=tk.RIGHT, padx=10)

    chk_enable_ai = ctk.CTkSwitch(
        pref_row_net,
        text="فعال‌سازی قابلیت‌های هوش مصنوعی",
        variable=var_ai_enabled,
        font=font_normal,
        command=on_toggle_ai_setting,
    )
    chk_enable_ai.pack(side=tk.RIGHT, padx=10)

    def manual_recheck_internet():
        if not var_internet_enabled.get():
            messagebox.showinfo(
                "وضعیت اینترنت",
                "دسترسی به اینترنت در تنظیمات برنامه غیرفعال شده است. ابتدا آن را فعال نمایید.",
                parent=root,
            )
            return

        lbl_boot_net_status.configure(text="در حال بررسی اتصال به اینترنت...", text_color="#38bdf8")

        def _worker():
            ok = probe_internet_connectivity(timeout=2.0)
            set_boot_internet_status(ok)

            def _done():
                update_boot_net_status_label()
                if ok:
                    messagebox.showinfo("بررسی اتصال", "اتصال به اینترنت برقرار و با موفقیت تأیید شد.", parent=root)
                else:
                    messagebox.showwarning(
                        "بررسی اتصال", "اتصال به اینترنت برقرار نشد. شبکه را بررسی کنید.", parent=root
                    )

            root.after(0, _done)

        threading.Thread(target=_worker, daemon=True).start()

    btn_recheck_net = create_icon_button_fn(
        pref_row_net,
        text=" بررسی مجدد اتصال ",
        icon_name="rotate-ccw",
        font=font_small,
        command=manual_recheck_internet,
        width=135,
        height=28,
    )
    btn_recheck_net.pack(side=tk.LEFT, padx=5)

    lbl_boot_net_status = ctk.CTkLabel(
        pref_row_net,
        text="",
        font=font_small,
        anchor="w",
    )
    lbl_boot_net_status.pack(side=tk.LEFT, padx=10)

    pref_row_otp = ctk.CTkFrame(pref_card, fg_color="transparent")
    pref_row_otp.pack(fill=tk.X, padx=16, pady=4)

    chk_enable_otp_cleanup = ctk.CTkSwitch(
        pref_row_otp,
        text="پاک‌سازی خودکار کدهای یک‌بارمصرف (OTP)",
        variable=var_otp_cleanup_enabled,
        font=font_normal,
    )
    chk_enable_otp_cleanup.pack(side=tk.RIGHT, padx=10)

    ctk.CTkLabel(pref_row_otp, text="بازه پاک‌سازی (ساعت):", font=font_normal).pack(side=tk.RIGHT, padx=(15, 5))

    combo_otp_interval = ctk.CTkOptionMenu(
        pref_row_otp,
        values=["1", "3", "6", "12", "24", "48"],
        width=80,
        font=font_normal,
        dropdown_font=font_normal,
    )
    combo_otp_interval.set("12")
    combo_otp_interval.pack(side=tk.RIGHT, padx=5)

    def trigger_clean_otp_now():
        try:
            deleted = otp_cleanup_manager.clean_now()
            messagebox.showinfo(
                "پاک‌سازی کدهای OTP",
                f"عملیات پاک‌سازی انجام شد. {deleted} رکورد کد/نشست منقضی از پایگاه داده پاک شد.",
                parent=root,
            )
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در پاک‌سازی کدهای OTP:\n{e}", parent=root)

    btn_clean_otp = create_icon_button_fn(
        pref_row_otp,
        text=" پاک‌سازی فوری کدهای OTP ",
        icon_name="rotate-ccw",
        font=font_small,
        command=trigger_clean_otp_now,
        width=175,
        height=28,
    )
    btn_clean_otp.pack(side=tk.LEFT, padx=5)

    pref_row2 = ctk.CTkFrame(pref_card, fg_color="transparent")
    pref_row2.pack(fill=tk.X, padx=16, pady=6)

    ctk.CTkLabel(pref_row2, text="ارسال یادآوری سررسید (چند روز قبل):", font=font_normal).pack(side=tk.RIGHT, padx=5)

    combo_advance_days = ctk.CTkOptionMenu(
        pref_row2,
        values=["1", "2", "3", "5", "7"],
        width=80,
        font=font_normal,
        dropdown_font=font_normal,
    )
    combo_advance_days.set("2")
    combo_advance_days.pack(side=tk.RIGHT, padx=10)

    ctk.CTkLabel(pref_row2, text="حداکثر تعداد امانت برای هر کاربر", font=font_normal).pack(side=tk.RIGHT, padx=5)

    combo_max_loans = ctk.CTkOptionMenu(
        pref_row2,
        values=["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
        width=80,
    )
    combo_max_loans.set("4")
    combo_max_loans.pack(side=tk.RIGHT, padx=10)

    ctk.CTkLabel(pref_row2, text="فاصله بررسی خودکار (دقیقه):", font=font_normal).pack(side=tk.RIGHT, padx=(20, 5))

    combo_interval = ctk.CTkOptionMenu(
        pref_row2,
        values=["15", "30", "60", "120", "360"],
        width=80,
        font=font_normal,
        dropdown_font=font_normal,
    )
    combo_interval.set("30")
    combo_interval.pack(side=tk.RIGHT, padx=10)

    ctk.CTkLabel(pref_row2, text="حالت تم:", font=font_normal).pack(side=tk.RIGHT, padx=(20, 5))

    def change_theme_mode(choice):
        if "روشن" in choice:
            ctk.set_appearance_mode("light")
            apply_treeview_styling_fn("light")
        elif "سیستم" in choice:
            ctk.set_appearance_mode("system")
            apply_treeview_styling_fn("dark")
        else:
            ctk.set_appearance_mode("dark")
            apply_treeview_styling_fn("dark")

    combo_theme = ctk.CTkOptionMenu(
        pref_row2,
        values=["تیره (Dark)", "روشن (Light)", "سیستم (System)"],
        width=130,
        command=change_theme_mode,
        font=font_normal,
        dropdown_font=font_normal,
    )
    combo_theme.set("تیره (Dark)")
    combo_theme.pack(side=tk.RIGHT, padx=5)

    def update_boot_net_status_label():
        try:
            if not var_internet_enabled.get():
                lbl_boot_net_status.configure(text="🔴 دسترسی اینترنت غیرفعال است", text_color="#dc2626")
                return
            net_ok = get_boot_internet_status(db_path)
            if net_ok:
                lbl_boot_net_status.configure(text="🟢 اینترنت متصل است", text_color="#16a34a")
            else:
                lbl_boot_net_status.configure(text="🔴 اینترنت قطع است", text_color="#dc2626")
        except Exception:
            pass

    # --- AI Provider Settings Card ---
    ai_card = ctk.CTkFrame(settings_container, corner_radius=10)
    ai_card.pack(fill=tk.X, pady=(0, 12))

    ai_header_row = ctk.CTkFrame(ai_card, fg_color="transparent")
    ai_header_row.pack(fill=tk.X, padx=16, pady=(12, 6))

    ctk.CTkLabel(
        ai_header_row,
        text=" تنظیمات ارائه‌دهنده هوش مصنوعی (AI Provider) ",
        font=font_header,
        anchor="e",
    ).pack(side=tk.RIGHT)

    lbl_ai_status = ctk.CTkLabel(
        ai_header_row,
        text="",
        font=font_small,
        text_color="#38bdf8",
        anchor="w",
    )
    lbl_ai_status.pack(side=tk.LEFT)

    def update_ai_card_inputs_state(enabled: bool):
        try:
            state = "normal" if enabled else "disabled"
            entry_ai_url.configure(state=state)
            entry_ai_key.configure(state=state)
            entry_ai_model.configure(state=state)
            btn_test_ai.configure(state=state)
            if not enabled:
                if not var_internet_enabled.get():
                    lbl_ai_status.configure(text="🔴 دسترسی اینترنت و هوش مصنوعی غیرفعال است", text_color="#dc2626")
                else:
                    lbl_ai_status.configure(text="🟡 قابلیت‌های هوش مصنوعی غیرفعال است", text_color="#f59e0b")
            else:
                lbl_ai_status.configure(text="")
        except Exception:
            pass

    ai_row1 = ctk.CTkFrame(ai_card, fg_color="transparent")
    ai_row1.pack(fill=tk.X, padx=16, pady=4)

    ctk.CTkLabel(ai_row1, text="آدرس سرور (Base URL):", font=font_normal, width=145, anchor="e").pack(
        side=tk.RIGHT, padx=(5, 0)
    )
    entry_ai_url = ctk.CTkEntry(
        ai_row1, font=font_normal, justify="left", height=32, placeholder_text="مثال: http://localhost:20128/v1"
    )
    entry_ai_url.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=5)

    ai_row2 = ctk.CTkFrame(ai_card, fg_color="transparent")
    ai_row2.pack(fill=tk.X, padx=16, pady=4)

    ctk.CTkLabel(ai_row2, text="کلید API (اختیاری):", font=font_normal, width=145, anchor="e").pack(
        side=tk.RIGHT, padx=(5, 0)
    )
    entry_ai_key = ctk.CTkEntry(
        ai_row2, font=font_normal, justify="left", height=32, show="*", placeholder_text="sk-... (در صورت نیاز به کلید)"
    )
    entry_ai_key.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=5)

    ai_row3 = ctk.CTkFrame(ai_card, fg_color="transparent")
    ai_row3.pack(fill=tk.X, padx=16, pady=4)

    ctk.CTkLabel(ai_row3, text="مدل زبانی (Model):", font=font_normal, width=145, anchor="e").pack(
        side=tk.RIGHT, padx=(5, 0)
    )
    entry_ai_model = ctk.CTkEntry(
        ai_row3,
        font=font_normal,
        justify="left",
        height=32,
        placeholder_text="مثال: claude-flash-3.6 یا openai/gpt-4o-mini",
    )
    entry_ai_model.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=5)

    ai_row4 = ctk.CTkFrame(ai_card, fg_color="transparent")
    ai_row4.pack(fill=tk.X, padx=16, pady=(6, 12))

    def test_ai_connection_ui():
        if not is_internet_access_enabled(db_path):
            messagebox.showwarning(
                "دسترسی به اینترنت",
                "دسترسی به اینترنت در تنظیمات برنامه غیرفعال شده است. لطفاً ابتدا دسترسی به اینترنت را فعال کنید.",
                parent=root,
            )
            return

        if not is_ai_features_enabled(db_path):
            messagebox.showwarning(
                "هوش مصنوعی",
                "قابلیت‌های هوش مصنوعی در تنظیمات برنامه غیرفعال شده است. لطفاً ابتدا آن را در تنظیمات فعال کنید.",
                parent=root,
            )
            return

        url = entry_ai_url.get().strip() or "http://localhost:20128"
        key = entry_ai_key.get().strip()
        lbl_ai_status.configure(text="در حال بررسی اتصال به سرویس هوش مصنوعی...", text_color="#38bdf8")

        def _test():
            try:
                from services.dewey_ai_agent import DeweyAIAgent

                net_ok = get_boot_internet_status(db_path)
                agent = DeweyAIAgent(base_url=url, api_key=key, database_path=db_path)
                is_alive = agent.is_available()
                if is_alive:
                    msg = "اتصال به سرویس هوش مصنوعی برقرار و سرور فعال است."
                    if net_ok:
                        msg += " (اینترنت متصل است)"
                    root.after(
                        0,
                        lambda: (
                            lbl_ai_status.configure(text=f"🟢 {msg}", text_color="#16a34a"),
                            messagebox.showinfo("تست اتصال هوش مصنوعی", msg, parent=root),
                        ),
                    )
                else:
                    root.after(
                        0,
                        lambda: (
                            lbl_ai_status.configure(
                                text="🔴 سرور هوش مصنوعی در این آدرس پاسخ نداد.", text_color="#dc2626"
                            ),
                            messagebox.showwarning(
                                "تست اتصال هوش مصنوعی",
                                "سرور هوش مصنوعی در این آدرس پاسخ نداد. لطفاً از روشن بودن سرور هوش مصنوعی اطمینان حاصل کنید.",
                                parent=root,
                            ),
                        ),
                    )
            except Exception as ex:
                err_text = str(ex)
                root.after(
                    0,
                    lambda msg=err_text: (
                        lbl_ai_status.configure(text=f"🔴 خطا: {msg}", text_color="#dc2626"),
                        messagebox.showerror("خطا در تست هوش مصنوعی", msg, parent=root),
                    ),
                )

        threading.Thread(target=_test, daemon=True).start()

    btn_test_ai = create_icon_button_fn(
        ai_row4,
        text=" تست اتصال به هوش مصنوعی ",
        icon_name="zap",
        font=font_normal,
        command=test_ai_connection_ui,
        width=180,
        height=32,
    )
    btn_test_ai.pack(side=tk.RIGHT, padx=5)

    pref_row3 = ctk.CTkFrame(pref_card, fg_color="transparent")
    pref_row3.pack(fill=tk.X, padx=16, pady=(10, 14))

    def save_settings_ui():
        notif_val = "true" if var_notif_enabled.get() else "false"
        sound_val = "true" if var_notif_sound.get() else "false"
        adv_days = str(combo_advance_days.get()).strip() or "2"
        max_loans = str(combo_max_loans.get()).strip() or "4"
        interval = str(combo_interval.get()).strip() or "30"

        internet_val = "true" if var_internet_enabled.get() else "false"
        if internet_val == "false":
            ai_val = "false"
            var_ai_enabled.set(False)
        else:
            ai_val = "true" if var_ai_enabled.get() else "false"

        otp_cleanup_val = "true" if var_otp_cleanup_enabled.get() else "false"
        otp_interval_val = str(combo_otp_interval.get()).strip() or "12"

        try:
            with get_db_connection(db_path) as conn:
                set_setting(conn, "max_loans", max_loans)
                set_setting(conn, "notifications_enabled", notif_val)
                set_setting(conn, "notification_sound", sound_val)
                set_setting(conn, "notification_advance_days", adv_days)
                set_setting(conn, "notification_check_interval_mins", interval)
                set_setting(conn, "internet_access_enabled", internet_val)
                set_setting(conn, "ai_features_enabled", ai_val)
                set_setting(conn, "otp_cleanup_enabled", otp_cleanup_val)
                set_setting(conn, "otp_cleanup_interval_hours", otp_interval_val)
                set_setting(conn, "openai_url", entry_ai_url.get().strip())
                set_setting(conn, "openai_key", entry_ai_key.get().strip())
                set_setting(conn, "openai_model", entry_ai_model.get().strip())

            if internet_val == "false":
                set_boot_internet_status(False)
            else:
                threading.Thread(
                    target=lambda: (
                        init_boot_internet_check(database_path=db_path, timeout=1.2),
                        root.after(0, update_boot_net_status_label),
                    ),
                    daemon=True,
                ).start()

            update_boot_net_status_label()
            on_toggle_internet_setting()

            try:
                reminder_manager.reschedule()
            except Exception:
                pass

            try:
                otp_cleanup_manager.reschedule()
            except Exception:
                pass

            messagebox.showinfo("موفقیت", "تنظیمات با موفقیت ذخیره و اعمال شد.", parent=root)
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در ذخیره تنظیمات:\n{e}", parent=root)

    def trigger_test_notification():
        try:
            notification_engine.show(
                "اعلان آزمایشی کتابخانه",
                "سیستم اعلان‌ها و هشدارهای نرم‌افزار به درستی فعال و در حال کار است.",
            )
            try:
                log_notification(db_path, notification_type="test", loan_id=None)
            except Exception:
                pass
            refresh_notification_logs()
            messagebox.showinfo("اعلان آزمایشی", "اعلان آزمایشی ارسال و در تاریخچه ثبت شد.", parent=root)
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در ارسال اعلان آزمایشی:\n{e}", parent=root)

    def trigger_check_now():
        try:
            found_count = reminder_manager.check_loans()
            refresh_notification_logs()
            if found_count > 0:
                messagebox.showinfo("بررسی امانات", f"بررسی انجام شد. {found_count} اعلان جدید صادر شد.", parent=root)
            else:
                messagebox.showinfo(
                    "بررسی امانات", "بررسی انجام شد. مورد جدیدی برای ارسال اعلان یافت نشد.", parent=root
                )
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در بررسی امانات:\n{e}", parent=root)

    def csv_print():
        csv_panel = ctk.CTkToplevel(root)
        csv_panel.title("دریافت جدول ها")
        csv_panel.geometry("900x450")
        csv_panel.resizable(False, False)
        if os.path.exists(icon_path):
            try:
                csv_panel.iconbitmap(icon_path)
            except Exception:
                pass
        csv_panel.grab_set()

        table_map = {
            "کتاب ها": ("books", "books_export"),
            "کاربران": ("auth_users", "users_export"),
            "اعضا": ("members", "members_export"),
            "امانت ها": ("loans", "loans_export"),
        }

        def table_choice(choice):
            table_name, export_name = table_map.get(choice, ("books", "books_export"))
            export_tables_btn.configure(
                command=lambda name=export_name: export_tree_to_csv_ui(table_choice_tree, name)
            )

            with get_db_connection(db_path) as conn:
                cur = conn.cursor()
                cur.execute(f"SELECT * FROM `{table_name}`")
                rows = cur.fetchall()
                cols = [desc[0] for desc in cur.description]

            table_choice_tree.delete(*table_choice_tree.get_children())

            table_choice_tree["displaycolumns"] = ()
            table_choice_tree["columns"] = cols
            table_choice_tree["show"] = "headings"
            table_choice_tree["displaycolumns"] = rtl_display_order(cols, cols)

            for col in cols:
                table_choice_tree.heading(col, text=tr(col), anchor="center")
                table_choice_tree.column(col, anchor="center")

            for row in rows:
                table_choice_tree.insert("", "end", values=row)

        btn_frame = ctk.CTkFrame(csv_panel)
        btn_frame.pack(padx=16, pady=(0, 12), fill=tk.BOTH)

        csv_tabel_op = ctk.CTkOptionMenu(
            btn_frame,
            values=list(table_map.keys()),
            width=140,
            command=table_choice,
            font=font_normal,
            dropdown_font=font_normal,
        )
        csv_tabel_op.set("کتاب ها")
        csv_tabel_op.pack(padx=5, side=tk.LEFT)

        export_tables_btn = create_icon_button_fn(
            btn_frame,
            text="گرفتن خروجی اکسل",
            icon_name="file-spreadsheet",
            font=font_normal,
            width=100,
        )
        export_tables_btn.pack(pady=10, side=tk.RIGHT)

        table_choice_frame = ctk.CTkFrame(csv_panel)
        table_choice_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 12))

        scrollbar_3 = ctk.CTkScrollbar(table_choice_frame)
        scrollbar_3.pack(side=tk.RIGHT, fill=tk.Y, padx=(4, 0), pady=4)

        table_choice_tree = ttk.Treeview(table_choice_frame, yscrollcommand=scrollbar_3.set)
        scrollbar_3.configure(command=table_choice_tree.yview)
        table_choice_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 8), pady=4)

        table_choice("کتاب ها")

    btn_save_settings = create_icon_button_fn(
        pref_row3,
        text=" ذخیره تنظیمات ",
        icon_name="check",
        font=font_bold,
        fg_color="#16a34a",
        hover_color="#15803d",
        command=save_settings_ui,
        width=130,
        height=34,
    )
    btn_save_settings.pack(side=tk.RIGHT, padx=5)

    btn_test_notif = create_icon_button_fn(
        pref_row3,
        text=" ارسال اعلان آزمایشی ",
        font=font_normal,
        command=trigger_test_notification,
        width=150,
        height=34,
    )
    btn_test_notif.pack(side=tk.RIGHT, padx=5)

    btn_check_now = create_icon_button_fn(
        pref_row3,
        text=" بررسی فوری امانات ",
        icon_name="rotate-ccw",
        font=font_normal,
        fg_color="transparent",
        hover_color=("#e2e8f0", "#1e293b"),
        command=trigger_check_now,
        width=150,
        height=34,
    )
    btn_check_now.pack(side=tk.RIGHT, padx=5)

    btn_csv_print = create_icon_button_fn(
        pref_row3,
        text="دریافت جدول ها",
        font=font_normal,
        command=csv_print,
        width=150,
        height=34,
    )
    btn_csv_print.pack(side=tk.RIGHT, padx=5)

    # --- Database Backup & Restore Card ---
    backup_card = ctk.CTkFrame(settings_container, corner_radius=10)
    backup_card.pack(fill=tk.X, pady=(0, 12))

    backup_header_row = ctk.CTkFrame(backup_card, fg_color="transparent")
    backup_header_row.pack(fill=tk.X, padx=16, pady=(12, 6))

    ctk.CTkLabel(
        backup_header_row,
        text=" پشتیبان‌گیری و بازیابی پایگاه داده (Backup & Restore) ",
        font=font_header,
        anchor="e",
    ).pack(side=tk.RIGHT)

    lbl_backup_status = ctk.CTkLabel(
        backup_header_row,
        text="",
        font=font_small,
        text_color="#94a3b8",
        anchor="w",
    )
    lbl_backup_status.pack(side=tk.LEFT)

    backup_row = ctk.CTkFrame(backup_card, fg_color="transparent")
    backup_row.pack(fill=tk.X, padx=16, pady=(4, 12))

    def do_backup_database_ui():
        try:
            default_filename = f"bager_library_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            dest_path = filedialog.asksaveasfilename(
                parent=root,
                title="ذخیره فایل پشتیبان پایگاه داده",
                defaultextension=".db",
                initialfile=default_filename,
                filetypes=[("پایگاه داده SQLite", "*.db"), ("تمام فایل‌ها", "*.*")],
            )
            if not dest_path:
                return

            saved_file = backup_database(dest_path, source_path_or_conn=db_path)
            size_kb = os.path.getsize(saved_file) / 1024
            msg = f"نسخه پشتیبان با موفقیت ذخیره شد:\n{saved_file}\nحجم: {size_kb:.1f} کیلوبایت"
            lbl_backup_status.configure(text="🟢 پشتیبان‌گیری موفق", text_color="#16a34a")
            messagebox.showinfo("پشتیبان‌گیری موفق", msg, parent=root)
        except Exception as e:
            lbl_backup_status.configure(text="🔴 خطا در پشتیبان‌گیری", text_color="#dc2626")
            messagebox.showerror("خطا در پشتیبان‌گیری", f"خطا در ایجاد نسخه پشتیبان:\n{e}", parent=root)

    def do_restore_database_ui():
        try:
            confirm = messagebox.askyesno(
                "تأیید بازیابی پایگاه داده",
                "هشدار: بازیابی نسخه پشتیبان تمام اطلاعات فعلی (کتاب‌ها، اعضا، امانات، کاربران) را جایگزین خواهد کرد.\n\nآیا از ادامه مطمئن هستید؟",
                icon="warning",
                parent=root,
            )
            if not confirm:
                return

            src_path = filedialog.askopenfilename(
                parent=root,
                title="انتخاب فایل پشتیبان پایگاه داده",
                filetypes=[("پایگاه داده SQLite", "*.db"), ("تمام فایل‌ها", "*.*")],
            )
            if not src_path:
                return

            restore_database(src_path, target_path_or_conn=db_path)
            lbl_backup_status.configure(text="🟢 بازیابی پایگاه داده موفق", text_color="#16a34a")
            messagebox.showinfo("بازیابی موفق", "پایگاه داده با موفقیت از فایل پشتیبان بازیابی شد.", parent=root)

            if on_data_restored:
                for fn in on_data_restored:
                    try:
                        fn()
                    except Exception:
                        pass
            load_notification_logs_ui()
        except Exception as e:
            lbl_backup_status.configure(text="🔴 خطا در بازیابی", text_color="#dc2626")
            messagebox.showerror("خطا در بازیابی", f"خطا در بازیابی پایگاه داده:\n{e}", parent=root)

    btn_backup_db = create_icon_button_fn(
        backup_row,
        text=" تهیه نسخه پشتیبان (Backup) ",
        icon_name="download",
        font=font_normal,
        command=do_backup_database_ui,
        width=180,
        height=32,
    )
    btn_backup_db.pack(side=tk.RIGHT, padx=5)

    btn_restore_db = create_icon_button_fn(
        backup_row,
        text=" بازیابی از نسخه پشتیبان (Restore) ",
        icon_name="upload",
        font=font_normal,
        fg_color="#b45309",
        hover_color="#92400e",
        command=do_restore_database_ui,
        width=210,
        height=32,
    )
    btn_restore_db.pack(side=tk.RIGHT, padx=5)

    # --- Audit Log Viewer Card ---
    log_card = ctk.CTkFrame(settings_container, corner_radius=10)
    log_card.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

    ctk.CTkLabel(log_card, text=" تاریخچه و لاگ اعلان‌ها ", font=font_header, anchor="e").pack(
        fill=tk.X, padx=16, pady=(12, 6)
    )

    filter_row = ctk.CTkFrame(log_card, fg_color="transparent")
    filter_row.pack(fill=tk.X, padx=16, pady=(0, 8))

    entry_log_search = ctk.CTkEntry(
        filter_row, placeholder_text="جستجو در لاگ‌ها...", font=font_normal, width=170, height=32
    )
    entry_log_search.pack(side=tk.RIGHT, padx=5)

    btn_search_logs = create_icon_button_fn(
        filter_row,
        text=" جستجو ",
        icon_name="search",
        font=font_bold,
        command=lambda: load_notification_logs_ui(),
        width=85,
        height=32,
    )
    btn_search_logs.pack(side=tk.RIGHT, padx=4)

    ctk.CTkLabel(filter_row, text="نوع اعلان:", font=font_normal).pack(side=tk.RIGHT, padx=(10, 4))

    audit_log_filter_settings = {
        "column": "all",
        "match_mode": "contains",
        "notification_type": "all",
        "sort_col": "id",
        "sort_dir": "DESC",
        "start_date": "",
        "end_date": "",
    }

    def on_combo_log_type_changed(choice=None):
        sel_type = combo_log_type.get().strip()
        type_code_map = {
            "همه": "all",
            "یادآوری سررسید": "due_reminder",
            "هشدار دیرکرد": "overdue",
            "اعلان آزمایشی": "test",
        }
        audit_log_filter_settings["notification_type"] = type_code_map.get(sel_type, "all")
        update_audit_log_filter_indicator()
        load_notification_logs_ui()

    combo_log_type = ctk.CTkOptionMenu(
        filter_row,
        values=["همه", "یادآوری سررسید", "هشدار دیرکرد", "اعلان آزمایشی"],
        width=140,
        command=on_combo_log_type_changed,
        font=font_normal,
        dropdown_font=font_normal,
    )
    combo_log_type.set("همه")
    combo_log_type.pack(side=tk.RIGHT, padx=5)

    def open_audit_log_filter_popup():
        popup = ctk.CTkToplevel(root)
        popup.title("فیلترهای تاریخچه اعلان‌ها")
        popup.geometry("460x520")
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
        py = max(50, ry + (rh - 520) // 2)
        popup.geometry(f"+{px}+{py}")

        col_var = tk.StringVar(value=audit_log_filter_settings["column"])
        match_var = tk.StringVar(value=audit_log_filter_settings["match_mode"])
        type_var = tk.StringVar(value=audit_log_filter_settings["notification_type"])
        sort_col_var = tk.StringVar(value=audit_log_filter_settings["sort_col"])
        sort_dir_var = tk.StringVar(value=audit_log_filter_settings["sort_dir"])

        group_col = ctk.CTkFrame(popup, corner_radius=8)
        group_col.pack(fill=tk.X, padx=15, pady=(10, 4))
        ctk.CTkLabel(group_col, text="جستجو در ستون", font=font_bold, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))

        col_frame_1 = ctk.CTkFrame(group_col, fg_color="transparent")
        col_frame_1.pack(fill=tk.X, padx=6, pady=2)
        rb_all = ctk.CTkRadioButton(col_frame_1, text="همه", variable=col_var, value="all", font=font_normal)
        rb_all.pack(side=tk.RIGHT, padx=4)
        rb_bt = ctk.CTkRadioButton(col_frame_1, text="کتاب", variable=col_var, value="book_title", font=font_normal)
        rb_bt.pack(side=tk.RIGHT, padx=4)
        rb_mn = ctk.CTkRadioButton(col_frame_1, text="کاربر", variable=col_var, value="member_name", font=font_normal)
        rb_mn.pack(side=tk.RIGHT, padx=4)

        col_frame_2 = ctk.CTkFrame(group_col, fg_color="transparent")
        col_frame_2.pack(fill=tk.X, padx=6, pady=(0, 6))
        rb_lid = ctk.CTkRadioButton(
            col_frame_2, text="شناسه امانت", variable=col_var, value="loan_id", font=font_normal
        )
        rb_lid.pack(side=tk.RIGHT, padx=4)
        rb_sd = ctk.CTkRadioButton(
            col_frame_2, text="تاریخ ارسال", variable=col_var, value="sent_date", font=font_normal
        )
        rb_sd.pack(side=tk.RIGHT, padx=4)
        rb_id = ctk.CTkRadioButton(col_frame_2, text="شناسه", variable=col_var, value="id", font=font_normal)
        rb_id.pack(side=tk.RIGHT, padx=4)

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

        group_type = ctk.CTkFrame(popup, corner_radius=8)
        group_type.pack(fill=tk.X, padx=15, pady=4)
        ctk.CTkLabel(group_type, text="نوع اعلان", font=font_bold, anchor="e").pack(fill=tk.X, padx=10, pady=(6, 2))
        type_frame = ctk.CTkFrame(group_type, fg_color="transparent")
        type_frame.pack(fill=tk.X, padx=6, pady=(0, 6))
        rb_t_all = ctk.CTkRadioButton(type_frame, text="همه", variable=type_var, value="all", font=font_normal)
        rb_t_all.pack(side=tk.RIGHT, padx=6)
        rb_t_due = ctk.CTkRadioButton(
            type_frame, text="یادآوری سررسید", variable=type_var, value="due_reminder", font=font_normal
        )
        rb_t_due.pack(side=tk.RIGHT, padx=6)
        rb_t_overdue = ctk.CTkRadioButton(
            type_frame, text="هشدار دیرکرد", variable=type_var, value="overdue", font=font_normal
        )
        rb_t_overdue.pack(side=tk.RIGHT, padx=6)
        rb_t_test = ctk.CTkRadioButton(
            type_frame, text="اعلان آزمایشی", variable=type_var, value="test", font=font_normal
        )
        rb_t_test.pack(side=tk.RIGHT, padx=6)

        group_log_date = ctk.CTkFrame(popup, corner_radius=8)
        group_log_date.pack(fill=tk.X, padx=15, pady=4)
        ctk.CTkLabel(group_log_date, text="بازه تاریخ ارسال اعلان (شمسی)", font=font_bold, anchor="e").pack(
            fill=tk.X, padx=10, pady=(6, 2)
        )
        date_log_frame = ctk.CTkFrame(group_log_date, fg_color="transparent")
        date_log_frame.pack(fill=tk.X, padx=6, pady=(0, 6))

        ctk.CTkLabel(date_log_frame, text="از:", font=font_normal).pack(side=tk.RIGHT, padx=(4, 2))
        ent_log_start = ctk.CTkEntry(
            date_log_frame, width=110, height=30, font=font_normal, justify="center", placeholder_text="YYYY-MM-DD"
        )
        ent_log_start.insert(0, audit_log_filter_settings.get("start_date", ""))
        btn_start_cal = create_date_picker_button(
            date_log_frame,
            entry_widget=ent_log_start,
            title="انتخاب تاریخ شروع ارسال",
            icon_path=icon_path,
            width=30,
            height=30,
        )
        btn_start_cal.pack(side=tk.RIGHT, padx=2)
        ent_log_start.pack(side=tk.RIGHT, padx=(2, 10))

        ctk.CTkLabel(date_log_frame, text="تا:", font=font_normal).pack(side=tk.RIGHT, padx=(4, 2))
        ent_log_end = ctk.CTkEntry(
            date_log_frame, width=110, height=30, font=font_normal, justify="center", placeholder_text="YYYY-MM-DD"
        )
        ent_log_end.insert(0, audit_log_filter_settings.get("end_date", ""))
        btn_end_cal = create_date_picker_button(
            date_log_frame,
            entry_widget=ent_log_end,
            title="انتخاب تاریخ پایان ارسال",
            icon_path=icon_path,
            width=30,
            height=30,
        )
        btn_end_cal.pack(side=tk.RIGHT, padx=2)
        ent_log_end.pack(side=tk.RIGHT, padx=2)

        group_sort = ctk.CTkFrame(popup, corner_radius=8)
        group_sort.pack(fill=tk.X, padx=15, pady=4)
        ctk.CTkLabel(group_sort, text="مرتب‌سازی نتایج", font=font_bold, anchor="e").pack(
            fill=tk.X, padx=10, pady=(6, 2)
        )
        sort_frame = ctk.CTkFrame(group_sort, fg_color="transparent")
        sort_frame.pack(fill=tk.X, padx=6, pady=(0, 6))

        ctk.CTkLabel(sort_frame, text="بر اساس:", font=font_normal).pack(side=tk.RIGHT, padx=(5, 0))
        sort_options = {
            "شناسه": "id",
            "تاریخ ارسال": "sent_date",
            "تاریخ ثبت": "created_at",
            "عنوان کتاب": "book_title",
            "نام کاربر": "member_name",
            "شناسه امانت": "loan_id",
        }
        rev_sort_options = {v: k for k, v in sort_options.items()}

        sort_col_cb = ctk.CTkOptionMenu(
            sort_frame,
            width=130,
            font=font_normal,
            dropdown_font=font_normal,
            values=list(sort_options.keys()),
        )
        current_sort_label = rev_sort_options.get(sort_col_var.get(), "شناسه")
        sort_col_cb.set(current_sort_label)
        sort_col_cb.pack(side=tk.RIGHT, padx=5)

        ctk.CTkLabel(sort_frame, text="ترتیب:", font=font_normal).pack(side=tk.RIGHT, padx=(12, 0))
        sort_dir_cb = ctk.CTkOptionMenu(
            sort_frame,
            width=140,
            font=font_normal,
            dropdown_font=font_normal,
            values=["نزولی (جدیدترین)", "صعودی (قدیمی‌ترین)"],
        )
        sort_dir_cb.set("نزولی (جدیدترین)" if sort_dir_var.get() == "DESC" else "صعودی (قدیمی‌ترین)")
        sort_dir_cb.pack(side=tk.RIGHT, padx=5)

        action_frame = ctk.CTkFrame(popup, fg_color="transparent")
        action_frame.pack(fill=tk.X, padx=15, pady=(15, 10))

        def apply_audit_log_filters():
            audit_log_filter_settings["column"] = col_var.get()
            audit_log_filter_settings["match_mode"] = match_var.get()
            audit_log_filter_settings["notification_type"] = type_var.get()
            audit_log_filter_settings["sort_col"] = sort_options.get(sort_col_cb.get(), "id")
            audit_log_filter_settings["sort_dir"] = "DESC" if "نزولی" in sort_dir_cb.get() else "ASC"
            audit_log_filter_settings["start_date"] = ent_log_start.get().strip()
            audit_log_filter_settings["end_date"] = ent_log_end.get().strip()

            type_display_map = {
                "all": "همه",
                "due_reminder": "یادآوری سررسید",
                "overdue": "هشدار دیرکرد",
                "test": "اعلان آزمایشی",
            }
            combo_log_type.set(type_display_map.get(audit_log_filter_settings["notification_type"], "همه"))

            update_audit_log_filter_indicator()
            popup.destroy()
            load_notification_logs_ui()

        def reset_audit_log_filters():
            audit_log_filter_settings["column"] = "all"
            audit_log_filter_settings["match_mode"] = "contains"
            audit_log_filter_settings["notification_type"] = "all"
            audit_log_filter_settings["sort_col"] = "id"
            audit_log_filter_settings["sort_dir"] = "DESC"
            audit_log_filter_settings["start_date"] = ""
            audit_log_filter_settings["end_date"] = ""

            combo_log_type.set("همه")
            update_audit_log_filter_indicator()
            popup.destroy()
            load_notification_logs_ui()

        btn_apply = create_icon_button_fn(
            action_frame,
            text=" اعمال فیلتر ",
            icon_name="check",
            font=font_bold,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            command=apply_audit_log_filters,
        )
        btn_apply.pack(side=tk.RIGHT, padx=4)

        btn_reset = create_icon_button_fn(
            action_frame,
            text=" تنظیم مجدد ",
            icon_name="rotate-ccw",
            font=font_normal,
            fg_color="transparent",
            hover_color=("#e2e8f0", "#1e293b"),
            command=reset_audit_log_filters,
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

    btn_filter_logs = create_icon_button_fn(
        filter_row,
        text=" فیلترها ",
        icon_name="filter",
        font=font_normal,
        command=open_audit_log_filter_popup,
        width=85,
        height=32,
    )
    btn_filter_logs.pack(side=tk.RIGHT, padx=4)

    def refresh_notification_logs():
        entry_log_search.delete(0, tk.END)
        combo_log_type.set("همه")
        audit_log_filter_settings["column"] = "all"
        audit_log_filter_settings["match_mode"] = "contains"
        audit_log_filter_settings["notification_type"] = "all"
        audit_log_filter_settings["sort_col"] = "id"
        audit_log_filter_settings["sort_dir"] = "DESC"
        audit_log_filter_settings["start_date"] = ""
        audit_log_filter_settings["end_date"] = ""
        update_audit_log_filter_indicator()
        load_notification_logs_ui()

    btn_refresh_logs = create_icon_button_fn(
        filter_row,
        text=" تازه‌سازی ",
        icon_name="rotate-ccw",
        font=font_normal,
        fg_color="transparent",
        hover_color=("#e2e8f0", "#1e293b"),
        command=refresh_notification_logs,
        width=90,
        height=32,
    )
    btn_refresh_logs.pack(side=tk.RIGHT, padx=4)

    def clear_logs_ui():
        confirm = messagebox.askyesno(
            "تأیید پاک‌سازی",
            "آیا از پاک‌سازی تمام تاریخچه اعلان‌ها اطمینان دارید؟ این عملیات غیرقابل بازگشت است.",
            parent=root,
        )
        if not confirm:
            return
        try:
            deleted = clear_notification_logs(db_path)
            refresh_notification_logs()
            messagebox.showinfo("موفقیت", f"تعداد {deleted} رکورد از تاریخچه اعلان‌ها پاک شد.", parent=root)
        except Exception as e:
            messagebox.showerror("خطا", f"خطا در پاک‌سازی تاریخچه:\n{e}", parent=root)

    btn_clear_logs = create_icon_button_fn(
        filter_row,
        text=" پاک‌سازی تاریخچه ",
        icon_name="x",
        font=font_normal,
        fg_color="#dc2626",
        hover_color="#b91c1c",
        command=clear_logs_ui,
        width=130,
        height=32,
    )
    btn_clear_logs.pack(side=tk.LEFT, padx=5)

    log_columns = ["id", "notification_type", "book_title", "member_name", "loan_id", "sent_date", "created_at"]

    log_tree_frame = ctk.CTkFrame(log_card, corner_radius=8)
    log_tree_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 12))

    log_scrollbar = ctk.CTkScrollbar(log_tree_frame)
    log_scrollbar.pack(side=tk.LEFT, fill=tk.Y, padx=(4, 0), pady=4)

    log_tree = ttk.Treeview(
        log_tree_frame,
        yscrollcommand=log_scrollbar.set,
        columns=log_columns,
        show="headings",
        height=9,
    )
    log_scrollbar.configure(command=log_tree.yview)

    for col in log_columns:
        log_tree.heading(col, text=tr(col), anchor=tk.CENTER)
        log_tree.column(col, anchor=tk.CENTER)

    log_tree.column("id", width=50, stretch=False)
    log_tree.column("notification_type", width=120)
    log_tree.column("book_title", width=160)
    log_tree.column("member_name", width=130)
    log_tree.column("loan_id", width=70, stretch=False)
    log_tree.column("sent_date", width=95)
    log_tree.column("created_at", width=135)

    log_tree["displaycolumns"] = rtl_display_order(
        log_columns, ["id", "notification_type", "book_title", "member_name", "loan_id", "sent_date", "created_at"]
    )
    log_tree.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(4, 8), pady=4)

    def update_audit_log_filter_indicator():
        is_custom = (
            audit_log_filter_settings["column"] != "all"
            or audit_log_filter_settings["match_mode"] != "contains"
            or audit_log_filter_settings["notification_type"] != "all"
            or audit_log_filter_settings["sort_col"] != "id"
            or audit_log_filter_settings["sort_dir"] != "DESC"
            or bool(audit_log_filter_settings.get("start_date"))
            or bool(audit_log_filter_settings.get("end_date"))
        )
        if is_custom:
            btn_filter_logs.configure(text=" فیلترها (فعال) ", fg_color="#2563eb")
        else:
            btn_filter_logs.configure(text=" فیلترها ", fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"])

    def load_notification_logs_ui():
        for item in log_tree.get_children():
            log_tree.delete(item)

        search_kw = entry_log_search.get().strip()
        raw_type = audit_log_filter_settings.get("notification_type", "all")
        type_filter = None if raw_type == "all" else raw_type

        col_filter = audit_log_filter_settings.get("column", "all")
        mode_filter = audit_log_filter_settings.get("match_mode", "contains")
        s_col = audit_log_filter_settings.get("sort_col", "id")
        s_dir = audit_log_filter_settings.get("sort_dir", "DESC")
        start_d = audit_log_filter_settings.get("start_date", "").strip() or None
        end_d = audit_log_filter_settings.get("end_date", "").strip() or None

        try:
            logs = get_notification_logs(
                conn_or_path=db_path,
                notification_type=type_filter,
                start_date=start_d,
                end_date=end_d,
                search_query=search_kw if search_kw else None,
                column=col_filter,
                match_mode=mode_filter,
                sort_col=s_col,
                sort_dir=s_dir,
                limit=200,
            )
            if not logs:
                log_tree.insert("", tk.END, values=("❌ هیچ رکوردی یافت نشد", "", "", "", "", "", ""))
                return

            type_map = {
                "due_reminder": "یادآوری سررسید",
                "due_soon": "یادآوری سررسید",
                "due_today": "یادآوری سررسید",
                "overdue": "هشدار دیرکرد",
                "test": "اعلان آزمایشی",
            }

            for row in logs:
                raw_type_row = row.get("notification_type", "")
                type_text = type_map.get(raw_type_row, tr(raw_type_row))
                loan_id_val = str(row.get("loan_id") or "-")
                book_val = str(row.get("book_title") or "-")
                member_val = str(row.get("member_name") or "-")
                sent_val = _format_shamsi_date(row.get("sent_date", ""))
                created_val = _format_shamsi_date(row.get("created_at", ""))

                vals = (
                    row.get("id"),
                    type_text,
                    book_val,
                    member_val,
                    loan_id_val,
                    sent_val,
                    created_val,
                )
                log_tree.insert("", tk.END, values=vals)
        except Exception as e:
            log_tree.insert("", tk.END, values=(f"❌ خطا: {e}", "", "", "", "", "", ""))

    audit_log_search_after_id = [None]

    def on_log_search_key_release(event=None):
        if event and event.keysym in ("Up", "Down", "Left", "Right", "Return", "Escape"):
            return
        if audit_log_search_after_id[0] is not None:
            try:
                root.after_cancel(audit_log_search_after_id[0])
            except Exception:
                pass
        audit_log_search_after_id[0] = root.after(200, load_notification_logs_ui)

    entry_log_search.bind("<KeyRelease>", on_log_search_key_release)
    entry_log_search.bind("<Return>", lambda e: load_notification_logs_ui())

    def load_settings_into_ui():
        try:
            with get_db_connection(db_path) as conn:
                settings = get_all_settings(conn)

            n_en = settings.get("notifications_enabled", "true").lower() == "true"
            s_en = settings.get("notification_sound", "true").lower() == "true"
            net_en = settings.get("internet_access_enabled", "true").lower() == "true"
            ai_en = settings.get("ai_features_enabled", "true").lower() == "true"
            adv = settings.get("notification_advance_days", "2")
            inv = settings.get("notification_check_interval_mins", "30")
            mln = int(settings.get("max_loans", "2"))
            combo_max_loans.set(str(mln))

            var_notif_enabled.set(n_en)
            var_notif_sound.set(s_en)
            var_internet_enabled.set(net_en)
            if not net_en:
                var_ai_enabled.set(False)
                chk_enable_ai.configure(state="disabled")
            else:
                var_ai_enabled.set(ai_en)
                chk_enable_ai.configure(state="normal")

            otp_en = settings.get("otp_cleanup_enabled", "true").lower() == "true"
            otp_int = settings.get("otp_cleanup_interval_hours", "12")
            var_otp_cleanup_enabled.set(otp_en)
            if otp_int in ["1", "3", "6", "12", "24", "48"]:
                combo_otp_interval.set(otp_int)
            else:
                combo_otp_interval.set("12")

            update_boot_net_status_label()
            update_ai_card_inputs_state(enabled=(net_en and ai_en))

            if adv in ["1", "2", "3", "5", "7"]:
                combo_advance_days.set(adv)
            else:
                combo_advance_days.set("2")

            if inv in ["15", "30", "60", "120", "360"]:
                combo_interval.set(inv)
            else:
                combo_interval.set("30")

            r_url = settings.get("openai_url") or "http://localhost:20128"
            r_key = settings.get("openai_key") or ""
            r_model = settings.get("openai_model") or "gemini-3.8-flash"

            entry_ai_url.delete(0, tk.END)
            entry_ai_url.insert(0, r_url)

            entry_ai_key.delete(0, tk.END)
            entry_ai_key.insert(0, r_key)

            entry_ai_model.delete(0, tk.END)
            entry_ai_model.insert(0, r_model)
        except Exception:
            pass

    load_settings_into_ui()
    load_notification_logs_ui()

    return {
        "load_settings_into_ui": load_settings_into_ui,
        "load_notification_logs_ui": load_notification_logs_ui,
        "refresh_notification_logs": refresh_notification_logs,
    }
