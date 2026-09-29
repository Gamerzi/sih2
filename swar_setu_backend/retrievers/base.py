"""Common base for the four source retrievers.

Each retriever = one official source. Implement `fetch_live(profile)` to call the real source.
Until that exists, `fetch_seed(profile)` serves entries from data/opportunities_seed.json so the
whole pipeline is testable. Every retriever returns records in ONE normalised shape."""
import json
from functools import lru_cache
from typing import List

import config

NORMALISED_KEYS = ["title", "type", "location", "state", "district", "description", "eligibility",
                   "skill_tags", "source", "source_url", "application_url", "is_sample"]


@lru_cache(maxsize=1)
def load_seed() -> List[dict]:
    with open(config.DATA_DIR / "opportunities_seed.json", encoding="utf-8") as f:
        return json.load(f)


def normalise(raw: dict, source: str) -> dict:
    state, district = raw.get("state", "") or "", raw.get("district", "") or ""
    out = {
        "title": raw.get("title", "").strip(),
        "type": raw.get("type", "scheme"),      # job | self_employment | scheme | business_support | training | state_portal
        "state": state,
        "district": district,
        "location": raw.get("location") or ", ".join(x for x in (district, state) if x) or "All India",
        "description": raw.get("description", ""),
        "eligibility": raw.get("eligibility", ""),
        "skill_tags": [t.lower() for t in raw.get("skill_tags", [])],
        "source": raw.get("source", source),
        "source_url": raw.get("source_url", ""),
        "application_url": raw.get("application_url", ""),
        "is_sample": bool(raw.get("is_sample", False)),
    }
    return out


class BaseRetriever:
    name = "base"
    seed_source = ""            # value of the "source" field in opportunities_seed.json

    def fetch_live(self, profile: dict) -> List[dict]:
        """TODO per source: call the official API / permitted feed and return raw dicts."""
        return []

    def fetch_seed(self, profile: dict) -> List[dict]:
        return [r for r in load_seed() if r.get("source") == self.seed_source]

    def search(self, profile: dict) -> List[dict]:
        try:
            raw = self.fetch_live(profile)
        except Exception as e:  # noqa: BLE001
            print(f"[{self.name}] live fetch failed, using seed: {e}")
            raw = []
        if not raw:
            raw = self.fetch_seed(profile)
        return [normalise(r, self.seed_source or self.name) for r in raw]
