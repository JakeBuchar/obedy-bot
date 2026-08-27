import unittest
from datetime import datetime
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from already_sent import already_sent_today

PRAGUE = ZoneInfo("Europe/Prague")
NOW = datetime(2026, 8, 27, 9, 30, tzinfo=PRAGUE)
ENV = {
    "GITHUB_TOKEN": "t",
    "GITHUB_REPOSITORY": "JakeBuchar/obedy-bot",
    "GITHUB_RUN_ID": "999",
}


def _response(runs: list[dict]) -> Mock:
    response = Mock()
    response.json.return_value = {"workflow_runs": runs}
    response.raise_for_status.return_value = None
    return response


class AlreadySentTest(unittest.TestCase):
    @patch.dict("os.environ", ENV, clear=True)
    @patch("already_sent.requests.get")
    def test_true_when_an_earlier_run_succeeded_today(self, get: Mock) -> None:
        get.return_value = _response(
            [{"id": 111, "run_number": 12, "run_started_at": "2026-08-27T06:50:00Z"}]
        )
        self.assertTrue(already_sent_today(NOW))

    @patch.dict("os.environ", ENV, clear=True)
    @patch("already_sent.requests.get")
    def test_false_when_only_yesterday_succeeded(self, get: Mock) -> None:
        get.return_value = _response(
            [{"id": 111, "run_number": 11, "run_started_at": "2026-08-26T06:50:00Z"}]
        )
        self.assertFalse(already_sent_today(NOW))

    @patch.dict("os.environ", ENV, clear=True)
    @patch("already_sent.requests.get")
    def test_ignores_the_current_run(self, get: Mock) -> None:
        get.return_value = _response(
            [{"id": 999, "run_number": 13, "run_started_at": "2026-08-27T07:30:00Z"}]
        )
        self.assertFalse(already_sent_today(NOW))

    @patch.dict("os.environ", ENV, clear=True)
    @patch("already_sent.requests.get", side_effect=RuntimeError("api down"))
    def test_sends_when_the_api_fails(self, get: Mock) -> None:
        self.assertFalse(already_sent_today(NOW))

    @patch.dict("os.environ", {}, clear=True)
    def test_sends_when_running_outside_actions(self) -> None:
        self.assertFalse(already_sent_today(NOW))


if __name__ == "__main__":
    unittest.main()
