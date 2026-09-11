"""
Offline Desktop Push Notification Engine for Bager Library.
Supports native Windows 10/11 Action Center toast notifications via winotify (100% offline),
with sound and custom logo icon, plus an offline Tkinter non-blocking floating popup fallback.
"""

import datetime
import os
import sqlite3
import sys
import tkinter as tk
from typing import Optional


class NotificationEngine:
    """
    Offline notification engine supporting Windows 10/11 Action Center toasts
    via winotify with sound and custom logo icon, and a graceful Tkinter floating toast fallback.
    """

    def __init__(
        self,
        root: Optional[tk.Tk] = None,
        app_id: str = "کتابخانه باقر العلوم",
        icon_path: Optional[str] = None,
        db_path: Optional[str] = None,
    ):
        self.root = root
        self.app_id = app_id
        self.icon_path = icon_path if (icon_path and os.path.exists(icon_path)) else None
        self.db_path = db_path

    def is_enabled(self) -> bool:
        """Returns True if desktop notifications are enabled in settings."""
        try:
            from database import get_setting
            val = get_setting("notifications_enabled", "true", database_path=self.db_path)
            return str(val).strip().lower() != "false"
        except Exception:
            return True

    def are_notifications_enabled(self) -> bool:
        """Alias for is_enabled()."""
        return self.is_enabled()

    def is_sound_enabled(self) -> bool:
        """Returns True if notification sound is enabled in settings."""
        try:
            from database import get_setting
            val = get_setting("notification_sound", "true", database_path=self.db_path)
            return str(val).strip().lower() != "false"
        except Exception:
            return True

    def show(self, title: str, message: str, force: bool = False):
        """
        Send a desktop notification. Tries native Windows toast first;
        falls back to Tkinter popup if on non-Windows or if winotify encounters an error.
        If force=False, respects the notifications_enabled setting.
        """
        if not force and not self.is_enabled():
            return

        if sys.platform == "win32":
            try:
                self._show_windows_toast(title, message)
                return
            except Exception as e:
                print(f"[NotificationEngine] Windows toast failed, falling back to popup: {e}")

        if self.root:
            self._show_tkinter_popup(title, message)

    def _show_windows_toast(self, title: str, message: str, sound: Optional[bool] = None):
        from winotify import Notification, audio

        if sound is None:
            sound = self.is_sound_enabled()

        toast = Notification(
            app_id=self.app_id, title=title, msg=message, icon=self.icon_path if self.icon_path else ""
        )
        if sound:
            toast.set_audio(audio.Default, loop=False)
        else:
            toast.set_audio(audio.Silent, loop=False)
        toast.show()

    def _show_tkinter_popup(self, title: str, message: str, sound: Optional[bool] = None):
        """
        Creates a floating non-blocking borderless toast window in the bottom-right corner of the screen.
        """
        if not self.root:
            return

        if sound is None:
            sound = self.is_sound_enabled()

        if sound:
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except Exception:
                pass

        try:
            popup = tk.Toplevel(self.root)
            popup.overrideredirect(True)
            popup.attributes("-topmost", True)

            width, height = 340, 110
            screen_w = popup.winfo_screenwidth()
            screen_h = popup.winfo_screenheight()
            x = screen_w - width - 24
            y = screen_h - height - 60
            popup.geometry(f"{width}x{height}+{x}+{y}")

            frame = tk.Frame(
                popup, bg="#1e293b", relief="flat", bd=0, highlightthickness=1, highlightbackground="#475569"
            )
            frame.pack(fill=tk.BOTH, expand=True)

            header = tk.Frame(frame, bg="#1e293b")
            header.pack(fill=tk.X, padx=10, pady=(8, 2))

            close_btn = tk.Label(
                header, text="✕", font=("Tahoma", 9, "bold"), fg="#94a3b8", bg="#1e293b", cursor="hand2"
            )
            close_btn.pack(side=tk.LEFT)
            close_btn.bind("<Button-1>", lambda e: popup.destroy())

            title_lbl = tk.Label(
                header, text=title, font=("Tahoma", 10, "bold"), fg="#38bdf8", bg="#1e293b", anchor="e"
            )
            title_lbl.pack(side=tk.RIGHT, fill=tk.X)

            msg_lbl = tk.Label(
                frame,
                text=message,
                font=("Tahoma", 9),
                fg="#f1f5f9",
                bg="#1e293b",
                wraplength=310,
                justify="right",
                anchor="e",
            )
            msg_lbl.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 8))

            popup.after(6000, lambda: popup.destroy() if popup.winfo_exists() else None)
        except Exception as e:
            print(f"[NotificationEngine] Tkinter popup error: {e}")


