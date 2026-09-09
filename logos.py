"""Download restaurant logos and attach them to the email as PNG.

Restaurants publish their logo in whatever format their website happens to
use, and Arco (WebP) and Obecní dům (ICO) both picked one that Outlook
cannot render - those two rows showed a broken-image placeholder while the
PNG logos next to them were fine. Every logo is therefore fetched once per
run, converted to PNG and attached to the message, so what the mail client
receives is always a format it understands.

A logo that cannot be fetched or converted keeps its original URL, which is
exactly what the email did before, so a hiccup here can never do worse than
the previous behaviour.
"""
from __future__ import annotations

import io

import requests

from scrapers.menubot import BROWSER_HEADERS

# Rendered at 44x44 in the email; twice that keeps it sharp on high-DPI
# screens while staying a few kilobytes per restaurant.
LOGO_PX = 88
MAX_DOWNLOAD_BYTES = 2_000_000


def inline_logos(results: list[dict], timeout: int = 10) -> dict[str, bytes]:
    """Point every logo at an attachment; return the attachments by content id."""
    images: dict[str, bytes] = {}
    for index, entry in enumerate(results):
        url = entry.get("logo_url")
        if not url:
            continue
        png = logo_as_png(url, timeout=timeout)
        if png is None:
            continue
        content_id = f"logo{index}"
        images[content_id] = png
        entry["logo_url"] = f"cid:{content_id}"
    return images


def logo_as_png(url: str, timeout: int = 10) -> bytes | None:
    try:
        response = requests.get(url, headers=BROWSER_HEADERS, timeout=timeout)
        response.raise_for_status()
        if len(response.content) > MAX_DOWNLOAD_BYTES:
            return None
        return _to_png(response.content)
    except Exception as exc:  # noqa: BLE001 - a logo is never worth failing a send
        print(f"Could not inline logo {url}: {exc}", flush=True)
        return None


def _to_png(data: bytes) -> bytes | None:
    from PIL import Image

    with Image.open(io.BytesIO(data)) as image:
        image.load()
        # ICO files hold several resolutions; Pillow opens the largest.
        converted = image.convert("RGBA")
    converted.thumbnail((LOGO_PX, LOGO_PX))
    buffer = io.BytesIO()
    converted.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
