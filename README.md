# GottaListEmAll 🐉
Bulk-scrape eBay listings → optimize title/description with ChatGPT → emit an eBay File Exchange CSV ready to upload. Also includes a helper to turn Google Drive images into direct `PictureURL`s.

## Why
Paste URLs, set a few toggles, and get a clean, upload‑ready CSV with:
- Optimized **Title** (≤80 chars, expert eBay SEO)
- Clean, factual **Description**
- Correct **PictureURL** (from Google Drive or scraped)
- Shipping, returns, price, quantity, condition… all mapped

## Features
- **Lean seed CSV** you can paste into fast
- **PhotoURL** support (Google Drive direct links)
- **Per‑row optimization** toggles for Title/Description
- **Dry‑run preview** (scraped vs optimized side‑by‑side)
- **Automatic timestamped outputs** (no overwrites)
- Optional **validator** for seed sanity checks

## Repo layout
src/ebay_scrape_to_fileexchange.py # main pipeline
tools/google_drive_photo_url_helper.py # fills PhotoURL from Drive folder
scripts/ebay_seed_validator.py # optional seed validator
config/ebay_allowed_values.json # enums, condition/grade lists
data/templates/Ebay_Category_NonSports_Cards.csv # your File Exchange template
data/seeds/ebay_seed_urls_LEAN_with_photo_OPT.csv # seed you maintain
data/docs/README_dryrun.txt # dry-run notes
data/docs/README_drive_helper.txt # drive helper notes
docs/ebay_seed_LEAN_README.txt # seed field cheat sheet

## Setup
```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

## (Optional) OpenAI for optimization
Set an environment variable:

export OPENAI_API_KEY="sk-..."   # Windows: setx OPENAI_API_KEY "sk-..."
If not set, the script still runs; it just skips optimization.

## (Optional) Google Drive helper (for PhotoURL)
Enable Google Drive API in Google Cloud.
Create OAuth Client ID (Desktop) and download client_secret.json.
Place client_secret.json in the repo root (listed in .gitignore).
First run will open a browser and save token.json.

## Quickstart
## 1) Prepare seed
Edit data/seeds/ebay_seed_urls_LEAN_with_photo_OPT.csv.

Minimum fields:

URL (required)

Price (your price)
Optional:

PhotoURL (direct link to main image)

OptimizeTitle / OptimizeDescription (Y/N)

PostagePaidBy (Buyer/Seller)

Shipping (Flat vs Calculated + dimensions)

See docs/ebay_seed_LEAN_README.txt for field help.

## 2) (Optional) Fill PhotoURL from your Drive folder
python tools/google_drive_photo_url_helper.py \
  --folder_id YOUR_FOLDER_ID \
  --seed data/seeds/ebay_seed_urls_LEAN_with_photo_OPT.csv \
  --out  data/seeds/ebay_seed_with_photos.csv \
  --label_col CustomLabel
Use --assign_by_order 1 to match by order instead of label.

## 3) (Optional) Validate your seed
python scripts/ebay_seed_validator.py \
  config/ebay_allowed_values.json \
  data/seeds/ebay_seed_urls_LEAN_with_photo_OPT.csv \
  data/seeds/ebay_seed_validation_report.csv

## 4) Generate preview + final upload
# Dry-run preview (scraped vs optimized), AND write final:
python src/ebay_scrape_to_fileexchange.py \
  --seed data/seeds/ebay_seed_urls_LEAN_with_photo_OPT.csv \
  --template data/templates/Ebay_Category_NonSports_Cards.csv \
  --optimize 1 \
  --dry_run 1 \
  --write_final 1

## Defaults when you omit paths:

Preview → EBAY_PREVIEW_YYYY-MM-DD_HH-MM.csv next to your seed

Final → FINAL_EBAY_UPLOAD_YYYY-MM-DD_HH-MM.csv next to your seed

You can always set explicit paths:
python src/ebay_scrape_to_fileexchange.py \
  --seed data/seeds/ebay_seed_urls_LEAN_with_photo_OPT.csv \
  --template data/templates/Ebay_Category_NonSports_Cards.csv \
  --out ./my_upload.csv \
  --preview ./my_preview.csv \
  --optimize 1
## Notes
Title optimization is capped at 80 characters (hard limit).

PhotoURL (if provided) overrides scraped images.

PostagePaidBy maps to ShippingCostPaidByOption (Buyer/Seller).

For Calculated shipping, include weight/dimensions in seed.

## Troubleshooting
If descriptions aren’t captured (eBay iframe), run with --use_selenium 1.

If optimization seems unchanged, ensure OPENAI_API_KEY is set and --optimize 1.

If PhotoURLs don’t load on eBay, confirm they’re public and use the uc?export=view&id=FILE_ID format.

## License
MIT. See LICENSE.
