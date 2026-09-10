"""Every restaurant in both configs must reach its adapter.

A missing import in main.py only shows up when that adapter runs, which for
Praha's menubot restaurants meant four broken cards in the daily email
(2026-09-10) while every unit test stayed green. These tests walk the real
configs and check each entry gets as far as making a request.
"""
import unittest
from unittest.mock import patch

import main


class ConfiguredAdaptersTest(unittest.TestCase):
    SENTINEL = "adapter reached the network"

    def _errors_for(self, path: str) -> list[tuple[str, str]]:
        restaurants = main.load_restaurants(path)
        self.assertTrue(restaurants, f"{path} has no restaurants")
        # Every adapter shares the one requests module, so stubbing it here
        # keeps the walk offline whichever way an adapter imported its helpers.
        with patch("requests.get", side_effect=RuntimeError(self.SENTINEL)):
            results = main.scrape_all(restaurants)
        return [(r["name"], r["error"] or "") for r in results]

    def _assert_every_adapter_resolves(self, path: str) -> None:
        for name, error in self._errors_for(path):
            with self.subTest(restaurant=name):
                self.assertIn(
                    self.SENTINEL,
                    error,
                    f"{name} never got as far as fetching its menu: {error}",
                )

    def test_praha_restaurants_reach_their_adapter(self) -> None:
        self._assert_every_adapter_resolves("config/praha.yaml")

    def test_kolin_restaurants_reach_their_adapter(self) -> None:
        self._assert_every_adapter_resolves("config/kolin.yaml")


if __name__ == "__main__":
    unittest.main()
