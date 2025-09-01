from pathlib import Path
import pandas as pd

def load_history(history_dir: Path = Path("history")):
    rows = []
    for p in sorted(history_dir.glob("history_*.csv")):
        try:
            df = pd.read_csv(p); df["source"] = p.name; rows.append(df)
        except Exception: pass
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
