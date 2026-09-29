"""Small shared helpers: language names, education parsing, tokenising, skill synonyms."""
import re

LANGUAGE_NAMES = {
    "en": "English", "hi": "Hindi", "te": "Telugu", "ta": "Tamil", "kn": "Kannada",
    "ml": "Malayalam", "mr": "Marathi", "bn": "Bengali", "gu": "Gujarati",
    "pa": "Punjabi", "od": "Odia",
}


def language_name(code: str) -> str:
    return LANGUAGE_NAMES.get((code or "en").lower(), "English")


# ---------- education ----------
_WORD_NUM = {"fifth": 5, "eighth": 8, "tenth": 10, "twelfth": 12, "matric": 10,
             "ssc": 10, "hsc": 12, "intermediate": 12}


def education_rank(text: str):
    """Rough schooling rank used ONLY to check a qualification's stated eligibility.
    It is never treated as an NSQF level. Returns None if it cannot tell."""
    t = (text or "").lower()
    if not t.strip():
        return None
    if re.search(r"illiterate|no education|never (went|attended)|unlettered|not studied", t):
        return 0
    if re.search(r"post ?graduate|master|m\.?tech|mba|m\.?sc|\bm\.?a\b", t):
        return 17
    if re.search(r"graduate|degree|b\.?tech|b\.?sc|b\.?com|\bb\.?a\b|bachelor|engineering", t):
        return 15
    if "diploma" in t or "polytechnic" in t:
        return 13
    if re.search(r"\biti\b", t):
        return 12
    for w, n in _WORD_NUM.items():
        if w in t:
            return n
    m = re.search(r"(\d{1,2})", t)
    if m and 1 <= int(m.group(1)) <= 12:
        return int(m.group(1))
    return None


# ---------- tokens & synonyms ----------
_STOP = {"the", "and", "for", "with", "have", "know", "can", "how", "very", "some", "work",
         "job", "years", "year", "experience", "about", "from", "that", "this", "your", "are"}


def tokens(text: str) -> set:
    return {w for w in re.findall(r"[a-z]{3,}", (text or "").lower()) if w not in _STOP}


SYNONYM_GROUPS = [
    {"tailor", "tailoring", "stitching", "sewing", "garment", "apparel", "fashion", "dressmaking", "darzi", "embroidery"},
    {"electrician", "electrical", "wiring", "electronics"},
    {"plumber", "plumbing", "pipe", "sanitary"},
    {"mobile", "phone", "smartphone", "repair", "technician"},
    {"retail", "sales", "shop", "salesperson", "store"},
    {"beauty", "beautician", "salon", "parlour", "parlor", "makeup", "hair", "barber"},
    {"dairy", "cattle", "milk", "farming", "farmer", "agriculture", "crop", "livestock"},
    {"food", "cooking", "cook", "chef", "catering", "bakery", "processing"},
    {"computer", "data", "entry", "typing", "office", "clerk"},
    {"carpenter", "carpentry", "wood", "furniture"},
    {"mason", "masonry", "construction", "building", "bricklayer"},
    {"driver", "driving", "vehicle", "auto", "mechanic"},
]


def expand_tokens(toks: set) -> set:
    out = set(toks)
    for grp in SYNONYM_GROUPS:
        if out & grp:
            out |= grp
    return out
