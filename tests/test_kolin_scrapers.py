import json
import unittest
from datetime import date
from unittest.mock import Mock, patch

from scrapers.arco import fetch_arco_menu
from scrapers.farina import fetch_farina_menu
from scrapers.katolak import fetch_katolak_menu
from scrapers.lamusica import fetch_lamusica_menu
from scrapers.nasidlisti import fetch_nasidlisti_menu
from scrapers.prague import StaleMenuError
from scrapers.stoleta import fetch_stoleta_menu
from scrapers.vodni import fetch_vodni_menu

TODAY = date(2026, 9, 9)


class VodniParserTest(unittest.TestCase):
    HTML = """
    <section id="dennimenu">
      <h3>Denní menu</h3>
      <div>...pro 9.9.2026</div>
      <div class="deme_place">
        <div class="deme_item"><b>Polévky</b></div>
        <div class="deme_item"><span>0,35l</span><span>Bramboračka (A:1)</span><span>49,- Kč</span></div>
        <div class="deme_item"><b>Hlavní jídla</b></div>
        <div class="deme_item"><span>150gr</span><span>Guláš</span><span>169,- Kč</span></div>
      </div>
    </section>
    """

    @patch("scrapers.vodni.requests.get")
    def test_parses_daily_rows_and_skips_categories(self, get: Mock) -> None:
        get.return_value.text = self.HTML
        get.return_value.content = self.HTML.encode()
        get.return_value.apparent_encoding = "utf-8"
        get.return_value.encoding = "utf-8"
        get.return_value.raise_for_status.return_value = None

        menu = fetch_vodni_menu("https://example.test/", TODAY)
        self.assertEqual([item.name for item in menu.items], ["Bramboračka (A:1)", "Guláš"])
        self.assertEqual(menu.items[0].category, "Polévky")
        self.assertEqual(menu.items[1].price, "169,- Kč")

    @patch("scrapers.vodni.requests.get")
    def test_accepts_next_day_menu_and_labels_it(self, get: Mock) -> None:
        html = self.HTML.replace("9.9.2026", "10.9.2026")
        get.return_value.text = html
        get.return_value.content = html.encode()
        get.return_value.apparent_encoding = "utf-8"
        get.return_value.encoding = "utf-8"
        get.return_value.raise_for_status.return_value = None

        menu = fetch_vodni_menu("https://example.test/", TODAY)
        self.assertEqual(menu.heading, "Denní menu 10.9.2026")
        self.assertEqual(len(menu.items), 2)

    @patch("scrapers.vodni.requests.get")
    def test_fails_when_the_page_is_stale(self, get: Mock) -> None:
        html = self.HTML.replace("9.9.2026", "8.9.2026")
        get.return_value.text = html
        get.return_value.content = html.encode()
        get.return_value.apparent_encoding = "utf-8"
        get.return_value.encoding = "utf-8"
        get.return_value.raise_for_status.return_value = None
        with self.assertRaisesRegex(StaleMenuError, "8.9.2026"):
            fetch_vodni_menu("https://example.test/", TODAY)


class FarinaParserTest(unittest.TestCase):
    HTML = """
    <div class="jet-listing-grid__item">
      <div class="jet-listing-dynamic-field__content">Středa</div>
      <h2 class="elementor-heading-title">10:30 - 14:00</h2>
      <h2 class="elementor-heading-title">Denní nabídka</h2>
      <div class="jet-listing-dynamic-field__content">Minestrone</div>
      <div class="jet-listing-dynamic-field__content">109 Kč</div>
      <div class="jet-listing-dynamic-field__content">Lasagne</div>
      <div class="jet-listing-dynamic-field__content">159 Kč</div>
      <h2 class="elementor-heading-title">Týdenní nabídka</h2>
      <div class="jet-listing-dynamic-field__content">Caprese</div>
      <div class="jet-listing-dynamic-field__content">319 Kč</div>
    </div>
    """

    @patch("scrapers.farina.requests.get")
    def test_keeps_daily_offer_only(self, get: Mock) -> None:
        get.return_value.text = self.HTML
        get.return_value.raise_for_status.return_value = None
        menu = fetch_farina_menu("https://farina.cz/poledni-menu/", TODAY)
        self.assertEqual([item.name for item in menu.items], ["Minestrone", "Lasagne"])
        self.assertEqual(menu.heading, "Středa · 10:30 - 14:00")


