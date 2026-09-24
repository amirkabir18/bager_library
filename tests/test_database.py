import os
import sqlite3
import sys
import tempfile
import unittest

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import database


class TestDatabaseMigration(unittest.TestCase):
    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_db_fd)
        self.conn = sqlite3.connect(self.temp_db_path)

    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except OSError:
                pass
        for key in ("NOTIFICATIONS_ENABLED", "CUSTOM_KEY", "SYNC_KEY", "TEST_ENV_VAR"):
            os.environ.pop(key, None)

    def test_init_database_fresh(self):
        database.init_database(self.conn)
        cur = self.conn.cursor()

        # Verify all tables exist
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cur.fetchall()}
        expected_tables = {
            "books",
            "members",
            "loans",
            "auth_users",
            "otp_sessions",
            "notification_logs",
            "app_settings",
        }
        self.assertTrue(expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}")

        # Check auth_users columns
        cur.execute('PRAGMA table_info("auth_users")')
        auth_cols = {row[1] for row in cur.fetchall()}
        expected_auth_cols = {
            "id",
            "username",
            "phone_number",
            "telegram_chat_id",
            "role",
            "password_hash",
            "is_active",
            "created_at",
        }
        self.assertTrue(
            expected_auth_cols.issubset(auth_cols), f"Missing auth_users cols: {expected_auth_cols - auth_cols}"
        )

        # Check otp_sessions columns
        cur.execute('PRAGMA table_info("otp_sessions")')
        otp_cols = {row[1] for row in cur.fetchall()}
        expected_otp_cols = {"id", "phone_number", "otp_hash", "created_at", "expires_at", "attempts", "is_used"}
        self.assertTrue(
            expected_otp_cols.issubset(otp_cols), f"Missing otp_sessions cols: {expected_otp_cols - otp_cols}"
        )

        # Check notification_logs columns
        cur.execute('PRAGMA table_info("notification_logs")')
        notif_cols = {row[1] for row in cur.fetchall()}
        expected_notif_cols = {"id", "loan_id", "notification_type", "sent_date", "created_at"}
        self.assertTrue(
            expected_notif_cols.issubset(notif_cols),
            f"Missing notification_logs cols: {expected_notif_cols - notif_cols}",
        )

        # Check app_settings default seed values
        cur.execute("SELECT key, value FROM app_settings")
        settings = dict(cur.fetchall())
        self.assertEqual(settings.get("notifications_enabled"), "true")
        self.assertEqual(settings.get("notification_advance_days"), "2")
        self.assertEqual(settings.get("notification_sound"), "true")
        self.assertEqual(settings.get("notification_check_interval_mins"), "30")

    def test_migration_on_preexisting_db(self):
        # Create older schema without auth or notification tables
        cur = self.conn.cursor()
        cur.execute(
            "CREATE TABLE books (id INTEGER PRIMARY KEY AUTOINCREMENT, author VARCHAR(255), isbn VARCHAR(255) UNIQUE, title VARCHAR(255), location VARCHAR(255))"
        )
        cur.execute(
            "CREATE TABLE members (id INTEGER PRIMARY KEY AUTOINCREMENT, member_id VARCHAR(255) UNIQUE NOT NULL, phone_number VARCHAR(255) NOT NULL)"
        )
        cur.execute(
            "CREATE TABLE loans (id INTEGER PRIMARY KEY AUTOINCREMENT, borrow_date DATE NOT NULL, return_date DATE, borrowed BOOLEAN DEFAULT 1, book_id VARCHAR(255), member_name VARCHAR(255))"
        )
        cur.execute(
            "CREATE TABLE auth_users (id INTEGER PRIMARY KEY AUTOINCREMENT, username VARCHAR(100) UNIQUE NOT NULL, phone_number VARCHAR(20) UNIQUE NOT NULL)"
        )
        self.conn.commit()

        # Run migration
        database.init_database(self.conn)

        # Check that missing columns were added to auth_users
        cur.execute('PRAGMA table_info("auth_users")')
        auth_cols = {row[1] for row in cur.fetchall()}
        self.assertIn("telegram_chat_id", auth_cols)
        self.assertIn("role", auth_cols)
        self.assertIn("password_hash", auth_cols)
        self.assertIn("is_active", auth_cols)

        # Check members table migrated from member_id to username
        cur.execute('PRAGMA table_info("members")')
        mem_cols = {row[1] for row in cur.fetchall()}
        self.assertIn("username", mem_cols)

        # Check loans table migrated with member_id and book_id
        cur.execute('PRAGMA table_info("loans")')
        loan_cols = {row[1] for row in cur.fetchall()}
        self.assertIn("member_id", loan_cols)
        self.assertIn("book_id", loan_cols)

    def test_idempotence(self):
        # Running multiple times should not raise errors
        database.init_database(self.conn)
        database.init_database(self.conn)
        database.init_database(self.conn)

    def test_settings_get_and_set(self):
        database.init_database(self.conn)
        self.assertEqual(database.get_setting("notifications_enabled", database_path=self.temp_db_path), "true")
        database.set_setting("notifications_enabled", "false", database_path=self.temp_db_path)
        self.assertEqual(database.get_setting("notifications_enabled", database_path=self.temp_db_path), "false")

        database.set_setting("custom_key", "custom_value", database_path=self.temp_db_path)
        self.assertEqual(database.get_setting("custom_key", database_path=self.temp_db_path), "custom_value")

        all_settings = database.get_all_settings(database_path=self.temp_db_path)
        self.assertEqual(all_settings["custom_key"], "custom_value")
        self.assertEqual(all_settings["notifications_enabled"], "false")

    def test_settings_env_vars(self):
        database.init_database(self.conn)
        os.environ["TEST_ENV_VAR"] = "env_value"
        try:
            self.assertEqual(database.get_setting("test_env_var", database_path=self.temp_db_path), "env_value")

            database.set_setting("sync_key", "sync_val", database_path=self.temp_db_path)
            self.assertEqual(os.environ.get("SYNC_KEY"), "sync_val")
            self.assertEqual(database.get_setting("sync_key", database_path=self.temp_db_path), "sync_val")
        finally:
            os.environ.pop("TEST_ENV_VAR", None)
            os.environ.pop("SYNC_KEY", None)
            os.environ.pop("sync_key", None)

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
            "idx_loans_return_borrowed",
            "idx_notification_logs_lookup",
            "idx_otp_sessions_phone",
            "idx_auth_users_username",
            "idx_auth_users_phone",
        }
        self.assertTrue(expected_indexes.issubset(indexes), f"Missing indexes: {expected_indexes - indexes}")

    def test_loan_lifecycle_and_return(self):
        database.init_database(self.conn)
        cur = self.conn.cursor()
        cur.execute("INSERT INTO books (title, author, isbn) VALUES ('کتاب تست', 'نویسنده تست', '1234567890')")
        book_id = cur.lastrowid
        cur.execute("INSERT INTO members (username, phone_number) VALUES ('عضو تستی', '09123456789')")
        member_id = cur.lastrowid
        cur.execute(
            """
            INSERT INTO loans (member_id, book_id, return_date, borrow_date, borrowed)
            VALUES (?, ?, '2026-09-20', '2026-09-10', 1)
            """,
            (member_id, book_id),
        )
        loan_id = cur.lastrowid
        self.conn.commit()

        # Check book is currently marked as borrowed
        cur.execute("SELECT COUNT(*) FROM loans WHERE book_id = ? AND (borrowed = 1 OR borrowed = '1')", (book_id,))
        self.assertEqual(cur.fetchone()[0], 1)

        # Return loan
        cur.execute("UPDATE loans SET borrowed = 0 WHERE id = ?", (loan_id,))
        self.conn.commit()

        # Check book is now returned and available
        cur.execute("SELECT COUNT(*) FROM loans WHERE book_id = ? AND (borrowed = 1 OR borrowed = '1')", (book_id,))
        self.assertEqual(cur.fetchone()[0], 0)

        cur.execute("SELECT borrowed FROM loans WHERE id = ?", (loan_id,))
        self.assertEqual(cur.fetchone()[0], 0)

    def test_get_app_data_dir_dev_mode(self):
        expected_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.assertEqual(os.path.abspath(database.get_app_data_dir()), expected_dir)

    def test_get_app_data_dir_env_override(self):
        with tempfile.TemporaryDirectory() as custom_dir:
            os.environ["BAGER_DATA_DIR"] = custom_dir
            try:
                self.assertEqual(database.get_app_data_dir(), custom_dir)
                self.assertEqual(database.get_db_path(), os.path.join(custom_dir, "bager_library.db"))
            finally:
                os.environ.pop("BAGER_DATA_DIR", None)

    def test_get_db_path_env_override(self):
        with tempfile.TemporaryDirectory() as custom_dir:
            custom_db = os.path.join(custom_dir, "custom.db")
            os.environ["BAGER_DB_PATH"] = custom_db
            try:
                self.assertEqual(database.get_db_path(), custom_db)
            finally:
                os.environ.pop("BAGER_DB_PATH", None)

    def test_get_app_data_dir_frozen_writable(self):
        with tempfile.TemporaryDirectory() as fake_exe_dir:
            fake_exe = os.path.join(fake_exe_dir, "bager_library.exe")
            with open(fake_exe, "w") as f:
                f.write("")

            original_frozen = getattr(sys, "frozen", False)
            original_exe = sys.executable
            try:
                sys.frozen = True
                sys.executable = fake_exe
                self.assertEqual(database.get_app_data_dir(), fake_exe_dir)
            finally:
                if original_frozen:
                    sys.frozen = original_frozen
                elif hasattr(sys, "frozen"):
                    delattr(sys, "frozen")
                sys.executable = original_exe

    def test_get_app_data_dir_frozen_fallback_localappdata(self):
        with tempfile.TemporaryDirectory() as fake_appdata:
            original_frozen = getattr(sys, "frozen", False)
            original_exe = sys.executable
            original_appdata = os.environ.get("LOCALAPPDATA")
            try:
                sys.frozen = True
                # Non-existent or unwritable exe path
                sys.executable = r"Z:\nonexistent_drive\bager_library.exe"
                os.environ["LOCALAPPDATA"] = fake_appdata
                resolved = database.get_app_data_dir()
                expected = os.path.join(fake_appdata, "bager_library")
                self.assertEqual(resolved, expected)
                self.assertTrue(os.path.isdir(expected))
            finally:
                if original_frozen:
                    sys.frozen = original_frozen
                elif hasattr(sys, "frozen"):
                    delattr(sys, "frozen")
                sys.executable = original_exe
                if original_appdata is not None:
                    os.environ["LOCALAPPDATA"] = original_appdata
                else:
                    os.environ.pop("LOCALAPPDATA", None)


