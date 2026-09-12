import datetime
import os
import sqlite3
import sys

try:
    import jdatetime
except ImportError:
    jdatetime = None

base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def get_app_data_dir() -> str:
    """
    Return the persistent directory where application data (database, settings) is stored.

    1. Respects BAGER_DATA_DIR environment variable if specified.
    2. When frozen (PyInstaller executable):
       - Attempts to use the directory containing the executable (portable mode).
       - Falls back to the user's Local AppData folder (%LOCALAPPDATA%/bager_library)
         if the executable directory is not writable (e.g. Program Files).
    3. In development mode: returns the repository root directory.
    """
    env_dir = os.environ.get("BAGER_DATA_DIR")
    if env_dir:
        os.makedirs(env_dir, exist_ok=True)
        return env_dir

    if getattr(sys, "frozen", False):
        sys_exe = getattr(sys, "executable", None) or ""
        exe_dir = os.path.dirname(os.path.abspath(sys_exe)) if sys_exe else ""
        if exe_dir and os.path.exists(exe_dir):
            try:
                test_file = os.path.join(exe_dir, f".write_test_{os.getpid()}")
                with open(test_file, "w") as f:
                    f.write("test")
                try:
                    os.remove(test_file)
                except OSError:
                    pass
                return exe_dir
            except (OSError, PermissionError):
                pass

        appdata = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        data_dir = os.path.join(appdata, "bager_library")
        os.makedirs(data_dir, exist_ok=True)
        return data_dir

    return os.path.dirname(os.path.abspath(__file__))


def get_db_path() -> str:
    """Return the absolute path to the persistent SQLite database file."""
    env_db = os.environ.get("BAGER_DB_PATH")
    if env_db:
        return env_db
    return os.path.join(get_app_data_dir(), "bager_library.db")


def load_env_file(filepath: str | None = None):
    candidates: list[str] = []
    if filepath:
        candidates.append(filepath)
    else:
        candidates.append(os.path.join(get_app_data_dir(), ".env"))
        if getattr(sys, "frozen", False):
            sys_exe = getattr(sys, "executable", None) or ""
            if sys_exe:
                candidates.append(os.path.join(os.path.dirname(os.path.abspath(sys_exe)), ".env"))
        if base_dir not in candidates:
            candidates.append(os.path.join(base_dir, ".env"))

    for p in candidates:
        if os.path.exists(p):
            try:
                from dotenv import load_dotenv

                load_dotenv(p)
                break
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
                    break
                except Exception:
                    pass


load_env_file()
app_data_dir = get_app_data_dir()
db_p = get_db_path()

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
    "loan_id": "شناسه امانت",
    "book_title": "عنوان کتاب",
    "due_soon": "یادآوری موعد",
    "due_today": "سررسید امروز",
    "due_reminder": "یادآوری سررسید",
    "overdue": "هشدار دیرکرد",
    "test": "اعلان آزمایشی",
    "status": "وضعیت",
    "notification_logs": "لاگ‌های اعلان",
    "notifications_enabled": "فعال‌سازی اعلان‌ها",
    "notification_sound": "صدای اعلان",
    "notification_advance_days": "روزهای پیش‌هشدار",
    "notification_check_interval_mins": "بازه بررسی خودکار",
    "all": "همه",
}


def tr(key: object) -> str:
    s = str(key) if key is not None else ""
    return TRANSLATIONS.get(s, s)


def rtl_display_order(cols: list[str], preferred_order: list[str]) -> list[str]:
    ordered = [c for c in preferred_order if c in cols] + [c for c in cols if c not in preferred_order]
    return list(reversed(ordered))


