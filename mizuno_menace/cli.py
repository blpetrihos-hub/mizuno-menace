"""Command-line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console

from . import output
from .aggregator import Aggregator
from .config import load_ebay_config
from .paths import find_config, user_data_dir
from .products import default_products, load_products, products_from_queries
from .sources import DemoSource, EbaySource, FootStoreSource


def build_sources(use_demo: bool, force_demo: bool, use_footstore: bool) -> list:
    if force_demo:
        return [DemoSource()]

    cfg = load_ebay_config()
    sources: list = []
    if cfg.is_configured:
        sources.append(EbaySource(cfg))
    if use_footstore:
        sources.append(FootStoreSource())
    if not sources and use_demo:
        sources.append(DemoSource())
    return sources


def load_input_products(args: argparse.Namespace) -> list | None:
    if args.query:
        return products_from_queries(args.query)
    if args.products is not None:
        if args.products.exists():
            return load_products(args.products)
        return None
    found = find_config("products.json")
    if found:
        return load_products(found)
    return default_products()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mizuno-menace",
        description="Find Mizuno deals and rank them by discount vs MSRP.",
    )
    parser.add_argument("-p", "--products", type=Path, default=None)
    parser.add_argument("-q", "--query", action="append", default=[])
    parser.add_argument("-n", "--limit", type=int, default=25)
    parser.add_argument("-t", "--top", type=int, default=15)
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--html", type=Path, default=None)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--no-prompt", action="store_true")
    parser.add_argument("--demo", action="store_true", help="Use offline demo data.")
    parser.add_argument("--sample", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--no-fallback", action="store_true")
    parser.add_argument("--no-footstore", action="store_true")
    parser.add_argument("--no-aspect", action="store_true")
    args = parser.parse_args(argv)

    if args.sample:
        args.demo = True

    console = Console(force_terminal=True)

    products = load_input_products(args)
    if products is None:
        console.print(f"[red]Product list not found:[/red] {args.products}")
        return 2
    if not products:
        console.print("[red]No products to search.[/red]")
        return 2

    sources = build_sources(
        use_demo=not args.no_fallback,
        force_demo=args.demo,
        use_footstore=not args.no_footstore and not args.demo,
    )
    if not sources:
        console.print("[red]No data sources available.[/red] Add eBay keys or use --demo.")
        return 1

    console.print(
        f"Checking {len(products)} product(s) via {', '.join(s.name for s in sources)} …\n"
    )

    agg = Aggregator(sources, limit=args.limit, use_aspects=not args.no_aspect)
    results = agg.search_all(products)

    ranked = output.print_best_discounts(results, console, top=args.top)
    output.print_zero_result_notes(results, console)

    html_path = args.html or (user_data_dir() / "report.html")
    output.write_html(results, html_path, top=args.top)
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
