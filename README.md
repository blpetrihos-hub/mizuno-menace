# Mizuno Menace

<p align="center">
  <img src="mizuno_menace/assets/logo.png" alt="Mizuno Menace" height="52">
</p>

Compare Mizuno apparel and shoe prices across retailers and rank the best deals against MSRP.

## Features

- **foot-store.com** — live retail prices (works out of the box)
- **eBay** — New With Tags, Buy It Now only, sorted by price + shipping (requires API keys)
- Discount ranking vs Mizuno MSRP
- Clickable color links in terminal and HTML reports
- Standalone Windows executable (no Python install required)

## Quick start

### Executable

```powershell
.\MizunoMenace.exe
```

Runs the built-in product list against foot-store, writes a report to `%LOCALAPPDATA%\MizunoMenace\report.html`, and opens it in your browser.

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

Optional `products.json` beside the executable overrides the built-in list:

```json
{
  "products": [
    {
      "name": "Mizuno Wave Rider (mens 11)",
      "query": "Mizuno Wave Rider mens 11",
      "msrp": 140.00,
      "size": "11",
      "kind": "shoe"
    }
  ]
}
```

| Field | Description |
| --- | --- |
| `query` | Search term sent to each source |
| `msrp` | Mizuno retail price for discount calculation |
| `size` | Used for eBay size aspect filtering |
| `kind` | `apparel` or `shoe` |

Verify MSRP values against [mizunousa.com](https://www.mizunousa.com) for accurate discount percentages.

## CLI

| Flag | Description |
| --- | --- |
| `-p, --products` | Product list JSON |
| `-q, --query` | One-off search term (repeatable) |
| `-n, --limit` | Max listings per product (default 25) |
| `-t, --top` | Products in the deals table (default 15) |
| `--csv`, `--json`, `--html` | Export paths |
| `--no-browser` | Skip opening the HTML report |
| `--no-footstore` | eBay only |
| `--no-aspect` | Disable eBay size facets |
| `--demo` | Offline demo data (no network) |

## eBay filters

Each eBay request applies:

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
