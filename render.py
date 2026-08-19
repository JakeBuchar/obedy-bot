"""Builds the plain-text and HTML email bodies from scrape results."""
from __future__ import annotations

from html import escape

from scrapers.menubot import Menu


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


def render_html(results: list[dict]) -> str:
    sections = []
    for r in results:
        name = escape(r["name"])
        url = r.get("url") or ""
        logo_url = r.get("logo_url") or ""
        menu_image_url = r.get("menu_image_url") or ""

        name_html = f'<a href="{escape(url)}">{name}</a>' if url else name
        logo_html = (
            f'<img class="logo" src="{escape(logo_url)}" alt="" onerror="this.remove()">'
            if logo_url
            else ""
        )
        header = f'<div class="restaurant-header">{logo_html}<h2>{name_html}</h2></div>'

        if r["error"]:
            sections.append(
                f'<div class="restaurant">{header}'
                f'<p class="error">Nepodařilo se načíst menu ({escape(r["error"])}).</p></div>'
            )
            continue

        menu: Menu = r["menu"]
        body_parts = []
        if menu.heading:
            body_parts.append(f'<p class="heading">{escape(menu.heading)}</p>')

        if menu.items:
            current_category = object()
            for item in menu.items:
                if item.category and item.category != current_category:
                    body_parts.append(f'<h3 class="category">{escape(item.category)}</h3>')
                    current_category = item.category

                price_html = f'<span class="price">{escape(item.price)}</span>' if item.price else ""
                allergens_html = (
                    f' <span class="allergens">{escape(item.allergens)}</span>' if item.allergens else ""
                )
                desc_html = f'<div class="desc">{escape(item.description)}</div>' if item.description else ""

                body_parts.append(
                    '<div class="item">'
                    f'<div class="item-row"><span class="name">{escape(item.name)}</span>{allergens_html} {price_html}</div>'
                    f"{desc_html}"
                    "</div>"
                )
        else:
            body_parts.append(f'<p class="fallback">{escape(menu.raw_text[:500])}</p>')

        if menu_image_url:
            body_parts.append(
                f'<img class="menu-photo" src="{escape(menu_image_url)}" alt="Foto denního menu" '
                'onerror="this.remove()">'
            )

        sections.append(f'<div class="restaurant">{header}{"".join(body_parts)}</div>')

    return f"""<!DOCTYPE html>
<html lang="cs">
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; color: #222; margin: 0; padding: 0; background: #f4f4f4; }}
  .wrapper {{ max-width: 640px; margin: 0 auto; padding: 24px 16px; }}
  .restaurant {{ background: #fff; border-radius: 10px; padding: 20px 24px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
  h1 {{ font-size: 20px; color: #444; }}
  .restaurant-header {{ display: flex; align-items: center; gap: 12px; margin: 0 0 12px; }}
  .logo {{ height: 44px; max-width: 120px; width: auto; object-fit: contain; border-radius: 6px; }}
  h2 {{ margin: 0; font-size: 18px; }}
  h2 a {{ color: #b5321a; text-decoration: none; }}
  .category {{ font-size: 13px; text-transform: uppercase; letter-spacing: 0.04em; color: #888; margin: 16px 0 6px; }}
  .heading {{ color: #666; font-size: 14px; margin: 0 0 12px; }}
  .item {{ padding: 8px 0; border-bottom: 1px solid #eee; }}
  .item:last-child {{ border-bottom: none; }}
  .item-row {{ display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }}
  .name {{ font-weight: 600; }}
  .price {{ white-space: nowrap; color: #b5321a; font-weight: 600; }}
  .allergens {{ color: #999; font-size: 11px; }}
  .desc {{ color: #555; font-size: 13px; margin-top: 2px; }}
  .error {{ color: #b5321a; }}
  .fallback {{ color: #555; font-size: 13px; white-space: pre-wrap; }}
  .menu-photo {{ display: block; max-width: 100%; height: auto; border-radius: 8px; margin-top: 8px; }}
</style>
</head>
<body>
<div class="wrapper">
<h1>🍽️ Dnešní obědové menu</h1>
{"".join(sections)}
</div>
</body>
</html>"""
