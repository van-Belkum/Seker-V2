from pathlib import Path
import pandas as pd
import datetime as dt

REPORTS_DIR = Path("reports")
HISTORY_DIR = Path("history")
RULESETS_DIR = Path("rulesets")

def ensure_dirs():
    for d in [REPORTS_DIR, HISTORY_DIR, RULESETS_DIR]:
        d.mkdir(parents=True, exist_ok=True)

def timestamp():
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")

def clean_address_title(text: str) -> str:
    if not isinstance(text, str):
        return ""
    # Ignore the exact token ", 0 ,"
    return text.replace(", 0 ,", ",").strip()

def save_history_row(payload: dict, exclude: bool = False):
    ensure_dirs()
    df = pd.DataFrame([payload])
    path = HISTORY_DIR / f"history_{timestamp()}{'_excluded' if exclude else ''}.csv"
    df.to_csv(path, index=False)
    return path
