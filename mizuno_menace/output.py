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

# Rich terminal colors approximating product color names.
_RICH_COLOR_MAP: dict[str, str] = {
    "black": "black",
    "white": "white",
    "red": "red",
    "blue": "blue",
    "navy": "blue",
    "navy blue": "blue",
    "royal": "bright_blue",
    "royal blue": "bright_blue",
    "green": "green",
    "grey": "bright_black",
    "gray": "bright_black",
    "mercury": "bright_black",
    "baritone blue": "blue",
    "blue granite": "cyan",
    "maui blue": "cyan",
    "aquifer": "cyan",
    "princess blue": "bright_blue",
    "odyssey gray": "bright_black",
    "blacksand": "bright_black",
    "metallicgray": "bright_black",
    "metallic gray": "bright_black",
    "dress blues": "blue",
    "fluorescent yellow": "yellow",
    "tangelo": "bright_red",
    "purple haze": "magenta",
    "snow white": "white",
}

# CSS hex colors for the HTML report (product color links).
_CSS_COLOR_MAP: dict[str, str] = {
    "black": "#b0b0b0",
    "white": "#e8e8e8",
    "red": "#f48771",
    "blue": "#569cd6",
    "navy": "#6cb6ff",
    "navy blue": "#6cb6ff",
    "royal": "#6796e6",
    "royal blue": "#6796e6",
    "green": "#89d185",
    "grey": "#9da5b4",
    "gray": "#9da5b4",
    "mercury": "#a8a8a8",
    "baritone blue": "#6cb6ff",
    "blue granite": "#4ec9b0",
    "maui blue": "#4ec9b0",
    "aquifer": "#4ec9b0",
    "princess blue": "#6796e6",
    "odyssey gray": "#9da5b4",
    "blacksand": "#b0b0b0",
    "fluorescent yellow": "#dcdcaa",
    "tangelo": "#f48771",
    "purple haze": "#c586c0",
    "snow white": "#e8e8e8",
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


def _rich_color(color: str) -> str:
    if not color:
        return "bright_blue"
    key = color.strip().lower()
    if key in _RICH_COLOR_MAP:
        return _RICH_COLOR_MAP[key]
    primary = key.split("/")[0].strip()
    return _RICH_COLOR_MAP.get(primary, "bright_blue")


def _css_color(color: str) -> str:
    if not color:
        return "#569cd6"
    key = color.strip().lower()
    if key in _CSS_COLOR_MAP:
        return _CSS_COLOR_MAP[key]
    primary = key.split("/")[0].strip()
    return _CSS_COLOR_MAP.get(primary, "#569cd6")


def _sorted_listings(listings: list[Listing]) -> list[Listing]:
    """Unique listings sorted cheapest-first; dedupe same color keeping cheapest."""
    seen_colors: set[str] = set()
    unique: list[Listing] = []
    for lst in sorted(listings, key=lambda x: x.total):
        key = (lst.color or lst.url or lst.title).lower()
        if key in seen_colors:
            continue
        seen_colors.add(key)
        unique.append(lst)
    return unique


MAX_COLOR_LINKS = 8


def _deal_listings(listings: list[Listing]) -> list[Listing]:
    """Listings that are actually below MSRP; fall back to all if none qualify."""
    discounted = [l for l in listings if (l.discount_pct or 0) > 0]
    return _sorted_listings(discounted if discounted else listings)


def _group_by_price(listings: list[Listing]) -> list[tuple[float, list[Listing]]]:
    """Group color variants that share the same total price."""
    buckets: dict[float, list[Listing]] = {}
    for lst in listings:
        buckets.setdefault(lst.total, []).append(lst)
    return sorted(buckets.items(), key=lambda kv: kv[0])


def _color_links_text(listings: list[Listing], *, max_links: int = MAX_COLOR_LINKS) -> Text | str:
    """Clickable color links; one price label per price tier."""
    items = _deal_listings(listings)
    if not items:
        return "[dim]none[/dim]"
    total = len(items)
    display = items[:max_links]
    cell = Text()
    for tier_i, (price, group) in enumerate(_group_by_price(display)):
        if tier_i:
            cell.append("   |   ", style="dim")
        for j, lst in enumerate(group):
            if j:
                cell.append("  ", style="dim")
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
                cell.append(label)
        cell.append(f" {_money(price, group[0].currency)}", style="dim")
    if total > max_links:
        cell.append(f"   +{total - max_links} more", style="dim")
    return cell


def _html_color_links(listings: list[Listing], *, max_links: int = MAX_COLOR_LINKS) -> str:
    items = _deal_listings(listings)
    if not items:
        return '<span class="muted">none</span>'
    total = len(items)
    display = items[:max_links]
    tiers: list[str] = []
    for price, group in _group_by_price(display):
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
                parts.append(label)
        price_label = html.escape(_money(price, group[0].currency))
        tiers.append(" ".join(parts) + f" <span class='muted'>{price_label}</span>")
    if total > max_links:
        tiers.append(f"<span class='muted'>+{total - max_links} more</span>")
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
    ranked = _all_discounted(results)
    groups = _group_by_product(ranked)
    return [
        (n, g) for n, g in groups if any((l.discount_pct or 0) > 0 for l in g)
    ][:top]


def print_best_discounts(results: list[ItemResult], console: Console, top: int = 15) -> list[Listing]:
    groups = _top_deal_groups(results, top=top)
    if not groups:
        console.print(
            "[yellow]No deals below MSRP[/yellow] — verify MSRP values or add eBay keys."
        )
        return []

    shown: list[Listing] = [lst for _, grp in groups for lst in grp]

    table = Table(
        title=f"Top {top} product deals vs Mizuno MSRP",
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
    logo = asset_path("logo.png")
    if not logo.exists():
        return ""
    encoded = base64.b64encode(logo.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def write_html(results: list[ItemResult], path: Path, top: int = 15) -> None:
    """Write a self-contained HTML report with clickable color-named links."""
    path.parent.mkdir(parents=True, exist_ok=True)
    groups = _top_deal_groups(results, top=top)
    logo_uri = _logo_data_uri()

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
            f"<td>{_html_color_links(grp)}</td>"
            "</tr>"
        )

    header = (
        f'<header class="brand"><img src="{logo_uri}" alt="Mizuno Menace"></header>'
        if logo_uri
        else '<header class="brand"><span class="brand-text">Mizuno Menace</span></header>'
    )

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mizuno Menace</title>
  <style>
    :root {{
      --bg: #1e1e1e;
      --fg: #cccccc;
      --muted: #858585;
      --border: #3c3c3c;
      --header: #252526;
      --disc: #89d185;
    }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
      margin: 0;
      padding: 2rem 1.5rem 2.5rem;
      background: var(--bg);
      color: var(--fg);
    }}
    .page {{
      max-width: 1100px;
      margin: 0 auto;
    }}
    .brand {{
      display: flex;
      justify-content: center;
      align-items: center;
      margin: 0 0 2rem;
      padding: 0.5rem 0 1.25rem;
    }}
    .brand img {{
      display: block;
      width: min(480px, 92vw);
      height: auto;
      max-height: 72px;
      object-fit: contain;
    }}
    .brand-text {{
      font-size: 1.75rem;
      font-weight: 600;
      letter-spacing: -0.02em;
      text-align: center;
    }}
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
    a {{ text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .disc {{ color: var(--disc); font-weight: 600; }}
    .muted {{ color: var(--muted); font-size: 0.85rem; }}
  </style>
</head>
<body>
  <div class="page">
  {header}

  <h2>Top {top} product deals</h2>
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
                        "condition": lst.condition,
                        "buying_option": lst.buying_option,
                        "msrp": lst.msrp,
                        "ebay_list_price": lst.original_price,
                        "reference_price": lst.reference_price,
                        "reference_label": lst.reference_label,
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
