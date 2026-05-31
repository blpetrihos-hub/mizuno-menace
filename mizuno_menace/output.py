"""Rendering results to the console and to files."""

from __future__ import annotations

import csv
import html
import json
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.style import Style
from rich.table import Table
from rich.text import Text

from .models import ItemResult, Listing

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

# CSS hex colors for the HTML report.
_CSS_COLOR_MAP: dict[str, str] = {
    "black": "#1a1a1a",
    "white": "#666666",
    "red": "#c5221f",
    "blue": "#1a73e8",
    "navy": "#1a3a6e",
    "navy blue": "#1a3a6e",
    "royal": "#4169e1",
    "royal blue": "#4169e1",
    "green": "#137333",
    "grey": "#5f6368",
    "gray": "#5f6368",
    "mercury": "#6b6b6b",
    "baritone blue": "#2c5282",
    "blue granite": "#4a7c9b",
    "maui blue": "#00838f",
    "aquifer": "#00838f",
    "princess blue": "#1565c0",
    "odyssey gray": "#757575",
    "blacksand": "#3d3d3d",
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
        return "#0b57d0"
    key = color.strip().lower()
    if key in _CSS_COLOR_MAP:
        return _CSS_COLOR_MAP[key]
    primary = key.split("/")[0].strip()
    return _CSS_COLOR_MAP.get(primary, "#0b57d0")


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


def _color_links_text(listings: list[Listing], *, max_links: int = MAX_COLOR_LINKS) -> Text | str:
    """Clickable links labeled by color name, styled in that color."""
    items = _deal_listings(listings)
    total = len(items)
    items = items[:max_links]
    if not items:
        return "[dim]none[/dim]"
    cell = Text()
    for i, lst in enumerate(items):
        if i:
            cell.append("   ")
        label = lst.color or "View"
        if lst.url:
            style = Style(
                link=lst.url,
                color=_rich_color(lst.color),
                bold=True,
                underline=True,
            )
            cell.append(label, style=style)
            cell.append(f" {_money(lst.total, lst.currency)}", style="dim")
        else:
            cell.append(label)
    if total > max_links:
        cell.append(f"   +{total - max_links} more", style="dim")
    return cell


def _html_color_links(listings: list[Listing], *, max_links: int = MAX_COLOR_LINKS) -> str:
    items = _deal_listings(listings)
    total = len(items)
    items = items[:max_links]
    if not items:
        return '<span class="muted">none</span>'
    parts: list[str] = []
    for lst in items:
        label = html.escape(lst.color or "View")
        price = html.escape(_money(lst.total, lst.currency))
        if lst.url:
            css = _css_color(lst.color)
            parts.append(
                f'<a href="{html.escape(lst.url)}" target="_blank" '
                f'rel="noopener noreferrer" style="color:{css};font-weight:600">'
                f"{label}</a> <span class='muted'>{price}</span>"
            )
        else:
            parts.append(f"{label} <span class='muted'>{price}</span>")
    if total > max_links:
        parts.append(f"<span class='muted'>+{total - max_links} more</span>")
    return " &nbsp;|&nbsp; ".join(parts)


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
    # Real deals first, then above-MSRP listings.
    listings.sort(
        key=lambda lst: (
            0 if (lst.discount_pct or 0) > 0 else 1,
            -(lst.discount_pct or 0),
        )
    )
    return listings


def print_product_summary(results: list[ItemResult], console: Console) -> None:
    table = Table(title="Mizuno Menace - per-product summary", show_lines=True)
    table.add_column("Product", style="bold", max_width=26)
    table.add_column("Found", justify="right")
    table.add_column("Cheapest\n(incl. ship)", justify="right", style="green")
    table.add_column("MSRP", justify="right")
    table.add_column("Best disc.", justify="right")
    table.add_column("Save", justify="right", style="green")
    table.add_column("Colors  (click to open)", overflow="fold")

    for r in results:
        if r.error:
            table.add_row(
                r.product_name or r.query, "0", "-", "-", "-", "-", "[red]error[/red]"
            )
            continue
        if r.count == 0:
            table.add_row(
                r.product_name or r.query, "0", "-", "-", "-", "-", "[dim]none[/dim]"
            )
            continue
        cur = r.currency
        cheapest = r.cheapest
        best = r.best_discount
        msrp = cheapest.msrp if cheapest else None
        table.add_row(
            r.product_name or r.query,
            str(r.count),
            _money(cheapest.total if cheapest else None, cur),
            _money(msrp, cur),
            _pct(best.discount_pct if best else None),
            _money(best.savings if best else None, cur),
            _color_links_text(r.listings),
        )
    console.print(table)


def print_best_discounts(results: list[ItemResult], console: Console, top: int = 15) -> list[Listing]:
    listings = _all_discounted(results)
    if not listings:
        console.print(
            "[yellow]No discounts to rank[/yellow] - no listings had a Mizuno MSRP "
            "or an eBay list price to compare against."
        )
        return []

    groups = _group_by_product(listings)[:top]
    # Product deals table: only groups with at least one below-MSRP listing.
    groups = [(n, g) for n, g in groups if any((l.discount_pct or 0) > 0 for l in g)][:top]
    shown: list[Listing] = [lst for _, grp in groups for lst in grp]

    table = Table(
        title=f"Top {len(groups)} product deals vs Mizuno price (eBay = NWT/Buy It Now)",
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


def print_zero_result_notes(results: list[ItemResult], console: Console) -> None:
    """Explain products with no in-stock listings (common for discontinued shoes)."""
    missing = [r for r in results if r.count == 0 and not r.error]
    above_msrp = [
        r for r in results
        if r.cheapest and r.cheapest.discount_pct is not None and r.cheapest.discount_pct <= 0
    ]
    if not missing and not above_msrp:
        return
    if missing:
        console.print("\n[dim]No in-stock listings found for:[/dim]")
        for r in missing:
            console.print(f"  [dim]- {r.product_name or r.query}[/dim]")
        console.print(
            "[dim]  (Often out of stock on foot-store, or no eBay NWT listings yet.)[/dim]"
        )
    if above_msrp:
        console.print("\n[yellow]Cheapest listing is at/above MSRP for:[/yellow]")
        for r in above_msrp:
            c = r.cheapest
            console.print(
                f"  [yellow]- {r.product_name or r.query}[/yellow] "
                f"({_money(c.total, r.currency)} vs MSRP {_money(c.msrp, r.currency)})"
            )


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

def write_html(results: list[ItemResult], path: Path, top: int = 15) -> None:
    """Write a self-contained HTML report with clickable color-named links."""
    path.parent.mkdir(parents=True, exist_ok=True)
    ranked = _all_discounted(results)
    groups = _group_by_product(ranked)
    groups = [(n, g) for n, g in groups if any((l.discount_pct or 0) > 0 for l in g)][:top]
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

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

    product_rows = []
    for r in results:
        cheapest = r.cheapest
        best = r.best_discount
        if r.error:
            product_rows.append(
                f"<tr><td>{esc(r.product_name or r.query)}</td>"
                "<td>0</td><td>-</td><td>-</td><td>-</td><td>-</td>"
                f"<td class='err'>{esc(r.error)}</td></tr>"
            )
            continue
        if r.count == 0 or not cheapest:
            product_rows.append(
                f"<tr><td>{esc(r.product_name or r.query)}</td>"
                "<td>0</td><td>-</td><td>-</td><td>-</td><td>-</td>"
                "<td class='muted'>none</td></tr>"
            )
            continue
        cur = r.currency
        disc = f"{best.discount_pct:+.1f}%" if best and best.discount_pct is not None else "-"
        product_rows.append(
            "<tr>"
            f"<td>{esc(r.product_name or r.query)}</td>"
            f"<td>{r.count}</td>"
            f"<td>{money(cheapest.total, cur)}</td>"
            f"<td>{money(cheapest.msrp, cur)}</td>"
            f"<td>{disc}</td>"
            f"<td>{money(best.savings, cur) if best else '-'}</td>"
            f"<td>{_html_color_links(r.listings)}</td>"
            "</tr>"
        )

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mizuno Menace - Deals Report</title>
  <style>
    body {{ font-family: Segoe UI, system-ui, sans-serif; margin: 2rem; color: #111; }}
    h1 {{ margin-bottom: 0.2rem; }}
    .meta {{ color: #666; margin-bottom: 1.5rem; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 2rem; }}
    th, td {{ border: 1px solid #ddd; padding: 0.55rem 0.65rem; vertical-align: top; }}
    th {{ background: #f5f5f5; text-align: left; }}
    a {{ text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .disc {{ color: #137333; font-weight: 600; }}
    .muted {{ color: #666; font-size: 0.85rem; }}
    .err {{ color: #b3261e; }}
  </style>
</head>
<body>
  <h1>Mizuno Menace</h1>
  <p class="meta">Report date: {esc(generated)}</p>

  <h2>Top {len(groups)} product deals</h2>
  <table>
    <thead>
      <tr>
        <th>Product</th><th>Discount</th><th>Save</th><th>From</th>
        <th>Source</th><th>Ref price</th><th>Colors (click to open)</th>
      </tr>
    </thead>
    <tbody>
      {''.join(top_rows) if top_rows else '<tr><td colspan="7">No discounts found.</td></tr>'}
    </tbody>
  </table>

  <h2>Per-product summary</h2>
  <table>
    <thead>
      <tr>
        <th>Product</th><th>Found</th><th>Cheapest</th><th>MSRP</th>
        <th>Best disc.</th><th>Save</th><th>Colors (click to open)</th>
      </tr>
    </thead>
    <tbody>
      {''.join(product_rows)}
    </tbody>
  </table>
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
