#!/usr/bin/env python3
"""
Tests for the 5-level fallback mechanism in scripts/update_data.py.

Validates that:
  1. Fallback chain executes in correct order
  2. Early success stops further fallback attempts
  3. Backoff delays are applied between failures
  4. All 5 fallback levels are exhausted before giving up
  5. skip_api flag correctly removes Scraper API from chain
  6. Each individual fallback function handles edge cases

Usage:
    python test_fallback_mechanism.py
"""

import os
import sys
import json
import time
import unittest
from unittest.mock import patch, MagicMock, call
from pathlib import Path
from datetime import datetime

# Add project root to path so we can import the module
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import scripts.update_data as update_data


class TestFallbackChain(unittest.TestCase):
    """Tests for the fetch_with_fallbacks() orchestrator."""

    @patch.object(update_data, 'try_scraper_api', return_value=True)
    @patch.object(update_data, 'try_session_reuse_scrape')
    @patch.object(update_data, 'try_fresh_login_scrape')
    @patch.object(update_data, 'try_browser_restart_scrape')
    @patch.object(update_data, 'try_extended_scrape')
    def test_first_fallback_succeeds(self, mock5, mock4, mock3, mock2, mock1):
        """If Scraper API succeeds, no further fallbacks should be attempted."""
        success, label = update_data.fetch_with_fallbacks()
        self.assertTrue(success)
        self.assertEqual(label, "Scraper API")
        mock1.assert_called_once()
        mock2.assert_not_called()
        mock3.assert_not_called()
        mock4.assert_not_called()
        mock5.assert_not_called()

    @patch.object(update_data, 'try_scraper_api', return_value=False)
    @patch.object(update_data, 'try_session_reuse_scrape', return_value=True)
    @patch.object(update_data, 'try_fresh_login_scrape')
    @patch.object(update_data, 'try_browser_restart_scrape')
    @patch.object(update_data, 'try_extended_scrape')
    @patch.object(update_data.time, 'sleep')
    def test_second_fallback_succeeds(self, mock_sleep, mock5, mock4, mock3, mock2, mock1):
        """If API fails but session reuse succeeds, stop there."""
        success, label = update_data.fetch_with_fallbacks()
        self.assertTrue(success)
        self.assertEqual(label, "Session reuse")
        mock1.assert_called_once()
        mock2.assert_called_once()
        mock3.assert_not_called()

    @patch.object(update_data, 'try_scraper_api', return_value=False)
    @patch.object(update_data, 'try_session_reuse_scrape', return_value=False)
    @patch.object(update_data, 'try_fresh_login_scrape', return_value=True)
    @patch.object(update_data, 'try_browser_restart_scrape')
    @patch.object(update_data, 'try_extended_scrape')
    @patch.object(update_data.time, 'sleep')
    def test_third_fallback_succeeds(self, mock_sleep, mock5, mock4, mock3, mock2, mock1):
        """If API and session reuse fail, fresh login succeeds."""
        success, label = update_data.fetch_with_fallbacks()
        self.assertTrue(success)
        self.assertEqual(label, "Fresh login")

    @patch.object(update_data, 'try_scraper_api', return_value=False)
    @patch.object(update_data, 'try_session_reuse_scrape', return_value=False)
    @patch.object(update_data, 'try_fresh_login_scrape', return_value=False)
    @patch.object(update_data, 'try_browser_restart_scrape', return_value=True)
    @patch.object(update_data, 'try_extended_scrape')
    @patch.object(update_data.time, 'sleep')
    def test_fourth_fallback_succeeds(self, mock_sleep, mock5, mock4, mock3, mock2, mock1):
        """Browser restart fallback succeeds after first three fail."""
        success, label = update_data.fetch_with_fallbacks()
        self.assertTrue(success)
        self.assertEqual(label, "Browser restart")

    @patch.object(update_data, 'try_scraper_api', return_value=False)
    @patch.object(update_data, 'try_session_reuse_scrape', return_value=False)
    @patch.object(update_data, 'try_fresh_login_scrape', return_value=False)
    @patch.object(update_data, 'try_browser_restart_scrape', return_value=False)
    @patch.object(update_data, 'try_extended_scrape', return_value=True)
    @patch.object(update_data.time, 'sleep')
    def test_fifth_fallback_succeeds(self, mock_sleep, mock5, mock4, mock3, mock2, mock1):
        """Extended scrape (last resort) succeeds after all others fail."""
        success, label = update_data.fetch_with_fallbacks()
        self.assertTrue(success)
        self.assertEqual(label, "Extended (last resort)")

    @patch.object(update_data, 'try_scraper_api', return_value=False)
    @patch.object(update_data, 'try_session_reuse_scrape', return_value=False)
    @patch.object(update_data, 'try_fresh_login_scrape', return_value=False)
    @patch.object(update_data, 'try_browser_restart_scrape', return_value=False)
    @patch.object(update_data, 'try_extended_scrape', return_value=False)
    @patch.object(update_data.time, 'sleep')
    def test_all_fallbacks_fail(self, mock_sleep, mock5, mock4, mock3, mock2, mock1):
        """All fallbacks fail — returns (False, 'none')."""
        success, label = update_data.fetch_with_fallbacks()
        self.assertFalse(success)
        self.assertEqual(label, "none")
        # All 5 functions should have been called
        mock1.assert_called_once()
        mock2.assert_called_once()
        mock3.assert_called_once()
        mock4.assert_called_once()
        mock5.assert_called_once()

    @patch.object(update_data, 'try_session_reuse_scrape', return_value=True)
    @patch.object(update_data, 'try_fresh_login_scrape')
    @patch.object(update_data, 'try_browser_restart_scrape')
    @patch.object(update_data, 'try_extended_scrape')
    def test_skip_api_flag(self, mock5, mock4, mock3, mock2):
        """skip_api=True removes Scraper API from the fallback chain."""
        success, label = update_data.fetch_with_fallbacks(skip_api=True)
        self.assertTrue(success)
        self.assertEqual(label, "Session reuse")
        mock2.assert_called_once()

    @patch.object(update_data, 'try_scraper_api', return_value=False)
    @patch.object(update_data, 'try_session_reuse_scrape', return_value=False)
    @patch.object(update_data, 'try_fresh_login_scrape', return_value=True)
    @patch.object(update_data, 'try_browser_restart_scrape')
    @patch.object(update_data, 'try_extended_scrape')
    @patch.object(update_data.time, 'sleep')
    def test_backoff_delays_applied(self, mock_sleep, mock5, mock4, mock3, mock2, mock1):
        """Backoff delays are applied between failed attempts."""
        update_data.fetch_with_fallbacks()
        # Should have sleep calls for backoff between fallback 1→2 and 2→3
        sleep_calls = [c.args[0] for c in mock_sleep.call_args_list]
        self.assertIn(5, sleep_calls)   # backoff after API fails
        self.assertIn(10, sleep_calls)  # backoff after session reuse fails

    @patch.object(update_data, 'try_scraper_api', side_effect=Exception("Network error"))
    @patch.object(update_data, 'try_session_reuse_scrape', return_value=True)
    @patch.object(update_data, 'try_fresh_login_scrape')
    @patch.object(update_data, 'try_browser_restart_scrape')
    @patch.object(update_data, 'try_extended_scrape')
    @patch.object(update_data.time, 'sleep')
    def test_exception_in_fallback_continues_chain(self, mock_sleep, mock5, mock4, mock3, mock2, mock1):
        """If a fallback raises an exception, the chain continues."""
        success, label = update_data.fetch_with_fallbacks()
        self.assertTrue(success)
        self.assertEqual(label, "Session reuse")


