import json
import os
import re
import secrets
import socket
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

from database import db_p, get_db_connection, get_setting, set_setting


# ==============================================================================
# Helper Functions: Phone Normalization & Conversions
# ==============================================================================

PERSIAN_ARABIC_DIGITS = {
    '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
    '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9',
    '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
    '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9',
}

def normalize_digits(text: str) -> str:
    """Converts Persian and Arabic digits to standard ASCII digits."""
    if not text:
        return ""
    result = []
    for ch in str(text):
        result.append(PERSIAN_ARABIC_DIGITS.get(ch, ch))
    return "".join(result)

def normalize_phone_number(phone: str) -> str:
    """
    Normalizes Iranian phone numbers to standard 11-digit format (09xxxxxxxxx).
    Handles:
      - Persian/Arabic digits
      - Country code prefixes: +98, 0098, 98
      - Leading zeroes or omitted leading zero: 9123456789 -> 09123456789
      - Non-digit separators (spaces, dashes, parentheses)
    """
    cleaned = normalize_digits(phone).strip()
    digits = re.sub(r'\D', '', cleaned)

    if not digits:
        return ""

    if digits.startswith('0098'):
        digits = digits[4:]
    elif digits.startswith('98') and len(digits) >= 11:
        digits = digits[2:]

    if digits.startswith('9') and len(digits) == 10:
        digits = '0' + digits

    if digits.startswith('09') and len(digits) == 11:
        return digits

    # Fallback if phone doesn't match standard Iranian mobile format
    return '0' + digits if not digits.startswith('0') else digits

def mask_phone_number(phone: str) -> str:
    """Masks phone number for secure display (e.g. 0912***6789)."""
    normalized = normalize_phone_number(phone)
    if len(normalized) == 11:
        return f"{normalized[:4]}***{normalized[7:]}"
    return normalized


# ==============================================================================
# Password Hashing & Verification (PBKDF2-HMAC-SHA256)
# ==============================================================================

PBKDF2_ITERATIONS = 100_000

def hash_password(password: str, iterations: int = PBKDF2_ITERATIONS, salt: bytes | None = None) -> str:
    """
    Hashes password using PBKDF2-HMAC-SHA256 with a cryptographically secure random salt.
    Format: pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>
    """
    if not password:
        raise ValueError("Password cannot be empty.")
    salt_bytes = salt if salt is not None else secrets.token_bytes(16)
    dk = secrets.compare_digest  # Ensure module availability
    import hashlib
    hash_bytes = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt_bytes, iterations)
    return f"pbkdf2_sha256${iterations}${salt_bytes.hex()}${hash_bytes.hex()}"

def verify_password(password: str, stored_hash: str) -> bool:
    """
    Verifies a plaintext password against a stored PBKDF2 hash using constant-time comparison.
    """
    if not password or not stored_hash:
        return False
    try:
        parts = stored_hash.split('$')
        if len(parts) != 4 or parts[0] != 'pbkdf2_sha256':
            return False
        iterations = int(parts[1])
        salt_bytes = bytes.fromhex(parts[2])
        expected_hash = parts[3]
        import hashlib
        calc_bytes = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt_bytes, iterations)
        return secrets.compare_digest(calc_bytes.hex(), expected_hash)
    except Exception:
        return False


# ==============================================================================
# OTP Cryptographic Generation & Salted Hashing
# ==============================================================================

def generate_otp_code(length: int = 6) -> str:
    """Generates a cryptographically secure random numeric OTP code."""
    upper_bound = 10 ** length
    code_int = secrets.randbelow(upper_bound)
    return f"{code_int:0{length}d}"

def hash_otp(otp_code: str, salt: str | None = None) -> str:
    """
    Generates a salted SHA-256 hash for OTP storage in otp_sessions.
    Format: <salt_hex>$<hash_hex>
    """
    import hashlib
    salt_str = salt if salt is not None else secrets.token_hex(8)
    h = hashlib.sha256(f"{salt_str}:{otp_code}".encode('utf-8')).hexdigest()
    return f"{salt_str}${h}"

