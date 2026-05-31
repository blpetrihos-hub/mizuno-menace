"""Rendering results to the console and to files."""

from __future__ import annotations

import base64
import csv
import html
import json
import webbrowser
from pathlib import Path

from rich.console import Console
from rich.style import Style
from rich.table import Table
from rich.text import Text

from .models import ItemResult, Listing
from .paths import asset_path

_CSS_COLOR_MAP: dict[str, str] = {
    "black": "#b0b0b0",
    "white": "#e8e8e8",
    "snow white": "#e8e8e8",
    "red": "#f48771",
    "bordeaux": "#c586c0",
    "burgundy": "#c586c0",
    "blue": "#569cd6",
    "light blue": "#6cb6ff",
    "navy": "#6cb6ff",
    "navy blue": "#6cb6ff",
    "royal": "#6796e6",
    "royal blue": "#6796e6",
    "princess blue": "#6796e6",
    "baritone blue": "#6cb6ff",
    "blue granite": "#4ec9b0",
    "maui blue": "#4ec9b0",
    "aquifer": "#4ec9b0",
    "green": "#89d185",
    "grey": "#9da5b4",
    "gray": "#9da5b4",
    "mercury": "#a8a8a8",
    "odyssey gray": "#9da5b4",
    "blacksand": "#b0b0b0",
    "metallicgray": "#9da5b4",
    "metallic gray": "#9da5b4",
    "yellow": "#dcdcaa",
    "fluorescent yellow": "#dcdcaa",
    "fluorescent orange": "#f48771",
    "orange": "#f48771",
    "tangelo": "#f48771",
    "purple": "#c586c0",
    "purple haze": "#c586c0",
    "pink": "#f0a0c0",
    "pink fluo": "#f0a0c0",
    "fluo": "#dcdcaa",
    "silver": "#c0c0c0",
    "copper": "#d4876a",
    "brown": "#c4a882",
    "lava smoke": "#9da5b4",
    "wild wind": "#6cb6ff",
    "neon yellow": "#dcdcaa",
    "neon": "#dcdcaa",
    "dress blues": "#6cb6ff",
}


def _rich_color_map() -> dict[str, str]:
    return {
        "black": "grey70",
        "white": "white",
        "snow white": "white",
        "red": "red1",
        "bordeaux": "magenta",
        "burgundy": "magenta",
        "blue": "bright_blue",
        "light blue": "bright_blue",
        "navy": "blue",
        "navy blue": "blue",
        "royal": "bright_blue",
        "royal blue": "bright_blue",
        "princess blue": "bright_blue",
        "baritone blue": "blue",
        "blue granite": "cyan",
        "maui blue": "cyan",
        "aquifer": "cyan",
        "green": "green",
        "grey": "bright_black",
        "gray": "bright_black",
        "mercury": "bright_black",
        "odyssey gray": "bright_black",
        "blacksand": "grey70",
        "metallicgray": "bright_black",
        "metallic gray": "bright_black",
        "yellow": "yellow",
        "fluorescent yellow": "yellow",
        "fluorescent orange": "bright_red",
        "orange": "bright_red",
        "tangelo": "bright_red",
        "purple": "magenta",
        "purple haze": "magenta",
        "pink": "bright_magenta",
        "pink fluo": "bright_magenta",
        "fluo": "yellow",
        "silver": "grey70",
        "copper": "bright_red",
        "brown": "yellow",
        "lava smoke": "bright_black",
        "wild wind": "bright_blue",
        "neon yellow": "yellow",
        "neon": "yellow",
        "dress blues": "blue",
    }


def _money(value: float | None, currency: str) -> str:
    if value is None:
        return "-"
    sym = {"USD": "$", "GBP": "\u00a3", "EUR": "\u20ac"}.get(currency, "")
    return f"{sym}{value:,.2f}" if sym else f"{value:,.2f} {currency}".strip()


def _pct(value: float | None) -> str:
    if value is None:
        return "-"
    tone = "green" if value > 0 else "red"
    return f"[{tone}]{value:+.1f}%[/{tone}]"


