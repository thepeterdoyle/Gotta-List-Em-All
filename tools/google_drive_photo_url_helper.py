
import argparse
import os
import re
from typing import Dict, List, Tuple
from pathlib import Path

import pandas as pd

# Google Auth / API
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

def get_service(creds_path: str = "client_secret.json", token_path: str = "token.json"):
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as token:
            token.write(creds.to_json())
    service = build("drive", "v3", credentials=creds)
    return service

def list_files_in_folder(service, folder_id: str) -> List[Dict]:
    files = []
    page_token = None
    query = f"'{folder_id}' in parents and trashed = false"
    while True:
        resp = service.files().list(
            q=query,
            spaces="drive",
            fields="nextPageToken, files(id, name, mimeType, parents, webViewLink)",
            pageToken=page_token
        ).execute()
        files.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken", None)
        if page_token is None:
            break
    return files

def to_direct_image_link(file_id: str) -> str:
    return f"https://drive.google.com/uc?export=view&id={file_id}"

def normalize_label(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "", (s or "").strip().lower())

def group_files_by_label(files: List[Dict]) -> Dict[str, List[Dict]]:
    groups: Dict[str, List[Dict]] = {}
    for f in files:
        name = f.get("name","")
        base = os.path.splitext(name)[0]
        core = normalize_label(base)
        if not core:
            core = "misc"
        groups.setdefault(core, []).append(f)
    return groups

def find_best_image(files: List[Dict]) -> Dict:
    image_files = [f for f in files if f.get("mimeType","").startswith("image/")]
    if not image_files:
        image_files = files
    image_files.sort(key=lambda x: x.get("name",""))
    return image_files[0] if image_files else None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder_id", required=True, help="Google Drive folder ID")
    ap.add_argument("--seed", required=True, help="Path to lean seed CSV")
    ap.add_argument("--out", required=True, help="Path to write updated seed CSV (with PhotoURL)")
    ap.add_argument("--label_col", default="CustomLabel", help="Seed column to match files by (CustomLabel, Notes, etc.)")
    ap.add_argument("--assign_by_order", type=int, default=0, help="If 1, assign images to rows in order")
    ap.add_argument("--creds", default="client_secret.json", help="Path to Google OAuth client_secret.json")
    ap.add_argument("--token", default="token.json", help="Path to OAuth token.json (will be created)")
    args = ap.parse_args()

    df = pd.read_csv(args.seed, dtype=str).fillna("")
    service = get_service(args.creds, args.token)
    files = list_files_in_folder(service, args.folder_id)
    if not files:
        print("No files found in the folder.")
        df.to_csv(args.out, index=False)
        return

    groups = group_files_by_label(files)

    assigned = 0
    if not args.assign_by_order:
        for i, row in df.iterrows():
            label = row.get(args.label_col, "")
            norm_label = normalize_label(label)
            if not norm_label:
                continue
            candidates = []
            if norm_label in groups:
                candidates = groups[norm_label]
            else:
                for key, flist in groups.items():
                    if norm_label in key:
                        candidates.extend(flist)
            if candidates:
                best = find_best_image(candidates)
                if best:
                    df.at[i, "PhotoURL"] = to_direct_image_link(best["id"])
                    assigned += 1

    if args.assign_by_order or assigned == 0:
        image_files = [f for f in files if f.get("mimeType","").startswith("image/")]
        image_files.sort(key=lambda x: x.get("name",""))
        idx = 0
        for i, _ in df.iterrows():
            if not df.at[i, "PhotoURL"] and idx < len(image_files):
                df.at[i, "PhotoURL"] = to_direct_image_link(image_files[idx]["id"])
                idx += 1

    df.to_csv(args.out, index=False)
    print(f"Updated seed written to: {args.out}")

if __name__ == "__main__":
    main()
