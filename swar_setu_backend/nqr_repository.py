"""Access layer for the normalised NQR/NSQF qualification records.
Reads from MongoDB collection `qualifications` when MONGODB_URI is set (load it with
scripts/import_nqr_to_mongo.py), otherwise from data/nqr_sample.json.
data/nqr_sample.json is PLACEHOLDER data (is_sample=true) — replace it with a real, permitted NQR export."""
import json
from typing import List, Optional

import config


class NQRRepository:
    def __init__(self):
        self._cache: Optional[List[dict]] = None
        self.source = "sample"

    def all(self) -> List[dict]:
        if self._cache is None:
            self._cache = self._load()
        return self._cache

    def _load(self) -> List[dict]:
        if config.MONGODB_URI:
            try:
                from pymongo import MongoClient
                col = MongoClient(config.MONGODB_URI, serverSelectionTimeoutMS=3000)[config.MONGODB_DB]["qualifications"]
                rows = list(col.find({}, {"_id": 0}))
                if rows:
                    self.source = "mongodb"
                    return rows
                print("[nqr] MongoDB collection empty, using sample file")
            except Exception as e:  # noqa: BLE001
                print(f"[nqr] MongoDB unavailable, using sample file: {e}")
        with open(config.DATA_DIR / "nqr_sample.json", encoding="utf-8") as f:
            self.source = "sample"
            return json.load(f)


nqr_repo = NQRRepository()