def get_db_connection(database_path: str | None = None, enable_foreign_keys: bool = True) -> sqlite3.Connection:
    target_path = database_path or db_p
    target_dir = os.path.dirname(os.path.abspath(target_path))
    if target_dir and not os.path.exists(target_dir):
        try:
            os.makedirs(target_dir, exist_ok=True)
        except OSError:
            pass
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
                loan_id INTEGER REFERENCES loans(id),
                notification_type VARCHAR(50) NOT NULL,
                sent_date DATE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Migration: check if loan_id in notification_logs is NOT NULL, and migrate if so
        try:
            cur.execute('PRAGMA table_info("notification_logs")')
            nl_info = {str(r[1]): r for r in cur.fetchall()}
            if "loan_id" in nl_info and nl_info["loan_id"][3] == 1:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS notification_logs_temp (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        loan_id INTEGER REFERENCES loans(id),
                        notification_type VARCHAR(50) NOT NULL,
                        sent_date DATE NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cur.execute(
                    "INSERT INTO notification_logs_temp (id, loan_id, notification_type, sent_date, created_at) SELECT id, loan_id, notification_type, sent_date, created_at FROM notification_logs"
                )
                cur.execute("DROP TABLE notification_logs")
                cur.execute("ALTER TABLE notification_logs_temp RENAME TO notification_logs")
        except Exception:
            pass

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


def _resolve_connection(conn_or_path: sqlite3.Connection | str | None = None) -> tuple[sqlite3.Connection, bool]:
    if isinstance(conn_or_path, sqlite3.Connection):
        return conn_or_path, False
    return get_db_connection(database_path=conn_or_path), True


def get_setting(
    key_or_conn: sqlite3.Connection | str,
    default_or_key: str = "",
    default: str = "",
    database_path: sqlite3.Connection | str | None = None,
    conn_or_path: sqlite3.Connection | str | None = None,
) -> str:
    target_path = conn_or_path if conn_or_path is not None else database_path
    if isinstance(key_or_conn, sqlite3.Connection):
        conn = key_or_conn
        key = default_or_key
        default_val = default
        try:
            cur = conn.cursor()
            cur.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
            row = cur.fetchone()
            if row is not None and str(row[0]) != "":
                return str(row[0])
        except Exception:
            pass
        return default_val

    key = str(key_or_conn)
    default_val = default_or_key if default_or_key != "" else default

    if target_path is not None:
        c, should_close = _resolve_connection(target_path)
        try:
            cur = c.cursor()
            cur.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
            row = cur.fetchone()
            if row is not None and str(row[0]) != "":
                return str(row[0])
        except Exception:
            pass
        finally:
            if should_close:
                c.close()

    env_val = os.getenv(key.upper())
    if env_val is None:
        env_val = os.getenv(key)
    if env_val is not None:
        return env_val

    c, should_close = _resolve_connection(target_path)
    try:
        cur = c.cursor()
        cur.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
        row = cur.fetchone()
        return str(row[0]) if row else default_val
    except Exception:
        return default_val
    finally:
        if should_close:
            c.close()


def set_setting(
    key_or_conn: sqlite3.Connection | str,
    value_or_key: str,
    database_path_or_value: sqlite3.Connection | str | None = None,
    database_path: sqlite3.Connection | str | None = None,
    conn_or_path: sqlite3.Connection | str | None = None,
    sync_env: bool = True,
):
    if isinstance(key_or_conn, sqlite3.Connection):
        conn = key_or_conn
        key = str(value_or_key)
        str_val = str(database_path_or_value)
        db_p = conn
    else:
        key = str(key_or_conn)
        str_val = str(value_or_key)
        db_p = conn_or_path if conn_or_path is not None else (database_path or database_path_or_value)

    if sync_env:
        os.environ[key.upper()] = str_val
        os.environ[key] = str_val

    c, should_close = _resolve_connection(db_p)
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
        if should_close:
            c.close()


def get_all_settings(
    database_path: sqlite3.Connection | str | None = None,
    conn_or_path: sqlite3.Connection | str | None = None,
) -> dict[str, str]:
    target_path = conn_or_path if conn_or_path is not None else database_path
    settings = {}
    c, should_close = _resolve_connection(target_path)
    try:
        cur = c.cursor()
        cur.execute("SELECT key, value FROM app_settings")
        for k, v in cur.fetchall():
            settings[str(k)] = str(v)
    except Exception:
        pass
    finally:
        if should_close:
            c.close()

    for k in list(settings.keys()):
        env_val = os.getenv(k.upper())
        if env_val is None:
            env_val = os.getenv(k)
        if env_val is not None:
            settings[k] = env_val

    return settings


def _normalize_filter_date(val: str | None) -> str | None:
    if not val:
        return None
    cleaned = val.strip().replace("/", "-")
    parts = cleaned.split("-")
    if len(parts) == 3:
        try:
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            if y < 1900 and jdatetime is not None:
                g_date = jdatetime.date(y, m, d).togregorian()
                return g_date.strftime("%Y-%m-%d")
            return f"{y:04d}-{m:02d}-{d:02d}"
        except Exception:
            pass
    return cleaned


def get_notification_logs(
    conn_or_path: sqlite3.Connection | str | None = None,
    notification_type: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    search_query: str | None = None,
    column: str = "all",
    match_mode: str = "contains",
    sort_col: str = "id",
    sort_dir: str = "DESC",
    limit: int | None = None,
    offset: int = 0,
) -> list[dict]:
    conn, should_close = _resolve_connection(conn_or_path)
    try:
        cur = conn.cursor()
        query = """
            SELECT
                nl.id,
                nl.loan_id,
                nl.notification_type,
                nl.sent_date,
                nl.created_at,
                CASE WHEN nl.loan_id IS NULL THEN NULL ELSE COALESCE(b.title, l.book_id, 'نامشخص') END AS book_title,
                CASE WHEN nl.loan_id IS NULL THEN NULL ELSE COALESCE(l.member_name, 'نامشخص') END AS member_name
            FROM notification_logs nl
            LEFT JOIN loans l ON nl.loan_id = l.id
            LEFT JOIN books b ON (CAST(l.book_id AS TEXT) = CAST(b.id AS TEXT) OR l.book_id = b.title)
        """
        conditions: list[str] = []
        params: list[object] = []

        if notification_type and notification_type.strip().lower() not in ("all", "همه", ""):
            nt = notification_type.strip()
            nt_lower = nt.lower()
            if nt_lower in ("due_reminder", "reminder", "due_soon", "یادآوری سررسید امانت", "یادآوری سررسید"):
                conditions.append("LOWER(nl.notification_type) IN ('due_reminder', 'due_soon', 'due_today')")
            elif nt_lower in ("overdue", "هشدار تأخیر بازگشت", "هشدار دیرکرد", "دارای تاخیر"):
                conditions.append("LOWER(nl.notification_type) IN ('overdue', 'هشدار دیرکرد', 'دارای تاخیر')")
            elif nt_lower in ("test", "test_notification", "اعلان آزمایشی"):
                conditions.append("LOWER(nl.notification_type) IN ('test', 'test_notification')")
            else:
                conditions.append("LOWER(nl.notification_type) = LOWER(?)")
                params.append(nt)

        start_date_norm = _normalize_filter_date(start_date)
        if start_date_norm:
            conditions.append("nl.sent_date >= ?")
            params.append(start_date_norm)

        end_date_norm = _normalize_filter_date(end_date)
        if end_date_norm:
            conditions.append("nl.sent_date <= ?")
            params.append(end_date_norm)

        if search_query and search_query.strip():
            sq_raw = search_query.strip()
            mode = (match_mode or "contains").strip().lower()
            if mode == "exact":
                pattern = sq_raw
            elif mode == "startswith":
                pattern = f"{sq_raw}%"
            else:
                pattern = f"%{sq_raw}%"

            col = (column or "all").strip().lower()
            type_case_expr = (
                "(CASE "
                "WHEN nl.notification_type IN ('due_reminder', 'due_soon', 'due_today') THEN 'due_reminder یادآوری سررسید امانت' "
                "WHEN nl.notification_type IN ('overdue', 'هشدار دیرکرد') THEN 'overdue هشدار دیرکرد تأخیر' "
                "WHEN nl.notification_type IN ('test', 'test_notification') THEN 'test اعلان آزمایشی' "
                "ELSE nl.notification_type END)"
            )

            sq_date_norm = _normalize_filter_date(sq_raw)

            if col == "book_title":
                conditions.append("(b.title LIKE ? OR l.book_id LIKE ?)")
                params.extend([pattern, pattern])
            elif col == "member_name":
                conditions.append("l.member_name LIKE ?")
                params.append(pattern)
            elif col == "loan_id":
                conditions.append("CAST(nl.loan_id AS TEXT) LIKE ?")
                params.append(pattern)
            elif col == "id":
                conditions.append("CAST(nl.id AS TEXT) LIKE ?")
                params.append(pattern)
            elif col == "sent_date":
                if sq_date_norm and sq_date_norm != sq_raw:
                    date_pattern = (
                        f"%{sq_date_norm}%"
                        if mode == "contains"
                        else (f"{sq_date_norm}%" if mode == "startswith" else sq_date_norm)
                    )
                    conditions.append("(CAST(nl.sent_date AS TEXT) LIKE ? OR CAST(nl.sent_date AS TEXT) LIKE ?)")
                    params.extend([pattern, date_pattern])
                else:
                    conditions.append("CAST(nl.sent_date AS TEXT) LIKE ?")
                    params.append(pattern)
            elif col in ("notification_type", "type"):
                conditions.append(f"(nl.notification_type LIKE ? OR {type_case_expr} LIKE ?)")
                params.extend([pattern, pattern])
            else:
                # "all"
                all_parts = [
                    "(b.title LIKE ? OR l.book_id LIKE ?)",
                    "l.member_name LIKE ?",
                    "CAST(nl.loan_id AS TEXT) LIKE ?",
                    "CAST(nl.id AS TEXT) LIKE ?",
                    "CAST(nl.sent_date AS TEXT) LIKE ?",
                    f"(nl.notification_type LIKE ? OR {type_case_expr} LIKE ?)",
                ]
                all_params = [pattern, pattern, pattern, pattern, pattern, pattern, pattern, pattern]
                if sq_date_norm and sq_date_norm != sq_raw:
                    date_pattern = (
                        f"%{sq_date_norm}%"
                        if mode == "contains"
                        else (f"{sq_date_norm}%" if mode == "startswith" else sq_date_norm)
                    )
                    all_parts.append("CAST(nl.sent_date AS TEXT) LIKE ?")
                    all_params.append(date_pattern)

                conditions.append(f"({' OR '.join(all_parts)})")
                params.extend(all_params)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        sort_map = {
            "id": "nl.id",
            "sent_date": "nl.sent_date",
            "created_at": "nl.created_at",
            "notification_type": "nl.notification_type",
            "type": "nl.notification_type",
            "loan_id": "nl.loan_id",
            "book_title": "book_title",
            "member_name": "member_name",
        }
        order_col = sort_map.get(str(sort_col).strip().lower(), "nl.id")
        order_dir = "ASC" if str(sort_dir).strip().upper() == "ASC" else "DESC"
        query += f" ORDER BY {order_col} {order_dir}"

        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
            if offset > 0:
                query += " OFFSET ?"
                params.append(offset)

        cur.execute(query, params)
        rows = cur.fetchall()
        results = []
        for r in rows:
            results.append(
                {
                    "id": r[0],
                    "loan_id": r[1],
                    "notification_type": r[2],
                    "sent_date": str(r[3]) if r[3] is not None else "",
                    "created_at": str(r[4]) if r[4] is not None else "",
                    "book_title": str(r[5]) if r[5] is not None else None,
                    "member_name": str(r[6]) if r[6] is not None else None,
                }
            )
        return results
    finally:
        if should_close:
            conn.close()


def clear_notification_logs(
    conn_or_path: sqlite3.Connection | str | None = None,
    before_date: str | None = None,
) -> int:
    conn, should_close = _resolve_connection(conn_or_path)
    try:
        cur = conn.cursor()
        if before_date and before_date.strip():
            cur.execute("DELETE FROM notification_logs WHERE sent_date < ?", (before_date.strip(),))
        else:
            cur.execute("DELETE FROM notification_logs")
        deleted_count = cur.rowcount
        conn.commit()
        return deleted_count
    finally:
        if should_close:
            conn.close()


def log_notification(
    conn_or_path: sqlite3.Connection | str | None = None,
    notification_type: str = "test",
    loan_id: int | None = None,
    sent_date: str | None = None,
) -> int:
    """Log an audit entry in notification_logs. Returns the inserted row ID."""
    conn, should_close = _resolve_connection(conn_or_path)
    try:
        cur = conn.cursor()
        if not sent_date:
            sent_date = datetime.date.today().isoformat()
        cur.execute(
            """
            INSERT INTO notification_logs (loan_id, notification_type, sent_date)
            VALUES (?, ?, ?)
            """,
            (loan_id, notification_type, sent_date),
        )
        inserted_id = cur.lastrowid or 0
        conn.commit()
        return inserted_id
    finally:
        if should_close:
            conn.close()
