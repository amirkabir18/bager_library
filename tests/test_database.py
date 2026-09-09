import unittest
import sqlite3
import tempfile
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import database

class TestDatabaseMigration(unittest.TestCase):
    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix='.db')
        os.close(self.temp_db_fd)
        self.conn = sqlite3.connect(self.temp_db_path)

    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except OSError:
                pass

    def test_init_database_fresh(self):
        database.init_database(self.conn)
        cur = self.conn.cursor()

        # Verify all tables exist
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cur.fetchall()}
        expected_tables = {
            'books', 'members', 'loans',
            'auth_users', 'otp_sessions',
            'notification_logs', 'app_settings'
        }
        self.assertTrue(expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}")

        # Check auth_users columns
        cur.execute('PRAGMA table_info("auth_users")')
        auth_cols = {row[1] for row in cur.fetchall()}
        expected_auth_cols = {
            'id', 'username', 'phone_number', 'telegram_chat_id',
            'role', 'password_hash', 'is_active', 'created_at'
        }
        self.assertTrue(expected_auth_cols.issubset(auth_cols), f"Missing auth_users cols: {expected_auth_cols - auth_cols}")

        # Check otp_sessions columns
        cur.execute('PRAGMA table_info("otp_sessions")')
        otp_cols = {row[1] for row in cur.fetchall()}
        expected_otp_cols = {'id', 'phone_number', 'otp_hash', 'created_at', 'expires_at', 'attempts', 'is_used'}
        self.assertTrue(expected_otp_cols.issubset(otp_cols), f"Missing otp_sessions cols: {expected_otp_cols - otp_cols}")

        # Check notification_logs columns
        cur.execute('PRAGMA table_info("notification_logs")')
        notif_cols = {row[1] for row in cur.fetchall()}
        expected_notif_cols = {'id', 'loan_id', 'notification_type', 'sent_date', 'created_at'}
        self.assertTrue(expected_notif_cols.issubset(notif_cols), f"Missing notification_logs cols: {expected_notif_cols - notif_cols}")

        # Check app_settings default seed values
        cur.execute("SELECT key, value FROM app_settings")
        settings = dict(cur.fetchall())
        self.assertEqual(settings.get('notifications_enabled'), 'true')
        self.assertEqual(settings.get('notification_advance_days'), '2')
        self.assertEqual(settings.get('notification_sound'), 'true')
        self.assertEqual(settings.get('notification_check_interval_mins'), '30')

    def test_migration_on_preexisting_db(self):
        # Create older schema without auth or notification tables
        cur = self.conn.cursor()
        cur.execute("CREATE TABLE books (id INTEGER PRIMARY KEY AUTOINCREMENT, author VARCHAR(255), isbn VARCHAR(255) UNIQUE, title VARCHAR(255), location VARCHAR(255))")
        cur.execute("CREATE TABLE members (id INTEGER PRIMARY KEY AUTOINCREMENT, member_id VARCHAR(255) UNIQUE NOT NULL, phone_number VARCHAR(255) NOT NULL)")
        cur.execute("CREATE TABLE loans (id INTEGER PRIMARY KEY AUTOINCREMENT, borrow_date DATE NOT NULL, return_date DATE, borrowed BOOLEAN DEFAULT 1, book_id VARCHAR(255), member_name VARCHAR(255))")
        cur.execute("CREATE TABLE auth_users (id INTEGER PRIMARY KEY AUTOINCREMENT, username VARCHAR(100) UNIQUE NOT NULL, phone_number VARCHAR(20) UNIQUE NOT NULL)")
        self.conn.commit()

        # Run migration
        database.init_database(self.conn)

        # Check that missing columns were added to auth_users
        cur.execute('PRAGMA table_info("auth_users")')
        auth_cols = {row[1] for row in cur.fetchall()}
        self.assertIn('telegram_chat_id', auth_cols)
        self.assertIn('role', auth_cols)
        self.assertIn('password_hash', auth_cols)
        self.assertIn('is_active', auth_cols)

    def test_idempotence(self):
        # Running multiple times should not raise errors
        database.init_database(self.conn)
        database.init_database(self.conn)
        database.init_database(self.conn)

    def test_settings_get_and_set(self):
        database.init_database(self.conn)
        self.assertEqual(database.get_setting('notifications_enabled', database_path=self.temp_db_path), 'true')
        database.set_setting('notifications_enabled', 'false', database_path=self.temp_db_path)
        self.assertEqual(database.get_setting('notifications_enabled', database_path=self.temp_db_path), 'false')

        database.set_setting('custom_key', 'custom_value', database_path=self.temp_db_path)
        self.assertEqual(database.get_setting('custom_key', database_path=self.temp_db_path), 'custom_value')

        all_settings = database.get_all_settings(database_path=self.temp_db_path)
        self.assertEqual(all_settings['custom_key'], 'custom_value')
        self.assertEqual(all_settings['notifications_enabled'], 'false')

    def test_settings_env_vars(self):
        database.init_database(self.conn)
        os.environ['TEST_ENV_VAR'] = 'env_value'
        try:
            self.assertEqual(database.get_setting('test_env_var', database_path=self.temp_db_path), 'env_value')

            database.set_setting('sync_key', 'sync_val', database_path=self.temp_db_path)
            self.assertEqual(os.environ.get('SYNC_KEY'), 'sync_val')
            self.assertEqual(database.get_setting('sync_key', database_path=self.temp_db_path), 'sync_val')
        finally:
            os.environ.pop('TEST_ENV_VAR', None)
            os.environ.pop('SYNC_KEY', None)
            os.environ.pop('sync_key', None)

    def test_foreign_key_enforcement(self):
        database.init_database(self.conn)
        cur = self.conn.cursor()
        # Enable foreign keys
        cur.execute("PRAGMA foreign_keys = ON")
        # Inserting notification log referencing non-existent loan should fail
        with self.assertRaises(sqlite3.IntegrityError):
            cur.execute("""
                INSERT INTO notification_logs (loan_id, notification_type, sent_date)
                VALUES (9999, 'due_today', '2026-09-09')
            """)
            self.conn.commit()

    def test_indexes_created(self):
        database.init_database(self.conn)
        cur = self.conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = {row[0] for row in cur.fetchall()}
        expected_indexes = {
            'idx_loans_return_borrowed',
            'idx_notification_logs_lookup',
            'idx_otp_sessions_phone',
            'idx_auth_users_username',
            'idx_auth_users_phone'
        }
        self.assertTrue(expected_indexes.issubset(indexes), f"Missing indexes: {expected_indexes - indexes}")

if __name__ == '__main__':
    unittest.main()
