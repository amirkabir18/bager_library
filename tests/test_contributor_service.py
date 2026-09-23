import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.contributor_service import (
    DEFAULT_CONTRIBUTORS,
    calculate_code_percentages,
    calculate_commit_percentages,
    fetch_contributors_from_github,
    get_contributor_display_name,
    get_contributors_stats,
    load_cached_contributors,
    save_cached_contributors,
)


class TestContributorService(unittest.TestCase):
    def test_display_name_mapping(self):
        self.assertEqual(get_contributor_display_name("amirkabir18"), "امیرحسین اسدی")
        self.assertEqual(get_contributor_display_name("Aliomosavi"), "سید محمد حسن موسوی")
        self.assertEqual(get_contributor_display_name("ARUSH221617"), "امیررضا یونس‌زاده شیرازی")
        self.assertEqual(get_contributor_display_name("unknown_dev"), "unknown_dev")

    def test_calculate_code_percentages(self):
        stats_mock = [
            {
                "author": {"login": "dev1", "html_url": "https://github.com/dev1"},
                "weeks": [{"a": 100, "d": 10, "c": 2}, {"a": 200, "d": 5, "c": 3}],
            },
            {
                "author": {"login": "dev2", "html_url": "https://github.com/dev2"},
                "weeks": [{"a": 100, "d": 0, "c": 1}],
            },
        ]
        # Total additions: 300 + 100 = 400. dev1: 300/400 = 75.0%, dev2: 100/400 = 25.0%
        result = calculate_code_percentages(stats_mock)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["login"], "dev1")
        self.assertEqual(result[0]["lines_added"], 300)
        self.assertEqual(result[0]["percent"], 75.0)

        self.assertEqual(result[1]["login"], "dev2")
        self.assertEqual(result[1]["lines_added"], 100)
        self.assertEqual(result[1]["percent"], 25.0)

    def test_calculate_code_percentages_empty(self):
        self.assertEqual(calculate_code_percentages([]), [])

    def test_calculate_commit_percentages(self):
        contributors_mock = [
            {"login": "dev1", "contributions": 30, "html_url": "https://github.com/dev1"},
            {"login": "dev2", "contributions": 10, "html_url": "https://github.com/dev2"},
        ]
        # Total commits: 40. dev1: 30/40 = 75.0%, dev2: 10/40 = 25.0%
        result = calculate_commit_percentages(contributors_mock)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["login"], "dev1")
        self.assertEqual(result[0]["percent"], 75.0)
        self.assertEqual(result[1]["login"], "dev2")
        self.assertEqual(result[1]["percent"], 25.0)

    def test_cache_roundtrip_and_expiration(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            cache_file = f.name

        try:
            sample_data = [{"login": "dev1", "name": "Dev One", "percent": 100.0}]
            save_cached_contributors(sample_data, cache_path=cache_file)

            # Valid cache
            loaded = load_cached_contributors(cache_path=cache_file, ttl=60)
            self.assertEqual(loaded, sample_data)

            # Expired cache
            loaded_expired = load_cached_contributors(cache_path=cache_file, ttl=-1)
            self.assertIsNone(loaded_expired)
        finally:
            if os.path.exists(cache_file):
                os.remove(cache_file)

    @patch("urllib.request.urlopen")
    def test_fetch_contributors_from_github_stats_success(self, mock_urlopen):
        stats_mock = [
            {
                "author": {"login": "amirkabir18", "html_url": "https://github.com/amirkabir18"},
                "weeks": [{"a": 500, "d": 50, "c": 5}],
            }
        ]
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(stats_mock).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        res = fetch_contributors_from_github("test/repo")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["login"], "amirkabir18")
        self.assertEqual(res[0]["name"], "امیرحسین اسدی")
        self.assertEqual(res[0]["percent"], 100.0)

    @patch("urllib.request.urlopen")
    def test_fetch_contributors_from_github_fallback_on_network_error(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("Connection refused")
        res = fetch_contributors_from_github("test/repo")
        self.assertEqual(res, DEFAULT_CONTRIBUTORS)

    @patch("services.contributor_service.fetch_contributors_from_github")
    def test_get_contributors_stats_uses_cache(self, mock_fetch):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            cache_file = f.name
        try:
            sample = [{"login": "cached_dev", "name": "Cached", "percent": 50.0}]
            save_cached_contributors(sample, cache_path=cache_file)

            result = get_contributors_stats(cache_path=cache_file, cache_ttl=3600)
            self.assertEqual(result, sample)
            mock_fetch.assert_not_called()
        finally:
            if os.path.exists(cache_file):
                os.remove(cache_file)


if __name__ == "__main__":
    unittest.main()
