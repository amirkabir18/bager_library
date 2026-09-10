import json
import os
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import updater


class TestAppInfoAndVersion(unittest.TestCase):
    def test_load_app_info_defaults(self):
        info = updater.load_app_info("/non/existent/path/app_info.json")
        self.assertIn("version", info)
        self.assertIn("name", info)
        self.assertEqual(info["version"], "0.1.0")

    def test_load_app_info_custom(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump({"name": "test_app", "version": "1.2.3"}, f)
            temp_path = f.name
        try:
            info = updater.load_app_info(temp_path)
            self.assertEqual(info["version"], "1.2.3")
            self.assertEqual(info["name"], "test_app")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_parse_version(self):
        self.assertEqual(updater.parse_version("0.1.0"), (0, 1, 0))
        self.assertEqual(updater.parse_version("v1.2.3"), (1, 2, 3))
        self.assertEqual(updater.parse_version("  v2.0  "), (2, 0))
        self.assertEqual(updater.parse_version("3.4.5.6"), (3, 4, 5, 6))
        self.assertEqual(updater.parse_version("unknown"), (0, 0, 0))

    def test_is_newer_version(self):
        self.assertTrue(updater.is_newer_version("0.2.0", "0.1.0"))
        self.assertTrue(updater.is_newer_version("1.0.0", "0.9.9"))
        self.assertTrue(updater.is_newer_version("v0.1.1", "0.1.0"))
        self.assertTrue(updater.is_newer_version("0.1.0.1", "0.1.0"))
        self.assertFalse(updater.is_newer_version("0.1.0", "0.1.0"))
        self.assertFalse(updater.is_newer_version("0.1.0", "0.2.0"))
        self.assertFalse(updater.is_newer_version("0.0.9", "0.1.0"))

    def test_format_size_and_speed(self):
        self.assertEqual(updater.format_size(0), "0 B")
        self.assertEqual(updater.format_size(1024), "1.0 KB")
        self.assertEqual(updater.format_size(1048576), "1.0 MB")
        self.assertEqual(updater.format_speed(1048576), "1.0 MB/s")


class TestUpdateChecker(unittest.TestCase):
    def setUp(self):
        self.checker = updater.UpdateChecker(repo="test/repo", current_version="0.1.0")

    @patch("urllib.request.urlopen")
    def test_check_with_update_available(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps(
            {
                "tag_name": "v0.2.0",
                "name": "Version 0.2.0",
                "body": "Bug fixes",
                "html_url": "https://github.com/test/repo/releases/v0.2.0",
                "assets": [
                    {
                        "name": "bager_library.exe",
                        "browser_download_url": "https://github.com/test/repo/releases/download/v0.2.0/bager_library.exe",
                        "size": 15000000,
                    }
                ],
            }
        ).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        res = self.checker.check()
        self.assertTrue(res["update_available"])
        self.assertEqual(res["latest_version"], "0.2.0")
        self.assertEqual(res["asset_name"], "bager_library.exe")
        self.assertEqual(
            res["download_url"],
            "https://github.com/test/repo/releases/download/v0.2.0/bager_library.exe",
        )

    @patch("urllib.request.urlopen")
    def test_check_with_no_update_available(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps(
            {
                "tag_name": "v0.1.0",
                "name": "Version 0.1.0",
                "body": "Initial",
                "html_url": "https://github.com/test/repo/releases/v0.1.0",
                "assets": [],
            }
        ).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        res = self.checker.check()
        self.assertFalse(res["update_available"])
        self.assertEqual(res["latest_version"], "0.1.0")


class TestDownloadManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.dest_file = os.path.join(self.temp_dir, "app_download.exe")

    def tearDown(self):
        if os.path.exists(self.dest_file):
            try:
                os.remove(self.dest_file)
            except OSError:
                pass
        tmp_file = self.dest_file + ".tmp"
        if os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except OSError:
                pass
        try:
            os.rmdir(self.temp_dir)
        except OSError:
            pass

    @patch("urllib.request.urlopen")
    def test_download_success(self, mock_urlopen):
        content = b"X" * 131072  # 128 KB
        mock_resp = MagicMock()
        mock_resp.headers = {"Content-Length": str(len(content))}
        mock_resp.read.side_effect = [content[:65536], content[65536:], b""]
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        dm = updater.DownloadManager(chunk_size=65536)
        progress_calls = []
        finished_calls = []

        def on_prog(down, total, pct, speed):
            progress_calls.append((down, total, pct))

        def on_fin(path):
            finished_calls.append(path)

        dm.download_async(
            url="http://example.com/app.exe",
            dest_path=self.dest_file,
            on_progress=on_prog,
            on_finished=on_fin,
        )

        dm._thread.join(timeout=5)

        self.assertEqual(len(finished_calls), 1)
        self.assertEqual(finished_calls[0], self.dest_file)
        self.assertTrue(os.path.exists(self.dest_file))
        self.assertEqual(os.path.getsize(self.dest_file), len(content))
        self.assertFalse(dm.is_downloading)

    @patch("urllib.request.urlopen")
    def test_download_cancel(self, mock_urlopen):
        def blocking_read(size):
            time.sleep(0.05)
            return b"A" * size

        mock_resp = MagicMock()
        mock_resp.headers = {"Content-Length": "1000000"}
        mock_resp.read.side_effect = blocking_read
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        dm = updater.DownloadManager(chunk_size=1024)
        cancelled_calls = []

        dm.download_async(
            url="http://example.com/app.exe",
            dest_path=self.dest_file,
            on_cancelled=lambda: cancelled_calls.append(True),
        )

        time.sleep(0.1)
        dm.cancel()
        dm._thread.join(timeout=5)

        self.assertEqual(len(cancelled_calls), 1)
        self.assertFalse(os.path.exists(self.dest_file))
        self.assertFalse(os.path.exists(self.dest_file + ".tmp"))


class TestApplyUpdate(unittest.TestCase):
    def test_apply_update_dev_mode(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"new exe")
            f_path = f.name
        try:
            with patch.object(sys, "frozen", False, create=True):
                applied = updater.apply_update(f_path)
                self.assertFalse(applied)
        finally:
            if os.path.exists(f_path):
                os.remove(f_path)

    @patch("subprocess.Popen")
    def test_apply_update_frozen_win32(self, mock_popen):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"new exe")
            f_path = f.name
        try:
            with (
                patch.object(sys, "frozen", True, create=True),
                patch.object(sys, "platform", "win32"),
            ):
                applied = updater.apply_update(f_path, target_exe="C:\\app\\bager.exe")
                self.assertTrue(applied)
                mock_popen.assert_called_once()
        finally:
            if os.path.exists(f_path):
                os.remove(f_path)
