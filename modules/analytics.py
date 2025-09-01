from pathlib import Path
import pandas as pd

def load_history(history_dir: Path = Path("history")):
    rows = []
    for p in sorted(history_dir.glob("history_*.csv")):
        try:
            df = pd.read_csv(p)
            df["source_file"] = p.name
            rows.append(df)
        except Exception:
            pass
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()

def compute_metrics(df: pd.DataFrame):
    if df.empty:
        return {}
    # Group by Internal ID + Template when present
    group_cols = [c for c in ["Internal ID","Template"] if c in df.columns]
    out = {}
    if group_cols:
        g = df.groupby(group_cols)
        out["groups"] = g.size().reset_index(name="count")
    # Simple rejection rate if Status present
    if "Status" in df.columns:
        out["rejection_rate"] = (df["Status"].str.contains("Rejected", case=False, na=False).mean())
    return out
