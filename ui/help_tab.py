"""
Help and About view for Bager Library.
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import tkinter as tk
import webbrowser
from tkinter import messagebox
from typing import Any, Callable

import customtkinter as ctk

from persian_calendar import to_persian_digits
from services.contributor_service import get_contributors_stats
from updater import (
    DownloadManager,
    UpdateChecker,
    apply_update,
    format_size,
    format_speed,
    load_app_info,
)


def build_help_tab(
    parent: ctk.CTkFrame,
    root: ctk.CTk,
    fonts: dict[str, Any],
    get_icon_fn: Callable[..., Any],
    create_icon_button_fn: Callable[..., Any],
    is_internet_access_enabled_fn: Callable[..., bool],
    db_path: str,
) -> dict[str, Any]:
    """
    Builds the Help & About scrollable tab and returns controllers for startup update checking.
    """
    # ponytail: builds inline help ui; upgrade to standalone docs viewer if full offline user manual added
    font_family = fonts.get("family", "IRANSans")
    font_header = fonts.get("header")
    font_normal = fonts.get("normal")
    font_bold = fonts.get("bold")
    font_small = fonts.get("small")

    help_scroll = ctk.CTkScrollableFrame(parent, corner_radius=10, fg_color="transparent")
    help_scroll.pack(fill=tk.BOTH, expand=True, padx=12, pady=(8, 8))

    def open_url(url: str):
        try:
            webbrowser.open(url)
        except Exception as e:
            messagebox.showerror("خطا", f"امکان باز کردن پیوند در مرورگر وجود ندارد:\n{e}", parent=root)

    app_info = load_app_info()
    app_version = app_info.get("version", "0.1.0")
    update_checker = UpdateChecker(
        repo=app_info.get("github_repo", "amirkabir18/bager_library"),
        current_version=app_version,
    )
    download_manager = DownloadManager()
    latest_update_info: dict = {}

    # --- 1. Hero Identity Banner ---
    hero_banner = ctk.CTkFrame(
        help_scroll,
        corner_radius=12,
        border_width=1,
        border_color=("#e2e8f0", "#334155"),
        fg_color=("#f8fafc", "#1e293b"),
    )
    hero_banner.pack(fill=tk.X, pady=(0, 12), padx=2)

    hero_content = ctk.CTkFrame(hero_banner, fg_color="transparent")
    hero_content.pack(fill=tk.X, padx=20, pady=16)

    ctk.CTkLabel(
        hero_content,
        text="کتابخانه باقر العلوم (ع)",
        font=ctk.CTkFont(family=font_family, size=18, weight="bold"),
        text_color=("#0f172a", "#f8fafc"),
        anchor="e",
    ).pack(fill=tk.X)

    ctk.CTkLabel(
        hero_content,
        text="سامانه یکپارچه مدیریت مخزن کتاب، رده‌بندی دهدهی دیویی (DDC)، گردش امانات و اعلان‌های رومیزی",
        font=font_normal,
        text_color=("#475569", "#94a3b8"),
        anchor="e",
    ).pack(fill=tk.X, pady=(4, 12))

    badges_row = ctk.CTkFrame(hero_content, fg_color="transparent")
    badges_row.pack(fill=tk.X)

    def make_badge(p, text, bg_color, text_color):
        return ctk.CTkLabel(
            p,
            text=f"  {text}  ",
            font=font_small,
            fg_color=bg_color,
            text_color=text_color,
            corner_radius=6,
            height=24,
        )

    make_badge(badges_row, f"نسخه {app_version}", ("#dbeafe", "#1e3a8a"), ("#1d4ed8", "#93c5fd")).pack(
        side=tk.RIGHT, padx=(0, 6)
    )
    make_badge(badges_row, "🟢 سیستم آماده به کار", ("#dcfce7", "#064e3b"), ("#15803d", "#6ee7b7")).pack(
        side=tk.RIGHT, padx=6
    )
    make_badge(badges_row, "⚡ پایگاه داده محلی SQLite", ("#f3e8ff", "#581c87"), ("#7e22ce", "#d8b4fe")).pack(
        side=tk.RIGHT, padx=6
    )
    make_badge(badges_row, "🔔 موتور اعلان ویندوز", ("#fef3c7", "#78350f"), ("#b45309", "#fde68a")).pack(
        side=tk.RIGHT, padx=6
    )

    # --- 2. Guide Cards Section ---
    guide_box = ctk.CTkFrame(
        help_scroll,
        corner_radius=12,
        border_width=1,
        border_color=("#e2e8f0", "#334155"),
        fg_color=("#ffffff", "#1e293b"),
    )
    guide_box.pack(fill=tk.X, pady=(0, 12), padx=2)

    guide_header = ctk.CTkFrame(guide_box, fg_color="transparent")
    guide_header.pack(fill=tk.X, padx=18, pady=(12, 6))
    ctk.CTkLabel(
        guide_header,
        text=" راهنمای بخش‌های سامانه ",
        font=font_header,
        text_color=("#0f172a", "#f8fafc"),
        anchor="e",
    ).pack(side=tk.RIGHT)

    cards_container = ctk.CTkFrame(guide_box, fg_color="transparent")
    cards_container.pack(fill=tk.X, padx=12, pady=(0, 12))
    cards_container.columnconfigure((0, 1), weight=1, uniform="guide")

    guide_features = [
        (
            "📚 مخزن کتاب و رده‌بندی دیویی (DDC)",
            "• استعلام برخط شابک (ISBN) از پایگاه‌های Open Library و Google Books.\n"
            "• طبقه‌بندی خودکار در رده‌های ده‌گانه دیویی (۰۰۰ تا ۹۰۰) با خط لوله هوشمند.\n"
            "• پشتیبانی از رده دستی (Manual) بدون تغییر در رده‌بندی خودکار دسته‌ای.\n"
            "• محاسبه خودکار و پیشنهاد دقیق محل فیزیکی کتاب در قفسه‌های کتابخانه.",
            0,
            0,
        ),
        (
            "🔄 میز امانت و گردش کتاب (Circulation)",
            "• ثبت سریع امانت با جستجوی هوشمند و تکمیل خودکار نام عضو و عنوان کتاب.\n"
            "• پشتیبانی کامل از تقویم خورشیدی (جلالی) و محاسبه موعد بازگشت و دیرکرد.\n"
            "• تسویه و ثبت بازگشت فوری کتاب تنها با دابل‌کلیک روی ردیف در جدول امانات.\n"
            "• قابلیت تمدید امانت، ثبت یادداشت و فیلتر کتاب‌های در امانت یا موجود.",
            0,
            1,
        ),
        (
            "👥 مدیریت اعضا و کاربران سامانه",
            "• تشکیل پرونده اعضا با شناسه یکتا و نرمال‌سازی شماره همراه ایران (+98 / 09).\n"
            "• کنترل سطح دسترسی با نقش‌های: سرپرست کل (Super Admin)، مدیر و کتابدار.\n"
            "• رمزنگاری امن کلمات عبور با استاندارد PBKDF2 با ۱۰۰٬۰۰۰ دور تکرار.\n"
            "• احراز هویت دومرحله‌ای با رمز عبور و ارسال کد یکبار مصرف (OTP) با تلگرام.",
            1,
            0,
        ),
        (
            "🔔 سامانه اعلان‌ها و هشدارهای رومیزی",
            "• موتور اعلان ۱۰۰٪ محلی و بدون نیاز به اینترنت برای ویندوز ۱۰ و ۱۱.\n"
            "• پایش خودکار با دیمن پس‌زمینه در بازه‌های ۱۵، ۳۰، ۶۰ یا ۱۲۰ دقیقه‌ای.\n"
            "• تفکیک هشدارهای پیش از موعد (Due Soon) و تاخیر (Overdue) با صدای زنگ.\n"
            "• پنجره شناور اختصاصی (Toast) و ثبت دقیق تاریخچه در دفتر لاگ اعلان‌ها.",
            1,
            1,
        ),
    ]

    for title, desc, r, c in guide_features:
        f_card = ctk.CTkFrame(
            cards_container,
            corner_radius=10,
            fg_color=("#f8fafc", "#0f172a"),
            border_width=1,
            border_color=("#e2e8f0", "#334155"),
        )
        f_card.grid(row=r, column=c, padx=6, pady=6, sticky="nsew")

        ctk.CTkLabel(
            f_card,
            text=title,
            font=font_bold,
            text_color=("#2563eb", "#38bdf8"),
            anchor="e",
        ).pack(fill=tk.X, padx=12, pady=(10, 4))

        ctk.CTkLabel(
            f_card,
            text=desc,
            font=font_small,
            text_color=("#334155", "#cbd5e1"),
            justify="right",
            anchor="e",
        ).pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 10))

    # --- 3. Keyboard Shortcuts Ribbon ---
    shortcut_box = ctk.CTkFrame(
        help_scroll,
        corner_radius=12,
        border_width=1,
        border_color=("#e2e8f0", "#334155"),
        fg_color=("#ffffff", "#1e293b"),
    )
    shortcut_box.pack(fill=tk.X, pady=(0, 12), padx=2)

    shortcut_header = ctk.CTkFrame(shortcut_box, fg_color="transparent")
    shortcut_header.pack(fill=tk.X, padx=18, pady=(12, 6))
    ctk.CTkLabel(
        shortcut_header,
        text=" کلیدهای میانبر و ترفندهای کاربری سریع ",
        font=font_header,
        text_color=("#0f172a", "#f8fafc"),
        anchor="e",
    ).pack(side=tk.RIGHT)

    shortcuts_row = ctk.CTkFrame(shortcut_box, fg_color="transparent")
    shortcuts_row.pack(fill=tk.X, padx=12, pady=(0, 12))
    shortcuts_row.columnconfigure((0, 1, 2, 3, 4), weight=1, uniform="sc")

    shortcut_items = [
        ("Enter", "جستجوی فوری در جدول"),
        ("Delete", "حذف ردیف انتخاب‌شده"),
        ("دابل‌کلیک", "امانت / ثبت برگشت"),
        ("کلیک راست", "منوی عملیات ویژه"),
        ("Esc", "بستن پنجره‌ها و دیالوگ‌ها"),
    ]

    for idx, (key_label, desc_label) in enumerate(shortcut_items):
        sc_item = ctk.CTkFrame(
            shortcuts_row,
            corner_radius=8,
            fg_color=("#f8fafc", "#0f172a"),
            border_width=1,
            border_color=("#e2e8f0", "#334155"),
        )
        sc_item.grid(row=0, column=idx, padx=4, pady=4, sticky="nsew")

        key_badge = ctk.CTkLabel(
            sc_item,
            text=f" {key_label} ",
            font=font_bold,
            fg_color=("#e2e8f0", "#334155"),
            text_color=("#0f172a", "#f8fafc"),
            corner_radius=6,
            height=26,
        )
        key_badge.pack(pady=(8, 4), padx=6)

        ctk.CTkLabel(
            sc_item,
            text=desc_label,
            font=font_small,
            text_color=("#475569", "#94a3b8"),
            justify="center",
        ).pack(pady=(0, 8), padx=4)

    # --- 4. Software Update Center ---
    update_group = ctk.CTkFrame(
        help_scroll,
        corner_radius=12,
        border_width=1,
        border_color=("#e2e8f0", "#334155"),
        fg_color=("#ffffff", "#1e293b"),
    )
    update_group.pack(fill=tk.X, pady=(0, 12), padx=2)

    update_title = ctk.CTkLabel(
        update_group,
        text=" مرکز بروزرسانی نرم‌افزار ",
        font=font_header,
        text_color=("#0f172a", "#f8fafc"),
        anchor="e",
    )
    update_title.pack(fill=tk.X, padx=18, pady=(12, 6))

    info_row = ctk.CTkFrame(update_group, fg_color="transparent")
    info_row.pack(fill=tk.X, padx=18, pady=4)

    lbl_current_ver = ctk.CTkLabel(
        info_row,
        text=f"نسخه فعلی: {app_version}",
        font=font_bold,
        text_color=("#2563eb", "#38bdf8"),
        anchor="e",
    )
    lbl_current_ver.pack(side=tk.RIGHT, padx=(0, 15))

    lbl_update_status = ctk.CTkLabel(
        info_row,
        text="وضعیت: در حال بررسی...",
        font=font_normal,
        text_color="#38bdf8",
        anchor="e",
    )
    lbl_update_status.pack(side=tk.RIGHT, padx=5)

    progress_row = ctk.CTkFrame(update_group, fg_color="transparent")

    update_progress = ctk.CTkProgressBar(progress_row, mode="determinate", height=10, corner_radius=5)
    update_progress.set(0.0)
    update_progress.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10, 0))

    lbl_progress_text = ctk.CTkLabel(
        progress_row,
        text="",
        font=font_small,
        text_color="#94a3b8",
        width=180,
        anchor="w",
    )
    lbl_progress_text.pack(side=tk.LEFT, padx=(0, 5))

    actions_row = ctk.CTkFrame(update_group, fg_color="transparent")
    actions_row.pack(fill=tk.X, padx=18, pady=(6, 12))

    def on_check_finished(res: dict, interactive: bool):
        latest_update_info.clear()
        latest_update_info.update(res)

        if res.get("update_available"):
            latest_ver = res.get("latest_version", "")
            lbl_update_status.configure(
                text=f"وضعیت: نسخه جدید {latest_ver} موجود است!",
                text_color="#16a34a",
            )
            btn_update_action.configure(
                state="normal",
                text=f" دریافت و نصب نسخه {latest_ver} ",
                command=start_update_download,
            )
            btn_update_action.pack(side=tk.RIGHT, padx=5)
            if interactive:
                messagebox.showinfo(
                    "بروزرسانی جدید",
                    f"نسخه جدید «{latest_ver}» در دسترس است.\nبرای دریافت و نصب، روی دکمه «دریافت و نصب» کلیک کنید.",
                    parent=root,
                )
        else:
            lbl_update_status.configure(
                text="وضعیت: نرم‌افزار به‌روز است.",
                text_color="#16a34a",
            )
            progress_row.pack_forget()
            btn_update_action.pack_forget()
            btn_cancel_update.pack_forget()
            if interactive:
                messagebox.showinfo("بروزرسانی", "نرم‌افزار شما به‌روز است.", parent=root)

    def on_check_failed(error_msg: str, interactive: bool):
        progress_row.pack_forget()
        btn_cancel_update.pack_forget()
        if interactive:
            btn_update_action.configure(
                state="normal",
                text=" تلاش مجدد برای بررسی ",
                command=lambda: perform_check(interactive=True),
            )
            btn_update_action.pack(side=tk.RIGHT, padx=5)
            lbl_update_status.configure(text="وضعیت: خطا در بررسی بروزرسانی", text_color="#dc2626")
            messagebox.showerror(
                "خطا در بررسی بروزرسانی", f"خطا در ارتباط با سرور بروزرسانی:\n{error_msg}", parent=root
            )
        else:
            btn_update_action.pack_forget()
            lbl_update_status.configure(text="وضعیت: نرم‌افزار به‌روز است.", text_color="#16a34a")

    def perform_check(interactive: bool = True):
        if not is_internet_access_enabled_fn(db_path):
            if interactive:
                messagebox.showwarning(
                    "دسترسی به اینترنت",
                    "دسترسی به اینترنت در تنظیمات برنامه غیرفعال شده است.",
                    parent=root,
                )
            lbl_update_status.configure(text="وضعیت: دسترسی به اینترنت در تنظیمات غیرفعال است.", text_color="#dc2626")
            return

        lbl_update_status.configure(text="وضعیت: در حال بررسی آخرین نسخه...", text_color="#38bdf8")
        btn_update_action.configure(state="disabled")

        def _worker():
            try:
                res = update_checker.check()
                root.after(0, lambda: on_check_finished(res, interactive))
            except Exception as ex:
                err_str = str(ex)
                root.after(0, lambda: on_check_failed(err_str, interactive))

        threading.Thread(target=_worker, daemon=True).start()

    def start_update_download():
        download_url = latest_update_info.get("download_url")
        if not download_url:
            messagebox.showerror("خطا", "آدرس دانلود فایل بروزرسانی یافت نشد.", parent=root)
            return

        dest_path = os.path.join(tempfile.gettempdir(), "bager_library_new.exe")
        btn_update_action.configure(state="disabled")
        btn_cancel_update.pack(side=tk.RIGHT, padx=5)
        lbl_update_status.configure(text="وضعیت: در حال دانلود فایل بروزرسانی...", text_color="#38bdf8")
        progress_row.pack(fill=tk.X, padx=18, pady=4, before=actions_row)
        update_progress.set(0.0)

        def _update_prog_ui(downloaded, total, pct, speed):
            update_progress.set(min(1.0, max(0.0, pct / 100.0)))
            speed_str = format_speed(speed)
            down_str = format_size(downloaded)
            total_str = format_size(total) if total > 0 else "نامشخص"
            lbl_progress_text.configure(text=f"{pct:.0f}% ({down_str} / {total_str}) {speed_str}")

        def _prompt_install(path):
            confirm = messagebox.askyesno(
                "نصب بروزرسانی",
                "دانلود نسخه جدید کامل شد.\nآیا مایلید برنامه بسته شده و نسخه جدید اجرا شود؟",
                parent=root,
            )
            if confirm:
                try:
                    applied = apply_update(path)
                    if applied:
                        root.destroy()
                        sys.exit(0)
                    else:
                        messagebox.showinfo(
                            "اطلاع",
                            f"برنامه در محیط توسعه پایتون در حال اجراست.\nفایل نصبی جدید در مسیر زیر ذخیره شد:\n{path}",
                            parent=root,
                        )
                except Exception as e:
                    messagebox.showerror("خطا در نصب بروزرسانی", f"خطا در جایگزینی فایل:\n{e}", parent=root)

        def _finish_download_ui(path):
            btn_cancel_update.pack_forget()
            btn_update_action.configure(
                state="normal",
                text=" نصب بروزرسانی ",
                command=lambda: _prompt_install(path),
            )
            btn_update_action.pack(side=tk.RIGHT, padx=5)
            update_progress.set(1.0)
            lbl_update_status.configure(text="وضعیت: دانلود با موفقیت انجام شد.", text_color="#16a34a")
            lbl_progress_text.configure(text="دانلود کامل شد")
            _prompt_install(path)

        def _error_download_ui(err):
            btn_cancel_update.pack_forget()
            btn_update_action.configure(
                state="normal",
                text=" تلاش مجدد برای دریافت ",
                command=start_update_download,
            )
            btn_update_action.pack(side=tk.RIGHT, padx=5)
            lbl_update_status.configure(text="وضعیت: خطا در دانلود بروزرسانی", text_color="#dc2626")
            messagebox.showerror("خطا در دانلود", f"خطا در حین دانلود فایل بروزرسانی:\n{err}", parent=root)

        def _cancelled_download_ui():
            btn_cancel_update.pack_forget()
            btn_update_action.configure(
                state="normal",
                text=" دریافت و نصب نسخه جدید ",
                command=start_update_download,
            )
            btn_update_action.pack(side=tk.RIGHT, padx=5)
            progress_row.pack_forget()
            update_progress.set(0.0)
            lbl_progress_text.configure(text="")
            lbl_update_status.configure(text="وضعیت: دانلود لغو شد.", text_color="#64748b")

        download_manager.download_async(
            url=download_url,
            dest_path=dest_path,
            on_progress=lambda d, t, p, s: root.after(0, lambda: _update_prog_ui(d, t, p, s)),
            on_finished=lambda p: root.after(0, lambda: _finish_download_ui(p)),
            on_error=lambda err: root.after(0, lambda: _error_download_ui(err)),
            on_cancelled=lambda: root.after(0, _cancelled_download_ui),
        )

    btn_update_action = create_icon_button_fn(
        actions_row,
        text=" بررسی بروزرسانی ",
        icon_name="refresh-cw",
        font=font_bold,
        fg_color="#2563eb",
        hover_color="#1d4ed8",
        command=lambda: perform_check(interactive=True),
        width=150,
        height=34,
    )
    btn_update_action.pack(side=tk.RIGHT, padx=5)

    btn_cancel_update = create_icon_button_fn(
        actions_row,
        text=" لغو دانلود ",
        icon_name="x",
        font=font_normal,
        fg_color="transparent",
        hover_color=("#e2e8f0", "#1e293b"),
        command=download_manager.cancel,
        width=110,
        height=34,
    )

    # --- 5. Team & Community Section ---
    dev_box = ctk.CTkFrame(
        help_scroll,
        corner_radius=12,
        border_width=1,
        border_color=("#e2e8f0", "#334155"),
        fg_color=("#ffffff", "#1e293b"),
    )
    dev_box.pack(fill=tk.X, pady=(0, 10), padx=2)

    dev_box_header = ctk.CTkFrame(dev_box, fg_color="transparent")
    dev_box_header.pack(fill=tk.X, padx=18, pady=(12, 6))
    ctk.CTkLabel(
        dev_box_header,
        text=" تیم توسعه و مشارکت‌کنندگان متن‌باز ",
        font=font_header,
        text_color=("#0f172a", "#f8fafc"),
        anchor="e",
    ).pack(side=tk.RIGHT)

    devs_container = ctk.CTkFrame(dev_box, fg_color="transparent")
    devs_container.pack(fill=tk.X, padx=14, pady=(2, 10))

    def render_contributor_cards(contributors: list[dict]):
        for child in devs_container.winfo_children():
            child.destroy()

        if not contributors:
            return

        devs_container.columnconfigure(0, weight=1, uniform="dev_boxes")
        devs_container.columnconfigure(1, weight=1, uniform="dev_boxes")

        box_style = {
            "corner_radius": 8,
            "fg_color": ("#f8fafc", "#0f172a"),
            "border_width": 1,
            "border_color": ("#e2e8f0", "#334155"),
        }

        left_box = ctk.CTkFrame(devs_container, **box_style)
        left_box.grid(row=0, column=0, padx=(0, 6), pady=4, sticky="nsew")

        left_header = ctk.CTkFrame(left_box, fg_color="transparent")
        left_header.pack(fill=tk.X, padx=14, pady=(10, 8))
        ctk.CTkLabel(
            left_header,
            text=" فهرست مشارکت‌کنندگان ",
            font=font_bold,
            text_color=("#0f172a", "#f8fafc"),
            image=get_icon_fn("user", size=(15, 15)),
            compound="right",
        ).pack(side=tk.RIGHT)

        right_box = ctk.CTkFrame(devs_container, **box_style)
        right_box.grid(row=0, column=1, padx=(6, 0), pady=4, sticky="nsew")

        right_header = ctk.CTkFrame(right_box, fg_color="transparent")
        right_header.pack(fill=tk.X, padx=14, pady=(10, 8))
        ctk.CTkLabel(
            right_header,
            text=" سهم مشارکت در کد پروژه ",
            font=font_bold,
            text_color=("#0f172a", "#f8fafc"),
            image=get_icon_fn("bookmark", size=(15, 15)),
            compound="right",
        ).pack(side=tk.RIGHT)

        stat_content = ctk.CTkFrame(right_box, fg_color="transparent")
        stat_content.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 10))

        top_row = ctk.CTkFrame(stat_content, fg_color="transparent")
        top_row.pack(fill=tk.X, pady=(2, 6))

        lbl_percent = ctk.CTkLabel(
            top_row,
            text="",
            font=ctk.CTkFont(family=font_family, size=24, weight="bold"),
            text_color=("#16a34a", "#22c55e"),
            anchor="w",
        )
        lbl_percent.pack(side=tk.LEFT)

        name_col = ctk.CTkFrame(top_row, fg_color="transparent")
        name_col.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        lbl_name = ctk.CTkLabel(
            name_col,
            text="",
            font=font_bold,
            text_color=("#0f172a", "#f8fafc"),
            anchor="e",
        )
        lbl_name.pack(fill=tk.X)

        lbl_role = ctk.CTkLabel(
            name_col,
            text="",
            font=font_small,
            text_color=("#64748b", "#94a3b8"),
            anchor="e",
        )
        lbl_role.pack(fill=tk.X)

        progress_bar = ctk.CTkProgressBar(
            stat_content,
            height=12,
            corner_radius=6,
            progress_color=("#16a34a", "#22c55e"),
            fg_color=("#e2e8f0", "#334155"),
        )
        progress_bar.pack(fill=tk.X, pady=(6, 8))

        meta_row = ctk.CTkFrame(stat_content, fg_color="transparent")
        meta_row.pack(fill=tk.X, pady=(2, 4))

        lbl_lines = ctk.CTkLabel(
            meta_row,
            text="",
            font=font_small,
            text_color=("#0f172a", "#f8fafc"),
            anchor="e",
        )
        lbl_lines.pack(side=tk.RIGHT)

        lbl_rank = ctk.CTkLabel(
            meta_row,
            text="",
            font=font_small,
            text_color=("#2563eb", "#38bdf8"),
            anchor="w",
        )
        lbl_rank.pack(side=tk.LEFT)

        lbl_hint = ctk.CTkLabel(
            stat_content,
            text="جهت مشاهده سهم هر توسعه‌دهنده، روی ردیف او در فهرست کلیک کنید.",
            font=font_small,
            text_color=("#64748b", "#94a3b8"),
            anchor="center",
        )
        lbl_hint.pack(fill=tk.X, pady=(6, 2))

        item_frames = []

        def select_contributor(target_idx: int):
            if target_idx < 0 or target_idx >= len(contributors):
                return
            c_item = contributors[target_idx]
            c_name = c_item.get("name") or c_item.get("login") or "توسعه‌دهنده"
            c_login = c_item.get("login", "")
            c_percent = float(c_item.get("percent", 0.0) or 0.0)
            c_lines = int(c_item.get("lines_added", 0) or 0)
            p_str = f"{to_persian_digits(f'{c_percent:.1f}')}٪"
            r_str = to_persian_digits(target_idx + 1)

            lbl_percent.configure(text=p_str)
            lbl_name.configure(text=c_name)
            lbl_role.configure(text=f"@{c_login} • سهم از کل کد مخزن")
            progress_bar.set(max(0.0, min(1.0, c_percent / 100.0)))

            if c_lines > 0:
                lines_str = to_persian_digits(f"{c_lines:,}")
                lbl_lines.configure(text=f"سطرهای افزوده: {lines_str} سطر")
            else:
                lbl_lines.configure(text="ثبت در آمار مشارکت‌کنندگان")

            lbl_rank.configure(text=f"رتبه {r_str} در مشارکت")

            for i, f in enumerate(item_frames):
                if i == target_idx:
                    f.configure(
                        fg_color=("#e2e8f0", "#1e293b"),
                        border_color=("#2563eb", "#38bdf8"),
                    )
                else:
                    f.configure(
                        fg_color=("#ffffff", "#1e293b"),
                        border_color=("#e2e8f0", "#334155"),
                    )

        for idx, c in enumerate(contributors):
            row_card = ctk.CTkFrame(
                left_box,
                corner_radius=6,
                fg_color=("#ffffff", "#1e293b"),
                border_width=1,
                border_color=("#e2e8f0", "#334155"),
                cursor="hand2",
            )
            row_card.pack(fill=tk.X, padx=10, pady=3)
            item_frames.append(row_card)

            rank_str = to_persian_digits(idx + 1)
            name = c.get("name") or c.get("login") or "توسعه‌دهنده"
            handle = f"@{c.get('login', '')}"
            percent = float(c.get("percent", 0.0) or 0.0)
            percent_str = f"{to_persian_digits(f'{percent:.1f}')}٪"
            profile_url = c.get("html_url") or f"https://github.com/{c.get('login', '')}"

            ctk.CTkButton(
                row_card,
                text=handle,
                font=font_small,
                fg_color="transparent",
                text_color=("#2563eb", "#38bdf8"),
                hover_color=("#e2e8f0", "#334155"),
                height=24,
                width=75,
                command=lambda u=profile_url: open_url(u),
            ).pack(side=tk.LEFT, padx=(6, 2), pady=4)

            ctk.CTkLabel(
                row_card,
                text=percent_str,
                font=font_bold,
                text_color=("#16a34a", "#4ade80") if percent > 0 else ("#64748b", "#94a3b8"),
                width=46,
                anchor="center",
            ).pack(side=tk.LEFT, padx=2)

            name_lbl = ctk.CTkLabel(
                row_card,
                text=name,
                font=font_normal,
                text_color=("#0f172a", "#f8fafc"),
                anchor="e",
            )
            name_lbl.pack(side=tk.RIGHT, padx=(0, 6), fill=tk.X, expand=True)

            rank_badge = ctk.CTkLabel(
                row_card,
                text=f" {rank_str} ",
                font=font_small,
                fg_color=("#e2e8f0", "#334155"),
                text_color=("#0f172a", "#f8fafc"),
                corner_radius=4,
                height=20,
                width=22,
            )
            rank_badge.pack(side=tk.RIGHT, padx=(6, 2))

            def _make_handler(target=idx):
                return lambda e: select_contributor(target)

            row_card.bind("<Button-1>", _make_handler(idx))
            name_lbl.bind("<Button-1>", _make_handler(idx))
            rank_badge.bind("<Button-1>", _make_handler(idx))

        select_contributor(0)

    def load_contributors_async():
        initial_data = get_contributors_stats(cache_ttl=86400)
        render_contributor_cards(initial_data)

        if not is_internet_access_enabled_fn(db_path):
            return

        def _worker():
            try:
                data = get_contributors_stats(force_refresh=False)
                if data:
                    root.after(0, lambda: render_contributor_cards(data))
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()

    load_contributors_async()

    links_row = ctk.CTkFrame(dev_box, fg_color="transparent")
    links_row.pack(fill=tk.X, padx=18, pady=(4, 14))

    create_icon_button_fn(
        links_row,
        text=" مشاهده مخزن گیت‌هاب ",
        icon_name="bookmark",
        font=font_normal,
        command=lambda: open_url("https://github.com/amirkabir18/bager_library"),
        width=175,
        height=32,
    ).pack(side=tk.RIGHT, padx=5)

    create_icon_button_fn(
        links_row,
        text=" ثبت باگ یا پیشنهاد (Issue) ",
        icon_name="filter",
        font=font_normal,
        command=lambda: open_url("https://github.com/amirkabir18/bager_library/issues/new"),
        width=185,
        height=32,
    ).pack(side=tk.RIGHT, padx=5)

    return {
        "update_checker": update_checker,
        "on_check_finished": on_check_finished,
        "on_check_failed": on_check_failed,
    }
