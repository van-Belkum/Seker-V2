import os, io, re, json, hashlib
from typing import Dict, Any, List
import yaml
import fitz  # PyMuPDF
from rapidfuzz import fuzz, process

RULES_DIR = "rules"
HISTORY_DIR = os.path.join("data","history")
PARSED_DIR = os.path.join(RULES_DIR, "parsed")
os.makedirs(RULES_DIR, exist_ok=True)
os.makedirs(HISTORY_DIR, exist_ok=True)
os.makedirs(PARSED_DIR, exist_ok=True)

def _extract_text_from_pdf_bytes(pdf_bytes: bytes) -> List[Dict[str, Any]]:
    pages = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for i, page in enumerate(doc):
        text = page.get_text("text") or ""
        pages.append({"page": i+1, "text": text})
    doc.close()
    return pages

def _load_mapping():
    fn = os.path.join(RULES_DIR, "mapping.yaml")
    if not os.path.exists(fn):
        return {"mappings":[]}
    return yaml.safe_load(open(fn,"r")) or {"mappings":[]}

def load_active_rules_for_meta(meta: Dict[str, Any]) -> Dict[str, Any]:
    """Return merged rules based on mapping: client/project/site_type."""
    mapping = _load_mapping().get("mappings",[])
    selected_files = []
    for m in mapping:
        if m.get("client")==meta.get("client"):
            if (not m.get("projects")) or (meta.get("project") in m.get("projects")):
                if (not m.get("site_types")) or (meta.get("site_type") in m.get("site_types")):
                    rf = m.get("rules_file")
                    if rf and os.path.exists(rf):
                        selected_files.append(rf)
    merged = {"rules":[]}
    for rf in selected_files:
        data = yaml.safe_load(open(rf,"r")) or {}
        merged["rules"].extend(data.get("rules", []))
    merged["__extracted_text"] = []  # caller fills later
    return merged

def _match_rule(page_text: str, rule: Dict[str, Any], meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    hits=[]
    title = rule.get("title","Rule")
    reason = rule.get("reason","")
    severity = rule.get("severity","minor")
    must = rule.get("must_contain")
    must_regex = rule.get("must_regex")
    must_not = rule.get("must_not_contain")

    gates = rule.get("when", {})
    for k,v in gates.items():
        if v and str(meta.get(k,"")) not in ([v] if isinstance(v,str) else v):
            return []

    if must:
        if all(s.lower() in page_text.lower() for s in ([must] if isinstance(must,str) else must)):
            pass
        else:
            hits.append({"title": title, "reason": f"Missing required text: {must}", "severity": severity})
    if must_regex:
        pattern = re.compile(must_regex, flags=re.IGNORECASE|re.MULTILINE)
        if not pattern.search(page_text):
            hits.append({"title": title, "reason": f"Regex not found: {must_regex}", "severity": severity})
    if must_not:
        if any(s.lower() in page_text.lower() for s in ([must_not] if isinstance(must_not,str) else must_not)):
            hits.append({"title": title, "reason": f"Forbidden text present: {must_not}", "severity": severity})

    return hits

def run_rule_checks(pages_text: List[Dict[str,Any]], meta: Dict[str,Any], rules_doc: Dict[str,Any]) -> List[Dict[str,Any]]:
    if not pages_text:
        pdf_bytes = meta.get("__pdf_bytes")
        if pdf_bytes:
            pages_text = _extract_text_from_pdf_bytes(pdf_bytes)
        else:
            return []

    findings=[]
    for p in pages_text:
        txt = p["text"]
        for rule in rules_doc.get("rules",[]):
            for hit in _match_rule(txt, rule, meta):
                hit["page"] = p["page"]
                hit["title"] = hit.get("title") or rule.get("title","Rule")
                hit["snippet"] = (txt[:120] + "...") if len(txt)>120 else txt
                findings.append(hit)

    sa = meta.get("site_address","").strip()
    if sa and ", 0 ," not in sa:
        title_like = " ".join([p["text"].splitlines()[0] if p["text"] else "" for p in pages_text[:2]])
        if sa.lower() not in title_like.lower():
            findings.append({
                "title":"Site Address mismatch",
                "reason": "Site address does not appear in the drawing title area.",
                "severity":"major",
                "page":1
            })

    return findings

def merge_feedback_into_rules(meta: Dict[str,Any], feedback_rows: List[Dict[str,Any]]) -> int:
    os.makedirs(RULES_DIR, exist_ok=True)
    custom_fn = os.path.join(RULES_DIR,"custom.yaml")
    doc = {"rules":[]}
    if os.path.exists(custom_fn):
        doc = yaml.safe_load(open(custom_fn,"r")) or {"rules":[]}

    add_count=0
    for r in feedback_rows:
        verdict = (r.get("verdict") or "").strip().lower()
        ru = (r.get("rule_update") or "").strip()
        f = r.get("finding",{})
        if verdict == "not valid":
            fp = hashlib.sha1((f.get("title","")+f.get("reason","")).encode()).hexdigest()
            doc["rules"].append({
                "title": f"Ignore finding {fp}",
                "reason": "Auto-ignore trained",
                "severity":"minor",
                "must_not_contain": None,
                "ignore_fingerprint": fp
            })
            add_count += 1
        elif verdict == "valid" and ru:
            doc["rules"].append({
                "title": "User-added rule",
                "reason": ru,
                "severity":"major",
                "must_contain": None,
                "must_regex": None,
                "when": {
                    "client": meta.get("client"),
                    "project": meta.get("project"),
                    "site_type": meta.get("site_type"),
                }
            })
            add_count += 1

    with open(custom_fn,"w") as f:
        yaml.safe_dump(doc, f, sort_keys=False)
    return add_count