def _match_color_name(color: str, mapping: dict[str, str], default: str) -> str:
    if not color:
        return default
    key = color.strip().lower()
    if key in mapping:
        return mapping[key]
    # Longest phrase match (e.g. "fluorescent yellow" before "yellow").
    for phrase in sorted(mapping, key=len, reverse=True):
        if phrase in key:
            return mapping[phrase]
    for part in [p.strip() for p in key.replace("/", " ").split() if p.strip()]:
        if part in mapping:
            return mapping[part]
    return default


def _rich_color(color: str) -> str:
    return _match_color_name(color, _rich_color_map(), "bright_blue")


def _css_color(color: str) -> str:
    return _match_color_name(color, _CSS_COLOR_MAP, "#569cd6")


def _sorted_listings(listings: list[Listing]) -> list[Listing]:
    """Unique listings sorted cheapest-first; dedupe by URL, else color."""
    seen: set[str] = set()
    unique: list[Listing] = []
    for lst in sorted(listings, key=lambda x: x.total):
        key = (lst.url or lst.color or lst.title).lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(lst)
    return unique


def _deal_listings(listings: list[Listing]) -> list[Listing]:
    """All color variants for display (product row is already a qualifying deal)."""
    return _sorted_listings(listings)


def _group_by_price(listings: list[Listing]) -> list[tuple[float, list[Listing]]]:
    """Group color variants that share the same total price."""
    buckets: dict[float, list[Listing]] = {}
    for lst in listings:
        buckets.setdefault(lst.total, []).append(lst)
    return sorted(buckets.items(), key=lambda kv: kv[0])


def _color_links_text(listings: list[Listing]) -> Text | str:
    """Clickable color links; one price label per price tier; all colors shown."""
    items = _deal_listings(listings)
    if not items:
        return "[dim]none[/dim]"
    cell = Text()
    for tier_i, (price, group) in enumerate(_group_by_price(items)):
        if tier_i:
            cell.append("   |   ", style="dim")
        for j, lst in enumerate(group):
            if j:
                cell.append(" | ", style="dim")
            label = lst.color or "View"
            if lst.url:
                style = Style(
                    link=lst.url,
                    color=_rich_color(lst.color),
                    bold=True,
                    underline=True,
                )
                cell.append(label, style=style)
            else:
                cell.append(label, style=Style(color=_rich_color(lst.color)))
        cell.append(f" {_money(price, group[0].currency)}", style="dim")
    return cell


def _html_color_links(listings: list[Listing]) -> str:
    items = _deal_listings(listings)
    if not items:
        return '<span class="muted">none</span>'
    tiers: list[str] = []
    for price, group in _group_by_price(items):
        parts: list[str] = []
        for lst in group:
            label = html.escape(lst.color or "View")
            if lst.url:
                css = _css_color(lst.color)
                parts.append(
                    f'<a href="{html.escape(lst.url)}" target="_blank" '
                    f'rel="noopener noreferrer" style="color:{css};font-weight:600">'
                    f"{label}</a>"
                )
            else:
                parts.append(f'<span style="color:{_css_color(lst.color)}">{label}</span>')
        price_label = html.escape(_money(price, group[0].currency))
        tiers.append(" | ".join(parts) + f" <span class='muted'>{price_label}</span>")
    return " &nbsp;|&nbsp; ".join(tiers)


def _group_by_product(listings: list[Listing]) -> list[tuple[str, list[Listing]]]:
    """Group discounted listings by product; sort groups by best discount."""
    groups: dict[str, list[Listing]] = {}
    for lst in listings:
        key = lst.product_name or lst.title
        groups.setdefault(key, []).append(lst)
    ranked = sorted(
        groups.items(),
        key=lambda kv: max(l.discount_pct or 0 for l in kv[1]),
        reverse=True,
    )
    return ranked


def _all_discounted(results: list[ItemResult]) -> list[Listing]:
    listings: list[Listing] = []
    for r in results:
        listings.extend(lst for lst in r.listings if lst.discount_pct is not None)
    listings.sort(
        key=lambda lst: (
            0 if (lst.discount_pct or 0) > 0 else 1,
            -(lst.discount_pct or 0),
        )
    )
    return listings


