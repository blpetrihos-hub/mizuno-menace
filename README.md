# Mizuno Menace

<p align="center">
  <img src="mizuno_menace/assets/logo.png" alt="Mizuno Menace" width="480">
</p>

Find **New With Tags, Buy It Now** Mizuno apparel and shoes on **eBay** and rank the best deals using an indexable **deal index** — percent below a verifiable reference, not keyword guesses.

**Default mode** queries eBay for **mens medium apparel** and **mens US size 11 shoes**. On launch, a settings page lets you pick **10–50 deals** (in 10s) before the scan runs.

## Features

- **eBay-first** — Browse API, NWT + BIN filters, size facets (M / US 11)
- **Deal index** — indexable score (% below reference) for ranking and export
- **Peer pricing** — compares each listing to eBay medians (same style → product → category)
- **Seller list prices** — uses eBay strikethrough / marketing price when provided
- **Optional Mizuno MSRP** — official lookup when style/MPN resolves (bonus tier)
- Settings page, HTML report, color-variant links per product

## Quick start

### From source

```bash
pip install -r requirements.txt
cp .env.example .env   # add eBay keys when ready
python run.py
```

### Without eBay keys (demo)

```powershell
python run.py --demo --no-settings -t 30
```

### Build executable

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```

Output: `dist\MizunoMenace.exe`

## Configuration

Copy `.env.example` to `.env` and add eBay credentials — **this is the only required setup**:

```
EBAY_CLIENT_ID=...
EBAY_CLIENT_SECRET=...
```

| Flag | Description |
| --- | --- |
| `-t, --top` | Top deals to show (skips settings page when set) |
| `--no-settings` | Skip settings page; use `-t` or last saved choice |
| `--footstore` | Also scan foot-store.com (dev/test only) |
| `--demo` | Offline demo using synthetic eBay-like listings |
| `--watchlist` | Legacy watchlist mode via `products.json` |
| `--no-browser` | Skip opening the HTML report |

## How deals are scored

Each listing gets a **deal index** = `(reference − total) / reference × 100`.

References are chosen in order — the Ref column shows which tier was used:

1. **Mizuno MSRP** — official USA lookup when US style number is known
2. **Mizuno EU MSRP** — EMEA lookup when EU article number is known
3. **vs seller list** — eBay marketing / strikethrough price on that listing
4. **Peer median (style)** — median eBay total for the same MPN/style (≥2 listings)
5. **Peer median (product)** — median for the same normalized product name (≥3 listings)
6. **Category median** — median for apparel or shoes cohort (≥5 listings)

**No keyword MSRP estimates** in default scan mode — if nothing above applies, the listing is not ranked as a deal.

This is designed so scores are **grounded in observable eBay prices** and can be stored/compared over time (`deal_index` in JSON export).

## eBay search

Two Browse API queries (plus NWT/BIN filters):

- `Mizuno medium mens NWT` — mens M apparel
- `Mens Mizuno size 11 new` — mens US 11 shoes

Filters: `conditionIds:{1000}`, `buyingOptions:{FIXED_PRICE}`, `sort=price`, size aspects.

## Project structure

```
mizuno_menace/
  cli.py                 Entry point
  deal_scorer.py         Peer median deal index (eBay-native)
  reference_resolver.py  Official MSRP + eBay seller list
  sources/ebay_source.py   eBay Browse API
  sources/demo_source.py   Offline demo (eBay-shaped data)
  sources/footstore_source.py  Optional test scraper (--footstore)
.env.example             eBay API key template
```

## Requirements

- Python 3.10+
- eBay developer account (production App ID + Cert ID)
- Internet access