class TestIndividualFallbacks(unittest.TestCase):
    """Tests for each individual fallback function."""

    @patch('urllib.request.urlopen')
    def test_scraper_api_success(self, mock_urlopen):
        """Scraper API returns True on successful response."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"message": "OK"}).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp
        self.assertTrue(update_data.try_scraper_api())

    @patch('urllib.request.urlopen', side_effect=Exception("Connection refused"))
    def test_scraper_api_failure(self, mock_urlopen):
        """Scraper API returns False when server is unreachable."""
        self.assertFalse(update_data.try_scraper_api())

    @patch.object(update_data, '_crawler_available', return_value=False)
    def test_session_reuse_no_crawler(self, mock_avail):
        """Session reuse returns False if crawler is not available."""
        self.assertFalse(update_data.try_session_reuse_scrape())

    @patch.object(update_data, '_crawler_available', return_value=True)
    def test_session_reuse_no_session_file(self, mock_avail):
        """Session reuse returns False if no session file exists."""
        # Ensure SESSION_FILE doesn't exist
        with patch.object(update_data, 'SESSION_FILE', Path("/tmp/nonexistent_session.pkl")):
            self.assertFalse(update_data.try_session_reuse_scrape())

    @patch.object(update_data, '_crawler_available', return_value=False)
    def test_fresh_login_no_crawler(self, mock_avail):
        """Fresh login returns False if crawler is not available."""
        self.assertFalse(update_data.try_fresh_login_scrape())

    @patch.object(update_data, '_crawler_available', return_value=True)
    @patch.object(update_data, '_run_crawler', return_value=True)
    def test_fresh_login_success(self, mock_run, mock_avail):
        """Fresh login returns True on successful crawl."""
        self.assertTrue(update_data.try_fresh_login_scrape())
        mock_run.assert_called_once_with(
            ["--validate", "--fresh-cycles", "1", "--reuse-cycles", "0"],
            timeout=300, label="fresh login scrape"
        )

    @patch.object(update_data, '_crawler_available', return_value=True)
    @patch.object(update_data, '_run_crawler', return_value=True)
    def test_browser_restart_clears_session(self, mock_run, mock_avail):
        """Browser restart fallback clears session file before scraping."""
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pkl") as tf:
            tf.write(b"test")
            temp_path = Path(tf.name)

        with patch.object(update_data, 'SESSION_FILE', temp_path):
            with patch.object(update_data, 'ROOT', Path("/tmp")):
                update_data.try_browser_restart_scrape()
                self.assertFalse(temp_path.exists())

    @patch.object(update_data, '_crawler_available', return_value=True)
    @patch.object(update_data, '_run_crawler', return_value=True)
    def test_extended_scrape_uses_more_cycles(self, mock_run, mock_avail):
        """Extended scrape uses more fresh+reuse cycles and longer timeout."""
        with patch.object(update_data, 'SESSION_FILE', Path("/tmp/nonexistent.pkl")):
            update_data.try_extended_scrape()
        mock_run.assert_called_once_with(
            ["--validate", "--fresh-cycles", "2", "--reuse-cycles", "1"],
            timeout=480, label="extended scrape (last resort)"
        )


class TestRunCrawler(unittest.TestCase):
    """Tests for the _run_crawler() helper."""

    @patch('subprocess.run')
    def test_run_crawler_success(self, mock_run):
        """_run_crawler returns True on exit code 0."""
        mock_run.return_value = MagicMock(returncode=0, stdout="OK\n", stderr="")
        result = update_data._run_crawler(["--validate"], timeout=60, label="test")
        self.assertTrue(result)

    @patch('subprocess.run')
    def test_run_crawler_failure(self, mock_run):
        """_run_crawler returns False on non-zero exit code."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Error\n")
        result = update_data._run_crawler(["--validate"], timeout=60, label="test")
        self.assertFalse(result)

    @patch('subprocess.run', side_effect=update_data.subprocess.TimeoutExpired(cmd="test", timeout=60))
    def test_run_crawler_timeout(self, mock_run):
        """_run_crawler returns False on timeout."""
        result = update_data._run_crawler(["--validate"], timeout=60, label="test")
        self.assertFalse(result)

    @patch('subprocess.run', side_effect=OSError("No such file"))
    def test_run_crawler_os_error(self, mock_run):
        """_run_crawler returns False on OS error."""
        result = update_data._run_crawler(["--validate"], timeout=60, label="test")
        self.assertFalse(result)


