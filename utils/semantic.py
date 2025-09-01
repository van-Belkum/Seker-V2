from rapidfuzz import fuzz, process

def fuzzy_contains(haystack: str, needle: str, threshold: int = 80) -> bool:
    hay = haystack.lower()
    ned = needle.lower()
    score = fuzz.partial_ratio(hay, ned)
    return score >= threshold
