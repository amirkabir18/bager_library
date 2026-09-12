import datetime
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import database
from notifications import LoanReminderManager, NotificationEngine


class TestAppSettingsDatabase(unittest.TestCase):
    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_db_fd)
        self.conn = sqlite3.connect(self.temp_db_path)
        database.init_database(self.conn)

    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except OSError:
                pass

    def test_default_settings_initialized(self):
        all_settings = database.get_all_settings(self.conn)
        self.assertEqual(all_settings.get("notifications_enabled"), "true")
        self.assertEqual(all_settings.get("notification_sound"), "true")
        self.assertEqual(all_settings.get("notification_advance_days"), "2")
        self.assertEqual(all_settings.get("notification_check_interval_mins"), "30")

    def test_get_and_set_setting(self):
        # Retrieve existing setting
        val = database.get_setting(self.conn, "notification_advance_days")
        self.assertEqual(val, "2")

        # Update setting
        database.set_setting(self.conn, "notification_advance_days", "5")
        val_updated = database.get_setting(self.conn, "notification_advance_days")
        self.assertEqual(val_updated, "5")

        # Non-existing setting with default
        val_none = database.get_setting(self.conn, "non_existing_key", default="fallback")
        self.assertEqual(val_none, "fallback")

        # Insert new setting via set_setting
        database.set_setting(self.conn, "custom_theme", "dark")
        self.assertEqual(database.get_setting(self.conn, "custom_theme"), "dark")

    def test_log_notification_and_retrieval(self):
        cur = self.conn.cursor()
        cur.execute("INSERT INTO books (title, author, isbn) VALUES ('کتاب تست', 'نویسنده', '1234567890123')")
        book_id = cur.lastrowid
        cur.execute(
            "INSERT INTO loans (book_id, member_name, borrow_date, return_date, borrowed) VALUES (?, ?, '2025-01-01', '2025-01-15', 1)",
            (book_id, "علی تست"),
        )
        loan_id = cur.lastrowid
        self.conn.commit()

        # Log with loan_id
        database.log_notification(self.conn, "DUE_SOON", loan_id=loan_id, sent_date="2025-01-13")

        # Log without loan_id (e.g., test notification)
        database.log_notification(self.conn, "TEST_NOTIFICATION", loan_id=None, sent_date="2025-01-14")

        # Retrieve all logs
        logs = database.get_notification_logs(self.conn)
        self.assertEqual(len(logs), 2)

        # Most recent first
        self.assertEqual(logs[0]["notification_type"], "TEST_NOTIFICATION")
        self.assertIsNone(logs[0]["loan_id"])
        self.assertIsNone(logs[0]["book_title"])

        self.assertEqual(logs[1]["notification_type"], "DUE_SOON")
        self.assertEqual(logs[1]["loan_id"], loan_id)
        self.assertEqual(logs[1]["book_title"], "کتاب تست")
        self.assertEqual(logs[1]["member_name"], "علی تست")

    def test_get_notification_logs_filtering(self):
        cur = self.conn.cursor()
        cur.execute("INSERT INTO books (title, author, isbn) VALUES ('فیزیک هالیدی', 'هالیدی', '1111111111111')")
        book1_id = cur.lastrowid
        cur.execute("INSERT INTO books (title, author, isbn) VALUES ('شیمی عمومی', 'مورتیمر', '2222222222222')")
        book2_id = cur.lastrowid

        cur.execute(
            "INSERT INTO loans (book_id, member_name, borrow_date, return_date, borrowed) VALUES (?, ?, '2025-01-01', '2025-01-15', 1)",
            (book1_id, "رضا احمدی"),
        )
        loan1 = cur.lastrowid
        cur.execute(
            "INSERT INTO loans (book_id, member_name, borrow_date, return_date, borrowed) VALUES (?, ?, '2025-01-01', '2025-01-10', 1)",
            (book2_id, "سارا کریمی"),
        )
        loan2 = cur.lastrowid
        self.conn.commit()

        database.log_notification(self.conn, "DUE_SOON", loan_id=loan1)
        database.log_notification(self.conn, "OVERDUE", loan_id=loan2)
        database.log_notification(self.conn, "TEST_NOTIFICATION", loan_id=None)

        # Filter by notification type
        overdue_logs = database.get_notification_logs(self.conn, notification_type="OVERDUE")
        self.assertEqual(len(overdue_logs), 1)
        self.assertEqual(overdue_logs[0]["book_title"], "شیمی عمومی")

        # Filter by search query (member name)
        search_logs = database.get_notification_logs(self.conn, search_query="احمدی")
        self.assertEqual(len(search_logs), 1)
        self.assertEqual(search_logs[0]["member_name"], "رضا احمدی")

        # Filter by search query (book title)
        search_book_logs = database.get_notification_logs(self.conn, search_query="هالیدی")
        self.assertEqual(len(search_book_logs), 1)
        self.assertEqual(search_book_logs[0]["loan_id"], loan1)

        # Test limit
        limit_logs = database.get_notification_logs(self.conn, limit=2)
        self.assertEqual(len(limit_logs), 2)

    def test_get_notification_logs_advanced_filtering_and_sorting(self):
        cur = self.conn.cursor()
        cur.execute("INSERT INTO books (title, author, isbn) VALUES ('کتاب الف', 'نویسنده ۱', '1000000000001')")
        b1 = cur.lastrowid
        cur.execute("INSERT INTO books (title, author, isbn) VALUES ('کتاب ب', 'نویسنده ۲', '1000000000002')")
        b2 = cur.lastrowid
        cur.execute("INSERT INTO books (title, author, isbn) VALUES ('الفبای فیزیک', 'نویسنده ۳', '1000000000003')")
        b3 = cur.lastrowid

        cur.execute(
            "INSERT INTO loans (book_id, member_name, borrow_date, return_date, borrowed) VALUES (?, 'محمد رضایی', '2025-01-01', '2025-01-10', 1)",
            (b1,),
        )
        l1 = cur.lastrowid
        cur.execute(
            "INSERT INTO loans (book_id, member_name, borrow_date, return_date, borrowed) VALUES (?, 'رضا محمدی', '2025-01-02', '2025-01-11', 1)",
            (b2,),
        )
        l2 = cur.lastrowid
        cur.execute(
            "INSERT INTO loans (book_id, member_name, borrow_date, return_date, borrowed) VALUES (?, 'احمد حسینی', '2025-01-03', '2025-01-12', 1)",
            (b3,),
        )
        l3 = cur.lastrowid
        self.conn.commit()

        database.log_notification(self.conn, "due_reminder", loan_id=l1, sent_date="2025-01-08")
        database.log_notification(self.conn, "overdue", loan_id=l2, sent_date="2025-01-09")
        database.log_notification(self.conn, "test", loan_id=l3, sent_date="2025-01-10")

        # 1. Targeted column: book_title
        res = database.get_notification_logs(self.conn, search_query="الف", column="book_title")
        self.assertEqual(len(res), 2)
        titles = {r["book_title"] for r in res}
        self.assertEqual(titles, {"کتاب الف", "الفبای فیزیک"})

        # 2. Targeted column: member_name with startswith
        res_starts = database.get_notification_logs(
            self.conn, search_query="رضا", column="member_name", match_mode="startswith"
        )
        self.assertEqual(len(res_starts), 1)
        self.assertEqual(res_starts[0]["member_name"], "رضا محمدی")

        # 3. Match mode exact
        res_exact = database.get_notification_logs(
            self.conn, search_query="کتاب الف", column="book_title", match_mode="exact"
        )
        self.assertEqual(len(res_exact), 1)
        self.assertEqual(res_exact[0]["book_title"], "کتاب الف")

        # 4. Search by loan_id column
        res_loan = database.get_notification_logs(self.conn, search_query=str(l2), column="loan_id")
        self.assertEqual(len(res_loan), 1)
        self.assertEqual(res_loan[0]["member_name"], "رضا محمدی")

        # 5. Sorting ASC vs DESC by sent_date
        res_asc = database.get_notification_logs(self.conn, sort_col="sent_date", sort_dir="ASC")
        self.assertEqual(res_asc[0]["sent_date"], "2025-01-08")
        self.assertEqual(res_asc[-1]["sent_date"], "2025-01-10")

        res_desc = database.get_notification_logs(self.conn, sort_col="sent_date", sort_dir="DESC")
        self.assertEqual(res_desc[0]["sent_date"], "2025-01-10")
        self.assertEqual(res_desc[-1]["sent_date"], "2025-01-08")

        # 6. Sorting by member_name
        res_member_sort = database.get_notification_logs(self.conn, sort_col="member_name", sort_dir="ASC")
        self.assertEqual(res_member_sort[0]["member_name"], "احمد حسینی")

        # 7. Shamsi date normalization in search query (1403/10/19 corresponds to 2025-01-08)
        # Check jdatetime conversion if available
        try:
            import jdatetime

            g_d = datetime.date(2025, 1, 8)
            j_d = jdatetime.date.fromgregorian(date=g_d)
            shamsi_str = j_d.strftime("%Y-%m-%d")
            res_shamsi = database.get_notification_logs(self.conn, search_query=shamsi_str, column="sent_date")
            self.assertEqual(len(res_shamsi), 1)
            self.assertEqual(res_shamsi[0]["sent_date"], "2025-01-08")
        except ImportError:
            pass

    def test_clear_notification_logs(self):
        database.log_notification(self.conn, "TEST_1", loan_id=None)
        database.log_notification(self.conn, "TEST_2", loan_id=None)

        logs_before = database.get_notification_logs(self.conn)
        self.assertEqual(len(logs_before), 2)

        deleted_count = database.clear_notification_logs(self.conn)
        self.assertEqual(deleted_count, 2)

        logs_after = database.get_notification_logs(self.conn)
        self.assertEqual(len(logs_after), 0)

        # Calling clear again on empty table returns 0
        deleted_count_empty = database.clear_notification_logs(self.conn)
        self.assertEqual(deleted_count_empty, 0)