def verify_otp_hash(otp_code: str, stored_hash: str) -> bool:
    """Constant-time verification of OTP code against stored salted hash."""
    if not otp_code or not stored_hash or '$' not in stored_hash:
        return False
    salt_str, expected_hash = stored_hash.split('$', 1)
    import hashlib
    calc_hash = hashlib.sha256(f"{salt_str}:{otp_code}".encode('utf-8')).hexdigest()
    return secrets.compare_digest(calc_hash, expected_hash)


# ==============================================================================
# User Management & Database Repository
# ==============================================================================

def create_user(
    username: str,
    phone_number: str,
    password: str | None = None,
    role: str = 'librarian',
    telegram_chat_id: str | None = None,
    is_active: bool = True,
    database_path: str | None = None
) -> tuple[bool, str, dict[str, Any] | None]:
    """
    Creates a new user in auth_users.
    Stores password hashed with PBKDF2.
    """
    norm_phone = normalize_phone_number(phone_number)
    clean_username = username.strip()

    if not clean_username:
        return False, "نام کاربری نمی‌تواند خالی باشد.", None
    if not norm_phone:
        return False, "شماره تلفن معتبر نیست.", None

    pwd_hash = hash_password(password) if password else None

    conn = get_db_connection(database_path=database_path)
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO auth_users (username, phone_number, telegram_chat_id, role, password_hash, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (clean_username, norm_phone, telegram_chat_id, role, pwd_hash, 1 if is_active else 0))
        user_id = cur.lastrowid
        conn.commit()

        user_data = {
            'id': user_id,
            'username': clean_username,
            'phone_number': norm_phone,
            'telegram_chat_id': telegram_chat_id,
            'role': role,
            'is_active': is_active
        }
        return True, "کاربر با موفقیت ثبت شد.", user_data
    except sqlite3.IntegrityError as e:
        err_msg = str(e)
        if 'auth_users.username' in err_msg or 'UNIQUE constraint failed: auth_users.username' in err_msg:
            return False, f"نام کاربری '{clean_username}' قبلاً ثبت شده است.", None
        if 'auth_users.phone_number' in err_msg or 'UNIQUE constraint failed: auth_users.phone_number' in err_msg:
            return False, f"شماره تلفن '{norm_phone}' قبلاً ثبت شده است.", None
        return False, f"خطای یکتایی در ثبت کاربر: {err_msg}", None
    except Exception as e:
        return False, f"خطا در ایجاد کاربر: {str(e)}", None
    finally:
        conn.close()

def get_user_by_username(username: str, database_path: str | None = None) -> dict[str, Any] | None:
    conn = get_db_connection(database_path=database_path)
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM auth_users WHERE username = ? COLLATE NOCASE", (username.strip(),))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def get_user_by_phone(phone_number: str, database_path: str | None = None) -> dict[str, Any] | None:
    norm_phone = normalize_phone_number(phone_number)
    conn = get_db_connection(database_path=database_path)
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM auth_users WHERE phone_number = ?", (norm_phone,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def get_user_by_identifier(identifier: str, database_path: str | None = None) -> dict[str, Any] | None:
    """Finds user by either username or phone number."""
    user = get_user_by_username(identifier, database_path=database_path)
    if user:
        return user
    norm_phone = normalize_phone_number(identifier)
    if norm_phone:
        return get_user_by_phone(norm_phone, database_path=database_path)
    return None

def update_user_telegram_chat_id(phone_number: str, telegram_chat_id: str, database_path: str | None = None) -> bool:
    norm_phone = normalize_phone_number(phone_number)
    conn = get_db_connection(database_path=database_path)
    try:
        cur = conn.cursor()
        cur.execute("UPDATE auth_users SET telegram_chat_id = ? WHERE phone_number = ?", (str(telegram_chat_id), norm_phone))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()

def list_users(database_path: str | None = None) -> list[dict[str, Any]]:
    conn = get_db_connection(database_path=database_path)
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT id, username, phone_number, telegram_chat_id, role, is_active, created_at FROM auth_users ORDER BY id ASC")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

