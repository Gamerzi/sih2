"""myScheme (myscheme.gov.in) — government scheme discovery.
Live access is UNVERIFIED. Implement fetch_live() once a permitted data source is confirmed."""
from typing import List

from retrievers.base import BaseRetriever


class MySchemeRetriever(BaseRetriever):
    name = "myscheme"
    seed_source = "myScheme"

    def fetch_live(self, profile: dict) -> List[dict]:
        # TODO: query myScheme filtered by state, occupation and category
        return []