class TestNotificationSettingsEngine(unittest.TestCase):
    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_db_fd)
        self.conn = sqlite3.connect(self.temp_db_path)
        database.init_database(self.conn)

        self.mock_root = MagicMock()
        self.engine = NotificationEngine(root=self.mock_root, db_path=self.temp_db_path)

    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except OSError:
                pass

    def test_engine_preferences_read_from_database(self):
        # Defaults
        self.assertTrue(self.engine.are_notifications_enabled())
        self.assertTrue(self.engine.is_sound_enabled())

        # Update in DB
        database.set_setting(self.conn, "notifications_enabled", "false")
        database.set_setting(self.conn, "notification_sound", "false")

        self.assertFalse(self.engine.are_notifications_enabled())
        self.assertFalse(self.engine.is_sound_enabled())

    def test_notifications_disabled_skips_showing(self):
        database.set_setting(self.conn, "notifications_enabled", "false")
        with patch.object(self.engine, "_show_windows_toast") as mock_toast:
            with patch.object(self.engine, "_show_tkinter_popup") as mock_popup:
                self.engine.show("Title", "Message")
                mock_toast.assert_not_called()
                mock_popup.assert_not_called()

    def test_sound_trigger_on_popup(self):
        database.set_setting(self.conn, "notifications_enabled", "true")
        database.set_setting(self.conn, "notification_sound", "true")

        with patch("winsound.MessageBeep") as mock_beep, patch("tkinter.Toplevel"):
            self.engine._show_tkinter_popup("Title", "Message")
            mock_beep.assert_called_once()

    def test_sound_disabled_on_popup(self):
        database.set_setting(self.conn, "notifications_enabled", "true")
        database.set_setting(self.conn, "notification_sound", "false")

        with patch("winsound.MessageBeep") as mock_beep, patch("tkinter.Toplevel"):
            self.engine._show_tkinter_popup("Title", "Message")
            mock_beep.assert_not_called()

    def test_sound_setting_on_windows_toast(self):
        mock_winotify = MagicMock()
        mock_toast_instance = MagicMock()
        mock_winotify.Notification.return_value = mock_toast_instance
        mock_winotify.audio.Default = "audio_default"
        mock_winotify.audio.Silent = "audio_silent"

        database.set_setting(self.conn, "notification_sound", "true")
        with patch.dict("sys.modules", {"winotify": mock_winotify}):
            self.engine._show_windows_toast("Title", "Message")
            mock_toast_instance.set_audio.assert_called_with("audio_default", loop=False)

        database.set_setting(self.conn, "notification_sound", "false")
        with patch.dict("sys.modules", {"winotify": mock_winotify}):
            self.engine._show_windows_toast("Title", "Message")
            mock_toast_instance.set_audio.assert_called_with("audio_silent", loop=False)

    def test_reminder_manager_dynamic_settings_and_reschedule(self):
        reminder_mgr = LoanReminderManager(
            root=self.mock_root,
            db_path=self.temp_db_path,
            notification_engine=self.engine,
        )

        # Default advance days: 2
        self.assertEqual(reminder_mgr.get_advance_days(), 2)

        # Default check interval: 30 minutes = 1,800,000 ms
        self.assertEqual(reminder_mgr.get_check_interval_ms(), 30 * 60 * 1000)

        # Update settings in DB
        database.set_setting(self.conn, "notification_advance_days", "5")
        database.set_setting(self.conn, "notification_check_interval_mins", "60")

        self.assertEqual(reminder_mgr.get_advance_days(), 5)
        self.assertEqual(reminder_mgr.get_check_interval_ms(), 60 * 60 * 1000)

        # Test reschedule
        reminder_mgr._running = True
        reminder_mgr._after_id = "timer_123"
        reminder_mgr.reschedule()

        self.mock_root.after_cancel.assert_called_with("timer_123")
        self.mock_root.after.assert_called_with(60 * 60 * 1000, reminder_mgr._run_and_schedule)


if __name__ == "__main__":
    unittest.main()