def _top_deal_groups(results: list[ItemResult], top: int = 15) -> list[tuple[str, list[Listing]]]:
    """One row per product, ranked by best discount (colors are not separate deals)."""
    ranked: list[tuple[str, list[Listing], float]] = []
    for r in results:
        best = r.best_discount
        if not best or (best.discount_pct or 0) <= 0:
            continue
        below = [l for l in r.listings if (l.discount_pct or 0) > 0]
        ranked.append((r.product_name or r.query, below, best.discount_pct or 0))
    ranked.sort(key=lambda item: -item[2])
    return [(name, grp) for name, grp, _ in ranked[:top]]


def print_best_discounts(results: list[ItemResult], console: Console, top: int = 15) -> list[Listing]:
    groups = _top_deal_groups(results, top=top)
    if not groups:
        console.print(
            "[yellow]No deals below MSRP[/yellow] — verify MSRP values or add eBay keys."
        )
        return []

    shown: list[Listing] = [lst for _, grp in groups for lst in grp]

    table = Table(
        title=f"Top {top} deals by deal index",
        show_lines=True,
    )
    table.add_column("Product", style="bold", max_width=24)
    table.add_column("Disc.", justify="right", style="bold green")
    table.add_column("Save", justify="right", style="green")
    table.add_column("From", justify="right")
    table.add_column("Source", no_wrap=True, min_width=11)
    table.add_column("Ref", justify="right")
    table.add_column("Colors  (click to open)", overflow="fold")

    for name, grp in groups:
        best = max(grp, key=lambda l: l.discount_pct or 0)
        cheapest = min(grp, key=lambda l: l.total)
        cur = best.currency
        ref = (
            f"{_money(best.reference_price, cur)}\n"
            f"[dim]{best.reference_label}[/dim]"
        )
        sources = ", ".join(sorted({l.source for l in grp}))
        table.add_row(
            name,
            _pct(best.discount_pct),
            _money(best.savings, cur),
            _money(cheapest.total, cur),
            sources,
            ref,
            _color_links_text(grp),
        )
    console.print(table)
    return shown


def prompt_open_links(listings: list[Listing], console: Console) -> None:
    """Let the user type a listing # to open that product in the default browser."""
    if not listings:
        return
    console.print(
        "\n[dim]Ctrl+click a color link above, or type a #[/dim] "
        f"[bold](1-{len(listings)})[/bold] [dim]to open in browser (Enter to skip):[/dim] ",
        end="",
    )
    try:
        choice = input().strip()
    except (EOFError, KeyboardInterrupt):
        console.print()
        return
    if not choice:
        return
    if not choice.isdigit():
        console.print("[yellow]Not a number - skipped.[/yellow]")
        return
    idx = int(choice)
    if idx < 1 or idx > len(listings):
        console.print(f"[yellow]Pick 1-{len(listings)}.[/yellow]")
        return
    lst = listings[idx - 1]
    if not lst.url:
        console.print("[yellow]That listing has no URL.[/yellow]")
        return
    webbrowser.open(lst.url)
    label = lst.color or lst.title
    console.print(f"[green]Opened in browser:[/green] {label}")


# ---------------------------------------------------------------------------
# File export
# ---------------------------------------------------------------------------

def _logo_data_uri() -> str:
    """Embedded logo for a self-contained HTML report."""
    return _asset_data_uri("logo.png")


def _asset_data_uri(name: str) -> str:
    path = asset_path(name)
    if not path.exists():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _vertical_logo_data_uri() -> str:
    return _asset_data_uri("logo-vertical.png")


def _logo_pixel_size() -> tuple[int, int]:
    """Read PNG dimensions without loading the full image."""
    logo = asset_path("logo.png")
    if not logo.exists():
        return 0, 0
    with logo.open("rb") as f:
        header = f.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        return 0, 0
    width, height = int.from_bytes(header[16:20], "big"), int.from_bytes(header[20:24], "big")
    return width, height


