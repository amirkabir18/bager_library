import os
import sqlite3
import sys
import tempfile
import time
import tkinter as tk

import customtkinter as ctk
from PIL import ImageGrab

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

OUTPUT_DIR = os.path.join(BASE_DIR, "assets", "images", "ui")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 1. Prepare isolated temporary database with realistic sample data
temp_db_fd, temp_db_path = tempfile.mkstemp(suffix=".db")
os.close(temp_db_fd)
os.environ["BAGER_DB_PATH"] = temp_db_path

import database

conn = sqlite3.connect(temp_db_path)
database.init_database(conn)
cur = conn.cursor()

from auth import ensure_bootstrap_admin

ensure_bootstrap_admin(database_path=temp_db_path)

cur.execute(
    "UPDATE auth_users SET role='super admin', phone_number='09925179177', telegram_chat_id='987654321' WHERE username='arush'"
)
cur.execute(
    "INSERT OR IGNORE INTO auth_users (username, role, phone_number, is_active, created_at, telegram_chat_id) VALUES (?, ?, ?, ?, ?, ?)",
    ("zahra_lib", "librarian", "09129876543", 1, "2024-02-15 11:30:00", "554433221"),
)
cur.execute(
    "INSERT OR IGNORE INTO auth_users (username, role, phone_number, is_active, created_at) VALUES (?, ?, ?, ?, ?)",
    ("admin_reza", "admin", "09301234567", 1, "2024-03-01 09:15:00"),
)

sample_books = [
    ("شاهنامه فردوسی", "ابوالقاسم فردوسی", "8fa1", "800", "ادبیات و شعر حماسی", "978-964-329-123-4"),
    ("بوستان سعدی", "مشرف‌الدین مصلح بن عبدالله (سعدی)", "8fa1.2", "800", "شعر کهن فارسی", "978-964-445-567-8"),
    ("دیوان حافظ", "خواجه شمس‌الدین محمد حافظ شیرازی", "8fa1.3", "800", "شعر و غزلیات", "978-964-00-0123-9"),
    ("تاریخ صدر اسلام", "دکتر غلامحسین زرگری‌نژاد", "297.91", "200", "تاریخ اسلام", "978-964-459-789-0"),
    ("قدرت داستان‌گویی در کسب‌وکار", "آنت سیمونز", "650.1", "600", "مدیریت و بازاریابی", "978-600-123-456-7"),
    ("اصول علم اقتصاد", "دکتر منوچهر فرهنگ", "330", "300", "علوم اجتماعی و اقتصاد", "978-964-03-3456-1"),
    ("مقدمه‌ای بر الگوریتم‌ها", "توماس کورمن", "005.1", "000", "علوم کامپیوتر و الگوریتم", "978-026-203-384-8"),
]
for title, author, dcode, dclass, dsubj, isbn in sample_books:
    cur.execute(
        "INSERT INTO books (title, author, dewey_code, dewey_class, dewey_subject, isbn) VALUES (?, ?, ?, ?, ?, ?)",
        (title, author, dcode, dclass, dsubj, isbn),
    )

sample_members = [
    ("علی محمدی", "09123456789"),
    ("زهرا حسینی", "09198765432"),
    ("محمد رضایی", "09351234567"),
    ("فاطمه صادقی", "09367891234"),
    ("امیرحسین عباسی", "09121112233"),
]
for uname, phone in sample_members:
    cur.execute("INSERT INTO members (username, phone_number) VALUES (?, ?)", (uname, phone))

cur.execute(
    "INSERT INTO loans (borrow_date, return_date, borrowed, book_id, member_id) VALUES (?, ?, ?, ?, ?)",
    ("2026-09-01", "2026-09-20", 0, 1, 1),
)
cur.execute(
    "INSERT INTO loans (borrow_date, return_date, borrowed, book_id, member_id) VALUES (?, ?, ?, ?, ?)",
    ("2026-09-15", "2026-10-05", 1, 2, 2),
)
cur.execute(
    "INSERT INTO loans (borrow_date, return_date, borrowed, book_id, member_id) VALUES (?, ?, ?, ?, ?)",
    ("2026-09-18", "2026-10-08", 1, 4, 3),
)
cur.execute(
    "INSERT INTO loans (borrow_date, return_date, borrowed, book_id, member_id) VALUES (?, ?, ?, ?, ?)",
    ("2026-09-20", "2026-10-10", 1, 5, 4),
)

cur.execute(
    "INSERT INTO notification_logs (loan_id, notification_type, sent_date) VALUES (?, ?, ?)",
    (2, "due_soon", "2026-09-25"),
)
cur.execute(
    "INSERT INTO notification_logs (loan_id, notification_type, sent_date) VALUES (?, ?, ?)",
    (3, "overdue", "2026-09-24"),
)

conn.commit()
conn.close()

# Disable startup network threads, reminder popups, and update dialogs
import auth
import notifications

