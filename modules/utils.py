from pathlib import Path
import pandas as pd
import datetime as dt

HISTORY_DIR = Path("history")
REPORTS_DIR = Path("reports")

def timestamp():
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")

def save_history_row(payload: dict, exclude: bool=False):
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    p = HISTORY_DIR / f"history_{timestamp()}{'_excluded' if exclude else ''}.csv"
    pd.DataFrame([payload]).to_csv(p, index=False)
    return p