def dark_theme_css() -> str:
    return """
    :root {
      --bg: #1e1e1e;
      --fg: #cccccc;
      --muted: #858585;
      --border: #3c3c3c;
      --header: #252526;
      --disc: #89d185;
    }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
      margin: 0;
      padding: 2rem 1.5rem 2.5rem;
      background: var(--bg);
      color: var(--fg);
    }
    .page {
      max-width: 1440px;
      margin: 0 auto;
    }
    .table-stage {
      display: flex;
      align-items: stretch;
      justify-content: center;
      gap: clamp(0.75rem, 2.5vw, 1.75rem);
      margin-top: 0.25rem;
    }
    .table-wrap {
      flex: 1 1 auto;
      min-width: 0;
      overflow-x: auto;
    }
    .side-brand {
      flex: 0 0 clamp(120px, 14vw, 200px);
      display: flex;
      align-items: center;
      justify-content: center;
      align-self: stretch;
      position: relative;
      pointer-events: none;
      user-select: none;
      background: transparent;
    }
    .side-brand img {
      display: block;
      width: 100%;
      height: auto;
      max-height: min(92vh, 980px);
      object-fit: contain;
      object-position: center;
      image-rendering: high-quality;
      image-rendering: -webkit-optimize-contrast;
    }
    @media (max-width: 1040px) {
      .side-brand { display: none; }
    }
    .brand {
      display: flex;
      justify-content: center;
      align-items: center;
      margin: 0 0 2rem;
      padding: 0.5rem 0 1.25rem;
    }
    .brand img {
      display: block;
      width: min(480px, 92vw);
      height: auto;
      max-height: 72px;
      object-fit: contain;
      image-rendering: high-quality;
      image-rendering: -webkit-optimize-contrast;
    }
    .brand-text {
      font-size: 1.75rem;
      font-weight: 600;
      letter-spacing: -0.02em;
      text-align: center;
    }
    """


def brand_header_html() -> str:
    logo_uri = _logo_data_uri()
    if logo_uri:
        w, h = _logo_pixel_size()
        dims = f' width="{w}" height="{h}"' if w and h else ""
        return (
            f'<header class="brand"><img src="{logo_uri}" alt="Mizuno Menace"'
            f'{dims} decoding="async"></header>'
        )
    return '<header class="brand"><span class="brand-text">Mizuno Menace</span></header>'


def _vertical_brand_aside() -> str:
    uri = _vertical_logo_data_uri()
    if not uri:
        return ""
    return (
        f'<aside class="side-brand">'
        f'<img src="{uri}" alt="" aria-hidden="true" decoding="async">'
        f"</aside>"
    )


