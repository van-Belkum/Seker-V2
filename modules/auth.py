import yaml
from pathlib import Path
SETTINGS = Path("rulesets/app_settings.yaml")
def get_settings():
    with open(SETTINGS, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
def is_admin(token: str) -> bool:
    s = get_settings()
    return bool(token) and token == s.get("admin", {}).get("passphrase", "")
