\
import re, os, yaml
from typing import Dict, Any, List
from .spell_tools import spelling_findings

def load_yaml(path: str) -> Dict[str,Any]:
    if not os.path.exists(path):
        return {}
    with open(path,"r",encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def save_yaml(path: str, data: Dict[str,Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path,"w",encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)

def context_key(meta: Dict[str,str], keys: List[str]) -> str:
    vals = [meta.get(k,"").strip() for k in keys]
    return " | ".join(vals)

def merge_rules(*dicts: Dict[str,Any]) -> Dict[str,Any]:
    out = {"policies":[]}
    for d in dicts:
        if not d: 
            continue
        out["policies"].extend(d.get("policies",[]))
    return out

def run_rule_engine(pages: List[str], meta: Dict[str,str], rules: Dict[str,Any], guidance_index, learned: Dict[str,Any]) -> List[Dict[str,Any]]:
    txt_all = "\n".join(pages)
    findings: List[Dict[str,Any]] = []

    # address rule (global flag in policies)
    for pol in rules.get("policies", []):
        trig = pol.get("trigger", {})
        if not _trigger_ok(meta, trig):
            continue

        # title contains site address
        if pol.get("title_must_contain_site_address"):
            site_addr = meta.get("site_address","").strip()
            if site_addr and ", 0 ," not in site_addr:
                title_text = pages[0] if pages else ""
                if site_addr.upper() not in title_text.upper():
                    findings.append({
                        "severity": pol.get("severity","major"),
                        "message": "Site Address not present in title block.",
                        "page": 1,
                        "type": "address"
                    })

        # forbidden regex
        for rx in pol.get("forbid_regex", []):
            try:
                if re.search(rx, txt_all):
                    findings.append({
                        "severity": pol.get("severity","major"),
                        "message": f"Forbidden pattern matched: {rx}",
                        "page": None,
                        "type": "regex",
                        "evidence_text": rx
                    })
            except re.error:
                pass

        # require any of terms in PDF text
        req_any = pol.get("require_any_pdf_text", [])
        if req_any:
            present = any(t.upper() in txt_all.upper() for t in req_any)
            if not present:
                findings.append({
                    "severity": pol.get("severity","minor"),
                    "message": pol.get("name","Policy unmet: require_any_pdf_text"),
                    "page": None,
                    "type": "require_any",
                    "required_terms": req_any
                })

        # guidance terms (for cross-reference hinting)
        # This does not fail the design; it attaches evidence paths.
        g_terms = pol.get("guidance_terms", [])
        if guidance_index and g_terms:
            # scoring occurs in app (we just note terms wanted)
            pass

    # spelling with allowlist
    allow_words = set()
    ctx_keys = learned.get("context_keys", ["client","project","vendor","site_type"])
    key = context_key(meta, ctx_keys)
    allow_words.update(set((learned.get("allow_words", {}) or {}).get(key, [])))
    findings.extend(spelling_findings(txt_all, allow_words))

    return findings

def _trigger_ok(meta: Dict[str,str], trig: Dict[str,Any]) -> bool:
    for k, v in trig.items():
        val = (meta.get(k,"") or "").strip()
        if isinstance(v, list):
            if val not in v:
                return False
        elif isinstance(v, str):
            if val != v:
                return False
    return True
