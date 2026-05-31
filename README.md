# Mizuno Menace

<p align="center">
  <img src="mizuno_menace/assets/logo.png" alt="Mizuno Menace" height="52">
</p>

Compare Mizuno apparel and shoe prices across retailers and rank the top 15 discounts vs MSRP.

**Default mode** scrapes foot-store for all in-stock Mizuno deals matching **mens medium apparel** and **mens US size 11 shoes** — no watchlist required.

## Features

- **Scrape mode** — discovers Mizuno deals from foot-store sitemaps (mens M + mens 11)
- **foot-store.com** — live retail prices (works out of the box)
- **eBay** — New With Tags, Buy It Now only, sorted by price + shipping (requires API keys)
- Top 15 product deals ranked by discount vs Mizuno MSRP (color variants grouped per product)

## Quick start

### Executable

```powershell
.\MizunoMenace.exe
```

Runs a full Mizuno deal scan, writes a report to `%LOCALAPPDATA%\MizunoMenace\report.html`, and opens it in your browser.

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

Copy `.env.example` to `.env` and add eBay credentials when ready:

```
EBAY_CLIENT_ID=...
EBAY_CLIENT_SECRET=...
```

Optional legacy watchlist via `--watchlist` and `products.json`. Default scrape filters: **mens M apparel**, **mens US 11 shoes**.

| Flag | Description |
| --- | --- |
| `-t, --top` | Top product deals to show (default 15) |
| `--max-pages` | Max foot-store pages to scan (default 350) |
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

## Project structure

```
mizuno_menace/
  cli.py              Entry point and argument parsing
  aggregator.py       Runs sources per product
  output.py           Tables, HTML report, exports
  sources/
    ebay_source.py    eBay Browse API
    footstore_source.py
    demo_source.py    Offline demo data
products.json         Product list (optional)
```

## Requirements

- Python 3.10+
- Internet access
- eBay developer account (optional, for eBay source)
