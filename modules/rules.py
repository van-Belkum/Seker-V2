import yaml
from pathlib import Path
from typing import Dict, Any

DEFAULT_RULESET_PATH = Path("rulesets/default_rules.yaml")

def load_ruleset(path: Path = DEFAULT_RULESET_PATH) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def save_ruleset(data: Dict[str, Any], path: Path = DEFAULT_RULESET_PATH):
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