def has_admin_user(database_path: str | None = None) -> bool:
    conn = get_db_connection(database_path=database_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM auth_users WHERE role = 'admin' AND is_active = 1")
        cnt = cur.fetchone()[0]
        return cnt > 0
    finally:
        conn.close()

def bootstrap_admin_user(
    username: str = "admin",
    phone_number: str = "09120000000",
    password: str = "admin1234",
    telegram_chat_id: str | None = None,
    database_path: str | None = None
) -> tuple[bool, str, dict[str, Any] | None]:
    """
    Bootstraps the default Administrator account if no admin exists.
    Useful for first-time launch wizard and initial setup.
    """
    if has_admin_user(database_path=database_path):
        existing = get_user_by_username(username, database_path=database_path)
        return False, "حساب مدیر از پیش در سامانه تعریف شده است.", existing

    success, msg, user_data = create_user(
        username=username,
        phone_number=phone_number,
        password=password,
        role='admin',
        telegram_chat_id=telegram_chat_id,
        is_active=True,
        database_path=database_path
    )
    if success:
        set_setting('admin_bootstrapped', 'true', database_path=database_path)
    return success, msg, user_data

def ensure_bootstrap_admin(database_path: str | None = None) -> tuple[bool, str]:
    """
    Ensures that at least one admin exists in the database.
    If no admin is found, creates a default admin account.
    """
    if not has_admin_user(database_path=database_path):
        success, msg, _ = bootstrap_admin_user(database_path=database_path)
        return success, msg
    return True, "حساب مدیر حاضر است."


# ==============================================================================
# Network Connectivity Probe
# ==============================================================================

def is_telegram_reachable(
    timeout: float = 2.5,
    proxy: str | None = None,
    api_url: str | None = None
) -> bool:
    """
    Probes whether the Telegram Bot API endpoint is reachable.
    Uses socket connection check for quick timeout without large request overhead.
    """
    target_url = api_url or "https://api.telegram.org"
    parsed = urllib.parse.urlparse(target_url)
    host = parsed.hostname or "api.telegram.org"
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)

    try:
        # Fast socket TCP connect probe
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        pass

    # Fallback to HTTP request probe if custom proxy or direct HTTP is configured
    try:
        req = urllib.request.Request(
            f"{target_url.rstrip('/')}",
            headers={'User-Agent': 'BagerLibrary/1.0'}
        )
        if proxy:
            proxy_handler = urllib.request.ProxyHandler({'http': proxy, 'https': proxy})
            opener = urllib.request.build_opener(proxy_handler)
            with opener.open(req, timeout=timeout) as resp:
                return resp.status in (200, 302, 404)
        else:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status in (200, 302, 404)
    except urllib.error.HTTPError as e:
        # 404 or 400 from telegram still means network connection to api.telegram.org succeeded
        return e.code in (200, 302, 400, 404)
    except Exception:
        return False

def get_network_status(database_path: str | None = None) -> dict[str, Any]:
    """Returns current connectivity status to assist offline vs online mode determination."""
    proxy = get_setting('telegram_proxy', default='', database_path=database_path) or None
    api_url = get_setting('telegram_api_url', default='https://api.telegram.org', database_path=database_path)
    reachable = is_telegram_reachable(timeout=2.0, proxy=proxy, api_url=api_url)

    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        'online': reachable,
        'telegram_reachable': reachable,
        'checked_at': now_iso,
        'mode': 'online' if reachable else 'offline',
        'message': 'اتصال به تلگرام برقرار است.' if reachable else 'عدم دسترسی به تلگرام (حالت آفلاین فعال است).'
    }


# ==============================================================================
# Telegram Bot Client (HTTP API + Update Handler)
# ==============================================================================

