\
import os, json
from datetime import datetime, timezone
from typing import Dict, Any, List
import pandas as pd

HISTORY_CSV = "history.csv"
FEEDBACK_DIR = "training"

def save_history_row(row: Dict[str, Any]) -> None:
    df = pd.DataFrame([row])
    if os.path.exists(HISTORY_CSV):
        df.to_csv(HISTORY_CSV, mode="a", header=False, index=False)
    else:
        df.to_csv(HISTORY_CSV, index=False)

def load_history() -> pd.DataFrame:
    if not os.path.exists(HISTORY_CSV):
        return pd.DataFrame()
    return pd.read_csv(HISTORY_CSV)

def save_feedback(records: List[Dict[str, Any]]) -> str:
    os.makedirs(FEEDBACK_DIR, exist_ok=True)
    fn = os.path.join(FEEDBACK_DIR, f"feedback_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json")
    with open(fn, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    return fn
