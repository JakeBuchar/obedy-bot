import unittest
from unittest.mock import Mock, patch

from scrapers.laventola import fetch_laventola_menu

HTML = """
<section id="menu">
  <div class="head-title">Polední menu</div>
  <div class="desc_price_list">25.8. 2026<br>11:00-15:00</div>
  <div class="tab" id="all" style="display:none">
    <div class="name-price-desc">
      <div class="name">Bramboračka</div>
      <div class="spl-price">45 ,- Kč</div>
    </div>
    <div class="name-price-desc">
      <div class="name">Penne s kuřecím</div>
      <div class="spl-price">179 ,- Kč</div>
    </div>
  </div>
  <div class="tab-pane">
    <div class="name-price-desc">
      <div class="name">Bramboračka</div>
      <div class="spl-price">45 ,- Kč</div>
    </div>
    <div class="name-price-desc">
      <div class="name">Penne s kuřecím</div>
      <div class="spl-price">179 ,- Kč</div>
    </div>
  </div>
</section>
"""


class LaventolaParserTest(unittest.TestCase):
    @patch("scrapers.laventola.requests.get")
    def test_dedupes_tabs_and_keeps_heading(self, get: Mock) -> None:
        get.return_value.text = HTML
        get.return_value.raise_for_status.return_value = None

        menu = fetch_laventola_menu("https://laventola.cz/#menu")

        self.assertEqual(menu.heading, "Polední menu · 25.8. 2026 11:00-15:00")
        self.assertEqual([item.name for item in menu.items], ["Bramboračka", "Penne s kuřecím"])
        self.assertEqual(menu.items[0].price, "45 ,- Kč")


if __name__ == "__main__":
    unittest.main()