class TelegramBotClient:
    """
    Lightweight Telegram Bot API client using standard library urllib.
    Supports:
      - /sendMessage with HTML formatting and custom keyboards
      - /getUpdates polling
      - Contact sharing for Telegram account pairing with auth_users
      - Connection testing via /getMe
    """

    def __init__(
        self,
        token: str | None = None,
        database_path: str | None = None,
        proxy: str | None = None,
        api_url: str | None = None
    ):
        self.database_path = database_path
        self._explicit_token = token
        self._proxy = proxy
        self._api_url = api_url

    @property
    def token(self) -> str:
        if self._explicit_token:
            return self._explicit_token
        # Try database setting
        db_token = get_setting('telegram_bot_token', default='', database_path=self.database_path)
        if db_token:
            return db_token.strip()
        # Try environment variable
        env_token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
        return env_token

    @property
    def api_url(self) -> str:
        if self._api_url:
            return self._api_url.rstrip('/')
        db_url = get_setting('telegram_api_url', default='https://api.telegram.org', database_path=self.database_path)
        return db_url.rstrip('/')

    @property
    def proxy(self) -> str | None:
        if self._proxy:
            return self._proxy
        db_proxy = get_setting('telegram_proxy', default='', database_path=self.database_path)
        return db_proxy.strip() or None

    def _make_request(self, method: str, data: dict[str, Any] | None = None, timeout: float = 10.0) -> dict[str, Any]:
        curr_token = self.token
        if not curr_token:
            raise ValueError("توکن ربات تلگرام تنظیم نشده است.")

        endpoint = f"{self.api_url}/bot{curr_token}/{method}"
        headers = {'User-Agent': 'BagerLibrary/1.0', 'Content-Type': 'application/json'}

        post_bytes = json.dumps(data).encode('utf-8') if data is not None else None
        req = urllib.request.Request(endpoint, data=post_bytes, headers=headers)

        opener = urllib.request.build_opener()
        if self.proxy:
            proxy_handler = urllib.request.ProxyHandler({'http': self.proxy, 'https': self.proxy})
            opener = urllib.request.build_opener(proxy_handler)

        with opener.open(req, timeout=timeout) as response:
            res_json = json.loads(response.read().decode('utf-8'))
            return res_json

    def test_connection(self) -> tuple[bool, str, dict[str, Any] | None]:
        """Tests bot token validity and connectivity using getMe."""
        try:
            res = self._make_request('getMe', timeout=4.0)
            if res.get('ok'):
                bot_user = res.get('result', {})
                bot_name = bot_user.get('first_name', '')
                username = bot_user.get('username', '')
                return True, f"اتصال به ربات @{username} ({bot_name}) با موفقیت برقرار شد.", bot_user
            return False, res.get('description', 'خطا در احراز هویت ربات'), None
        except Exception as e:
            return False, f"خطا در اتصال به ربات تلگرام: {str(e)}", None

    def send_message(
        self,
        chat_id: str | int,
        text: str,
        parse_mode: str = 'HTML',
        reply_markup: dict[str, Any] | None = None
    ) -> tuple[bool, str, dict[str, Any] | None]:
        """Sends a message to a specific Telegram chat_id."""
        payload: dict[str, Any] = {
            'chat_id': str(chat_id),
            'text': text,
            'parse_mode': parse_mode
        }
        if reply_markup:
            payload['reply_markup'] = reply_markup

        try:
            res = self._make_request('sendMessage', data=payload, timeout=8.0)
            if res.get('ok'):
                return True, "پیام با موفقیت ارسال شد.", res.get('result')
            return False, res.get('description', 'خطا در ارسال پیام تلگرام'), None
        except Exception as e:
            return False, f"خطا در ارسال پیام: {str(e)}", None

    def send_otp_message(self, chat_id: str | int, otp_code: str, username: str = "") -> tuple[bool, str]:
        """Sends an OTP authentication message formatted in RTL Persian with security notices."""
        user_display = f"کاربر گرامی <b>{username}</b>\n" if username else ""
        text = (
            f"🔐 <b>سامانه کتابخانه باقرالعلوم</b>\n\n"
            f"{user_display}"
            f"کد یکبار مصرف ورود شما:\n"
            f"<code>{otp_code}</code>\n\n"
            f"⏱ این کد به مدت <b>۲ دقیقه</b> معتبر است.\n"
            f"⚠️ این کد را در اختیار دیگران قرار ندهید."
        )
        success, msg, _ = self.send_message(chat_id=chat_id, text=text)
        return success, msg

    def get_updates(self, offset: int | None = None, timeout: int = 2) -> list[dict[str, Any]]:
        """Polls for pending updates from the Telegram Bot API."""
        payload: dict[str, Any] = {'timeout': timeout}
        if offset is not None:
            payload['offset'] = offset
        try:
            res = self._make_request('getUpdates', data=payload, timeout=timeout + 5)
            if res.get('ok'):
                return res.get('result', [])
            return []
        except Exception:
            return []

    def process_updates(self) -> int:
        """
        Polls and handles pending updates:
          - /start command -> sends contact-sharing keyboard
          - Shared contact -> links phone number to auth_users.telegram_chat_id
        Returns number of processed updates.
        """
        last_offset_str = get_setting('telegram_last_update_id', default='0', database_path=self.database_path)
        last_offset = int(last_offset_str) if last_offset_str.isdigit() else 0

        updates = self.get_updates(offset=last_offset + 1 if last_offset > 0 else None, timeout=2)
        if not updates:
            return 0

        processed_count = 0
        new_max_offset = last_offset

        for update in updates:
            update_id = update.get('update_id', 0)
            if update_id > new_max_offset:
                new_max_offset = update_id

            msg = update.get('message') or update.get('edited_message')
            if not msg:
                continue

            chat = msg.get('chat', {})
            chat_id = str(chat.get('id', ''))
            if not chat_id:
                continue

            # Case 1: User shared contact
            contact = msg.get('contact')
            if contact:
                raw_phone = contact.get('phone_number', '')
                norm_phone = normalize_phone_number(raw_phone)
                user = get_user_by_phone(norm_phone, database_path=self.database_path)

                if user:
                    update_user_telegram_chat_id(norm_phone, chat_id, database_path=self.database_path)
                    confirmation_text = (
                        f"✅ <b>اتصال با موفقیت برقرار شد!</b>\n\n"
                        f"حساب کاربری <b>{user['username']}</b> به این شناسه تلگرام متصل گردید.\n"
                        f"از این پس کدهای یکبار مصرف ورود (OTP) به این چت ارسال خواهند شد."
                    )
                    # Remove custom keyboard
                    remove_markup = {'remove_keyboard': True}
                    self.send_message(chat_id, confirmation_text, reply_markup=remove_markup)
                else:
                    masked = mask_phone_number(raw_phone)
                    reject_text = (
                        f"⚠️ شماره تماس <b>{masked}</b> در سامانه کتابخانه باقرالعلوم یافت نشد.\n\n"
                        f"لطفاً از مدیر کتابخانه بخواهید این شماره را به عنوان کاربر ثبت کند."
                    )
                    self.send_message(chat_id, reject_text)

                processed_count += 1
                continue

            # Case 2: Text message (/start or greeting)
            text = (msg.get('text') or '').strip()
            if text.startswith('/start'):
                start_text = (
                    "سلام! به ربات اطلاع‌رسانی <b>کتابخانه باقرالعلوم</b> خوش آمدید.\n\n"
                    "برای اتصال حساب کاربری و دریافت کدهای ورود یکبار مصرف (OTP)، "
                    "لطفاً با لمس دکمه زیر شماره تماس خود را به اشتراک بگذارید:"
                )
                contact_keyboard = {
                    'keyboard': [[{'text': '📱 ارسال شماره تماس برای اتصال', 'request_contact': True}]],
                    'resize_keyboard': True,
                    'one_time_keyboard': True
                }
                self.send_message(chat_id, start_text, reply_markup=contact_keyboard)
                processed_count += 1
                continue

        if new_max_offset > last_offset:
            set_setting('telegram_last_update_id', str(new_max_offset), database_path=self.database_path)

        return processed_count


