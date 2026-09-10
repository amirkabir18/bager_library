import datetime
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import database
from notifications import LoanReminderManager, NotificationEngine


class TestNotificationEngine(unittest.TestCase):
    def test_notification_engine_fallback(self):
        engine = NotificationEngine(root=None, app_id="TestApp")
        # Should not throw even with root=None
        with patch.object(engine, "_show_windows_toast", side_effect=Exception("winotify failed")):
            with patch.object(engine, "_show_tkinter_popup") as mock_popup:
                engine.show("Title", "Message")
                # When root is None, show_tkinter_popup will not crash
                engine.root = MagicMock()
                engine.show("Title", "Message")
                mock_popup.assert_called_with("Title", "Message")


class TestLoanReminderManager(unittest.TestCase):
    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix='.db')
        os.close(self.temp_db_fd)
        self.conn = sqlite3.connect(self.temp_db_path)
        database.init_database(self.conn)

        self.mock_root = MagicMock()
        self.mock_engine = MagicMock(spec=NotificationEngine)
        self.reminder_manager = LoanReminderManager(
            root=self.mock_root,
            db_path=self.temp_db_path,
            notification_engine=self.mock_engine,
            check_interval_ms=10000
        )

    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except OSError:
                pass

    def test_check_loans_due_soon_and_due_today_and_overdue(self):
        cur = self.conn.cursor()
        today = datetime.date.today()
        today_str = today.strftime("%Y-%m-%d")
        due_tomorrow_str = (today + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        overdue_str = (today - datetime.timedelta(days=3)).strftime("%Y-%m-%d")
        returned_overdue_str = (today - datetime.timedelta(days=5)).strftime("%Y-%m-%d")

        # 1. Due today
        cur.execute("INSERT INTO loans (book_id, member_name, return_date, borrow_date, borrowed) VALUES (?, ?, ?, ?, 1)",
                    ("کتاب امروز", "علی", today_str, today_str))
        # 2. Due soon (tomorrow)
        cur.execute("INSERT INTO loans (book_id, member_name, return_date, borrow_date, borrowed) VALUES (?, ?, ?, ?, 1)",
                    ("کتاب فردا", "رضا", due_tomorrow_str, today_str))
        # 3. Overdue (3 days late)
        cur.execute("INSERT INTO loans (book_id, member_name, return_date, borrow_date, borrowed) VALUES (?, ?, ?, ?, 1)",
                    ("کتاب تاخیر خورده", "سارا", overdue_str, today_str))
        # 4. Returned loan (should be ignored)
        cur.execute("INSERT INTO loans (book_id, member_name, return_date, borrow_date, borrowed) VALUES (?, ?, ?, ?, 0)",
                    ("کتاب برگشتی", "مهدی", returned_overdue_str, today_str))
        self.conn.commit()

        sent = self.reminder_manager.check_loans()
        self.assertEqual(sent, 3)
        self.assertEqual(self.mock_engine.show.call_count, 3)

        # De-duplication test: running check_loans again on the same day should send 0 new notifications
        sent_again = self.reminder_manager.check_loans()
        self.assertEqual(sent_again, 0)
        self.assertEqual(self.mock_engine.show.call_count, 3)

    def test_notifications_disabled_in_settings(self):
        cur = self.conn.cursor()
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        cur.execute("INSERT INTO loans (book_id, member_name, return_date, borrow_date, borrowed) VALUES (?, ?, ?, ?, 1)",
                    ("کتاب تست", "علی", today_str, today_str))
        cur.execute("UPDATE app_settings SET value = 'false' WHERE key = 'notifications_enabled'")
        self.conn.commit()

        sent = self.reminder_manager.check_loans()
        self.assertEqual(sent, 0)
        self.mock_engine.show.assert_not_called()

    def test_start_and_stop_daemon(self):
        self.reminder_manager.start()
        self.assertTrue(self.reminder_manager._running)
        self.mock_root.after.assert_called()

        self.reminder_manager.stop()
        self.assertFalse(self.reminder_manager._running)


if __name__ == '__main__':
    unittest.main()