class LoanReminderManager:
    """
    Background daemon using Tkinter root.after() polling loop to scan the loans table,
    detect due soon, due today, and overdue loans, and send de-duplicated notifications.
    """

    def __init__(
        self, root: tk.Tk, db_path: str, notification_engine: NotificationEngine, check_interval_ms: int = 60000
    ):
        self.root = root
        self.db_path = db_path
        self.notification_engine = notification_engine
        self.check_interval_ms = check_interval_ms
        self._running = False
        self._after_id = None

    def start(self):
        """Starts the periodic background scan."""
        self._running = True
        # Run first check after a brief 1-second delay so GUI initializes smoothly
        self._after_id = self.root.after(1000, self._run_and_schedule)

    def stop(self):
        """Stops the periodic background scan."""
        self._running = False
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def reschedule(self, new_interval_ms: Optional[int] = None):
        """Cancels pending check and reschedules with new or current interval."""
        if new_interval_ms is not None:
            self.check_interval_ms = new_interval_ms
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        if self._running:
            self._after_id = self.root.after(self.get_check_interval_ms(), self._run_and_schedule)

    def get_advance_days(self) -> int:
        """Returns the configured advance reminder days (default: 2)."""
        try:
            from database import get_setting
            val = get_setting("notification_advance_days", "2", database_path=self.db_path)
            if val is not None:
                days = int(val)
                if days > 0:
                    return days
        except Exception:
            pass
        return 2

    def get_check_interval_ms(self) -> int:
        """Returns check interval in milliseconds, preferring app_settings if configured."""
        try:
            from database import get_setting
            val = get_setting("notification_check_interval_mins", database_path=self.db_path)
            if val is not None:
                mins = float(val)
                if mins > 0:
                    return int(mins * 60 * 1000)
        except Exception:
            pass
        return self.check_interval_ms

    def _run_and_schedule(self):
        if not self._running:
            return
        try:
            self.check_loans()
        except Exception as e:
            print(f"[LoanReminderManager] Periodic check error: {e}")
        finally:
            if self._running:
                interval = self.get_check_interval_ms()
                self._after_id = self.root.after(interval, self._run_and_schedule)

    def check_loans(self) -> int:
        """
        Scans active loans (borrowed=1) and fires notifications for:
        1. Due Soon (1-2 days before return_date)
        2. Due Today (return_date == today)
        3. Overdue (return_date < today)
        Uses notification_logs for daily de-duplication.
        Returns the number of notifications sent.
        """
        notifications_sent = 0
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Check if notifications are enabled in app_settings
            try:
                cursor.execute("SELECT value FROM app_settings WHERE key = 'notifications_enabled'")
                row = cursor.fetchone()
                if row and str(row[0]).strip().lower() == "false":
                    conn.close()
                    return 0
            except sqlite3.Error:
                pass

            # Fetch advance days setting (default: 2)
            advance_days = self.get_advance_days()

            # Ensure notification_logs exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notification_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    loan_id INTEGER REFERENCES loans(id),
                    notification_type VARCHAR(50) NOT NULL,
                    sent_date DATE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                SELECT id, book_id, member_name, return_date
                FROM loans
                WHERE borrowed = 1 AND return_date IS NOT NULL AND return_date != ''
            """)
            active_loans = cursor.fetchall()

            today = datetime.date.today()
            today_str = today.strftime("%Y-%m-%d")

            for loan in active_loans:
                loan_id = loan["id"]
                book_id = loan["book_id"] or "نامشخص"
                member_name = loan["member_name"] or "کاربر"
                return_date_raw = str(loan["return_date"]).strip()

                try:
                    return_date_obj = datetime.datetime.strptime(return_date_raw, "%Y-%m-%d").date()
                except ValueError:
                    continue

                days_left = (return_date_obj - today).days

                notification_type = None
                title = ""
                message = ""

                if days_left < 0:
                    overdue_days = abs(days_left)
                    notification_type = "overdue"
                    title = "هشدار دیرکرد بازگشت کتاب"
                    message = f"کتاب «{book_id}» به امانت {member_name} دارای {overdue_days} روز تاخیر است."
                elif days_left == 0:
                    notification_type = "due_today"
                    title = "امروز موعد تحویل کتاب است"
                    message = f"امروز آخرین مهلت بازگشت کتاب «{book_id}» توسط {member_name} است."
                elif 0 < days_left <= advance_days:
                    notification_type = "due_soon"
                    title = "یادآوری موعد بازگشت کتاب"
                    if days_left == 1:
                        message = f"فردا موعد بازگشت کتاب «{book_id}» توسط {member_name} است."
                    else:
                        message = f"کتاب «{book_id}» توسط {member_name} تا {days_left} روز دیگر باید بازگردانده شود."

                if not notification_type:
                    continue

                # De-duplication check for today
                cursor.execute(
                    """
                    SELECT id FROM notification_logs
                    WHERE loan_id = ? AND notification_type = ? AND sent_date = ?
                """,
                    (loan_id, notification_type, today_str),
                )

                if cursor.fetchone():
                    # Already sent today
                    continue

                # Fire notification
                self.notification_engine.show(title, message)
                notifications_sent += 1

                # Log notification
                cursor.execute(
                    """
                    INSERT INTO notification_logs (loan_id, notification_type, sent_date)
                    VALUES (?, ?, ?)
                """,
                    (loan_id, notification_type, today_str),
                )
                conn.commit()

            conn.close()

        except Exception as e:
            print(f"[LoanReminderManager] Check loans error: {e}")

        return notifications_sent
