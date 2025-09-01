from pathlib import Path
import yaml
SETTINGS = Path("rulesets/app_settings.yaml")
def get_settings():
    with open(SETTINGS, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
def is_admin(passphrase: str) -> bool:
    s = get_settings()
    return bool(passphrase) and passphrase == s.get("admin",{}).get("passphrase","")
