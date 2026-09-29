"""Session storage. In-memory by default; uses MongoDB (collection `sessions`) if MONGODB_URI is set.
One session = one beneficiary journey (transcript -> profile -> qualifications -> opportunities)."""
import time
import uuid
from typing import Optional

from fastapi import HTTPException

import config


class SessionStore:
    def __init__(self):
        self._mem: dict = {}
        self._col = None
        if config.MONGODB_URI:
            try:
                from pymongo import MongoClient
                self._col = MongoClient(config.MONGODB_URI, serverSelectionTimeoutMS=3000)[config.MONGODB_DB]["sessions"]
                self._col.database.client.admin.command("ping")
                print("[store] using MongoDB")
            except Exception as e:  # noqa: BLE001
                print(f"[store] MongoDB unavailable, falling back to memory: {e}")
                self._col = None

    def create(self, language: str = "en") -> dict:
        s = {
            "id": uuid.uuid4().hex,
            "language": language,
            "created_at": time.time(),
            "transcript": [],          # [{"role": "assistant"|"user", "text": str, "field": str|None}]
            "profile": {},
            "edited_fields": [],       # fields the user edited by hand; never overwritten by AI
            "skip": [],                # fields the user could not/would not answer
            "ask_count": {},
            "interview_done": False,
            "profile_confirmed": False,
            "qualifications": [],
            "opportunities": [],
        }
        self.save(s)
        return s

    def get(self, sid: str) -> Optional[dict]:
        if self._col is not None:
            doc = self._col.find_one({"_id": sid})
            if doc:
                doc.pop("_id", None)
            return doc
        return self._mem.get(sid)

    def save(self, session: dict) -> None:
        if self._col is not None:
            self._col.replace_one({"_id": session["id"]}, {**session, "_id": session["id"]}, upsert=True)
        else:
            self._mem[session["id"]] = session


store = SessionStore()


def require_session(sid: str) -> dict:
    s = store.get(sid)
    if not s:
        raise HTTPException(status_code=404, detail="Unknown session_id. Call /api/interview/start first.")
    return s
