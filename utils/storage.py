\
import os, json, csv, datetime as dt, pandas as pd

DATA_DIR = "data"
HIST_CSV = os.path.join(DATA_DIR, "history.csv")

os.makedirs(DATA_DIR, exist_ok=True)

def append_history(row:dict):
    row = {**row}
    row["timestamp_utc"] = dt.datetime.utcnow().isoformat()
    exists = os.path.exists(HIST_CSV)
    with open(HIST_CSV,"a",newline="",encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "timestamp_utc","status","client","project","site_type","vendor","supplier",
            "cabinet_location","radio_location","sectors","site_address","pdf_name",
            "excel_name","excluded","notes"
        ])
        if not exists:
            w.writeheader()
        w.writerow({
            "timestamp_utc": row.get("timestamp_utc"),
            "status": row.get("status"),
            "client": row.get("client"),
            "project": row.get("project"),
            "site_type": row.get("site_type"),
            "vendor": row.get("vendor"),
            "supplier": row.get("supplier"),
            "cabinet_location": row.get("cabinet_location"),
            "radio_location": row.get("radio_location"),
            "sectors": row.get("sectors"),
            "site_address": row.get("site_address"),
            "pdf_name": row.get("pdf_name"),
            "excel_name": row.get("excel_name"),
            "excluded": row.get("excluded", False),
            "notes": row.get("notes",""),
        })

def load_history()->pd.DataFrame:
    if not os.path.exists(HIST_CSV):
        return pd.DataFrame(columns=[
            "timestamp_utc","status","client","project","site_type","vendor","supplier",
            "cabinet_location","radio_location","sectors","site_address","pdf_name",
            "excel_name","excluded","notes"
        ])
    try:
        return pd.read_csv(HIST_CSV)
    except Exception:
        return pd.DataFrame()
