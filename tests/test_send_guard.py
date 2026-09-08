import unittest
from unittest.mock import patch

import main


class SendGuardTest(unittest.TestCase):
    """Which triggers consult already_sent_today() before sending."""

    def _run(self, env: dict, already_sent: bool = True) -> bool:
        """Returns True when the run sent the email."""
        with patch.dict("os.environ", env, clear=True), patch(
            "main.already_sent_today", return_value=already_sent
        ), patch("main.load_restaurants", return_value=[]), patch(
            "main.scrape_all", return_value=[]
        ), patch("main.send_email") as send_email, patch("sys.argv", ["main.py"]):
            main.main()
            return send_email.called

    def test_cron_skips_when_already_sent(self) -> None:
        self.assertFalse(self._run({"GITHUB_EVENT_NAME": "schedule"}))

    def test_cron_sends_when_nothing_sent_yet(self) -> None:
        self.assertTrue(self._run({"GITHUB_EVENT_NAME": "schedule"}, already_sent=False))

    def test_external_dispatch_skips_when_already_sent(self) -> None:
        env = {"GITHUB_EVENT_NAME": "workflow_dispatch", "SKIP_IF_SENT": "true"}
        self.assertFalse(self._run(env))

    def test_manual_dispatch_always_sends(self) -> None:
        env = {"GITHUB_EVENT_NAME": "workflow_dispatch", "SKIP_IF_SENT": "false"}
        self.assertTrue(self._run(env))

    def test_manual_dispatch_without_input_always_sends(self) -> None:
        self.assertTrue(self._run({"GITHUB_EVENT_NAME": "workflow_dispatch"}))

    def test_local_run_always_sends(self) -> None:
        self.assertTrue(self._run({}))


if __name__ == "__main__":
    unittest.main()
