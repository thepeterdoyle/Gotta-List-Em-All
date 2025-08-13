
import os
import re
import json
import time
import argparse
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime

import requests
from bs4 import BeautifulSoup
import pandas as pd

# Optional Selenium imports
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.common.by import By
    from webdriver_manager.chrome import ChromeDriverManager
except Exception:
    webdriver = None

# Optional OpenAI (optimization)
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

TITLE_PROMPT = """You are an expert eBay seller. Rewrite this title to maximize clicks and keyword relevance.
Rules:
- ≤ 80 characters (hard limit).
- Keep critical keywords first; no keyword stuffing.
- No ALL CAPS, no emojis, no misleading claims.
- Keep brand, year/series, character, #, parallel/variant where applicable.
- American spelling; title case; remove duplicate words.
Original: "{title}"
Return ONLY the new title.
"""

DESC_PROMPT = """You are an expert eBay seller. Rewrite this description to be clear, factual, and conversion-focused.
Rules:
- Preserve 100% factual accuracy; do not invent details.
- Open with a concise summary (what it is, key features, condition).
- Then bullet points: condition specifics, inclusions, shipping/returns highlights.
- No prohibited language; no guarantees or unverifiable claims.
- Keep formatting simple (plain text or basic bullets).
Original description:
{description}

Return ONLY the revised description (no extra commentary).
"""

CONDITION_MAP = {
    "New": 1000,
    "New (Other)": 1500,
    "Used": 3000
}

DEFAULTS = {
    "Format": "FixedPrice",
    "DurationFixedPrice": "GTC",
    "DurationAuction": "Days_7",
    "Quantity": 1,
    "Location": "",
    "ShippingType": "Flat",
    "PostagePaidBy": "Buyer",
}

@dataclass
class ScrapeResult:
    title: str = ""
    description_html: str = ""
    price: Optional[float] = None
    category_id: str = ""
    condition_text: str = ""
    images: List[str] = field(default_factory=list)
    item_specifics: Dict[str, str] = field(default_factory=dict)


def timestamp_str() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M")


def default_path_near_seed(seed_path: str, basename: str) -> str:
    seed_dir = Path(seed_path).resolve().parent
    return str(seed_dir / f"{basename}_{timestamp_str()}.csv")


def fetch_page(url: str, timeout: int = 20) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
    }
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.text


def parse_json_ld(soup: BeautifulSoup) -> Dict:
    data = {}
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            parsed = json.loads(tag.string or "{}")
            if isinstance(parsed, list):
                for entry in parsed:
                    if isinstance(entry, dict) and entry.get("@type") in ("Product", "Offer", "BreadcrumbList"):
                        data[entry.get("@type")] = entry
            elif isinstance(parsed, dict) and parsed.get("@type"):
                data[parsed.get("@type")] = parsed
        except Exception:
            continue
    return data


def extract_text(soup, selector_list: List[Tuple[str, Dict]]) -> str:
    for name, attrs in selector_list:
        el = soup.find(name, attrs=attrs)
        if el and el.get_text(strip=True):
            return el.get_text(" ", strip=True)
    return ""


