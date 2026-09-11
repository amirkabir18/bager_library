import os
import sqlite3
import sys

base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
db_p = os.path.join(base_dir, "bager_library.db")


def load_env_file(filepath: str | None = None):
    p = filepath or os.path.join(base_dir, ".env")
    if not os.path.exists(p):
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(p)
    except Exception:
        try:
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass


load_env_file()

TRANSLATIONS: dict[str, str] = {
    "id": "شناسه",
    "title": "عنوان کتاب",
    "author": "نویسنده",
    "isbn": "شابک",
    "member_id": "نام کاربر",
    "phone_number": "شماره تلفن",
    "borrow_date": "تاریخ امانت",
    "return_date": "تاریخ بازگشت",
    "borrowed": "وضعیت امانت",
    "book_id": "نام کتاب",
    "member_name": "نام کاربر",
    "username": "نام کاربری",
    "role": "نقش",
    "telegram_chat_id": "شناسه تلگرام",
    "telegram_relay_url": "آدرس رله تلگرام",
    "telegram_relay_secret": "کلید امنیتی رله",
    "is_active": "وضعیت فعال",
    "created_at": "تاریخ ثبت",
    "password_hash": "هش رمز عبور",
    "otp_hash": "هش کد یکبار مصرف",
    "expires_at": "تاریخ انقضا",
    "attempts": "تعداد تلاش‌ها",
    "is_used": "استفاده شده",
    "notification_type": "نوع اعلان",
    "sent_date": "تاریخ ارسال",
    "key": "کلید تنظیمات",
    "value": "مقدار تنظیمات",
    "super admin": "سرپرست",
    "superadmin": "سرپرست",
    "admin": "مدیر",
    "librarian": "کتابدار",
    "user": "کاربر",
}


def tr(key: object) -> str:
    s = str(key) if key is not None else ""
    return TRANSLATIONS.get(s, s)


def rtl_display_order(cols: list[str], preferred_order: list[str]) -> list[str]:
    ordered = [c for c in preferred_order if c in cols] + [c for c in cols if c not in preferred_order]
    return list(reversed(ordered))


def get_db_connection(database_path: str | None = None, enable_foreign_keys: bool = True) -> sqlite3.Connection:
    target_path = database_path or db_p
    c = sqlite3.connect(target_path)
    if enable_foreign_keys:
        c.execute("PRAGMA foreign_keys = ON")
    return c


def init_database(connection: sqlite3.Connection | None = None):
    should_close = False
    if connection is None:
        connection = get_db_connection()
        should_close = True

    try:
        cur = connection.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                author VARCHAR(255),
                isbn VARCHAR(255) UNIQUE,
                title VARCHAR(255)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                member_id VARCHAR(255) UNIQUE NOT NULL,
                phone_number VARCHAR(255) NOT NULL
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS loans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                borrow_date DATE NOT NULL,
                return_date DATE,
                borrowed BOOLEAN DEFAULT 1,
                book_id VARCHAR(255),
                member_name VARCHAR(255)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS auth_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(100) UNIQUE NOT NULL,
                phone_number VARCHAR(20) UNIQUE NOT NULL,
                telegram_chat_id VARCHAR(50),
                role VARCHAR(20) DEFAULT 'librarian',
                password_hash VARCHAR(255),
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS otp_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number VARCHAR(20) NOT NULL,
                otp_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                attempts INTEGER DEFAULT 0,
                is_used BOOLEAN DEFAULT 0
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS notification_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                loan_id INTEGER NOT NULL REFERENCES loans(id),
                notification_type VARCHAR(50) NOT NULL,
                sent_date DATE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key VARCHAR(100) PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        default_settings = [
            ("notifications_enabled", "true"),
            ("notification_advance_days", "2"),
            ("notification_sound", "true"),
            ("notification_check_interval_mins", "30"),
        ]
        cur.executemany(
            """
            INSERT OR IGNORE INTO app_settings (key, value)
            VALUES (?, ?)
        """,
            default_settings,
        )

        try:
            cur.execute("ALTER TABLE books DROP COLUMN location")
        except Exception:
            pass

        cur.execute('PRAGMA table_info("auth_users")')
        existing_user_cols = {str(row[1]) for row in cur.fetchall()}
        user_col_defs = {
            "telegram_chat_id": "VARCHAR(50)",
            "role": "VARCHAR(20) DEFAULT 'librarian'",
            "password_hash": "VARCHAR(255)",
            "is_active": "BOOLEAN DEFAULT 1",
            "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        }
        for col_name, col_def in user_col_defs.items():
            if col_name not in existing_user_cols:
                try:
                    cur.execute(f"ALTER TABLE auth_users ADD COLUMN {col_name} {col_def}")
                except Exception:
                    pass

        cur.execute("CREATE INDEX IF NOT EXISTS idx_loans_return_borrowed ON loans(return_date, borrowed)")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_notification_logs_lookup ON notification_logs(loan_id, sent_date, notification_type)"
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_otp_sessions_phone ON otp_sessions(phone_number, expires_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_auth_users_username ON auth_users(username)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_auth_users_phone ON auth_users(phone_number)")

        connection.commit()
    finally:
        if should_close:
            connection.close()


def get_setting(key: str, default: str = "", database_path: str | None = None) -> str:
    if database_path is not None:
        c = get_db_connection(database_path=database_path)
        try:
            cur = c.cursor()
            cur.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
            row = cur.fetchone()
            if row is not None and str(row[0]) != "":
                return str(row[0])
        except Exception:
            pass
        finally:
            c.close()

    env_val = os.getenv(key.upper())
    if env_val is None:
        env_val = os.getenv(key)
    if env_val is not None:
        return env_val

    c = get_db_connection(database_path=database_path)
    try:
        cur = c.cursor()
        cur.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
        row = cur.fetchone()
        return str(row[0]) if row else default
    except Exception:
        return default
    finally:
        c.close()


def set_setting(key: str, value: str, database_path: str | None = None, sync_env: bool = True):
    str_val = str(value)
    if sync_env:
        os.environ[key.upper()] = str_val
        os.environ[key] = str_val

    c = get_db_connection(database_path=database_path)
    try:
        cur = c.cursor()
        cur.execute(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
        """,
            (key, str_val),
        )
        c.commit()
    finally:
        c.close()


def get_all_settings(database_path: str | None = None) -> dict[str, str]:
    settings = {}
    c = get_db_connection(database_path=database_path)
    try:
        cur = c.cursor()
        cur.execute("SELECT key, value FROM app_settings")
        for k, v in cur.fetchall():
            settings[str(k)] = str(v)
    except Exception:
        pass
    finally:
        c.close()

    for k in list(settings.keys()):
        env_val = os.getenv(k.upper())
        if env_val is None:
            env_val = os.getenv(k)
        if env_val is not None:
            settings[k] = env_val

    return settings
