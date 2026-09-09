import io
import os
import unittest
from unittest.mock import Mock, patch

from PIL import Image

from email_sender import send_email
from logos import inline_logos, logo_as_png


def _image_bytes(fmt: str, size: tuple[int, int] = (180, 180)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGBA", size, (200, 40, 20, 255)).save(buffer, format=fmt)
    return buffer.getvalue()


class LogoConversionTest(unittest.TestCase):
    @patch("logos.requests.get")
    def test_converts_webp_to_png(self, get: Mock) -> None:
        get.return_value.content = _image_bytes("WEBP")
        get.return_value.raise_for_status.return_value = None

        png = logo_as_png("https://example.test/logo.webp")

        with Image.open(io.BytesIO(png)) as image:
            self.assertEqual(image.format, "PNG")
            self.assertLessEqual(max(image.size), 88)

    @patch("logos.requests.get")
    def test_converts_ico_to_png(self, get: Mock) -> None:
        get.return_value.content = _image_bytes("ICO", (32, 32))
        get.return_value.raise_for_status.return_value = None

        png = logo_as_png("https://example.test/favicon.ico")

        with Image.open(io.BytesIO(png)) as image:
            self.assertEqual(image.format, "PNG")

    @patch("logos.requests.get", side_effect=RuntimeError("offline"))
    def test_download_failure_returns_none(self, _get: Mock) -> None:
        self.assertIsNone(logo_as_png("https://example.test/logo.png"))


class InlineLogosTest(unittest.TestCase):
    @patch("logos.requests.get")
    def test_rewrites_urls_to_attachments(self, get: Mock) -> None:
        get.return_value.content = _image_bytes("WEBP")
        get.return_value.raise_for_status.return_value = None
        results = [
            {"name": "Arco", "logo_url": "https://example.test/arco.webp"},
            {"name": "Bez loga", "logo_url": None},
        ]

        images = inline_logos(results)

        self.assertEqual(results[0]["logo_url"], "cid:logo0")
        self.assertEqual(list(images), ["logo0"])
        self.assertIsNone(results[1]["logo_url"])

    @patch("logos.requests.get", side_effect=RuntimeError("offline"))
    def test_keeps_the_original_url_when_conversion_fails(self, _get: Mock) -> None:
        results = [{"name": "Arco", "logo_url": "https://example.test/arco.webp"}]

        images = inline_logos(results)

        self.assertEqual(results[0]["logo_url"], "https://example.test/arco.webp")
        self.assertEqual(images, {})


class InlineImageMessageTest(unittest.TestCase):
    SMTP_ENV = {
        "SMTP_HOST": "smtp.example.test",
        "SMTP_USER": "bot@example.test",
        "SMTP_PASSWORD": "secret",
        "MAIL_TO": "a@example.test",
    }

    def test_attachments_travel_next_to_the_body(self) -> None:
        with patch.dict(os.environ, self.SMTP_ENV, clear=True), patch("email_sender.smtplib.SMTP_SSL") as smtp:
            send_email(
                subject="Test",
                html_body='<img src="cid:logo0">',
                text_body="Test",
                inline_images={"logo0": _image_bytes("PNG", (8, 8))},
            )

            raw = smtp.return_value.__enter__.return_value.sendmail.call_args[0][2]
            self.assertIn("multipart/related", raw)
            self.assertIn("<logo0>", raw)

    def test_plain_message_stays_a_simple_alternative(self) -> None:
        with patch.dict(os.environ, self.SMTP_ENV, clear=True), patch("email_sender.smtplib.SMTP_SSL") as smtp:
            send_email(subject="Test", html_body="<p>Test</p>", text_body="Test")

            raw = smtp.return_value.__enter__.return_value.sendmail.call_args[0][2]
            self.assertIn("multipart/alternative", raw)
            self.assertNotIn("multipart/related", raw)


if __name__ == "__main__":
    unittest.main()
