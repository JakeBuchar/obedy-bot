import unittest
from unittest.mock import Mock, patch

import requests

from scrapers.http import with_retries


def _response(status_code: int) -> Mock:
    return Mock(status_code=status_code)


class WithRetriesTest(unittest.TestCase):
    @patch("scrapers.http.time.sleep")
    def test_returns_the_first_successful_answer(self, sleep: Mock) -> None:
        send = Mock(return_value=_response(200))

        self.assertEqual(with_retries(send, "example.test").status_code, 200)
        self.assertEqual(send.call_count, 1)
        sleep.assert_not_called()

    @patch("scrapers.http.time.sleep")
    def test_retries_a_dropped_connection(self, sleep: Mock) -> None:
        send = Mock(side_effect=[requests.ConnectTimeout("timed out"), _response(200)])

        self.assertEqual(with_retries(send, "example.test").status_code, 200)
        self.assertEqual(send.call_count, 2)
        sleep.assert_called_once()

    @patch("scrapers.http.time.sleep")
    def test_gives_up_after_the_last_attempt(self, sleep: Mock) -> None:
        send = Mock(side_effect=requests.ConnectionError("refused"))

        with self.assertRaises(requests.ConnectionError):
            with_retries(send, "example.test", attempts=3)
        self.assertEqual(send.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    @patch("scrapers.http.time.sleep")
    def test_retries_an_overloaded_site(self, sleep: Mock) -> None:
        send = Mock(side_effect=[_response(502), _response(200)])

        self.assertEqual(with_retries(send, "example.test").status_code, 200)
        self.assertEqual(send.call_count, 2)
        sleep.assert_called_once()

    @patch("scrapers.http.time.sleep")
    def test_returns_the_last_answer_even_when_it_is_an_error(self, _sleep: Mock) -> None:
        # The caller raises for status itself, so the final answer is handed
        # back rather than swallowed.
        send = Mock(return_value=_response(503))

        self.assertEqual(with_retries(send, "example.test", attempts=2).status_code, 503)
        self.assertEqual(send.call_count, 2)

    @patch("scrapers.http.time.sleep")
    def test_a_refusal_is_not_retried(self, sleep: Mock) -> None:
        # A 404 is the site's answer, not a hiccup; asking again cannot
        # change it.
        send = Mock(return_value=_response(404))

        self.assertEqual(with_retries(send, "example.test").status_code, 404)
        self.assertEqual(send.call_count, 1)
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
