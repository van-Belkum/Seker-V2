# Simple placeholder spell-check.
# Replace with 'pyspellchecker' or your preferred library for production.
import re

COMMON_WORDS = set("""project north arrow antenna heights label address site drawing mimo sector power resilience
acceptance accepted rejected valid invalid unique coverage low level midway high template general title block
alpha queen king road street ms6 msv ga dd access ran supplier reviewer template metadata radio
""".split())

def tokenize(text: str):
    return re.findall(r"[A-Za-z']{3,}", text or "")

def basic_spelling_issues(*texts):
    issues = []
    for t in texts:
        for w in tokenize(t.lower()):
            if w not in COMMON_WORDS and not w.isdigit():
                # Heuristic: flag rare-looking tokens (very naive)
                if len(w) > 15:
                    issues.append((w, "suspiciously long"))
    return issues
