import io
import unittest
from unittest.mock import patch

import main
from scrapers.prague import StaleMenuError


class FailIfErrorsTest(unittest.TestCase):
    def test_stale_menu_is_a_warning_and_does_not_fail(self) -> None:
        results = [
            {
                "name": "La Musica",
                "error": "La Musica still shows the menu for 9.9.2026, not 10.9.2026",
                "stale": True,
            }
        ]
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            main.fail_if_errors(results)
        self.assertIn("have not published today's menu", buf.getvalue())
        self.assertNotIn("Failing the run", buf.getvalue())

    def test_a_broken_scrape_still_fails_the_job(self) -> None:
        results = [
            {"name": "La Ventola", "error": "laventola.cz did not answer", "stale": False},
        ]
        with self.assertRaises(SystemExit) as caught:
            main.fail_if_errors(results)
        self.assertEqual(caught.exception.code, 1)

    def test_a_stale_menu_does_not_hide_a_real_failure(self) -> None:
        results = [
            {"name": "Arco", "error": "still shows yesterday", "stale": True},
            {"name": "La Ventola", "error": "network is unreachable", "stale": False},
        ]
        with self.assertRaises(SystemExit) as caught:
            main.fail_if_errors(results)
        self.assertEqual(caught.exception.code, 1)


class ScrapeAllWarningTest(unittest.TestCase):
    def test_stale_exception_is_logged_as_a_github_warning(self) -> None:
        restaurants = [{"name": "Arco", "url": "https://example.test", "adapter": "arco"}]
        buf = io.StringIO()
        with patch("main.fetch_arco_menu", side_effect=StaleMenuError("Arco still shows yesterday")), patch(
            "sys.stdout", buf
        ):
            results = main.scrape_all(restaurants)
        self.assertTrue(results[0]["stale"])
        self.assertIn("::warning title=Arco::", buf.getvalue())
        self.assertNotIn("::error title=Arco::", buf.getvalue())

    def test_a_connection_error_is_logged_as_a_github_error(self) -> None:
        restaurants = [{"name": "La Ventola", "url": "https://laventola.cz", "adapter": "laventola"}]
        buf = io.StringIO()
        with patch(
            "main.fetch_laventola_menu", side_effect=RuntimeError("network is unreachable")
        ), patch("sys.stdout", buf):
            results = main.scrape_all(restaurants)
        self.assertFalse(results[0]["stale"])
        self.assertIn("::error title=La Ventola::", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
