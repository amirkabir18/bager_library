import hashlib
import json
import re
import secrets
import socket
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

from database import get_db_connection, get_setting, set_setting

PERSIAN_ARABIC_DIGITS = {
    "۰": "0",
    "۱": "1",
    "۲": "2",
    "۳": "3",
    "۴": "4",
    "۵": "5",
    "۶": "6",
    "۷": "7",
    "۸": "8",
    "۹": "9",
    "٠": "0",
    "١": "1",
    "٢": "2",
    "٣": "3",
    "٤": "4",
    "٥": "5",
    "٦": "6",
    "٧": "7",
    "٨": "8",
    "٩": "9",
}

OTP_EXPIRY_SECONDS = 120
OTP_RATE_LIMIT_SECONDS = 60
MAX_OTP_ATTEMPTS = 3
PBKDF2_ITERATIONS = 100_000


def normalize_digits(text: str) -> str:
    if not text:
        return ""
    return "".join(PERSIAN_ARABIC_DIGITS.get(ch, ch) for ch in str(text))


def normalize_phone_number(phone: str) -> str:
    cleaned = normalize_digits(phone).strip()
    digits = re.sub(r"\D", "", cleaned)
    if not digits:
        return ""

    if digits.startswith("0098"):
        digits = digits[4:]
    elif digits.startswith("98") and len(digits) >= 11:
        digits = digits[2:]

    if digits.startswith("9") and len(digits) == 10:
        digits = "0" + digits

    if digits.startswith("09") and len(digits) == 11:
        return digits

    return "0" + digits if not digits.startswith("0") else digits


def mask_phone_number(phone: str) -> str:
    normalized = normalize_phone_number(phone)
    if len(normalized) == 11:
        return f"{normalized[:4]}***{normalized[7:]}"
    return normalized


def hash_password(password: str, iterations: int = PBKDF2_ITERATIONS, salt: bytes | None = None) -> str:
    if not password:
        raise ValueError("Password cannot be empty.")
    salt_bytes = salt if salt is not None else secrets.token_bytes(16)
    hash_bytes = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, iterations)
    return f"pbkdf2_sha256${iterations}${salt_bytes.hex()}${hash_bytes.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    if not password or not stored_hash:
        return False
    try:
        parts = stored_hash.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iterations = int(parts[1])
        salt_bytes = bytes.fromhex(parts[2])
        expected_hash = parts[3]
        calc_bytes = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, iterations)
        return secrets.compare_digest(calc_bytes.hex(), expected_hash)
    except Exception:
        return False


def generate_otp_code(length: int = 6) -> str:
    upper_bound = 10**length
    return f"{secrets.randbelow(upper_bound):0{length}d}"


def hash_otp(otp_code: str, salt: str | None = None) -> str:
    salt_str = salt if salt is not None else secrets.token_hex(8)
    h = hashlib.sha256(f"{salt_str}:{otp_code}".encode("utf-8")).hexdigest()
    return f"{salt_str}${h}"


def verify_otp_hash(otp_code: str, stored_hash: str) -> bool:
    if not otp_code or not stored_hash or "$" not in stored_hash:
        return False
    salt_str, expected_hash = stored_hash.split("$", 1)
    calc_hash = hashlib.sha256(f"{salt_str}:{otp_code}".encode("utf-8")).hexdigest()
    return secrets.compare_digest(calc_hash, expected_hash)


