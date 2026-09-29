"""State employment portals. Every state differs (interface, data format, API), so this module keeps a
state -> portal map (data/state_portals.json) and returns a pointer to the user's state portal.
Add a dedicated fetch_live() per state as each portal is individually verified."""
import json
from typing import List

import config
from retrievers.base import BaseRetriever


class StatePortalRetriever(BaseRetriever):
    name = "state_portal"
    seed_source = "State Portal"

    def fetch_live(self, profile: dict) -> List[dict]:
        # TODO: state-specific adapters (e.g. Telangana) once each portal is verified
        return []

    def fetch_seed(self, profile: dict) -> List[dict]:
        state = (profile.get("state") or "").strip()
        with open(config.DATA_DIR / "state_portals.json", encoding="utf-8") as f:
            portals = json.load(f)
        url = next((u for s, u in portals.items() if s.lower() == state.lower()), None)
        if not url:
            return []
        skills = ", ".join(profile.get("skills") or []) or "your skill"
        return [{
            "title": f"{state} government employment & skill resources",
            "type": "state_portal",
            "state": state,
            "district": "",
            "description": f"Official {state} portal. Look here for state-level jobs, skilling and welfare programmes for {skills}. "
                           "This is a pointer only; a state-specific listing retriever has not been built yet.",
            "eligibility": "Varies",
            "skill_tags": [],
            "source": "State Portal",
            "source_url": url,
            "application_url": "",
            "is_sample": False,
        }]
