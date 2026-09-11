import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from database import init_database
from auth import (
    normalize_digits,
    normalize_phone_number,
    mask_phone_number,
    hash_password,
    verify_password,
    generate_otp_code,
    hash_otp,
    verify_otp_hash,
    create_user,
    delete_user,
    get_user_by_username,
    get_user_by_phone,
    get_user_by_identifier,
    update_user_telegram_chat_id,
    has_admin_user,
    bootstrap_admin_user,
    ensure_bootstrap_admin,
    authenticate_with_password,
    authenticate,
    get_network_status,
    get_telegram_api_url,
    TelegramBotClient,
    OTPService,
    OTP_EXPIRY_SECONDS,
    OTP_RATE_LIMIT_SECONDS,
    MAX_OTP_ATTEMPTS,
)


class TestAuthUtilities(unittest.TestCase):
    def test_normalize_digits(self):
        persian_str = "۰۱۲۳۴۵۶۷۸۹"
        arabic_str = "٠١٢٣٤٥٦٧٨٩"
        self.assertEqual(normalize_digits(persian_str), "0123456789")
        self.assertEqual(normalize_digits(arabic_str), "0123456789")
        self.assertEqual(normalize_digits("abc 123"), "abc 123")

    def test_normalize_phone_number(self):
        cases = [
            ("09123456789", "09123456789"),
            ("9123456789", "09123456789"),
            ("+989123456789", "09123456789"),
            ("00989123456789", "09123456789"),
            ("989123456789", "09123456789"),
            ("۰۹۱۲-۳۴۵-۶۷۸۹", "09123456789"),
            ("+98 (912) 345 6789", "09123456789"),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_phone_number(raw), expected)

    def test_mask_phone_number(self):
        self.assertEqual(mask_phone_number("09123456789"), "0912***6789")
        self.assertEqual(mask_phone_number("+989123456789"), "0912***6789")


class TestPasswordHashing(unittest.TestCase):
    def test_hash_and_verify_password(self):
        pwd = "SecurePassword#2026"
        pwd_hash = hash_password(pwd)
        self.assertTrue(pwd_hash.startswith("pbkdf2_sha256$100000$"))
        self.assertTrue(verify_password(pwd, pwd_hash))
        self.assertFalse(verify_password("WrongPassword", pwd_hash))
        self.assertFalse(verify_password("", pwd_hash))
        self.assertFalse(verify_password(pwd, "invalid_hash_string"))

    def test_empty_password_raises(self):
        with self.assertRaises(ValueError):
            hash_password("")


class TestOTPCryptography(unittest.TestCase):
    def test_otp_generation(self):
        code = generate_otp_code(6)
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())

    def test_otp_hash_and_verify(self):
        code = "123456"
        h = hash_otp(code)
        self.assertIn("$", h)
        self.assertTrue(verify_otp_hash(code, h))
        self.assertFalse(verify_otp_hash("654321", h))
        self.assertFalse(verify_otp_hash("", h))


