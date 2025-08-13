import json
import re
import sys
import pandas as pd
from pathlib import Path

ALLOWED_PATH = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("config/ebay_allowed_values.json")
SEED_PATH = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data/seeds/ebay_seed_urls_LEAN_with_photo_OPT.csv")
REPORT_PATH = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("data/seeds/ebay_seed_validation_report.csv")

def is_number(x):
    try:
        float(x)
        return True
    except:
        return False

def main():
    allowed = json.loads(ALLOWED_PATH.read_text())
    df = pd.read_csv(SEED_PATH, dtype=str).fillna("")
    issues = []

    required_cols = ["URL"]
    for c in required_cols:
        if c not in df.columns:
            issues.append({"row": 0, "field": c, "issue": "Missing required column in seed file"})
    
    for idx, row in df.iterrows():
        if not row.get("URL", "").strip():
            issues.append({"row": idx+2, "field": "URL", "issue": "URL is required"})
        
        po = row.get("Price","").strip() or row.get("PriceOverride","").strip()
        if po and not is_number(po):
            issues.append({"row": idx+2, "field": "Price", "issue": "Must be numeric"})
        if po and is_number(po) and float(po) <= 0:
            issues.append({"row": idx+2, "field": "Price", "issue": "Must be > 0"})
        
        qo = row.get("Quantity","").strip() or row.get("QuantityOverride","").strip()
        if qo:
            if not qo.isdigit():
                issues.append({"row": idx+2, "field": "Quantity", "issue": "Must be an integer >= 1"})
            elif int(qo) < 1:
                issues.append({"row": idx+2, "field": "Quantity", "issue": "Must be >= 1"})
        
        sc = row.get("FlatCost","").strip() or row.get("ShippingService1_Cost","").strip()
        if sc:
            if not is_number(sc):
                issues.append({"row": idx+2, "field": "FlatCost", "issue": "Must be numeric"})
            elif float(sc) < 0:
                issues.append({"row": idx+2, "field": "FlatCost", "issue": "Must be >= 0"})
        
        rwithin = row.get("ReturnsWithinOverride","").strip()
        if rwithin and not re.fullmatch(r"Days_\d+", rwithin):
            issues.append({"row": idx+2, "field": "ReturnsWithinOverride", "issue": "Use format Days_30, Days_60, etc."})
        
        for field, allowed_list_key in [
            ("ReturnsAcceptedOverride", "ReturnsAcceptedOverride"),
            ("ShippingType", "ShippingTypeOverride"),
            ("ShippingCostPaidByOverride", "ShippingCostPaidByOverride"),
        ]:
            val = row.get(field, "").strip()
            if val and val not in allowed.get(allowed_list_key, []):
                issues.append({"row": idx+2, "field": field, "issue": f"Value '{val}' not in allowed: {allowed.get(allowed_list_key, [])}"})
        
        ship_type = row.get("ShippingType","").strip()
        if ship_type == "Calculated":
            for f in ["Weight_lbs","Weight_oz","Depth_in","Length_in","Width_in",
                      "WeightMajor_lbs","WeightMinor_oz","PackageDepth_in","PackageLength_in","PackageWidth_in"]:
                if (f in df.columns) and (not row.get(f,"").strip()):
                    issues.append({"row": idx+2, "field": f, "issue": "Required for Calculated shipping"})
            for f in ["Weight_lbs","Weight_oz","Depth_in","Length_in","Width_in",
                      "WeightMajor_lbs","WeightMinor_oz","PackageDepth_in","PackageLength_in","PackageWidth_in"]:
                if f in df.columns:
                    v = row.get(f,"").strip()
                    if v and not is_number(v):
                        issues.append({"row": idx+2, "field": f, "issue": "Must be numeric"})
        
        cond = row.get("Condition","").strip() or row.get("ConditionOverride","").strip()
        if cond and cond not in allowed["ConditionOverride_to_ConditionID"]:
            issues.append({"row": idx+2, "field": "Condition", "issue": f"Unknown condition '{cond}'. Allowed: {list(allowed['ConditionOverride_to_ConditionID'].keys())}"})
    
    report = pd.DataFrame(issues, columns=["row","field","issue"])
    report.to_csv(REPORT_PATH, index=False)
    print(f"Validation complete. Issues: {len(report)}")
    print(f"Report saved to: {REPORT_PATH}")

if __name__ == "__main__":
    main()

