"""Command-line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console

from . import output
from .aggregator import Aggregator
from .config import ebay_setup_hint, load_ebay_config
from .launcher import (
    notify_scan_complete,
    prompt_scan_settings,
    shutdown_launcher_server,
)
from .scan_settings import ScanSettings, load_scan_settings, save_scan_settings
from .fetch_budget import DEFAULT_MAX_PAGES, DEFAULT_SOURCE_LIMIT, effective_max_pages
from .paths import find_config, user_data_dir
from .products import load_products, products_from_queries
from .search_criteria import plan_scan_searches, us_shoe_to_eu
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

    saved = load_scan_settings()
    used_launcher = False
    if args.top is not None:
        scan_settings = ScanSettings(
            top=args.top,
            apparel_size=saved.apparel_size,
            shoe_size_us=saved.shoe_size_us,
            search_scope=saved.search_scope,
            custom_query=saved.custom_query,
        ).normalized()
    elif args.no_settings:
        scan_settings = saved
    else:
        scan_settings = prompt_scan_settings(saved)
        used_launcher = True
    save_scan_settings(scan_settings)
    top = scan_settings.top
    apparel_size = scan_settings.apparel_size
    shoe_size_us = scan_settings.shoe_size_us
    shoe_size_eu = us_shoe_to_eu(shoe_size_us)
    search_scope = scan_settings.search_scope
    custom_query = scan_settings.custom_query

    exit_code = 0
    try:
        exit_code = _run_scan(args, console, scan_settings)
    finally:
        if used_launcher:
            notify_scan_complete()
            shutdown_launcher_server()

    return exit_code


def _run_scan(args: argparse.Namespace, console: Console, scan_settings: ScanSettings) -> int:
    top = scan_settings.top
    apparel_size = scan_settings.apparel_size
    shoe_size_us = scan_settings.shoe_size_us
    shoe_size_eu = us_shoe_to_eu(shoe_size_us)
    search_scope = scan_settings.search_scope
    custom_query = scan_settings.custom_query

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
            f"{', '.join(s.name for s in sources)} ...\n"
        )
        results = agg.search_all(products)
    else:
        scope_label = {
            "both": f"mens {apparel_size} apparel + US {shoe_size_us} shoes",
            "apparel": f"mens {apparel_size} apparel only",
            "shoes": f"mens US {shoe_size_us} shoes only",
        }.get(search_scope, search_scope)
        if custom_query:
            console.print(
                f'Scanning Mizuno eBay deals (custom: "{custom_query}") via '
                f"{', '.join(s.name for s in sources)} ..."
            )
        else:
            console.print(
                f"Scanning Mizuno eBay deals ({scope_label}) via "
                f"{', '.join(s.name for s in sources)} ..."
            )
        cfg = load_ebay_config()
        if cfg.is_configured:
            queries = [
                q for q, _, _ in plan_scan_searches(
                    apparel_size=apparel_size,
                    shoe_size_us=shoe_size_us,
                    search_scope=search_scope,
                    custom_query=custom_query,
                )
            ]
            if queries:
                joined = '", "'.join(queries)
                console.print(
                    f'  eBay queries: [dim]"{joined}"[/dim] (NWT, Buy It Now)'
                )
        console.print()
        page_budget = effective_max_pages(args.max_pages, top)
        if cfg.is_configured or args.demo:
            from .fetch_budget import ebay_scan_limit
            el = ebay_scan_limit(top, page_budget)
            query_count = len(
                plan_scan_searches(
                    apparel_size=apparel_size,
                    shoe_size_us=shoe_size_us,
                    search_scope=search_scope,
                    custom_query=custom_query,
                )
            )
            console.print(
                f"  [dim]eBay budget: up to {el} results per query "
                f"({query_count} quer{'y' if query_count == 1 else 'ies'})[/dim]"
            )
        if use_footstore:
            console.print(
                f"  [dim]foot-store budget: up to {page_budget} pages (test source)[/dim]"
            )
        results = agg.scan_deals(
            max_pages=args.max_pages,
            top=top,
            apparel_size=apparel_size,
            shoe_size_us=shoe_size_us,
            shoe_size_eu=shoe_size_eu,
            search_scope=search_scope,
            custom_query=custom_query,
        )
        stats = getattr(agg, "last_scan_stats", {})
        if stats:
            refs = stats.get("references", {})
            ref_bits = ", ".join(
                f"{k}: {v}" for k, v in sorted(refs.items()) if v
            )
            pages = stats.get("footstore_pages")
            extra = f", {pages} foot-store pages" if pages else ""
            excluded_total = stats.get("excluded", 0)
            if excluded_total:
                extra += f", {excluded_total} filtered"
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