def scrape_ebay_listing(url: str, use_selenium: bool = False, headless: bool = True) -> ScrapeResult:
    html_text = fetch_page(url)
    soup = BeautifulSoup(html_text, "lxml")

    result = ScrapeResult()

    ld = parse_json_ld(soup)
    product = ld.get("Product", {})
    offer = ld.get("Offer", {})

    # Title
    result.title = product.get("name") or extract_text(soup, [
        ("h1", {"id": "itemTitle"}),
        ("h1", {"class": re.compile(r".*item-title.*", re.I)})
    ])

    # Price
    if offer.get("price"):
        try:
            result.price = float(offer["price"])
        except Exception:
            pass

    # Category via breadcrumbs
    breadcrumbs = ld.get("BreadcrumbList", {})
    if breadcrumbs and "itemListElement" in breadcrumbs:
        try:
            last = breadcrumbs["itemListElement"][-1]
            result.category_id = str(last.get("item", {}).get("@id", "")).split("/")[-1]
        except Exception:
            pass

    # Condition
    condition_text = ""
    for lbl in ["Condition:", "Condition", "Item condition"]:
        el = soup.find(text=re.compile(lbl, re.I))
        if el and hasattr(el, "parent"):
            txt = el.parent.get_text(" ", strip=True)
            if ":" in txt:
                condition_text = txt.split(":", 1)[1].strip()
            else:
                condition_text = txt.strip()
            break
    result.condition_text = condition_text or product.get("itemCondition", "")

    # Images
    images = []
    for key in ["image", "images"]:
        val = product.get(key)
        if isinstance(val, list):
            images.extend([v for v in val if isinstance(v, str) and v.startswith("http")])
        elif isinstance(val, str) and val.startswith("http"):
            images.append(val)
    result.images = list(dict.fromkeys(images))

    # Description (basic)
    description = ""
    desc_candidates = [
        ("div", {"id": "desc_div"}),
        ("div", {"id": "viTabs_0_is"}),
        ("div", {"id": "vi-desc-maincntr"}),
        ("div", {"class": re.compile(r".*item-desc.*", re.I)}),
        ("div", {"class": re.compile(r".*d-item-desc.*", re.I)}),
    ]
    for name, attrs in desc_candidates:
        el = soup.find(name, attrs=attrs)
        if el:
            description = str(el)
            break

    # Selenium fallback for iframe description
    if use_selenium and webdriver is not None and not description:
        options = ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(ChromeDriverManager().install(), options=options)
        try:
            driver.get(url)
            time.sleep(2.5)
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            for iframe in iframes:
                try:
                    driver.switch_to.frame(iframe)
                    time.sleep(0.5)
                    html_source = driver.page_source
                    if "html" in html_source.lower():
                        description = html_source
                        driver.switch_to.default_content()
                        break
                    driver.switch_to.default_content()
                except Exception:
                    driver.switch_to.default_content()
                    continue
        finally:
            driver.quit()

    result.description_html = description

    # Item specifics (best-effort)
    item_specifics = {}
    specifics_sections = soup.find_all(["div", "section"], attrs={"class": re.compile(r"(itemAttr|itemSpecifics|ux-layout-section-evo__section-content)", re.I)})
    for sec in specifics_sections:
        labels = sec.find_all(["td", "span", "div"], attrs={"class": re.compile(r"(attrLabels|ux-labels-values__labels-content)", re.I)})
        for lbl in labels:
            key = lbl.get_text(" ", strip=True).strip(":")
            val = lbl.find_next(["td", "span", "div"], attrs={"class": re.compile(r"(attrLabels|ux-labels-values__values-content|val)", re.I)})
            if val:
                vtxt = val.get_text(" ", strip=True)
                if key and vtxt:
                    item_specifics[key] = vtxt
    result.item_specifics = item_specifics

    return result


def openai_optimize(text: str, is_title: bool, model: str = "gpt-4o-mini") -> str:
    if not OpenAI:
        return text
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return text
    client = OpenAI(api_key=api_key)
    prompt = TITLE_PROMPT.format(title=text) if is_title else DESC_PROMPT.format(description=text)
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=300
        )
        out = resp.choices[0].message.content.strip()
        if is_title:
            out = out[:80]
        return out
    except Exception:
        return text


def normalize_price(val: Optional[str], scraped: Optional[float]) -> Optional[float]:
    if val:
        try:
            return float(val)
        except Exception:
            return scraped
    return scraped


