"""Builds the plain-text and HTML email bodies from scrape results.

The HTML email uses only inline styles and table-based layout instead of a
<style> block with CSS classes / flexbox. Many mail clients (Gmail among
them, depending on context, and virtually all versions of Outlook) strip or
ignore <head> <style> blocks and have poor/no flexbox support, which made
the previous class-based markup render "bare" (no colors, no card
background, and - worst of all - no size limit on logo images, so a
restaurant photo used as a logo showed up full-size in the middle of the
email). Inline styles and tables are the only layout technique that mail
clients consistently honor.
"""
from __future__ import annotations

from html import escape

from scrapers.menubot import Menu

FONT = "Arial, Helvetica, sans-serif"
ACCENT = "#b5321a"


def render_text(results: list[dict]) -> str:
    lines = []
    for r in results:
        lines.append(f"== {r['name']} ==")
        if r["error"]:
            lines.append(f"  (chyba: {r['error']})")
            lines.append("")
            continue

        menu: Menu = r["menu"]
        if menu.heading:
            lines.append(menu.heading)
        if menu.items:
            for item in menu.items:
                prefix = f"[{item.category}] " if item.category else ""
                price = f" – {item.price}" if item.price else ""
                lines.append(f"  {prefix}{item.name}{price}")
                if item.description:
                    lines.append(f"      {item.description}")
        else:
            lines.append(f"  (nerozpoznáno, surový text): {menu.raw_text[:400]}")
        lines.append("")
    return "\n".join(lines)


def _header_html(name: str, url: str, logo_url: str) -> str:
    name_html = f'<a href="{escape(url)}" style="color:{ACCENT};text-decoration:none;">{name}</a>' if url else name
    logo_cell = ""
    if logo_url:
        logo_cell = (
            '<td style="padding-right:12px;width:44px;">'
            f'<img src="{escape(logo_url)}" alt="" width="44" height="44" '
            'style="display:block;height:44px;width:44px;max-width:44px;'
            'object-fit:cover;border-radius:6px;" onerror="this.style.display=\'none\'">'
            "</td>"
        )
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 12px;">'
        f'<tr>{logo_cell}<td valign="middle"><h2 style="margin:0;font-size:18px;'
        f'font-family:{FONT};">{name_html}</h2></td></tr></table>'
    )


def _item_html(item) -> str:
    allergens_html = (
        f' <span style="color:#999;font-size:11px;font-weight:normal;">{escape(item.allergens)}</span>'
        if item.allergens
        else ""
    )
    price_html = escape(item.price) if item.price else ""
    desc_html = (
        f'<div style="color:#555;font-size:13px;margin-top:2px;font-family:{FONT};">{escape(item.description)}</div>'
        if item.description
        else ""
    )
    desc_row = f'<tr><td colspan="2">{desc_html}</td></tr>' if desc_html else ""
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        'style="padding:8px 0;border-bottom:1px solid #eee;">'
        "<tr>"
        f'<td style="font-weight:600;font-family:{FONT};">{escape(item.name)}{allergens_html}</td>'
        f'<td align="right" valign="top" style="white-space:nowrap;color:{ACCENT};font-weight:600;'
        f'font-family:{FONT};padding-left:8px;">{price_html}</td>'
        "</tr>"
        f"{desc_row}"
        "</table>"
    )


def render_html(results: list[dict]) -> str:
    sections = []
    for r in results:
        name = escape(r["name"])
        url = r.get("url") or ""
        logo_url = r.get("logo_url") or ""
        menu_image_url = r.get("menu_image_url") or ""

        header = _header_html(name, url, logo_url)

        if r["error"]:
            body = (
                f'<div style="color:{ACCENT};font-family:{FONT};">'
                f'Nepodařilo se načíst menu ({escape(r["error"])}).</div>'
            )
            sections.append(_card_html(header, body))
            continue

        menu: Menu = r["menu"]
        body_parts = []
        if menu.heading:
            body_parts.append(
                f'<div style="color:#666;font-size:14px;margin:0 0 12px;font-family:{FONT};">{escape(menu.heading)}</div>'
            )

        if menu.items:
            current_category = object()
            for item in menu.items:
                if item.category and item.category != current_category:
                    body_parts.append(
                        '<div style="font-size:13px;text-transform:uppercase;letter-spacing:0.04em;'
                        f'color:#888;font-weight:bold;margin:16px 0 6px;font-family:{FONT};">'
                        f"{escape(item.category)}</div>"
                    )
                    current_category = item.category
                body_parts.append(_item_html(item))
        else:
            body_parts.append(
                f'<div style="color:#555;font-size:13px;white-space:pre-wrap;font-family:{FONT};">'
                f"{escape(menu.raw_text[:500])}</div>"
            )

        if menu_image_url:
            body_parts.append(
                f'<img src="{escape(menu_image_url)}" alt="Foto denního menu" width="600" '
                'style="display:block;width:100%;max-width:600px;height:auto;border-radius:8px;'
                'margin-top:8px;" onerror="this.style.display=\'none\'">'
            )

        sections.append(_card_html(header, "".join(body_parts)))

    return f"""<!DOCTYPE html>
<html lang="cs">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#f4f4f4;font-family:{FONT};color:#222;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f4f4f4;">
<tr><td align="center">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" border="0" style="max-width:640px;width:100%;">
<tr><td style="padding:24px 16px;">
<h1 style="font-size:20px;color:#444;font-family:{FONT};margin:0 0 16px;">🍽️ Dnešní obědové menu</h1>
{"".join(sections)}
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""


def _card_html(header: str, body: str) -> str:
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        'style="background:#ffffff;border-radius:10px;margin-bottom:20px;">'
        f'<tr><td style="padding:20px 24px;">{header}{body}</td></tr>'
        "</table>"
    )
