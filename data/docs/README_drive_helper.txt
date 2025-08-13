
Google Drive -> PhotoURL helper

This script fills the PhotoURL column in your lean seed CSV using images from a Google Drive folder.

Prereqs:
1) Enable Google Drive API in your Google Cloud project.
2) Create OAuth 'Desktop App' credentials and download client_secret.json.
3) Put client_secret.json next to the script.

Install:
pip install google-api-python-client google-auth google-auth-oauthlib pandas python-dotenv

Usage:
python google_drive_photo_url_helper.py \
  --folder_id 1CupcRDcR0829QoeyKV2bD2cykhgcyOTf \
  --seed ./ebay_seed_urls_LEAN_with_photo_OPT.csv \
  --out ./ebay_seed_with_photos.csv \
  --label_col CustomLabel

Tips:
- The script tries to match file names to your seed's 'CustomLabel' (or the column you specify).
- File name like 'SET-0100_1.jpg' will match CustomLabel 'SET-0100'.
- If you prefer, use --assign_by_order 1 to assign images to rows in order (alphabetical by file name).
- Ensure the Drive folder or files are shared 'Anyone with the link' so eBay can fetch them.
- The script converts each file ID to a direct link: https://drive.google.com/uc?export=view&id=FILE_ID
