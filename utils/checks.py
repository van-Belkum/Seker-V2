import re, os
from rapidfuzz import fuzz

def site_address_in_title(meta, pdf_name) -> list[dict]:
    addr = (meta.get("site_address") or "").strip()
    if not addr or ", 0 ," in addr:
        return []
    ok = addr.lower().replace(" ", "")
    name = (pdf_name or "").lower().replace(" ", "")
    if ok in name or fuzz.partial_ratio(addr.lower(), pdf_name.lower()) >= 90:
        return []
    return [{
        "rule": "site_address_mismatch",
        "severity": "Major",
        "page": 1,
        "snippet": f"Site Address '{addr}' not found in PDF name",
        "comment": "Filename must contain the site address (ignoring spaces).",
    }]

def power_resilience_hides_mimo(meta) -> list[dict]:
    # Reserved for future logic
    return []

def gps_eltek_note(meta, pages_text) -> list[dict]:
    if (meta.get("project") or "").lower() != "power resilience":
        return []
    want = "eltek psu"
    want2 = "tdee53201"
    hit = any((want in p.lower() and want2 in p.lower()) for p in pages_text)
    if hit:
        return []
    return [{
        "rule": "eltek_power_res_note_missing",
        "severity": "Major",
        "page": 1,
        "snippet": "Required Eltek PSU configuration note not found.",
        "comment": "Add note: 'To support the power resilience configure settings the Eltek PSU will need to be configured as per TDEE53201 section 3.8.1'.",
    }]

def spelling_findings(pages_text, allow_words: set):
    try:
        from spellchecker import SpellChecker
    except Exception:
        return [{"rule":"spellcheck_unavailable","severity":"Minor","page":1,
                 "snippet":"Spellchecker module not installed.",
                 "comment":"Install pyspellchecker to enable spelling checks."}]
    sp = SpellChecker()
    out=[]
    for i, t in enumerate(pages_text, start=1):
        words = re.findall(r"[A-Za-z]{3,}", t)
        miss = [w for w in sp.unknown(w.lower() for w in words) if w.lower() not in allow_words]
        for w in miss[:50]:
            sug = next(iter(sp.candidates(w)), None)
            out.append({
                "rule":"spelling",
                "severity":"Minor",
                "page": i,
                "snippet": w,
                "comment": f"Possible misspelling. Suggestion: {sug}" if sug else "Possible misspelling."
            })
    return out

def apply_learning_overrides(findings, learning_df, meta):
    if learning_df is None or learning_df.empty:
        return findings
    keep=[]
    for f in findings:
        mask = (
            (learning_df["rule"]==f["rule"]) &
            (learning_df["snippet"].fillna("")==f.get("snippet","")) &
            (learning_df["client"]==meta.get("client")) &
            (learning_df["project"]==meta.get("project")) &
            (learning_df["site_type"]==meta.get("site_type")) &
            (learning_df["vendor"]==meta.get("vendor"))
        )
        rows = learning_df[mask]
        if not rows.empty and rows.iloc[-1]["verdict"]=="Invalid":
            continue
        keep.append(f)
    return keep