# ==============================================================================
# OTP Service (Generation, Rate Limiting, Verification)
# ==============================================================================

OTP_EXPIRY_SECONDS = 120    # 2 minutes
OTP_RATE_LIMIT_SECONDS = 60 # Max 1 request per 60 seconds
MAX_OTP_ATTEMPTS = 3        # Max 3 incorrect attempts

class OTPService:
    """
    Manages generation, storage, rate limiting, and verification of OTP sessions.
    Works with Telegram Bot for online delivery, and enforces strict rate limits.
    """

    def __init__(self, database_path: str | None = None, bot_client: TelegramBotClient | None = None):
        self.database_path = database_path
        self.bot_client = bot_client or TelegramBotClient(database_path=database_path)

    def request_otp(self, identifier: str) -> tuple[bool, str, dict[str, Any] | None]:
        """
        Initiates an OTP session for the user identified by username or phone number.
        Enforces:
          - User existence and active status
          - Paired telegram_chat_id
          - 60-second cooldown rate limit
          - Telegram message delivery
        """
        user = get_user_by_identifier(identifier, database_path=self.database_path)
        if not user:
            return False, "کاربری با این مشخصات یافت نشد.", None

        if not user.get('is_active'):
            return False, "این حساب کاربری غیرفعال است. لطفاً با مدیر تماس بگیرید.", None

        phone = user.get('phone_number')
        chat_id = user.get('telegram_chat_id')

        if not chat_id:
            masked = mask_phone_number(phone)
            return False, (
                f"حساب شما ({masked}) به ربات تلگرام متصل نشده است.\n"
                f"لطفاً ابتدا در ربات تلگرام دستور /start را ارسال و شماره تماس خود را به اشتراک بگذارید، "
                f"یا با رمز عبور آفلاین وارد شوید."
            ), {'user': user, 'paired': False}

        now_utc = datetime.now(timezone.utc)
        conn = get_db_connection(database_path=self.database_path)
        try:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # Check rate limiting: max 1 request every 60s per phone
            cur.execute("""
                SELECT created_at FROM otp_sessions
                WHERE phone_number = ?
                ORDER BY id DESC LIMIT 1
            """, (phone,))
            last_sess = cur.fetchone()
            if last_sess:
                try:
                    last_created = datetime.fromisoformat(str(last_sess['created_at']))
                    # Ensure timezone-aware comparison
                    if last_created.tzinfo is None:
                        last_created = last_created.replace(tzinfo=timezone.utc)
                    elapsed = (now_utc - last_created).total_seconds()
                    if elapsed < OTP_RATE_LIMIT_SECONDS:
                        remaining = int(OTP_RATE_LIMIT_SECONDS - elapsed)
                        return False, f"لطفاً {remaining} ثانیه دیگر جهت درخواست مجدد کد شکیبا باشید.", {
                            'retry_after_seconds': remaining
                        }
                except Exception:
                    pass

            # Invalidate any previous unexpired unused OTP sessions for this phone
            cur.execute("""
                UPDATE otp_sessions
                SET is_used = 1
                WHERE phone_number = ? AND is_used = 0
            """, (phone,))

            # Generate new 6-digit code and salted hash
            otp_code = generate_otp_code(6)
            otp_hash_val = hash_otp(otp_code)
            created_str = now_utc.isoformat()
            expires_at = now_utc + timedelta(seconds=OTP_EXPIRY_SECONDS)
            expires_str = expires_at.isoformat()

            cur.execute("""
                INSERT INTO otp_sessions (phone_number, otp_hash, created_at, expires_at, attempts, is_used)
                VALUES (?, ?, ?, ?, 0, 0)
            """, (phone, otp_hash_val, created_str, expires_str))
            session_id = cur.lastrowid
            conn.commit()

            # Deliver via Telegram Bot
            sent_ok, send_msg = self.bot_client.send_otp_message(
                chat_id=chat_id,
                otp_code=otp_code,
                username=user.get('username', '')
            )

            if not sent_ok:
                # Mark session used so stale unsent code is invalidated
                cur.execute("UPDATE otp_sessions SET is_used = 1 WHERE id = ?", (session_id,))
                conn.commit()
                return False, (
                    f"ارسال کد به تلگرام با خطا مواجه شد ({send_msg}).\n"
                    f"در صورت قطعی اینترنت، می‌توانید از گزینه 'ورود آفلاین با رمز عبور' استفاده کنید."
                ), None

            return True, "کد یکبار مصرف به چت تلگرام شما ارسال شد.", {
                'session_id': session_id,
                'phone_masked': mask_phone_number(phone),
                'expires_in_seconds': OTP_EXPIRY_SECONDS,
                'username': user.get('username')
            }

        finally:
            conn.close()

    def verify_otp(self, identifier: str, otp_code: str) -> tuple[bool, str, dict[str, Any] | None]:
        """
        Verifies the OTP code for the user.
        Enforces:
          - Active session lookup
          - Expiry check (2 minutes)
          - Max attempts (3 attempts max)
          - Hash matching
          - Single-use consumption (is_used = 1)
        """
        clean_code = normalize_digits(otp_code).strip()
        if not clean_code or len(clean_code) != 6:
            return False, "کد یکبار مصرف باید ۶ رقمی باشد.", None

        user = get_user_by_identifier(identifier, database_path=self.database_path)
        if not user:
            return False, "کاربری با این مشخصات یافت نشد.", None

        phone = user.get('phone_number')
        now_utc = datetime.now(timezone.utc)

        conn = get_db_connection(database_path=self.database_path)
        try:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            cur.execute("""
                SELECT id, otp_hash, created_at, expires_at, attempts, is_used
                FROM otp_sessions
                WHERE phone_number = ? AND is_used = 0
                ORDER BY id DESC LIMIT 1
            """, (phone,))
            session = cur.fetchone()

            if not session:
                return False, "کد یکبار مصرفی برای این کاربر یافت نشد یا قبلاً استفاده شده است.", None

            session_id = session['id']
            stored_hash = session['otp_hash']
            attempts = session['attempts'] or 0

            # Check expiration
            expires_at = datetime.fromisoformat(str(session['expires_at']))
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)

            if now_utc > expires_at:
                cur.execute("UPDATE otp_sessions SET is_used = 1 WHERE id = ?", (session_id,))
                conn.commit()
                return False, "کد یکبار مصرف منقضی شده است. لطفاً کد جدید دریافت کنید.", None

            # Check max attempts limit
            if attempts >= MAX_OTP_ATTEMPTS:
                cur.execute("UPDATE otp_sessions SET is_used = 1 WHERE id = ?", (session_id,))
                conn.commit()
                return False, "تعداد دفعات ورود اشتباه بیش از حد مجاز است. لطفاً کد جدید دریافت کنید.", None

            # Verify OTP hash
            is_valid = verify_otp_hash(clean_code, stored_hash)

            if not is_valid:
                new_attempts = attempts + 1
                remaining_attempts = MAX_OTP_ATTEMPTS - new_attempts
                if new_attempts >= MAX_OTP_ATTEMPTS:
                    cur.execute("UPDATE otp_sessions SET attempts = ?, is_used = 1 WHERE id = ?", (new_attempts, session_id))
                    conn.commit()
                    return False, "کد اشتباه است. حداکثر دفعات مجاز به پایان رسید. لطفاً کد جدید دریافت کنید.", None
                else:
                    cur.execute("UPDATE otp_sessions SET attempts = ? WHERE id = ?", (new_attempts, session_id))
                    conn.commit()
                    return False, f"کد وارد شده نادرست است. ({remaining_attempts} بار تلاش باقی مانده)", None

            # OTP is valid: mark session as used
            cur.execute("UPDATE otp_sessions SET is_used = 1 WHERE id = ?", (session_id,))
            conn.commit()

            return True, "ورود با موفقیت انجام شد.", user

        finally:
            conn.close()


