import os
import unittest
from unittest.mock import patch

from email_sender import send_email

SMTP_ENV = {
    "SMTP_HOST": "smtp.example.test",
    "SMTP_USER": "bot@example.test",
    "SMTP_PASSWORD": "secret",
}


class RecipientGuardTest(unittest.TestCase):
    def test_missing_recipient_fails_before_smtp(self) -> None:
        with patch.dict(os.environ, SMTP_ENV, clear=True), patch("email_sender.smtplib.SMTP_SSL") as smtp:
            with self.assertRaisesRegex(ValueError, "MAIL_TO_KOLIN"):
                send_email(subject="Test", html_body="<p>Test</p>")
            smtp.assert_not_called()

    def test_blank_recipient_secret_fails_before_smtp(self) -> None:
        env = {**SMTP_ENV, "MAIL_TO": " , "}
        with patch.dict(os.environ, env, clear=True), patch("email_sender.smtplib.SMTP_SSL") as smtp:
            with self.assertRaises(ValueError):
                send_email(subject="Test", html_body="<p>Test</p>")
            smtp.assert_not_called()

    def test_sends_to_every_configured_recipient(self) -> None:
        env = {**SMTP_ENV, "MAIL_TO": "a@example.test, b@example.test"}
        with patch.dict(os.environ, env, clear=True), patch("email_sender.smtplib.SMTP_SSL") as smtp:
            send_email(subject="Test", html_body="<p>Test</p>", text_body="Test")
            server = smtp.return_value.__enter__.return_value
            recipients = server.sendmail.call_args[0][1]
            self.assertEqual(recipients, ["a@example.test", "b@example.test"])


if __name__ == "__main__":
    unittest.main()