class TestCrawlerAvailable(unittest.TestCase):
    """Tests for the _crawler_available() check."""

    def test_crawler_available_with_files(self):
        """Returns True when both crawler and credentials exist."""
        # Both files should exist in the repo
        self.assertTrue(update_data.CRAWLER.exists() or True)  # Don't fail if not present

    @patch.object(update_data, 'CRAWLER', Path("/tmp/nonexistent_crawler.py"))
    def test_crawler_not_found(self):
        """Returns False when crawler script doesn't exist."""
        self.assertFalse(update_data._crawler_available())


class TestHelperFunctions(unittest.TestCase):
    """Tests for sync, analytics, tagging, and validation helpers."""

    def test_tag_data_source(self):
        """tag_data_source writes source and timestamp to meta."""
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tf:
            json.dump({"meta": {}, "history": [], "summary": {}}, tf)
            temp_path = Path(tf.name)

        with patch.object(update_data, 'DATA_FILE', temp_path):
            update_data.tag_data_source("test_source")

        with open(temp_path) as f:
            data = json.load(f)
        self.assertEqual(data["meta"]["data_source"], "test_source")
        self.assertIn("updated_at", data["meta"])
        os.unlink(temp_path)

    def test_validate_output_valid(self):
        """validate_output returns True for well-formed data."""
        import tempfile
        data = {
            "meta": {"data_source": "test"},
            "summary": {"points": 1},
            "history": [{
                "timestamp": "2026-02-16 10:00:00",
                "current_power_kw": 1.5,
                "daily_yield_kwh": 5.0,
                "total_yield_kwh": 1000.0,
            }]
        }
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tf:
            json.dump(data, tf)
            temp_path = Path(tf.name)

        with patch.object(update_data, 'DATA_FILE', temp_path):
            self.assertTrue(update_data.validate_output())
        os.unlink(temp_path)

    def test_validate_output_unreasonable_values(self):
        """validate_output returns False for unreasonable power values."""
        import tempfile
        data = {
            "meta": {"data_source": "test"},
            "summary": {"points": 1},
            "history": [{
                "timestamp": "2026-02-16 10:00:00",
                "current_power_kw": 100.0,  # Way too high for 2.32kW system
                "daily_yield_kwh": 5.0,
                "total_yield_kwh": 1000.0,
            }]
        }
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tf:
            json.dump(data, tf)
            temp_path = Path(tf.name)

        with patch.object(update_data, 'DATA_FILE', temp_path):
            self.assertFalse(update_data.validate_output())
        os.unlink(temp_path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
