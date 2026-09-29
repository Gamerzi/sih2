"""National Career Service (ncs.gov.in) — employment listings.
Live access method / API terms are UNVERIFIED. Implement fetch_live() once confirmed."""
from typing import List

from retrievers.base import BaseRetriever


class NCSRetriever(BaseRetriever):
    name = "ncs"
    seed_source = "NCS"

    def fetch_live(self, profile: dict) -> List[dict]:
        # TODO: query NCS for profile["skills"] filtered by state/district and return raw dicts
        return []