class LamusicaParserTest(unittest.TestCase):
    HTML = """
    <div class="tst-menu-rows">
      <h3 class="tst-title--h">POLEDNÍ MENU: Středa 9. 9. 2026</h3>
      <div class="tst-menu-book-item">
        <div class="tst-menu-book-name"><h5>Polévka: Krém</h5><div class="tst-text">smetana</div></div>
        <div class="tst-price">55 Kč</div>
      </div>
    </div>
    <div class="tst-menu-rows">
      <h3 class="tst-title--h">TÝDENNÍ POLEDNÍ JÍDLA: 7. 9. - 11. 9. 2026</h3>
      <div class="tst-menu-book-item">
        <div class="tst-menu-book-name"><h5>Burgundsko</h5></div>
        <div class="tst-price">209 Kč</div>
      </div>
    </div>
    """

    @patch("scrapers.lamusica.requests.get")
    def test_ignores_weekly_block(self, get: Mock) -> None:
        get.return_value.text = self.HTML
        get.return_value.raise_for_status.return_value = None
        menu = fetch_lamusica_menu("https://restauracelamusica.cz/denni-menu/", TODAY)
        self.assertEqual([item.name for item in menu.items], ["Polévka: Krém"])
        self.assertEqual(menu.items[0].description, "smetana")

    @patch("scrapers.lamusica.requests.get")
    def test_accepts_next_day_menu(self, get: Mock) -> None:
        get.return_value.text = self.HTML.replace("Středa 9. 9. 2026", "Čtvrtek 10. 9. 2026")
        get.return_value.raise_for_status.return_value = None
        menu = fetch_lamusica_menu("https://restauracelamusica.cz/denni-menu/", TODAY)
        self.assertIn("10. 9. 2026", menu.heading)

    @patch("scrapers.lamusica.requests.get")
    def test_fails_when_the_page_is_stale(self, get: Mock) -> None:
        get.return_value.text = self.HTML.replace("Středa 9. 9. 2026", "Úterý 8. 9. 2026")
        get.return_value.raise_for_status.return_value = None
        with self.assertRaisesRegex(StaleMenuError, "8.9.2026"):
            fetch_lamusica_menu("https://restauracelamusica.cz/denni-menu/", TODAY)


class ArcoParserTest(unittest.TestCase):
    HTML = """
    <div class="elementor-widget-wrap">
      <h4 class="pbmit-element-title">POLEDNÍ MENU: Středa 9. 9. 2026</h4>
      <ul class="elementor-price-list">
        <li class="elementor-price-list-item">
          <span class="elementor-price-list-title">Polévka: Krém</span>
          <span class="elementor-price-list-price">55 Kč</span>
          <p class="elementor-price-list-description">cizrna</p>
        </li>
      </ul>
    </div>
    <div class="elementor-widget-wrap">
      <h4 class="pbmit-element-title">TÝDENNÍ SEZÓNNÍ POKRM: 7. 9. - 11. 9. 2026</h4>
      <ul class="elementor-price-list">
        <li class="elementor-price-list-item">
          <span class="elementor-price-list-title">Žebra</span>
          <span class="elementor-price-list-price">209 Kč</span>
        </li>
      </ul>
    </div>
    """

    @patch("scrapers.arco.requests.get")
    def test_takes_only_daily_price_list(self, get: Mock) -> None:
        get.return_value.text = self.HTML
        get.return_value.raise_for_status.return_value = None
        menu = fetch_arco_menu("https://restauracearco.cz/menu/denni-menu/", TODAY)
        self.assertEqual([item.name for item in menu.items], ["Polévka: Krém"])
        self.assertEqual(menu.items[0].description, "cizrna")


class NasidlistiParserTest(unittest.TestCase):
    FRAGMENT = {
        "state": "menu",
        "html": """
        <div class="today-head" data-menu-date="2026-09-09">
          <span class="today-date">9. 9. 2026</span>
        </div>
        <table class="daily-menu">
          <tr>
            <td class="dm-size">350 ml</td>
            <td class="dm-name">Česnečka <span class="dm-alerg">1</span></td>
            <td class="dm-price">49 Kč</td>
          </tr>
        </table>
        """,
    }

    @patch("scrapers.nasidlisti.requests.get")
    def test_parses_fragment_table(self, get: Mock) -> None:
        get.return_value.text = json.dumps(self.FRAGMENT)
        get.return_value.raise_for_status.return_value = None
        menu = fetch_nasidlisti_menu("https://www.nasidlisti1962.cz/#dnesni-menu", TODAY)
        self.assertEqual(menu.items[0].name, "Česnečka")
        self.assertEqual(menu.items[0].allergens, "1")
        self.assertEqual(menu.items[0].price, "49 Kč")
        self.assertTrue(get.call_args[0][0].endswith("/denni-menu/fragment"))

    @patch("scrapers.nasidlisti.requests.get")
    def test_fails_when_the_fragment_is_stale(self, get: Mock) -> None:
        stale = {**self.FRAGMENT, "html": self.FRAGMENT["html"].replace("2026-09-09", "2026-09-08")}
        get.return_value.text = json.dumps(stale)
        get.return_value.raise_for_status.return_value = None
        with self.assertRaisesRegex(StaleMenuError, "8.9.2026"):
            fetch_nasidlisti_menu("https://www.nasidlisti1962.cz/#dnesni-menu", TODAY)