class TestDatabaseBackupRestore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.source_db = os.path.join(self.temp_dir.name, "source.db")
        self.backup_db = os.path.join(self.temp_dir.name, "backup.db")

        # Initialize source db with standard schema and some records
        conn = sqlite3.connect(self.source_db)
        database.init_database(conn)
        cur = conn.cursor()
        cur.execute("INSERT INTO books (title, author, isbn) VALUES ('کتاب تستی', 'نویسنده تست', '9780001112223')")
        cur.execute("INSERT INTO members (username, phone_number) VALUES ('کاربر تستی', '09123456789')")
        conn.commit()
        conn.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_backup_and_restore_success(self):
        # 1. Take backup
        saved_path = database.backup_database(self.backup_db, source_path_or_conn=self.source_db)
        self.assertTrue(os.path.exists(saved_path))

        # 2. Modify original source db
        conn = sqlite3.connect(self.source_db)
        cur = conn.cursor()
        cur.execute("DELETE FROM books")
        conn.commit()
        cur.execute("SELECT COUNT(*) FROM books")
        self.assertEqual(cur.fetchone()[0], 0)
        conn.close()

        # 3. Restore from backup
        database.restore_database(self.backup_db, target_path_or_conn=self.source_db)

        # 4. Verify original books restored
        conn = sqlite3.connect(self.source_db)
        cur = conn.cursor()
        cur.execute("SELECT title, author FROM books")
        rows = cur.fetchall()
        conn.close()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "کتاب تستی")

    def test_restore_invalid_file_fails(self):
        invalid_path = os.path.join(self.temp_dir.name, "invalid.db")
        with open(invalid_path, "w", encoding="utf-8") as f:
            f.write("not a sqlite database")
        with self.assertRaises(ValueError):
            database.restore_database(invalid_path, target_path_or_conn=self.source_db)

    def test_restore_nonexistent_file_fails(self):
        fake_path = os.path.join(self.temp_dir.name, "does_not_exist.db")
        with self.assertRaises(FileNotFoundError):
            database.restore_database(fake_path, target_path_or_conn=self.source_db)