def write_html(results: list[ItemResult], path: Path, top: int = 15) -> None:
    """Write a self-contained HTML report with clickable color-named links."""
    path.parent.mkdir(parents=True, exist_ok=True)
    groups = _top_deal_groups(results, top=top)

    def esc(value: object) -> str:
        return html.escape("" if value is None else str(value))

    def money(value: float | None, currency: str) -> str:
        if value is None:
            return "-"
        sym = {"USD": "$", "GBP": "\u00a3", "EUR": "\u20ac"}.get(currency, "")
        body = f"{value:,.2f}"
        return f"{sym}{body}" if sym else f"{body} {currency}".strip()

    top_rows = []
    for name, grp in groups:
        best = max(grp, key=lambda l: l.discount_pct or 0)
        cheapest = min(grp, key=lambda l: l.total)
        cur = best.currency
        sources = ", ".join(sorted({l.source for l in grp}))
        top_rows.append(
            "<tr>"
            f"<td>{esc(name)}</td>"
            f"<td class='disc'>{best.discount_pct:+.1f}%</td>"
            f"<td>{money(best.savings, cur)}</td>"
            f"<td>{money(cheapest.total, cur)}</td>"
            f"<td>{esc(sources)}</td>"
            f"<td>{money(best.reference_price, cur)}<br>"
            f"<span class='muted'>{esc(best.reference_label)}</span></td>"
            f"<td class='colors'>{_html_color_links(grp)}</td>"
            "</tr>"
        )

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mizuno Menace</title>
  <style>
{dark_theme_css()}
    h2 {{
      font-size: 1.05rem;
      font-weight: 600;
      color: var(--fg);
      margin: 0 0 1rem;
      text-align: center;
    }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid var(--border); padding: 0.6rem 0.7rem; vertical-align: top; }}
    th {{ background: var(--header); text-align: left; font-weight: 600; }}
    tr:nth-child(even) td {{ background: #232323; }}
    td.colors {{ line-height: 1.65; }}
    a {{ text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .disc {{ color: var(--disc); font-weight: 600; }}
    .muted {{ color: var(--muted); font-size: 0.85rem; }}
  </style>
</head>
<body>
  <div class="page">
  {brand_header_html()}

  <h2>Top {top} deals by deal index</h2>
  <div class="table-stage">
    {_vertical_brand_aside()}
    <div class="table-wrap">
  <table>
    <thead>
      <tr>
        <th>Product</th><th>Discount</th><th>Save</th><th>From</th>
        <th>Source</th><th>Ref price</th><th>Colors (click to open)</th>
      </tr>
    </thead>
    <tbody>
      {''.join(top_rows) if top_rows else f'<tr><td colspan="7" class="muted">No deals below MSRP found.</td></tr>'}
    </tbody>
  </table>
    </div>
    {_vertical_brand_aside()}
  </div>
  </div>
</body>
</html>
"""
    path.write_text(doc, encoding="utf-8")


def open_report_in_browser(path: Path, console: Console | None = None) -> None:
    """Open an HTML report (or any file) in the default web browser."""
    uri = path.resolve().as_uri()
    webbrowser.open(uri)
    if console:
        console.print(f"Report opened: {path}")


def _rows(results: list[ItemResult]) -> list[dict]:
    rows: list[dict] = []
    for r in results:
        cheapest = r.cheapest
        best = r.best_discount
        colors = ", ".join(
            f"{lst.color or '?'} ({_money(lst.total, lst.currency)})"
            for lst in _sorted_listings(r.listings)
        )
        rows.append(
            {
                "product": r.product_name or r.query,
                "query": r.query,
                "found": r.count,
                "currency": r.currency,
                "cheapest_total": cheapest.total if cheapest else None,
                "cheapest_color": cheapest.color if cheapest else "",
                "all_colors": colors,
                "mizuno_msrp": cheapest.msrp if cheapest else None,
                "best_deal_index": best.deal_index if best else None,
                "best_discount_pct": best.discount_pct if best else None,
                "best_savings": best.savings if best else None,
                "best_color": best.color if best else "",
                "best_title": best.title if best else "",
                "best_url": best.url if best else "",
                "error": r.error or "",
            }
        )
    return rows


def write_csv(results: list[ItemResult], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = _rows(results)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["product"])
        writer.writeheader()
        writer.writerows(rows)


def write_json(results: list[ItemResult], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = []
    for r in results:
        payload.append(
            {
                "product": r.product_name or r.query,
                "query": r.query,
                "error": r.error,
                "note": r.note,
                "listings": [
                    {
                        "title": lst.title,
                        "price": lst.price,
                        "shipping": lst.shipping,
                        "total": lst.total,
                        "currency": lst.currency,
                        "color": lst.color,
                        "style_id": lst.style_id,
                        "condition": lst.condition,
                        "buying_option": lst.buying_option,
                        "msrp": lst.msrp,
                        "ebay_list_price": lst.original_price,
                        "reference_price": lst.reference_price,
                        "reference_label": lst.reference_label,
                        "reference_source": lst.reference_source,
                        "reference_as_of": lst.reference_as_of,
                        "deal_index": lst.deal_index,
                        "estimated": lst.estimated,
                        "discount_pct": lst.discount_pct,
                        "savings": lst.savings,
                        "url": lst.url,
                    }
                    for lst in r.listings
                ],
            }
        )
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
