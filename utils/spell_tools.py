\
import re
from typing import List, Dict, Any, Set

def spelling_findings(text: str, allow: Set[str]) -> List[Dict[str,Any]]:
    try:
        from spellchecker import SpellChecker
    except Exception:
        return []
    sp = SpellChecker(language="en")
    words = re.findall(r"[A-Za-z]{3,}", text)
    out = []
    seen = set()
    for w in set(w.lower() for w in words):
        if w in allow:
            continue
        if w not in sp and w not in seen:
            sug = next(iter(sp.candidates(w)), None)
            seen.add(w)
            out.append({
                "severity":"minor",
                "message": f"Possible misspelling: '{w}' → '{sug}'" if sug else f"Unknown term: '{w}'",
                "page": None,
                "type": "spelling",
                "evidence_text": w
            })
    return out
