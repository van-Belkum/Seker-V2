
from rapidfuzz import fuzz

def fuzzy_terms(text: str, terms):
    text_l = text.lower()
    out = []
    for t in terms:
        t = t.lower()
        if t in text_l:
            out.append((t, 1.0))
        else:
            score = fuzz.partial_ratio(t, text_l[:20000])/100.0
            if score > 0.9:
                out.append((t, score))
    return out

def simple_highlight(text: str, term: str) -> str:
    i = text.lower().find(term.lower())
    if i < 0:
        return text[:240]
    start = max(0, i-80)
    end = min(len(text), i+160)
    return text[start:end].replace("\n"," ")
