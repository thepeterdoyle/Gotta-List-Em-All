
Dry-run preview mode

This script now supports a side-by-side preview CSV so you can review scraped vs. optimized text before generating the final upload file.

Example:
python ebay_scrape_to_fileexchange.py \
  --seed ./ebay_seed_urls_LEAN_with_photo_OPT.csv \
  --template ./Ebay_Category_NonSports_Cards.csv \
  --out ./ebay_bulk_upload_ready.csv \
  --optimize 1 \
  --dry_run 1 \
  --preview ./ebay_preview.csv \
  --write_final 0

- --dry_run 1: create the preview CSV and skip the final output
- --preview: path for the preview CSV (default: ./ebay_preview.csv)
- --write_final 1: ALSO write the final upload CSV in the same run

When you are satisfied with the preview, re-run with:
  --dry_run 0
or use:
  --dry_run 1 --write_final 1
