\
from typing import List, Dict, Any
import re

# Extremely simple placeholder engine:
# - Site Address vs PDF title
# - Mandatory fields present
# - Optional spelling hook (handled at app-level)

def run_core_checks(pages: List[str], meta: Dict[str,Any]) -> List[Dict[str,Any]]:
    findings = []

    # 1) Ensure all required metadata filled
    required = ["client","project","site_type","vendor","supplier","cabinet_location","radio_location","sectors","site_address"]
    missing = [k for k in required if not meta.get(k)]
    if missing:
        findings.append(dict(rule_id="META_MISSING", severity="MAJOR",
                             message=f"Missing required metadata: {', '.join(missing)}",
                             page=1))
        return findings  # stop early

    # 2) Project-specific: if Power Resilience => MIMO optional
    if meta.get("project") == "Power Resilience":
        pass  # no check
    else:
        if not meta.get("mimo_s1"):
            findings.append(dict(rule_id="MIMO_REQUIRED", severity="MINOR",
                                 message="Proposed MIMO Config (S1) must be set unless Project is Power Resilience",
                                 page=1))

    # 3) Site Address must appear in the first page title (unless ", 0 ," present)
    addr = (meta.get("site_address") or "").strip()
    if addr and ", 0 ," not in addr:
        first = pages[0] if pages else ""
        if addr.lower() not in first.lower():
            findings.append(dict(rule_id="ADDR_TITLE_MISMATCH", severity="MAJOR",
                                 message="Site Address does not match the PDF title / first page",
                                 page=1))

    return findings
