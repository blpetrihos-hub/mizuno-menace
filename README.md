# Mizuno Menace

<p align="center">
  <img src="mizuno_menace/assets/logo.png" alt="Mizuno Menace" width="480">
</p>

Compare Mizuno apparel and shoe prices across retailers and rank the top discounts vs MSRP.

**Default mode** scrapes foot-store for all in-stock Mizuno deals matching **mens medium apparel** and **mens US size 11 shoes** — no watchlist required. On launch, a settings page lets you pick **10–50 deals** (in 10s) before the scan runs.

## Features

- **Settings page** — choose how many deals to show (10, 20, 30, 40, or 50) before scanning
- **Scrape mode** — discovers Mizuno deals from foot-store sitemaps (mens M + mens 11)
- **foot-store.com** — live retail prices (works out of the box)
- **eBay** — New With Tags, Buy It Now only, sorted by price + shipping (requires API keys in `.env`)
- Top product deals ranked by discount vs Mizuno MSRP (all color variants listed per product)

## Quick start

### Executable

```powershell
.\MizunoMenace.exe
```

Runs a full Mizuno deal scan (after the settings page), writes a report to `%LOCALAPPDATA%\MizunoMenace\report.html`, and opens it in your browser.

### From source

```bash
pip install -r requirements.txt
python run.py
```

### Build

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```

Output: `dist\MizunoMenace.exe`

## Configuration

Copy `.env.example` to `.env` and add eBay credentials when ready — that is the only setup required to enable eBay results. The tool auto-detects keys and merges eBay listings with foot-store in scrape mode.

```
EBAY_CLIENT_ID=...
EBAY_CLIENT_SECRET=...
```

Foot-store scraping works without any API keys. Scan depth defaults are tuned via `FETCH_DEPTH_MULTIPLIER` in `fetch_budget.py` (currently 1.5× base limits).

Optional legacy watchlist via `--watchlist` and `products.json`. Default scrape filters: **mens M apparel**, **mens US 11 shoes**.

| Flag | Description |
| --- | --- |
| `-t, --top` | Top product deals to show (skips settings page when set) |
| `--no-settings` | Skip settings page; use `-t` or last saved choice (default 30) |
| `--max-pages` | Max foot-store pages (`0` = auto from `--top`) |
| `--watchlist` | Use `products.json` instead of scrape mode |
| `-p, --products` | Custom watchlist JSON path |
| `-q, --query` | One-off search term (watchlist mode) |
| `--csv`, `--json`, `--html` | Export paths |
| `--no-browser` | Skip opening the HTML report |
| `--no-footstore` | eBay only |
| `--no-aspect` | Disable eBay size facets |
| `--demo` | Offline demo data (no network) |

## eBay search

Scrape mode runs these two Browse API queries (plus NWT/BIN filters below):

- `Mizuno medium mens NWT` — mens medium apparel (`Size: M`)
- `Mens Mizuno size 11 new` — mens shoes (`US Shoe Size: 11`)

Each request also applies:

- `conditionIds:{1000}` — New With Tags
- `buyingOptions:{FIXED_PRICE}` — Buy It Now
- `sort=price` — lowest price + shipping
- Size aspect from `kind` + `size` (`Size` for apparel, `US Shoe Size` for shoes)

## Reference prices (discount %)

Discounts use a tiered waterfall — the Ref column shows which source was used and when it was verified:

1. **Mizuno MSRP** — live lookup from [usa.mizuno.com](https://usa.mizuno.com) by US style number (cached weekly)
2. **Mizuno EU MSRP** — live lookup from [emea.mizuno.com](https://emea.mizuno.com) by EU article number (foot-store MPN; EUR→USD conversion)
3. **Catalog MSRP** — local catalog cache (`%LOCALAPPDATA%\MizunoMenace\cache\catalog_msrp.json`)
4. **Market reference** — median of ≥3 NWT retail observations for the same style
5. **vs seller list** — eBay strikethrough / list price on the listing
6. **Estimated MSRP** — keyword fallback (legacy rules) when nothing else matches
7. **No reference** — listing excluded from discount ranking

Style IDs are extracted from foot-store MPN (JSON-LD), URL slugs, and eBay aspects.

## Project structure

```
mizuno_menace/
  cli.py                 Entry point and argument parsing
  launcher.py            Settings page (deal count picker)
  aggregator.py          Runs sources and ranks deals
  fetch_budget.py        Adaptive scan depth limits
  reference_resolver.py  Tiered MSRP / reference-price waterfall
  mizuno_usa.py          Official Mizuno USA price lookup + cache
  mizuno_eu.py           Official Mizuno EMEA price lookup + cache
  currency_util.py       EUR/GBP → USD for discount math
  style_extractor.py     MPN / style id from URLs and eBay aspects
  output.py              Tables, HTML report, exports
  sources/
    ebay_source.py       eBay Browse API (NWT, Buy It Now)
    footstore_source.py  foot-store.com sitemap scraper
    demo_source.py       Offline demo data (--demo)
products.json            Optional legacy watchlist (empty by default)
.env.example             eBay API key template — copy to .env
```

## Requirements

- Python 3.10+
- Internet access
- eBay developer account (optional, for eBay source)
