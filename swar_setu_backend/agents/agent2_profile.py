"""AGENT 2 — Profile Builder
Turns the interview transcript into a structured profile, lets the user edit it, and gates the
rest of the pipeline behind an explicit confirmation (human-in-the-loop against voice errors).

Endpoints
  POST /api/profile/build/{session_id}   re-extract profile from transcript
  GET  /api/profile/{session_id}         current profile + missing fields
  PUT  /api/profile/{session_id}         user edits fields  {"fields": {...}}
  POST /api/profile/{session_id}/confirm user confirms -> unlocks Agents 3 & 4
"""
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import llm
from session_store import require_session, store

router = APIRouter(prefix="/api/profile", tags=["Agent 2 - Profile Builder"])

REQUIRED_FIELDS = ["education", "skills", "experience", "district", "state", "work_preference"]
LIST_FIELDS = {"skills", "interests"}
ALLOWED_FIELDS = set(REQUIRED_FIELDS) | {"interests"}
WORK_PREFS = {"employment", "self_employment", "either"}

INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat", "Haryana",
    "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur",
    "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana",
    "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal", "Delhi", "Jammu and Kashmir", "Ladakh",
    "Puducherry", "Chandigarh", "Andaman and Nicobar Islands", "Lakshadweep",
    "Dadra and Nagar Haveli and Daman and Diu",
]

EXTRACT_SYSTEM = """You extract a beneficiary profile from an interview transcript (AI questions, USER answers).
Return ONLY a JSON object with exactly these keys:
  education (string|null), skills (array of strings), experience (string|null),
  district (string|null), state (string|null), interests (array of strings),
  work_preference ("employment" | "self_employment" | "either" | null)
Rules: use ONLY what the USER said. Never guess or fill gaps. Use null / [] when unknown.
Write values in English (translate/transliterate if the user spoke another language)."""


# ---------------------------------------------------------------- helpers
def transcript_text(transcript: List[dict]) -> str:
    return "\n".join(f"{'AI' if t['role'] == 'assistant' else 'USER'}: {t['text']}" for t in transcript)


def _clean_list(v: Any) -> List[str]:
    if isinstance(v, str):
        v = re.split(r"[,;/]| and | और ", v)
    if not isinstance(v, list):
        return []
    seen, out = set(), []
    for x in v:
        x = str(x).strip()
        if x and x.lower() not in seen:
            seen.add(x.lower())
            out.append(x)
    return out


def _normalise(raw: dict) -> dict:
    out: Dict[str, Any] = {}
    for f in ("education", "experience", "district", "state"):
        v = raw.get(f)
        out[f] = str(v).strip() if v not in (None, "", "null") else None
    out["skills"] = _clean_list(raw.get("skills"))
    out["interests"] = _clean_list(raw.get("interests"))
    wp = str(raw.get("work_preference") or "").strip().lower().replace("-", "_").replace(" ", "_")
    out["work_preference"] = wp if wp in WORK_PREFS else None
    return out


# ---------------------------------------------------------------- extraction
def _extract_llm(transcript: List[dict]) -> Optional[dict]:
    data = llm.chat_json(EXTRACT_SYSTEM, transcript_text(transcript))
    return _normalise(data) if isinstance(data, dict) else None


def _match_state(text: str) -> Optional[str]:
    low = text.lower()
    for s in INDIAN_STATES:
        if s.lower() in low:
            return s
    return None


def _extract_fallback(transcript: List[dict]) -> dict:
    """Rule-based extraction, driven by the `field` tag Agent 1 stored on each question."""
    p: Dict[str, Any] = {"education": None, "skills": [], "experience": None, "district": None,
                         "state": None, "interests": [], "work_preference": None}
    for i, turn in enumerate(transcript):
        if turn["role"] != "user":
            continue
        text = turn["text"].strip()
        prev = transcript[i - 1] if i > 0 else {}
        field = prev.get("field") if prev.get("role") == "assistant" else None

        st = _match_state(text)
        if st:
            p["state"] = st

        if field == "education":
            p["education"] = text
        elif field == "skills":
            cleaned = re.sub(r"^(i\s+(know|do|can do|work as|am a|am an)\s+)", "", text, flags=re.I)
            p["skills"] = _clean_list(cleaned)
        elif field == "experience":
            p["experience"] = text
        elif field == "district":
            d = re.sub(r"^(i\s+(am|live)\s+(from|in)\s+|from\s+|in\s+)", "", text, flags=re.I)
            d = d.split(",")[0].strip().title()
            p["district"] = d or None
        elif field == "state" and not st:
            p["state"] = text.title()
        elif field == "work_preference":
            low = text.lower()
            if re.search(r"both|any|either|dono", low):
                p["work_preference"] = "either"
            elif re.search(r"self|own|business|shop|start|apna|sontha", low):
                p["work_preference"] = "self_employment"
            elif re.search(r"job|employ|work for|naukri|udyogam", low):
                p["work_preference"] = "employment"
    return p


# ---------------------------------------------------------------- public API used by Agent 1
def missing_fields(session: dict) -> List[str]:
    prof = session.get("profile", {})
    return [f for f in REQUIRED_FIELDS if not prof.get(f) and f not in session.get("skip", [])]


def update_profile(session: dict) -> dict:
    """Extract from transcript and merge into session['profile'] (never overwrites user edits)."""
    extracted = _extract_llm(session["transcript"]) if llm.llm_available() else None
    if extracted is None:
        extracted = _extract_fallback(session["transcript"])
    prof = session.setdefault("profile", {})
    edited = set(session.get("edited_fields", []))
    for k, v in extracted.items():
        if k in edited or v in (None, "", []):
            continue
        prof[k] = v
    return prof


def profile_payload(session: dict) -> dict:
    return {
        "session_id": session["id"],
        "profile": session.get("profile", {}),
        "missing": missing_fields(session),
        "skipped": session.get("skip", []),
        "confirmed": session.get("profile_confirmed", False),
    }


# ---------------------------------------------------------------- endpoints
class EditRequest(BaseModel):
    fields: Dict[str, Any]


@router.post("/build/{session_id}")
def build(session_id: str):
    s = require_session(session_id)
    update_profile(s)
    store.save(s)
    return profile_payload(s)


@router.get("/{session_id}")
def get_profile(session_id: str):
    return profile_payload(require_session(session_id))


@router.put("/{session_id}")
def edit_profile(session_id: str, req: EditRequest):
    s = require_session(session_id)
    bad = set(req.fields) - ALLOWED_FIELDS
    if bad:
        raise HTTPException(400, f"Unknown fields: {sorted(bad)}. Allowed: {sorted(ALLOWED_FIELDS)}")
    clean = _normalise({**s.get("profile", {}), **req.fields})
    for k in req.fields:
        s["profile"][k] = clean[k]
        if k not in s["edited_fields"]:
            s["edited_fields"].append(k)
        if k in s.get("skip", []) and clean[k]:
            s["skip"].remove(k)
    s["profile_confirmed"] = False  # any edit requires re-confirmation
    store.save(s)
    return profile_payload(s)


@router.post("/{session_id}/confirm")
def confirm(session_id: str):
    s = require_session(session_id)
    if not s.get("profile", {}).get("skills"):
        raise HTTPException(409, "Profile needs at least one skill before it can be confirmed.")
    s["profile_confirmed"] = True
    store.save(s)
    return profile_payload(s)
