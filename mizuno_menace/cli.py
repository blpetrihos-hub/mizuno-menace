"""Command-line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console

from . import output
from .aggregator import Aggregator
from .config import ebay_setup_hint, load_ebay_config
from .launcher import load_last_top, prompt_top_count, save_last_top
from .fetch_budget import DEFAULT_MAX_PAGES, DEFAULT_SOURCE_LIMIT, effective_max_pages
from .paths import find_config, user_data_dir
from .products import load_products, products_from_queries
from .search_criteria import APPAREL_SIZE, SHOE_SIZE_US
from .sources import DemoSource, EbaySource, FootStoreSource


def build_sources(*, force_demo: bool, use_footstore: bool) -> list:
    if force_demo:
        return [DemoSource()]

    cfg = load_ebay_config()
    sources: list = []
    if cfg.is_configured:
        sources.append(EbaySource(cfg))
    if use_footstore:
        sources.append(FootStoreSource())
    return sources


def load_input_products(args: argparse.Namespace) -> list | None:
    if args.query:
        return products_from_queries(args.query)
    if args.products is not None:
        if args.products.exists():
            return load_products(args.products)
        return None
    if args.watchlist:
        found = find_config("products.json")
        if found:
            return load_products(found)
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="Mizuno Menace",
        description="Find Mizuno NWT deals on eBay ranked by deal index vs market peers.",
    )
    parser.add_argument(
        "-p", "--products", type=Path, default=None,
        help="Optional watchlist JSON (legacy; default is full scrape mode).",
    )
    parser.add_argument(
        "--watchlist", action="store_true",
        help="Use products.json watchlist instead of scraping all Mizuno deals.",
    )
    parser.add_argument("-q", "--query", action="append", default=[])
    parser.add_argument("-n", "--limit", type=int, default=DEFAULT_SOURCE_LIMIT)
    parser.add_argument("-t", "--top", type=int, default=None,
                        help="Top product deals to show (default: pick on settings page).")
    parser.add_argument(
        "--no-settings",
        action="store_true",
        help="Skip the settings page and use --top or the last saved choice.",
    )
    parser.add_argument(
        "--max-pages", type=int, default=DEFAULT_MAX_PAGES,
        help="Max foot-store pages (0 = auto from --top, default auto).",
    )
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--html", type=Path, default=None)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--no-prompt", action="store_true")
    parser.add_argument("--demo", action="store_true", help="Offline demo (no eBay keys).")
    parser.add_argument("--sample", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--no-fallback",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--footstore",
        action="store_true",
        help="Also scan foot-store.com (dev/test; eBay is the primary source).",
    )
    parser.add_argument(
        "--no-footstore",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--no-aspect", action="store_true")
    args = parser.parse_args(argv)

    if args.sample:
        args.demo = True

    console = Console(force_terminal=True)

    if args.top is not None:
        top = args.top
    elif args.no_settings:
        top = load_last_top()
    else:
        top = prompt_top_count(load_last_top())
    save_last_top(top)

    use_footstore = args.footstore and not args.demo
    sources = build_sources(
        force_demo=args.demo,
        use_footstore=use_footstore,
    )
    if not sources:
        console.print(f"[red]{ebay_setup_hint()}[/red]")
        return 1

    agg = Aggregator(sources, limit=args.limit, use_aspects=not args.no_aspect)
    products = load_input_products(args)

    if products is not None:
        if not products:
            console.print("[red]No products to search.[/red]")
            return 2
        console.print(
            f"Checking {len(products)} watchlist item(s) via "
            f"{', '.join(s.name for s in sources)} …\n"
        )
        results = agg.search_all(products)
    else:
        console.print(
            f"Scanning Mizuno eBay deals (mens {APPAREL_SIZE} apparel, mens US {SHOE_SIZE_US} "
            f"shoes) via {', '.join(s.name for s in sources)} …"
        )
        cfg = load_ebay_config()
        if cfg.is_configured:
            from .search_criteria import EBAY_APPAREL_QUERY, EBAY_SHOE_QUERY
            console.print(
                f"  eBay queries: [dim]\"{EBAY_APPAREL_QUERY}\"[/dim], "
                f"[dim]\"{EBAY_SHOE_QUERY}\"[/dim] (NWT, Buy It Now)"
            )
        console.print()
        page_budget = effective_max_pages(args.max_pages, top)
        if cfg.is_configured or args.demo:
            from .fetch_budget import ebay_scan_limit
            el = ebay_scan_limit(top, page_budget)
            console.print(
                f"  [dim]eBay budget: up to {el} results per query (2 queries)[/dim]"
            )
        if use_footstore:
            console.print(
                f"  [dim]foot-store budget: up to {page_budget} pages (test source)[/dim]"
            )
        results = agg.scan_deals(max_pages=args.max_pages, top=top)
        stats = getattr(agg, "last_scan_stats", {})
        if stats:
            refs = stats.get("references", {})
            ref_bits = ", ".join(
                f"{k}: {v}" for k, v in sorted(refs.items()) if v
            )
            pages = stats.get("footstore_pages")
            extra = f", {pages} foot-store pages" if pages else ""
            console.print(
                f"  [dim]Fetched {stats.get('listings', 0)} listings{extra}[/dim]"
            )
            if ref_bits:
                console.print(f"  [dim]Reference tiers: {ref_bits}[/dim]")
            ranked = stats.get("products_ranked")
            skipped = stats.get("skipped_no_discount")
            if ranked is not None:
                console.print(
                    f"  [dim]{ranked} product(s) ranked"
                    + (f", {skipped} listing(s) without discount" if skipped else "")
                    + "[/dim]"
                )
            for err in stats.get("errors", []):
                console.print(f"  [yellow]{err}[/yellow]")
        console.print()

    ranked = output.print_best_discounts(results, console, top=top)

    html_path = args.html or (user_data_dir() / "report.html")
    output.write_html(results, html_path, top=top)
    console.print(f"\nReport: {html_path}")

    if not args.no_browser:
        output.open_report_in_browser(html_path, console)
    elif not args.no_prompt and ranked:
        output.prompt_open_links(ranked, console)

    if args.csv:
        output.write_csv(results, args.csv)
    if args.json:
        output.write_json(results, args.json)

    return 0


if __name__ == "__main__":
    sys.exit(main())