class StoletaParserTest(unittest.TestCase):
    @patch("scrapers.stoleta.requests.get")
    def test_selects_today_from_latest_week(self, get: Mock) -> None:
        page = Mock()
        page.text = '<script src="/assets/index-abc.js"></script>'
        page.raise_for_status.return_value = None
        bundle = Mock()
        bundle.text = (
            'createClient("https://abc.supabase.co","eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.'
            "eyJpc3MiOiJzdXBhYmFzZSJ9.signature\")"
        )
        bundle.raise_for_status.return_value = None
        api = Mock()
        api.raise_for_status.return_value = None
        api.json.return_value = [
            {"name": "Guláš", "description": "", "price": 171, "category": "Hlavní chod", "order_in_category": 0},
            {"name": "Polévka", "description": "", "price": 59, "category": "Polévka", "order_in_category": 0},
        ]
        get.side_effect = [page, bundle, api]

        menu = fetch_stoleta_menu("https://stoleta.cz/menu", TODAY)
        self.assertEqual([item.category for item in menu.items], ["Polévka", "Hlavní chod"])
        self.assertEqual(menu.items[1].price, "171 Kč")
        self.assertEqual(get.call_args_list[2].kwargs["params"]["week_start_date"], "eq.2026-09-07")
        self.assertEqual(get.call_args_list[2].kwargs["params"]["day_of_week"], "eq.2")


class KatolakParserTest(unittest.TestCase):
    PAYLOAD = {
        "forDate": "2026-09-09",
        "pages": [
            {
                "spans": [
                    {"text": "k výhodnému menu 0,2l limonády zdarma"},
                    {"text": "polévky"},
                    {"text": "Polévka zeleninová"},
                    {"text": "(1)"},
                    {"text": "54,-"},
                    {"text": "dnes nabízíme"},
                    {"text": "150g"},
                    {"text": "(1,7)"},
                    {"text": "Zapečená kotletka"},
                    {"text": "189,-"},
                    {"text": "výhodná menu"},
                    {"text": "menu 1)"},
                    {"text": "Polévka zeleninová"},
                    {"text": "239,-"},
                ]
            }
        ],
    }

    @patch("scrapers.katolak.requests.get")
    def test_parses_spans_and_skips_combo_block(self, get: Mock) -> None:
        get.return_value.json.return_value = self.PAYLOAD
        get.return_value.raise_for_status.return_value = None
        menu = fetch_katolak_menu("https://katolak.cz/", TODAY)
        self.assertEqual([item.name for item in menu.items], ["Polévka zeleninová", "Zapečená kotletka"])
        self.assertEqual(menu.items[1].price, "189 Kč")
        self.assertEqual(menu.items[1].description, "150g")
        self.assertEqual(menu.image_url, "https://be.katolak.cz/menu/today/page/0")

    @patch("scrapers.katolak.requests.get")
    def test_accepts_next_day_menu_and_labels_it(self, get: Mock) -> None:
        get.return_value.json.return_value = {**self.PAYLOAD, "forDate": "2026-09-10"}
        get.return_value.raise_for_status.return_value = None
        menu = fetch_katolak_menu("https://katolak.cz/", TODAY)
        self.assertEqual(menu.heading, "Denní menu 10.9.2026")

    @patch("scrapers.katolak.requests.get")
    def test_fails_when_the_api_is_stale(self, get: Mock) -> None:
        get.return_value.json.return_value = {**self.PAYLOAD, "forDate": "2026-09-08"}
        get.return_value.raise_for_status.return_value = None
        with self.assertRaisesRegex(StaleMenuError, "8.9.2026"):
            fetch_katolak_menu("https://katolak.cz/", TODAY)


if __name__ == "__main__":
    unittest.main()