def create_user(
    username: str,
    phone_number: str,
    password: str | None = None,
    role: str = "librarian",
    telegram_chat_id: str | None = None,
    is_active: bool = True,
    database_path: str | None = None,
) -> tuple[bool, str, dict[str, Any] | None]:
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
        cur.execute(
            """
            INSERT INTO auth_users (username, phone_number, telegram_chat_id, role, password_hash, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                clean_username,
                norm_phone,
                telegram_chat_id,
                role,
                pwd_hash,
                1 if is_active else 0,
            ),
        )
        user_id = cur.lastrowid
        conn.commit()

        user_data = {
            "id": user_id,
            "username": clean_username,
            "phone_number": norm_phone,
            "telegram_chat_id": telegram_chat_id,
            "role": role,
            "is_active": is_active,
        }
        return True, "کاربر با موفقیت ثبت شد.", user_data
    except sqlite3.IntegrityError as e:
        err_msg = str(e)
        if "auth_users.username" in err_msg or "UNIQUE constraint failed: auth_users.username" in err_msg:
            return False, f"نام کاربری '{clean_username}' قبلاً ثبت شده است.", None
        if "auth_users.phone_number" in err_msg or "UNIQUE constraint failed: auth_users.phone_number" in err_msg:
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
        cur.execute(
            "SELECT * FROM auth_users WHERE username = ? COLLATE NOCASE",
            (username.strip(),),
        )
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
        cur.execute(
            "UPDATE auth_users SET telegram_chat_id = ? WHERE phone_number = ?",
            (str(telegram_chat_id), norm_phone),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def list_users(database_path: str | None = None) -> list[dict[str, Any]]:
    conn = get_db_connection(database_path=database_path)
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, phone_number, telegram_chat_id, role, is_active, created_at FROM auth_users ORDER BY id ASC"
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def has_admin_user(database_path: str | None = None) -> bool:
    conn = get_db_connection(database_path=database_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM auth_users WHERE role = 'admin' AND is_active = 1")
        return cur.fetchone()[0] > 0
    finally:
        conn.close()


def bootstrap_admin_user(
    username: str = "admin",
    phone_number: str = "09120000000",
    password: str = "admin1234",
    telegram_chat_id: str | None = None,
    database_path: str | None = None,
) -> tuple[bool, str, dict[str, Any] | None]:
    if has_admin_user(database_path=database_path):
        existing = get_user_by_username(username, database_path=database_path)
        return False, "حساب مدیر از پیش در سامانه تعریف شده است.", existing

    success, msg, user_data = create_user(
        username=username,
        phone_number=phone_number,
        password=password,
        role="admin",
        telegram_chat_id=telegram_chat_id,
        is_active=True,
        database_path=database_path,
    )
    if success:
        set_setting("admin_bootstrapped", "true", database_path=database_path)
    return success, msg, user_data


def ensure_bootstrap_admin(database_path: str | None = None) -> tuple[bool, str]:
    if not has_admin_user(database_path=database_path):
        success, msg, _ = bootstrap_admin_user(database_path=database_path)
        return success, msg
    return True, "حساب مدیر حاضر است."


def is_telegram_reachable(timeout: float = 2.5, proxy: str | None = None, api_url: str | None = None) -> bool:
    target_url = api_url or "https://api.telegram.org"
    parsed = urllib.parse.urlparse(target_url)
    host = parsed.hostname or "api.telegram.org"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        pass

    try:
        req = urllib.request.Request(f"{target_url.rstrip('/')}", headers={"User-Agent": "BagerLibrary/1.0"})
        opener = urllib.request.build_opener()
        if proxy:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
        with opener.open(req, timeout=timeout) as resp:
            return resp.status in (200, 302, 404)
    except urllib.error.HTTPError as e:
        return e.code in (200, 302, 400, 404)
    except Exception:
        return False


def get_telegram_api_url(database_path: str | None = None) -> str:
    url = (
        get_setting("telegram_relay_url", database_path=database_path)
        or get_setting("cloudflare_relay_url", database_path=database_path)
        or get_setting("vercel_relay_url", database_path=database_path)
        or get_setting(
            "telegram_api_url",
            default="https://api.telegram.org",
            database_path=database_path,
        )
    ).strip()

    if not url:
        url = "https://api.telegram.org"

    if not url.startswith("http://") and not url.startswith("https://"):
        url = f"https://{url}"

    return url.rstrip("/")


def get_network_status(database_path: str | None = None) -> dict[str, Any]:
    proxy = get_setting("telegram_proxy", default="", database_path=database_path) or None
    api_url = get_telegram_api_url(database_path=database_path)
    reachable = is_telegram_reachable(timeout=2.0, proxy=proxy, api_url=api_url)
    is_relay = not api_url.startswith("https://api.telegram.org")

    msg = "اتصال به تلگرام برقرار است."
    if reachable and is_relay:
        msg = f"اتصال به تلگرام از طریق رله برقرار است ({api_url})."
    elif not reachable:
        msg = "عدم دسترسی به تلگرام (حالت آفلاین فعال است)."

    return {
        "online": reachable,
        "telegram_reachable": reachable,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "mode": "online" if reachable else "offline",
        "is_relay": is_relay,
        "relay_url": api_url if is_relay else None,
        "message": msg,
    }


class TelegramBotClient:
    def __init__(
        self,
        token: str | None = None,
        database_path: str | None = None,
        proxy: str | None = None,
        api_url: str | None = None,
        relay_secret: str | None = None,
    ):
        self.database_path = database_path
        self._explicit_token = token
        self._proxy = proxy
        self._api_url = api_url
        self._relay_secret = relay_secret

    @property
    def token(self) -> str:
        if self._explicit_token:
            return self._explicit_token
        return get_setting("telegram_bot_token", default="", database_path=self.database_path).strip()

    @property
    def api_url(self) -> str:
        if self._api_url:
            url = self._api_url
            if not url.startswith("http://") and not url.startswith("https://"):
                url = f"https://{url}"
            return url.rstrip("/")
        return get_telegram_api_url(database_path=self.database_path)

    @property
    def proxy(self) -> str | None:
        if self._proxy:
            return self._proxy
        return get_setting("telegram_proxy", default="", database_path=self.database_path).strip() or None

    @property
    def relay_secret(self) -> str | None:
        if self._relay_secret:
            return self._relay_secret
        return get_setting("telegram_relay_secret", default="", database_path=self.database_path).strip() or None

    def _build_endpoint(self, method: str) -> str:
        base = self.api_url
        token = self.token
        if base.endswith(f"/bot{token}"):
            return f"{base}/{method}"
        if base.endswith("/bot"):
            return f"{base}{token}/{method}"
        return f"{base}/bot{token}/{method}"

    def _make_request(self, method: str, data: dict[str, Any] | None = None, timeout: float = 10.0) -> dict[str, Any]:
        curr_token = self.token
        if not curr_token:
            raise ValueError("توکن ربات تلگرام تنظیم نشده است.")

        endpoint = self._build_endpoint(method)
        headers = {"User-Agent": "BagerLibrary/1.0", "Content-Type": "application/json"}
        if self.relay_secret:
            headers["X-Relay-Secret"] = self.relay_secret

        post_bytes = json.dumps(data).encode("utf-8") if data is not None else None
        req = urllib.request.Request(endpoint, data=post_bytes, headers=headers)

        opener = urllib.request.build_opener()
        if self.proxy:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": self.proxy, "https": self.proxy}))

        with opener.open(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def test_connection(self) -> tuple[bool, str, dict[str, Any] | None]:
        try:
            res = self._make_request("getMe", timeout=4.0)
            if res.get("ok"):
                bot_user = res.get("result", {})
                return (
                    True,
                    f"اتصال به ربات @{bot_user.get('username', '')} برقرار شد.",
                    bot_user,
                )
            return False, res.get("description", "خطا در احراز هویت ربات"), None
        except Exception as e:
            return False, f"خطا در اتصال به ربات تلگرام: {str(e)}", None

    def send_message(
        self,
        chat_id: str | int,
        text: str,
        parse_mode: str = "HTML",
        reply_markup: dict[str, Any] | None = None,
    ) -> tuple[bool, str, dict[str, Any] | None]:
        payload: dict[str, Any] = {
            "chat_id": str(chat_id),
            "text": text,
            "parse_mode": parse_mode,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            res = self._make_request("sendMessage", data=payload, timeout=8.0)
            if res.get("ok"):
                return True, "پیام با موفقیت ارسال شد.", res.get("result")
            return False, res.get("description", "خطا در ارسال پیام تلگرام"), None
        except Exception as e:
            return False, f"خطا در ارسال پیام: {str(e)}", None

    def send_otp_message(self, chat_id: str | int, otp_code: str, username: str = "") -> tuple[bool, str]:
        user_line = f"کاربر گرامی <b>{username}</b>\n" if username else ""
        text = (
            f"🔐 <b>سامانه کتابخانه باقرالعلوم</b>\n\n"
            f"{user_line}"
            f"کد یکبار مصرف ورود شما:\n"
            f"<code>{otp_code}</code>\n\n"
            f"⏱ این کد به مدت <b>۲ دقیقه</b> معتبر است.\n"
            f"⚠️ این کد را در اختیار دیگران قرار ندهید."
        )
        success, msg, _ = self.send_message(chat_id=chat_id, text=text)
        return success, msg

    def get_updates(self, offset: int | None = None, timeout: int = 2) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {"timeout": timeout}
        if offset is not None:
            payload["offset"] = offset
        try:
            res = self._make_request("getUpdates", data=payload, timeout=timeout + 5)
            return res.get("result", []) if res.get("ok") else []
        except Exception:
            return []

    def process_updates(self) -> int:
        last_offset_str = get_setting("telegram_last_update_id", default="0", database_path=self.database_path)
        last_offset = int(last_offset_str) if last_offset_str.isdigit() else 0

        updates = self.get_updates(offset=last_offset + 1 if last_offset > 0 else None, timeout=2)
        if not updates:
            return 0

        processed = 0
        new_offset = last_offset

        for item in updates:
            up_id = item.get("update_id", 0)
            if up_id > new_offset:
                new_offset = up_id

            msg = item.get("message") or item.get("edited_message")
            if not msg:
                continue

            chat_id = str(msg.get("chat", {}).get("id", ""))
            if not chat_id:
                continue

            contact = msg.get("contact")
            if contact:
                raw_phone = contact.get("phone_number", "")
                norm_phone = normalize_phone_number(raw_phone)
                user = get_user_by_phone(norm_phone, database_path=self.database_path)

                if user:
                    update_user_telegram_chat_id(norm_phone, chat_id, database_path=self.database_path)
                    text = (
                        f"✅ <b>اتصال با موفقیت برقرار شد!</b>\n\n"
                        f"حساب کاربری <b>{user['username']}</b> به این شناسه متصل گردید.\n"
                        f"کدهای یکبار مصرف ورود به این چت ارسال خواهند شد."
                    )
                    self.send_message(chat_id, text, reply_markup={"remove_keyboard": True})
                else:
                    text = (
                        f"⚠️ شماره تماس <b>{mask_phone_number(raw_phone)}</b> در سامانه ثبت نشده است.\n"
                        f"لطفاً از مدیر کتابخانه بخواهید شماره شما را ثبت کند."
                    )
                    self.send_message(chat_id, text)
                processed += 1
                continue

            txt = (msg.get("text") or "").strip()
            if txt.startswith("/start"):
                start_text = (
                    "سلام! به ربات اطلاع‌رسانی <b>کتابخانه باقرالعلوم</b> خوش آمدید.\n\n"
                    "برای اتصال حساب کاربری و دریافت کدهای ورود، دکمه زیر را لمس کرده و شماره تماس خود را ارسال کنید:"
                )
                keyboard = {
                    "keyboard": [
                        [
                            {
                                "text": "📱 ارسال شماره تماس برای اتصال",
                                "request_contact": True,
                            }
                        ]
                    ],
                    "resize_keyboard": True,
                    "one_time_keyboard": True,
                }
                self.send_message(chat_id, start_text, reply_markup=keyboard)
                processed += 1

        if new_offset > last_offset:
            set_setting(
                "telegram_last_update_id",
                str(new_offset),
                database_path=self.database_path,
            )

        return processed


class OTPService:
    def __init__(
        self,
        database_path: str | None = None,
        bot_client: TelegramBotClient | None = None,
    ):
        self.database_path = database_path
        self.bot_client = bot_client or TelegramBotClient(database_path=database_path)

    def request_otp(self, identifier: str) -> tuple[bool, str, dict[str, Any] | None]:
        user = get_user_by_identifier(identifier, database_path=self.database_path)
        if not user:
            return False, "کاربری با این مشخصات یافت نشد.", None

        if not user.get("is_active"):
            return False, "این حساب کاربری غیرفعال است.", None

        phone = str(user.get("phone_number") or "")
        chat_id = user.get("telegram_chat_id")

        if not chat_id:
            return (
                False,
                (
                    f"حساب شما ({mask_phone_number(phone)}) به ربات تلگرام متصل نشده است.\n"
                    f"لطفاً ابتدا در ربات تلگرام دستور /start را ارسال و شماره خود را به اشتراک بگذارید، "
                    f"یا با رمز عبور آفلاین وارد شوید."
                ),
                {"user": user, "paired": False},
            )

        now_utc = datetime.now(timezone.utc)
        conn = get_db_connection(database_path=self.database_path)
        try:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            cur.execute(
                "SELECT created_at FROM otp_sessions WHERE phone_number = ? ORDER BY id DESC LIMIT 1",
                (phone,),
            )
            last_sess = cur.fetchone()
            if last_sess:
                try:
                    last_created = datetime.fromisoformat(str(last_sess["created_at"]))
                    if last_created.tzinfo is None:
                        last_created = last_created.replace(tzinfo=timezone.utc)
                    elapsed = (now_utc - last_created).total_seconds()
                    if elapsed < OTP_RATE_LIMIT_SECONDS:
                        remaining = int(OTP_RATE_LIMIT_SECONDS - elapsed)
                        return (
                            False,
                            f"لطفاً {remaining} ثانیه دیگر جهت درخواست مجدد کد شکیبا باشید.",
                            {"retry_after_seconds": remaining},
                        )
                except Exception:
                    pass

            cur.execute(
                "UPDATE otp_sessions SET is_used = 1 WHERE phone_number = ? AND is_used = 0",
                (phone,),
            )

            otp_code = generate_otp_code(6)
            otp_hash_val = hash_otp(otp_code)
            created_str = now_utc.isoformat()
            expires_str = (now_utc + timedelta(seconds=OTP_EXPIRY_SECONDS)).isoformat()

            cur.execute(
                """
                INSERT INTO otp_sessions (phone_number, otp_hash, created_at, expires_at, attempts, is_used)
                VALUES (?, ?, ?, ?, 0, 0)
            """,
                (phone, otp_hash_val, created_str, expires_str),
            )
            session_id = cur.lastrowid
            conn.commit()

            sent_ok, send_msg = self.bot_client.send_otp_message(
                chat_id=chat_id, otp_code=otp_code, username=user.get("username", "")
            )

            if not sent_ok:
                cur.execute("UPDATE otp_sessions SET is_used = 1 WHERE id = ?", (session_id,))
                conn.commit()
                return (
                    False,
                    (
                        f"ارسال کد به تلگرام با خطا مواجه شد ({send_msg}).\n"
                        f"در صورت قطعی اینترنت، می‌توانید از رمز عبور آفلاین استفاده کنید."
                    ),
                    None,
                )

            return (
                True,
                "کد یکبار مصرف به تلگرام شما ارسال شد.",
                {
                    "session_id": session_id,
                    "phone_masked": mask_phone_number(phone),
                    "expires_in_seconds": OTP_EXPIRY_SECONDS,
                    "username": user.get("username"),
                },
            )
        finally:
            conn.close()

    def verify_otp(self, identifier: str, otp_code: str) -> tuple[bool, str, dict[str, Any] | None]:
        clean_code = normalize_digits(otp_code).strip()
        if not clean_code or len(clean_code) != 6:
            return False, "کد یکبار مصرف باید ۶ رقمی باشد.", None

        user = get_user_by_identifier(identifier, database_path=self.database_path)
        if not user:
            return False, "کاربری با این مشخصات یافت نشد.", None

        phone = str(user.get("phone_number") or "")
        now_utc = datetime.now(timezone.utc)

        conn = get_db_connection(database_path=self.database_path)
        try:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            cur.execute(
                """
                SELECT id, otp_hash, created_at, expires_at, attempts, is_used
                FROM otp_sessions
                WHERE phone_number = ? AND is_used = 0
                ORDER BY id DESC LIMIT 1
            """,
                (phone,),
            )
            session = cur.fetchone()

            if not session:
                return (
                    False,
                    "کد یکبار مصرفی برای این کاربر یافت نشد یا قبلاً استفاده شده است.",
                    None,
                )

            session_id = session["id"]
            stored_hash = session["otp_hash"]
            attempts = session["attempts"] or 0

            expires_at = datetime.fromisoformat(str(session["expires_at"]))
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)

            if now_utc > expires_at:
                cur.execute("UPDATE otp_sessions SET is_used = 1 WHERE id = ?", (session_id,))
                conn.commit()
                return (
                    False,
                    "کد یکبار مصرف منقضی شده است. لطفاً کد جدید دریافت کنید.",
                    None,
                )

            if attempts >= MAX_OTP_ATTEMPTS:
                cur.execute("UPDATE otp_sessions SET is_used = 1 WHERE id = ?", (session_id,))
                conn.commit()
                return (
                    False,
                    "تعداد دفعات ورود اشتباه بیش از حد مجاز است. لطفاً کد جدید دریافت کنید.",
                    None,
                )

            if not verify_otp_hash(clean_code, stored_hash):
                new_attempts = attempts + 1
                remaining = MAX_OTP_ATTEMPTS - new_attempts
                if new_attempts >= MAX_OTP_ATTEMPTS:
                    cur.execute(
                        "UPDATE otp_sessions SET attempts = ?, is_used = 1 WHERE id = ?",
                        (new_attempts, session_id),
                    )
                    conn.commit()
                    return (
                        False,
                        "کد اشتباه است. حداکثر دفعات مجاز به پایان رسید. لطفاً کد جدید دریافت کنید.",
                        None,
                    )
                cur.execute(
                    "UPDATE otp_sessions SET attempts = ? WHERE id = ?",
                    (new_attempts, session_id),
                )
                conn.commit()
                return (
                    False,
                    f"کد وارد شده نادرست است. ({remaining} بار تلاش باقی مانده)",
                    None,
                )

            cur.execute("UPDATE otp_sessions SET is_used = 1 WHERE id = ?", (session_id,))
            conn.commit()
            return True, "ورود با موفقیت انجام شد.", user
        finally:
            conn.close()


def authenticate_with_password(
    identifier: str, password: str, database_path: str | None = None
) -> tuple[bool, str, dict[str, Any] | None]:
    if not password:
        return False, "رمز عبور نمی‌تواند خالی باشد.", None

    user = get_user_by_identifier(identifier, database_path=database_path)
    if not user:
        return False, "نام کاربری یا رمز عبور اشتباه است.", None

    if not user.get("is_active"):
        return False, "حساب کاربری غیرفعال است.", None

    stored_hash = user.get("password_hash")
    if not stored_hash:
        return False, "برای این حساب رمز عبور محلی تعریف نشده است.", None

    if verify_password(password, stored_hash):
        return True, "ورود با رمز عبور با موفقیت انجام شد.", user
    return False, "نام کاربری یا رمز عبور اشتباه است.", None


def authenticate(
    identifier: str,
    credential: str,
    mode: str = "auto",
    database_path: str | None = None,
) -> tuple[bool, str, dict[str, Any] | None]:
    clean_identifier = identifier.strip()
    clean_credential = credential.strip()

    if mode == "password":
        return authenticate_with_password(clean_identifier, clean_credential, database_path=database_path)

    if mode == "otp":
        return OTPService(database_path=database_path).verify_otp(clean_identifier, clean_credential)

    otp_candidate = normalize_digits(clean_credential)
    if len(otp_candidate) == 6 and otp_candidate.isdigit():
        success, msg, user = OTPService(database_path=database_path).verify_otp(clean_identifier, otp_candidate)
        if success:
            return True, msg, user

    return authenticate_with_password(clean_identifier, clean_credential, database_path=database_path)


if __name__ == "__main__":
    from database import init_database

    init_database()
    status = get_network_status()
    print(f"Network: {status['mode']} | Telegram reachable: {status['online']}")
    ensure_bootstrap_admin()
    print(f"Users: {len(list_users())}")