# ==============================================================================
# Offline Authentication Fallback & Unified Login Authenticator
# ==============================================================================

def authenticate_with_password(
    identifier: str,
    password: str,
    database_path: str | None = None
) -> tuple[bool, str, dict[str, Any] | None]:
    """
    Offline password authentication using local PBKDF2 hash.
    Works completely offline without network or Telegram dependency.
    """
    if not password:
        return False, "رمز عبور نمی‌تواند خالی باشد.", None

    user = get_user_by_identifier(identifier, database_path=database_path)
    if not user:
        return False, "نام کاربری یا رمز عبور اشتباه است.", None

    if not user.get('is_active'):
        return False, "حساب کاربری غیرفعال است.", None

    stored_hash = user.get('password_hash')
    if not stored_hash:
        return False, "برای این حساب رمز عبور محلی تعریف نشده است. لطفاً از کد تلگرام استفاده کنید.", None

    if verify_password(password, stored_hash):
        return True, "ورود با رمز عبور آفلاین با موفقیت انجام شد.", user
    return False, "نام کاربری یا رمز عبور اشتباه است.", None

def authenticate(
    identifier: str,
    credential: str,
    mode: str = 'auto',
    database_path: str | None = None
) -> tuple[bool, str, dict[str, Any] | None]:
    """
    Unified dual-mode authentication method.
    Modes:
      - 'password': Authenticates using local offline password hash
      - 'otp': Authenticates using 6-digit Telegram OTP session
      - 'auto': Checks network; if offline or credential appears to be password,
                uses password; if online and 6 digits, tries OTP first with password fallback.
    """
    clean_identifier = identifier.strip()
    clean_credential = credential.strip()

    if mode == 'password':
        return authenticate_with_password(clean_identifier, clean_credential, database_path=database_path)

    if mode == 'otp':
        otp_service = OTPService(database_path=database_path)
        return otp_service.verify_otp(clean_identifier, clean_credential)

    # Auto mode
    otp_candidate = normalize_digits(clean_credential)
    if len(otp_candidate) == 6 and otp_candidate.isdigit():
        # Check if there is an active OTP session
        otp_service = OTPService(database_path=database_path)
        success, msg, user = otp_service.verify_otp(clean_identifier, otp_candidate)
        if success:
            return True, msg, user

    # Fallback to password check
    return authenticate_with_password(clean_identifier, clean_credential, database_path=database_path)


