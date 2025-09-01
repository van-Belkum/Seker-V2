import pandas as pd
from .rules import load_ruleset, save_ruleset

def apply_training(excel_path: str):
    df = pd.read_excel(excel_path)
    ruleset = load_ruleset()
    valid_map = {r["Rule ID"]: r["Valid"] for _, r in df.iterrows() if "Rule ID" in r and "Valid" in r}
    # Simple placeholder: add notes under each rule id
    for rule in ruleset.get("rules", []):
        rid = rule.get("id")
        if rid in valid_map:
            rule.setdefault("training", {})["label"] = str(valid_map[rid])
    save_ruleset(ruleset)

def quick_add_rule(rule_id: str, type_: str, description: str, severity: str="minor"):
    rs = load_ruleset()
    rs.setdefault("rules", []).append({
        "id": rule_id, "type": type_, "severity": severity, "description": description
    })
    save_ruleset(rs)