class TestAuthWithDatabase(unittest.TestCase):
    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_file.close()
        self.db_path = self.temp_file.name
        conn = sqlite3.connect(self.db_path)
        init_database(conn)
        conn.close()
        self._orig_env = dict(os.environ)
        for k in [
            'TELEGRAM_RELAY_URL', 'CLOUDFLARE_RELAY_URL', 'VERCEL_RELAY_URL',
            'telegram_relay_url', 'cloudflare_relay_url', 'vercel_relay_url',
            'SUPER_ADMIN_USERNAME', 'SUPER_ADMIN_PHONE', 'SUPER_ADMIN_PHONE_NUMBER',
            'SUPER_ADMIN_PASSWORD', 'SUPER_ADMIN_TELEGRAM_CHAT_ID', 'SUPER_ADMIN_ROLE',
            'ADMIN_USERNAME', 'ADMIN_PHONE', 'ADMIN_PHONE_NUMBER',
            'ADMIN_PASSWORD', 'ADMIN_TELEGRAM_CHAT_ID', 'ADMIN_ROLE'
        ]:
            os.environ.pop(k, None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._orig_env)
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except Exception:
                pass

    def test_bootstrap_admin(self):
        self.assertFalse(has_admin_user(database_path=self.db_path))
        ok, msg, user = bootstrap_admin_user(
            username="admin",
            phone_number="09121112233",
            password="adminpassword",
            database_path=self.db_path
        )
        self.assertTrue(ok)
        self.assertTrue(has_admin_user(database_path=self.db_path))
        self.assertIsNotNone(user)
        assert user is not None
        self.assertEqual(user['role'], 'super admin')

        ok2, msg2, _ = bootstrap_admin_user(database_path=self.db_path)
        self.assertFalse(ok2)

        ens_ok, _ = ensure_bootstrap_admin(database_path=self.db_path)
        self.assertTrue(ens_ok)

    def test_bootstrap_admin_with_env_vars(self):
        os.environ['SUPER_ADMIN_USERNAME'] = 'env_superadmin'
        os.environ['SUPER_ADMIN_PHONE'] = '09129998877'
        os.environ['SUPER_ADMIN_PASSWORD'] = 'env_secret_pass'
        os.environ['SUPER_ADMIN_TELEGRAM_CHAT_ID'] = '99887766'

        ok, msg, user = bootstrap_admin_user(database_path=self.db_path)
        self.assertTrue(ok)
        self.assertIsNotNone(user)
        assert user is not None
        self.assertEqual(user['username'], 'env_superadmin')
        self.assertEqual(user['phone_number'], '09129998877')
        self.assertEqual(user['role'], 'super admin')
        self.assertEqual(user['telegram_chat_id'], '99887766')

    def test_create_and_query_users(self):
        ok, _, user = create_user(
            username="librarian1",
            phone_number="09191234567",
            password="secretpassword",
            role="librarian",
            database_path=self.db_path
        )
        self.assertTrue(ok)

        by_u = get_user_by_username("librarian1", database_path=self.db_path)
        self.assertIsNotNone(by_u)
        assert by_u is not None
        self.assertEqual(by_u['phone_number'], "09191234567")

        by_p = get_user_by_phone("09191234567", database_path=self.db_path)
        self.assertIsNotNone(by_p)
        assert by_p is not None
        self.assertEqual(by_p['username'], "librarian1")

        by_id1 = get_user_by_identifier("librarian1", database_path=self.db_path)
        by_id2 = get_user_by_identifier("+989191234567", database_path=self.db_path)
        self.assertIsNotNone(by_id1)
        self.assertIsNotNone(by_id2)
        assert by_id1 is not None and by_id2 is not None
        self.assertEqual(by_id1['id'], by_id2['id'])

    def test_offline_password_authentication(self):
        create_user(
            username="user_offline",
            phone_number="09180001122",
            password="offlinePass123",
            database_path=self.db_path
        )

        ok, msg, user = authenticate_with_password("user_offline", "offlinePass123", database_path=self.db_path)
        self.assertTrue(ok)
        self.assertIsNotNone(user)
        assert user is not None
        self.assertEqual(user['username'], "user_offline")

        ok, _, _ = authenticate_with_password("09180001122", "offlinePass123", database_path=self.db_path)
        self.assertTrue(ok)

        ok, msg, user = authenticate_with_password("user_offline", "wrong", database_path=self.db_path)
        self.assertFalse(ok)
        self.assertIsNone(user)

        ok, msg, user = authenticate_with_password("nobody", "offlinePass123", database_path=self.db_path)
        self.assertFalse(ok)

    def test_otp_flow_with_telegram_mock(self):
        mock_bot = MagicMock(spec=TelegramBotClient)
        mock_bot.send_otp_message.return_value = (True, "OK")

        create_user(
            username="otp_user",
            phone_number="09129998877",
            password="password",
            database_path=self.db_path
        )

        otp_service = OTPService(database_path=self.db_path, bot_client=mock_bot)

        ok, msg, data = otp_service.request_otp("otp_user")
        self.assertFalse(ok)
        self.assertIn("متصل نشده است", msg)

        update_user_telegram_chat_id("09129998877", "987654321", database_path=self.db_path)

        ok, msg, data = otp_service.request_otp("otp_user")
        self.assertTrue(ok)
        mock_bot.send_otp_message.assert_called_once()
        call_args = mock_bot.send_otp_message.call_args[1]
        sent_code = call_args['otp_code']
        self.assertEqual(len(sent_code), 6)

        ok_v, msg_v, _ = otp_service.verify_otp("otp_user", "000000" if sent_code != "000000" else "111111")
        self.assertFalse(ok_v)
        self.assertIn("تلاش باقی مانده", msg_v)

        ok_v, msg_v, user = otp_service.verify_otp("otp_user", sent_code)
        self.assertTrue(ok_v)
        self.assertIsNotNone(user)
        assert user is not None
        self.assertEqual(user['username'], "otp_user")

        ok_reuse, _, _ = otp_service.verify_otp("otp_user", sent_code)
        self.assertFalse(ok_reuse)

    def test_otp_rate_limiting(self):
        mock_bot = MagicMock(spec=TelegramBotClient)
        mock_bot.send_otp_message.return_value = (True, "OK")

        create_user(
            username="rate_user",
            phone_number="09128887766",
            telegram_chat_id="123456",
            database_path=self.db_path
        )
        otp_service = OTPService(database_path=self.db_path, bot_client=mock_bot)

        ok1, _, _ = otp_service.request_otp("rate_user")
        self.assertTrue(ok1)

        ok2, msg2, info2 = otp_service.request_otp("rate_user")
        self.assertFalse(ok2)
        self.assertIn("شکیبا باشید", msg2)
        self.assertIsNotNone(info2)
        assert info2 is not None
        self.assertIn("retry_after_seconds", info2)

    def test_otp_max_attempts_exceeded(self):
        mock_bot = MagicMock(spec=TelegramBotClient)
        mock_bot.send_otp_message.return_value = (True, "OK")

        create_user(
            username="attempts_user",
            phone_number="09127776655",
            telegram_chat_id="654321",
            database_path=self.db_path
        )
        otp_service = OTPService(database_path=self.db_path, bot_client=mock_bot)
        otp_service.request_otp("attempts_user")
        sent_code = mock_bot.send_otp_message.call_args[1]['otp_code']
        wrong_code = "000000" if sent_code != "000000" else "111111"

        ok, _, _ = otp_service.verify_otp("attempts_user", wrong_code)
        self.assertFalse(ok)
        ok, _, _ = otp_service.verify_otp("attempts_user", wrong_code)
        self.assertFalse(ok)
        ok, msg, _ = otp_service.verify_otp("attempts_user", wrong_code)
        self.assertFalse(ok)
        self.assertIn("حداکثر دفعات", msg)

        ok, _, _ = otp_service.verify_otp("attempts_user", sent_code)
        self.assertFalse(ok)

    def test_otp_expiration(self):
        mock_bot = MagicMock(spec=TelegramBotClient)
        mock_bot.send_otp_message.return_value = (True, "OK")

        create_user(
            username="expired_user",
            phone_number="09126665544",
            telegram_chat_id="999888",
            database_path=self.db_path
        )
        otp_service = OTPService(database_path=self.db_path, bot_client=mock_bot)
        otp_service.request_otp("expired_user")
        sent_code = mock_bot.send_otp_message.call_args[1]['otp_code']

        past_iso = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        conn = sqlite3.connect(self.db_path)
        conn.execute("UPDATE otp_sessions SET expires_at = ? WHERE phone_number = '09126665544'", (past_iso,))
        conn.commit()
        conn.close()

        ok, msg, _ = otp_service.verify_otp("expired_user", sent_code)
        self.assertFalse(ok)
        self.assertIn("منقضی شده است", msg)

    def test_telegram_pairing_process_updates(self):
        create_user(
            username="telegram_pair_user",
            phone_number="09125554433",
            database_path=self.db_path
        )

        bot = TelegramBotClient(token="123:ABC", database_path=self.db_path)

        mock_updates = [
            {
                'update_id': 101,
                'message': {
                    'chat': {'id': 777111},
                    'text': '/start'
                }
            },
            {
                'update_id': 102,
                'message': {
                    'chat': {'id': 777111},
                    'contact': {
                        'phone_number': '+989125554433',
                        'first_name': 'Test'
                    }
                }
            }
        ]

        with patch.object(bot, 'get_updates', return_value=mock_updates), \
             patch.object(bot, 'send_message', return_value=(True, "OK", {})) as mock_send:
            count = bot.process_updates()
            self.assertEqual(count, 2)

            user = get_user_by_phone("09125554433", database_path=self.db_path)
            self.assertIsNotNone(user)
            assert user is not None
            self.assertEqual(str(user['telegram_chat_id']), "777111")
            self.assertTrue(mock_send.called)

    def test_unified_authenticate(self):
        create_user(
            username="unified_user",
            phone_number="09124443322",
            password="mySecurePassword",
            telegram_chat_id="555444",
            database_path=self.db_path
        )

        ok, _, user = authenticate("unified_user", "mySecurePassword", mode="password", database_path=self.db_path)
        self.assertTrue(ok)
        self.assertIsNotNone(user)
        assert user is not None
        self.assertEqual(user['username'], "unified_user")

        ok, _, user = authenticate("unified_user", "mySecurePassword", mode="auto", database_path=self.db_path)
        self.assertTrue(ok)

    def test_relay_configuration_and_headers(self):
        from database import set_setting

        set_setting('cloudflare_relay_url', 'https://cf-relay.workers.dev', database_path=self.db_path)
        set_setting('telegram_relay_secret', 'secret123', database_path=self.db_path)

        url = get_telegram_api_url(database_path=self.db_path)
        self.assertEqual(url, 'https://cf-relay.workers.dev')

        client = TelegramBotClient(token='123:TOKEN', database_path=self.db_path)
        self.assertEqual(client.api_url, 'https://cf-relay.workers.dev')
        self.assertEqual(client.relay_secret, 'secret123')
        self.assertEqual(client._build_endpoint('sendMessage'), 'https://cf-relay.workers.dev/bot123:TOKEN/sendMessage')

        # Vercel relay priority test
        set_setting('vercel_relay_url', 'https://vercel-relay.vercel.app', database_path=self.db_path)
        # telegram_relay_url takes highest precedence
        set_setting('telegram_relay_url', 'https://custom-relay.example.com/', database_path=self.db_path)
        self.assertEqual(get_telegram_api_url(database_path=self.db_path), 'https://custom-relay.example.com')

        # Test relay headers in _make_request
        relay_client = TelegramBotClient(token='123:TOKEN', database_path=self.db_path)
        with patch('urllib.request.urlopen') as mock_urlopen, patch('urllib.request.build_opener') as mock_build_opener:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"ok": true, "result": {}}'
            mock_build_opener.return_value.open.return_value.__enter__.return_value = mock_resp

            relay_client._make_request('sendMessage', {'chat_id': '123', 'text': 'hi'})
            call_req = mock_build_opener.return_value.open.call_args[0][0]
            self.assertEqual(call_req.get_header('X-relay-target'), 'https://api.telegram.org/bot123:TOKEN/sendMessage#')
            self.assertEqual(call_req.get_header('X-relay-secret'), 'secret123')

    def test_delete_user(self):
        ok, _, u1 = create_user("testadmin1", "09121110001", role="admin", database_path=self.db_path)
        self.assertTrue(ok)
        ok, _, u2 = create_user("testadmin2", "09121110002", role="super admin", database_path=self.db_path)
        self.assertTrue(ok)
        ok, _, u3 = create_user("regularuser", "09121110003", role="user", database_path=self.db_path)
        self.assertTrue(ok)

        # Deleting regular user succeeds
        assert u3 is not None
        del_ok, _ = delete_user(u3['id'], database_path=self.db_path)
        self.assertTrue(del_ok)

        # Deleting one of two admins succeeds
        assert u1 is not None
        del_ok, _ = delete_user(u1['id'], database_path=self.db_path)
        self.assertTrue(del_ok)

        # Deleting last admin is prevented
        assert u2 is not None
        del_ok, msg = delete_user(u2['id'], database_path=self.db_path)
        self.assertFalse(del_ok)
        self.assertIn("آخرین مدیر", msg)


if __name__ == "__main__":
    unittest.main()