def build_output_row(headers: List[str],
                     seed: Dict[str, str],
                     scraped_title: str,
                     scraped_desc_text: str,
                     price: Optional[float],
                     category_id: str,
                     condition_text: str,
                     images: List[str],
                     scraped_specifics: Dict[str, str]) -> List[str]:
    row = {h: "" for h in headers}

    # Action
    action_col = next((h for h in headers if h.startswith("*Action(")), None)
    if action_col:
        row[action_col] = "Add"

    # Custom label
    row["CustomLabel"] = seed.get("CustomLabel", "")

    # Category
    if "*Category" in headers:
        row["*Category"] = category_id or ""

    # Title
    if "*Title" in headers:
        row["*Title"] = scraped_title

    # Subtitle
    if "Subtitle" in headers:
        row["Subtitle"] = ""

    # Condition
    cond_override = seed.get("Condition", "").strip() or seed.get("ConditionOverride","").strip()
    if cond_override in CONDITION_MAP:
        cond_id = CONDITION_MAP[cond_override]
    else:
        cond_id = 3000  # default Used
    if "*ConditionID" in headers:
        row["*ConditionID"] = str(cond_id)

    # Description
    if "*Description" in headers:
        row["*Description"] = scraped_desc_text

    # Format/Duration
    if "*Format" in headers:
        row["*Format"] = seed.get("FormatOverride", DEFAULTS["Format"])
    if "*Duration" in headers:
        if row["*Format"] == "FixedPrice":
            row["*Duration"] = DEFAULTS["DurationFixedPrice"]
        else:
            row["*Duration"] = seed.get("DurationOverride", DEFAULTS["DurationAuction"])

    # Price/Quantity
    price_val = normalize_price(seed.get("Price") or seed.get("PriceOverride"), price)
    if "*StartPrice" in headers and price_val is not None:
        row["*StartPrice"] = f"{price_val:.2f}"
    if "*Quantity" in headers:
        qty = seed.get("Quantity") or seed.get("QuantityOverride") or str(DEFAULTS["Quantity"])
        row["*Quantity"] = qty

    # PictureURL
    picture_url = seed.get("PhotoURL", "").strip() or (images[0] if images else "")
    if "PictureURL" in headers:
        row["PictureURL"] = picture_url

    # Shipping/Returns
    ship_type = seed.get("ShippingType", "").strip() or seed.get("ShippingTypeOverride","").strip() or DEFAULTS["ShippingType"]
    if "ShippingType" in headers:
        row["ShippingType"] = ship_type
    if "*Location" in headers:
        row["*Location"] = seed.get("LocationOverride","") or DEFAULTS["Location"]
    if ship_type == "Flat":
        if "ShippingService-1:Option" in headers:
            row["ShippingService-1:Option"] = seed.get("FlatService","") or seed.get("ShippingService1_Option","")
        if "ShippingService-1:Cost" in headers:
            row["ShippingService-1:Cost"] = seed.get("FlatCost","") or seed.get("ShippingService1_Cost","")

    if "*ReturnsAcceptedOption" in headers:
        row["*ReturnsAcceptedOption"] = "ReturnsAccepted"
    if "ShippingCostPaidByOption" in headers:
        row["ShippingCostPaidByOption"] = seed.get("PostagePaidBy","Buyer")

    # Item specifics (selected + scraped best-effort)
    specifics_map = {
        "C:Card Condition": seed.get("CardCondition",""),
        "CD:Professional Grader - (ID: 27501)": seed.get("ProfessionalGrader",""),
        "CD:Grade - (ID: 27502)": seed.get("Grade",""),
        "CDA:Certification Number - (ID: 27503)": seed.get("CertNumber",""),
    }
    for k, v in specifics_map.items():
        if k in headers and v:
            row[k] = v

    for h in headers:
        if h.startswith("C:"):
            key = h.replace("C:", "").strip()
            if key in scraped_specifics and scraped_specifics[key]:
                row[h] = scraped_specifics[key]

    return [row.get(h, "") for h in headers]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", required=True)
    ap.add_argument("--template", required=True)
    ap.add_argument("--out", required=False, help="Final CSV path. If omitted, will save next to the seed as FINAL_EBAY_UPLOAD_<timestamp>.csv")
    ap.add_argument("--optimize", type=int, default=1)
    ap.add_argument("--use_selenium", type=int, default=0)
    ap.add_argument("--headless", type=int, default=1)
    # Dry-run flags
    ap.add_argument("--dry_run", type=int, default=0, help="If 1, write a side-by-side preview CSV")
    ap.add_argument("--preview", required=False, help="Preview CSV path. If omitted with --dry_run=1, saves next to seed as EBAY_PREVIEW_<timestamp>.csv")
    ap.add_argument("--write_final", type=int, default=0, help="If 1 with --dry_run, also writes the final upload CSV")
    args = ap.parse_args()

    # Load template headers from the FIRST ROW
    tpl_df = pd.read_csv(args.template, dtype=str, header=None)
    headers = tpl_df.iloc[0].dropna().tolist()

    seed_df = pd.read_csv(args.seed, dtype=str).fillna("")

    # Default paths (when omitted)
    if args.dry_run and not args.preview:
        args.preview = default_path_near_seed(args.seed, "EBAY_PREVIEW")
    if (not args.out) and ((not args.dry_run) or (args.dry_run and args.write_final)):
        args.out = default_path_near_seed(args.seed, "FINAL_EBAY_UPLOAD")

    preview_rows = []
    final_rows = []

    for _, seed in seed_df.iterrows():
        url = seed.get("URL", "").strip()
        if not url:
            continue

        scraped = scrape_ebay_listing(url, use_selenium=bool(args.use_selenium), headless=bool(args.headless))

        # Make plain text description for optimization & preview
        scraped_desc_text = BeautifulSoup(scraped.description_html or "", "lxml").get_text("\n", strip=True)

        # Optimization toggles (respect per-row + global flag)
        do_title_opt = (seed.get("OptimizeTitle","Y") == "Y") and bool(args.optimize)
        do_desc_opt  = (seed.get("OptimizeDescription","Y") == "Y") and bool(args.optimize)

        opt_title = openai_optimize(scraped.title, is_title=True) if do_title_opt else scraped.title
        opt_desc  = openai_optimize(scraped_desc_text, is_title=False) if do_desc_opt else scraped_desc_text

        # Build preview row
        if args.dry_run:
            preview_rows.append({
                "URL": url,
                "Title_Scraped": scraped.title,
                "Title_Optimized": opt_title,
                "TitleLen_Scraped": len(scraped.title or ""),
                "TitleLen_Optimized": len(opt_title or ""),
                "Desc_Scraped_Snippet": (scraped_desc_text or "")[:400],
                "Desc_Optimized_Snippet": (opt_desc or "")[:400],
                "PhotoURL": seed.get("PhotoURL",""),
                "PostagePaidBy": seed.get("PostagePaidBy","Buyer")
            })

        # Build final row data (using optimized texts)
        row = build_output_row(
            headers=headers,
            seed=seed,
            scraped_title=opt_title,
            scraped_desc_text=opt_desc,
            price=scraped.price,
            category_id=scraped.category_id,
            condition_text=scraped.condition_text,
            images=scraped.images,
            scraped_specifics=scraped.item_specifics
        )
        final_rows.append(row)

    # Write preview if needed
    if args.dry_run and args.preview:
        prev_df = pd.DataFrame(preview_rows)
        prev_df.to_csv(args.preview, index=False)
        print(f"Preview written: {args.preview}")
        if not args.write_final:
            print("Dry-run mode: skipping final upload CSV (use --write_final 1 to also write it).")

    # Write final if requested (or normal run)
    if (not args.dry_run) or (args.dry_run and args.write_final):
        out_df = pd.DataFrame(final_rows, columns=headers)
        out_df.to_csv(args.out, index=False)
        print(f"Done. Wrote {len(final_rows)} rows to {args.out}")


if __name__ == "__main__":
    main()
