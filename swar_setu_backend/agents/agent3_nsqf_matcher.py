"""AGENT 3 — NQR / NSQF Qualification Matcher
Takes the CONFIRMED profile and returns the most relevant qualifications from the normalised NQR data.
Ranking is deterministic keyword/field scoring — NOT LLM output. The LLM only explains the results.

Rules kept from the project brief:
  * education is NOT treated as an NSQF level; it is only compared with each qualification's own
    stated minimum eligibility.
  * only fields relevant to matching are used (skills, interests, education, work preference).

Endpoint
  POST /api/nsqf/match   {"session_id": "...", "top_k": 5}
"""
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import llm
from nqr_repository import nqr_repo
from session_store import require_session, store
from utils import education_rank, expand_tokens, language_name, tokens

router = APIRouter(prefix="/api/nsqf", tags=["Agent 3 - NQR/NSQF Matcher"])

W_TITLE, W_ROLE, W_SECTOR, W_KEYWORDS = 3, 3, 2, 2


def match_qualifications(profile: dict, top_k: int = 5) -> dict:
    skills = profile.get("skills") or []
    interests = profile.get("interests") or []
    user_tokens = expand_tokens(tokens(" ".join(skills + interests)))
    if not user_tokens:
        return {"matches": [], "ineligible_skipped": 0, "note": "No skills in profile to match on."}

    edu = education_rank(profile.get("education") or "")
    self_emp = profile.get("work_preference") == "self_employment"

    scored, skipped = [], 0
    for q in nqr_repo.all():
        min_rank = q.get("min_education_rank")
        if edu is not None and min_rank is not None and min_rank > edu:
            skipped += 1
            continue

        score, reasons = 0, []
        for field, weight in (("qualification_title", W_TITLE), ("job_role", W_ROLE), ("sector", W_SECTOR)):
            hit = tokens(q.get(field, "")) & user_tokens
            if hit:
                score += weight * len(hit)
                reasons.append(f"{field.replace('_', ' ')} matches: {', '.join(sorted(hit))}")
        kw_hit = tokens(" ".join(q.get("keywords", []))) & user_tokens
        if kw_hit:
            score += W_KEYWORDS * len(kw_hit)
            reasons.append(f"keywords match: {', '.join(sorted(kw_hit))}")
        if score and self_emp and "self" in (q.get("job_role", "") + " ".join(q.get("keywords", []))).lower():
            score += 2
            reasons.append("suits your self-employment preference")
        if score:
            scored.append({**q, "score": score, "match_reasons": reasons,
                           "eligibility_checked": edu is not None and min_rank is not None})

    scored.sort(key=lambda r: (-r["score"], -(r.get("nsqf_level") or 0)))
    return {"matches": scored[:top_k], "ineligible_skipped": skipped, "note": None}


def _fallback_text(matches: List[dict]) -> str:
    if not matches:
        return "I could not find a matching qualification for your skills yet."
    names = ", ".join(m["qualification_title"] for m in matches[:3])
    return f"Based on your skills, these qualifications may help you grow: {names}. Details are on your screen."


class MatchRequest(BaseModel):
    session_id: str
    top_k: int = 5


@router.post("/match")
def match(req: MatchRequest):
    s = require_session(req.session_id)
    if not s.get("profile_confirmed"):
        raise HTTPException(409, "Profile must be confirmed (POST /api/profile/{id}/confirm) before matching.")

    result = match_qualifications(s["profile"], top_k=max(1, min(req.top_k, 10)))
    matches = result["matches"]
    slim = [{k: m[k] for k in ("qualification_title", "nsqf_level", "sector", "eligibility", "duration")} for m in matches]
    explanation = llm.grounded_explain(
        "Explain in simple words which of these qualifications suit the user and why.",
        {"skills": s["profile"].get("skills"), "qualifications": slim},
        language_name(s["language"]),
        _fallback_text(matches),
    )
    s["qualifications"] = matches
    store.save(s)
    return {
        "session_id": s["id"],
        "qualifications": matches,
        "explanation": explanation,
        "ineligible_skipped": result["ineligible_skipped"],
        "note": result["note"],
        "data_source": nqr_repo.source,          # "sample" until real NQR data is loaded
        "contains_sample_data": any(m.get("is_sample") for m in matches),
    }
