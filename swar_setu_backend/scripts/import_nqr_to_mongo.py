"""Load a real NQR/NSQF export (JSON list or CSV) into MongoDB `qualifications`.
Usage:  python scripts/import_nqr_to_mongo.py path/to/nqr_export.json
Edit FIELD_ALIASES to map your export's column names onto the normalised fields.
Only use data you are permitted to use — verify NQR access terms first."""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from utils import education_rank  # noqa: E402

FIELD_ALIASES = {
    "qualification_title": ["qualification_title", "qualification name", "title", "name"],
    "nsqf_level": ["nsqf_level", "nsqf level", "level"],
    "sector": ["sector", "sector name"],
    "job_role": ["job_role", "job role", "occupation"],
    "eligibility": ["eligibility", "entry qualification", "minimum eligibility"],
    "duration": ["duration", "hours", "course duration"],
    "official_url": ["official_url", "url", "link"],
}


def pick(row: dict, aliases):
    low = {k.lower().strip(): v for k, v in row.items()}
    for a in aliases:
        if a in low and low[a] not in (None, ""):
            return low[a]
    return None


def normalise(row: dict) -> dict:
    out = {k: pick(row, al) for k, al in FIELD_ALIASES.items()}
    out["nsqf_level"] = int(out["nsqf_level"]) if str(out["nsqf_level"] or "").isdigit() else out["nsqf_level"]
    out["min_education_rank"] = education_rank(out.get("eligibility") or "")
    out["keywords"] = []
    out["official_source"] = "NQR"
    out["official_url"] = out.get("official_url") or "https://nqr.gov.in"
    out["is_sample"] = False
    return out


def main(path: str):
    p = Path(path)
    if p.suffix.lower() == ".csv":
        rows = list(csv.DictReader(p.open(encoding="utf-8-sig")))
    else:
        rows = json.loads(p.read_text(encoding="utf-8"))
    docs = [normalise(r) for r in rows if pick(r, FIELD_ALIASES["qualification_title"])]

    from pymongo import ASCENDING, MongoClient
    col = MongoClient(config.MONGODB_URI)[config.MONGODB_DB]["qualifications"]
    col.delete_many({})
    if docs:
        col.insert_many(docs)
    col.create_index([("sector", ASCENDING)])
    col.create_index([("nsqf_level", ASCENDING)])
    print(f"Imported {len(docs)} qualifications into {config.MONGODB_DB}.qualifications")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