class TestCsvExport(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.csv_path = os.path.join(self.temp_dir.name, "export.csv")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_write_csv_file_basic(self):
        headers = ["شناسه", "عنوان", "نویسنده"]
        rows = [
            [1, "شاهنامه", "فردوسی"],
            [2, "گلستان", "سعدی"],
        ]
        out_path = database.write_csv_file(self.csv_path, headers, rows)
        self.assertTrue(os.path.exists(out_path))

        # Check BOM is present (0xEF, 0xBB, 0xBF)
        with open(out_path, "rb") as f:
            raw = f.read(3)
            self.assertEqual(raw, b"\xef\xbb\xbf")

        # Read back with csv.reader
        import csv

        with open(out_path, "r", encoding="utf-8-sig") as f:
            reader = list(csv.reader(f))
            self.assertEqual(reader[0], headers)
            self.assertEqual(reader[1], ["1", "شاهنامه", "فردوسی"])
            self.assertEqual(reader[2], ["2", "گلستان", "سعدی"])


class TestLoanEligibility(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        database.init_database(self.conn)
        cur = self.conn.cursor()
        cur.execute("INSERT INTO members (id, username, phone_number) VALUES (1, 'علی رضایی', '09120000001')")
        cur.execute("INSERT INTO books (id, title, author) VALUES (1, 'کتاب اول', 'نویسنده ۱')")
        cur.execute("INSERT INTO books (id, title, author) VALUES (2, 'کتاب دوم', 'نویسنده ۲')")
        cur.execute("INSERT INTO books (id, title, author) VALUES (3, 'کتاب سوم', 'نویسنده ۳')")
        cur.execute("INSERT INTO books (id, title, author) VALUES (4, 'کتاب چهارم', 'نویسنده ۴')")
        cur.execute("INSERT INTO books (id, title, author) VALUES (5, 'کتاب پنجم', 'نویسنده ۵')")
        database.set_setting(self.conn, "max_loans", "3")
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_fresh_member_is_eligible(self):
        ok, msg, stats = database.check_member_loan_eligibility(1, conn_or_path=self.conn, current_date="2026-09-24")
        self.assertTrue(ok)
        self.assertEqual(stats["active_loans"], 0)
        self.assertEqual(stats["overdue_loans"], 0)
        self.assertEqual(stats["max_quota"], 3)

    def test_member_under_quota_is_eligible(self):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO loans (member_id, book_id, borrow_date, return_date, borrowed) VALUES (1, 1, '2026-09-20', '2026-09-30', 1)"
        )
        self.conn.commit()
        ok, msg, stats = database.check_member_loan_eligibility(1, conn_or_path=self.conn, current_date="2026-09-24")
        self.assertTrue(ok)
        self.assertEqual(stats["active_loans"], 1)

    def test_member_at_quota_is_blocked(self):
        cur = self.conn.cursor()
        for b_id in (1, 2, 3):
            cur.execute(
                f"INSERT INTO loans (member_id, book_id, borrow_date, return_date, borrowed) VALUES (1, {b_id}, '2026-09-20', '2026-09-30', 1)"
            )
        self.conn.commit()
        ok, msg, stats = database.check_member_loan_eligibility(1, conn_or_path=self.conn, current_date="2026-09-24")
        self.assertFalse(ok)
        self.assertIn("سقف مجاز", msg)
        self.assertEqual(stats["active_loans"], 3)

    def test_member_with_overdue_is_blocked(self):
        cur = self.conn.cursor()
        # Return date was 2026-09-22, but today is 2026-09-24
        cur.execute(
            "INSERT INTO loans (member_id, book_id, borrow_date, return_date, borrowed) VALUES (1, 1, '2026-09-10', '2026-09-22', 1)"
        )
        self.conn.commit()
        ok, msg, stats = database.check_member_loan_eligibility(1, conn_or_path=self.conn, current_date="2026-09-24")
        self.assertFalse(ok)
        self.assertIn("تأخیر", msg)
        self.assertEqual(stats["overdue_loans"], 1)

    def test_returned_overdue_book_does_not_block(self):
        cur = self.conn.cursor()
        # Overdue date, but returned (borrowed = 0)
        cur.execute(
            "INSERT INTO loans (member_id, book_id, borrow_date, return_date, borrowed) VALUES (1, 1, '2026-09-10', '2026-09-22', 0)"
        )
        self.conn.commit()
        ok, msg, stats = database.check_member_loan_eligibility(1, conn_or_path=self.conn, current_date="2026-09-24")
        self.assertTrue(ok)
        self.assertEqual(stats["overdue_loans"], 0)


if __name__ == "__main__":
    unittest.main()