notifications.NotificationEngine.show = lambda *a, **kw: None
notifications.LoanReminderManager.start = lambda *a, **kw: None
auth.OTPCleanupManager.start = lambda *a, **kw: None

import services.dewey_ai_agent

services.dewey_ai_agent.init_boot_internet_check = lambda *a, **kw: None
import updater

updater.UpdateChecker.check = lambda self: {"update_available": False}


def capture_screen(root, filename):
    root.update()
    root.update_idletasks()
    root.lift()
    root.attributes("-topmost", True)
    root.update()
    time.sleep(0.35)
    root.attributes("-topmost", False)

    cx, cy, cw, ch = root.winfo_rootx(), root.winfo_rooty(), root.winfo_width(), root.winfo_height()
    img = ImageGrab.grab(bbox=(cx, cy, cx + cw, cy + ch))
    out_path = os.path.join(OUTPUT_DIR, filename)
    img.save(out_path)
    print(f"Captured: {filename} ({img.size[0]}x{img.size[1]})")


def close_all_toplevels(root):
    for w in list(root.winfo_children()):
        if isinstance(w, (tk.Toplevel, ctk.CTkToplevel)):
            try:
                w.destroy()
            except Exception:
                pass
    root.update()
    root.update_idletasks()


def trigger_pwd_view(parent):
    for child in parent.winfo_children():
        if isinstance(child, ctk.CTkButton):
            txt = str(child.cget("text"))
            if "رمز عبور" in txt:
                cmd = child.cget("command")
                if cmd:
                    cmd()
                    return True
        if trigger_pwd_view(child):
            return True
    return False


def run_capture_pipeline(m):
    root = m.root
    root.state("zoomed")
    root.update()
    root.update_idletasks()

    # 1. Login Page (OTP Step)
    capture_screen(root, "login.png")

    # 2. Login Page (Password Step)
    trigger_pwd_view(m.login_frame)
    time.sleep(0.2)
    capture_screen(root, "login_password.png")

    # Log in as Super Admin
    admin_u = {
        "id": 1,
        "username": "arush",
        "role": "super admin",
        "phone_number": "09925179177",
        "telegram_chat_id": "987654321",
        "is_active": 1,
        "created_at": "2024-01-10 10:00:00",
    }
    m.on_login_success(admin_u)

    # 3. Books Page
    m.switch_tab("books")
    m.search()
    time.sleep(0.3)
    capture_screen(root, "books.png")

    # 4. Modal: Add Book
    try:
        m.books_tab_controllers["open_add_book_popup"]()
        time.sleep(0.3)
        capture_screen(root, "modal_add_book.png")
        close_all_toplevels(root)
    except Exception as ex:
        print("Failed modal_add_book:", ex)

    # 5. Loans Page
    m.switch_tab("loans")
    m.refresh_loans_table()
    time.sleep(0.3)
    capture_screen(root, "loans.png")

    # 6. Modal: Add Loan
    try:
        m.loans_tab_controllers["open_add_loan_popup"]()
        time.sleep(0.3)
        capture_screen(root, "modal_add_loan.png")
        close_all_toplevels(root)
    except Exception as ex:
        print("Failed modal_add_loan:", ex)

    # 7. Members Page
    m.switch_tab("members")
    m.search_members()
    time.sleep(0.3)
    capture_screen(root, "members.png")

    # 8. Modal: Add Member
    try:
        m.members_tab_controllers["open_add_member_popup"]()
        time.sleep(0.3)
        capture_screen(root, "modal_add_member.png")
        close_all_toplevels(root)
    except Exception as ex:
        print("Failed modal_add_member:", ex)

    # 9. System Users Page
    m.switch_tab("users")
    m.search_users()
    time.sleep(0.3)
    capture_screen(root, "users.png")

    # 10. Modal: Add User
    try:
        m.users_tab_controllers["open_create_user_popup"]()
        time.sleep(0.3)
        capture_screen(root, "modal_add_user.png")
        close_all_toplevels(root)
    except Exception as ex:
        print("Failed modal_add_user:", ex)

    # 11. Settings Page
    m.switch_tab("settings")
    m.load_settings_into_ui()
    m.load_notification_logs_ui()
    time.sleep(0.3)
    capture_screen(root, "settings.png")

    # 12. Help Page
    m.switch_tab("help")
    time.sleep(0.3)
    capture_screen(root, "help.png")

    # 13. User Profile Popover
    try:
        m.open_user_profile_popover()
        time.sleep(0.3)
        capture_screen(root, "user_profile.png")
        m.close_user_profile_popover()
    except Exception as ex:
        print("Failed user_profile:", ex)

    print("All screenshots successfully captured!")
    root.destroy()
    try:
        if os.path.exists(temp_db_path):
            os.remove(temp_db_path)
    except Exception:
        pass


orig_mainloop = ctk.CTk.mainloop


def patched_mainloop(self):
    self.after(200, lambda: run_capture_pipeline(sys.modules["main"]))
    orig_mainloop(self)


ctk.CTk.mainloop = patched_mainloop

import main  # noqa: F401
