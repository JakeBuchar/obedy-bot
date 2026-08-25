import unittest
from datetime import date
from unittest.mock import Mock, patch

from scrapers.govinda import fetch_govinda_menu


HTML = """
<section id="menu">
  <div class="col space-bottom">
    <h4>Pondělí – 24.8.2026</h4>
    <p><b>Polévka –</b> Pondělní polévka</p>
  </div>
  <div class="col space-bottom">
    <h4>Úterý – 25.8.2026</h4>
    <p><b>Polévka –</b> Čočková <b>VEGAN</b></p>
    <p><b>Sabdží –</b> Květák se smetanou (7)</p>
  </div>
</section>
"""


class GovindaParserTest(unittest.TestCase):
    @patch("scrapers.govinda.requests.get")
    def test_selects_only_today_and_splits_categories(self, get: Mock) -> None:
        get.return_value.text = HTML
        get.return_value.raise_for_status.return_value = None

        menu = fetch_govinda_menu("https://example.test/#menu", date(2026, 8, 25))

        self.assertEqual(menu.heading, "Úterý – 25.8.2026")
        self.assertEqual([item.category for item in menu.items], ["Polévka", "Sabdží"])
        self.assertEqual(menu.items[0].name, "Čočková VEGAN")
        self.assertEqual(menu.items[1].name, "Květák se smetanou")
        self.assertEqual(menu.items[1].allergens, "(7)")

    @patch("scrapers.govinda.requests.get")
    def test_fails_when_today_is_not_published(self, get: Mock) -> None:
        get.return_value.text = HTML
        get.return_value.raise_for_status.return_value = None

        with self.assertRaisesRegex(ValueError, "26.8.2026"):
            fetch_govinda_menu("https://example.test/#menu", date(2026, 8, 26))


if __name__ == "__main__":
    unittest.main()
