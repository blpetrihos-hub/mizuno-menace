# Mizuno Menace

<p align="center">
  <img src="mizuno_menace/assets/logo.png" alt="Mizuno Menace" width="480">
</p>

Find **New With Tags, Buy It Now** Mizuno apparel and shoes on **eBay** and rank the best deals using an indexable **deal index** — percent below a verifiable reference, not keyword guesses.

On launch, a settings page lets you pick **apparel size**, **shoe size (US)**, and **how many deals** (10–50) before the scan runs.

## Features

- **eBay-first** — Browse API, NWT + BIN filters, size facets
- **Deal index** — indexable score (% below reference) for ranking and export
- **Peer pricing** — compares each listing to eBay medians (same style → product → category)
- **Seller list prices** — uses eBay strikethrough / marketing price when provided
- **Optional Mizuno MSRP** — official lookup when style/MPN resolves (bonus tier)
- Settings page with size dropdowns, HTML report, color-variant links per product

## Quick start

### 1. Install

```bash
pip install -r requirements.txt
```

### 2. Add eBay keys (required for live scans)

```powershell
copy .env.example .env
```

Edit `.env` with your **production** App ID (Client ID) and Cert ID (Client Secret) from [developer.ebay.com](https://developer.ebay.com/).

The tool looks for `.env` in (first match wins):

- Current working directory
- Folder containing `MizunoMenace.exe` (or project root when running from source)
- `%LOCALAPPDATA%\MizunoMenace\.env`

### 3. Run

```powershell
python run.py
```

Settings page → pick sizes and deal count → scan → HTML report opens in your browser.

Preferences are saved to `%LOCALAPPDATA%\MizunoMenace\settings.json`.

### Without eBay keys (demo only)

```powershell
python run.py --demo --no-settings -t 30
```

### Build local executable

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```

Output: `dist\MizunoMenace.exe` plus `dist\.env.example`.

**After building:** copy `dist\.env.example` → `dist\.env`, add your eBay keys, run the exe. Reports and cache go to `%LOCALAPPDATA%\MizunoMenace\`.

## Configuration

Only eBay credentials are required:

```
EBAY_CLIENT_ID=...
EBAY_CLIENT_SECRET=...
```

Optional: `EBAY_ENV=production`, `EBAY_MARKETPLACE_ID=EBAY_US`

| Flag | Description |
| --- | --- |
| `-t, --top` | Top deals to show (skips settings page when set) |
| `--no-settings` | Skip settings page; use saved preferences |
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

Two Browse API queries (built from your size choices, plus NWT/BIN filters), for example:

- `Mizuno medium mens running NWT` — mens M apparel
- `Mens Mizuno running size 11 new` — mens US 11 shoes

Filters: `conditionIds:{1000}`, `buyingOptions:{FIXED_PRICE}`, `sort=price`, size aspects.

## Project structure

```
mizuno_menace/
  cli.py                 Entry point
  launcher.py            Settings page (browser UI)
  scan_settings.py       Saved preferences (top, sizes)
  search_criteria.py     Size options and eBay query text
  deal_scorer.py         Peer median deal index (eBay-native)
  reference_resolver.py  Official MSRP + eBay seller list
  sources/ebay_source.py   eBay Browse API
  sources/demo_source.py   Offline demo (eBay-shaped data)
  sources/footstore_source.py  Optional test scraper (--footstore)
.env.example             eBay API key template
build.ps1                PyInstaller build script
```

## Requirements

- Python 3.10+
- eBay developer account (production App ID + Cert ID)
- Internet access