# ==============================================================================
# CLI and Maintenance Utilities
# ==============================================================================

def main_cli():
    import argparse
    parser = argparse.ArgumentParser(description="Bager Library Auth & Telegram Bot Service CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: status
    subparsers.add_parser("status", help="Displays current network and auth status")

    # Command: bootstrap
    boot_parser = subparsers.add_parser("bootstrap", help="Creates default admin if none exists")
    boot_parser.add_argument("--username", default="admin", help="Admin username")
    boot_parser.add_argument("--phone", default="09120000000", help="Admin phone number")
    boot_parser.add_argument("--password", default="admin1234", help="Admin password")

    # Command: create-user
    user_parser = subparsers.add_parser("create-user", help="Creates a new user")
    user_parser.add_argument("username", help="Username")
    user_parser.add_argument("phone", help="Phone number")
    user_parser.add_argument("--password", default=None, help="Password for offline access")
    user_parser.add_argument("--role", default="librarian", choices=["admin", "librarian"], help="User role")

    # Command: test-bot
    subparsers.add_parser("test-bot", help="Tests Telegram bot token and connection")

    # Command: poll-bot
    subparsers.add_parser("poll-bot", help="Runs single poll cycle for Telegram updates")

    args = parser.parse_args()

    if args.command == "status":
        from database import init_database
        init_database()
        status = get_network_status()
        admin_exists = has_admin_user()
        users = list_users()
        print("=== Bager Library Auth Status ===")
        print(f"Network Status: {'Online' if status['online'] else 'Offline'} ({status['message']})")
        print(f"Admin User Configured: {'Yes' if admin_exists else 'No'}")
        print(f"Total Users: {len(users)}")
        for u in users:
            paired = "Paired" if u.get('telegram_chat_id') else "Unpaired"
            print(f" - [{u['role']}] {u['username']} ({u['phone_number']}) -> Telegram: {paired}")

    elif args.command == "bootstrap":
        from database import init_database
        init_database()
        ok, msg, user = bootstrap_admin_user(
            username=args.username,
            phone_number=args.phone,
            password=args.password
        )
        print(f"Bootstrap result: {msg}")
        if user:
            print(f"User: {user['username']} | Role: {user['role']}")

    elif args.command == "create-user":
        from database import init_database
        init_database()
        ok, msg, user = create_user(
            username=args.username,
            phone_number=args.phone,
            password=args.password,
            role=args.role
        )
        print(f"Create User result: {msg}")

    elif args.command == "test-bot":
        bot = TelegramBotClient()
        ok, msg, info = bot.test_connection()
        print(f"Bot Test: {'SUCCESS' if ok else 'FAILED'} -> {msg}")
        if info:
            print(f"Bot Info: {info}")

    elif args.command == "poll-bot":
        bot = TelegramBotClient()
        count = bot.process_updates()
        print(f"Processed {count} Telegram updates.")

    else:
        parser.print_help()

if __name__ == "__main__":
    main_cli()

