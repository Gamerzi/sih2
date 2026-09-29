"""AGENT 4 — Local Livelihood / Opportunity Finder
Targeted retrieval (not open browsing):  retrieve -> normalise -> filter -> verify -> rank -> explain.
Runs the four source retrievers in parallel, keeps only records that carry a source link, filters by
skill + location, ranks by the user's employment / self-employment preference.

If no direct job listing exists (typical for villages), schemes / self-employment / MSME support are
returned and clearly labelled by `type`.

Endpoint
  POST /api/opportunities/find   {"session_id": "..."}
"""
from concurrent.futures import ThreadPoolExecutor
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import llm
from retrievers.myscheme_retriever import MySchemeRetriever
from retrievers.ncs_retriever import NCSRetriever
from retrievers.state_portal_retriever import StatePortalRetriever
from retrievers.udyam_retriever import UdyamRetriever
from session_store import require_session, store
from utils import expand_tokens, language_name, tokens

router = APIRouter(prefix="/api/opportunities", tags=["Agent 4 - Livelihood Finder"])

RETRIEVERS = [NCSRetriever(), StatePortalRetriever(), UdyamRetriever(), MySchemeRetriever()]

EMPLOYMENT_TYPES = {"job", "state_portal", "training"}
SELF_TYPES = {"self_employment", "business_support", "scheme", "training"}
TOP_N = 10


def _same(a: str, b: str) -> bool:
    return bool(a) and bool(b) and a.strip().lower() == b.strip().lower()


def _rank(opps: List[dict], profile: dict, skill_tokens: set) -> List[dict]:
    state, district = profile.get("state") or "", profile.get("district") or ""
    pref = profile.get("work_preference")
    kept = []
    for o in opps:
        if not o["source_url"]:                                   # VERIFY: no source link -> drop
            continue
        tags = set(o["skill_tags"])
        if tags and not (tags & skill_tokens):                    # skill filter (empty tags = applies to all)
            continue
        if o["state"] and o["state"].lower() != "all india" and not _same(o["state"], state):
            continue                                              # location filter
        score, why = 0, []
        if tags & skill_tokens:
            score += 3; why.append("matches your skill")
        if _same(o["district"], district):
            score += 2; why.append("in your district")
        elif _same(o["state"], state):
            score += 1; why.append("in your state")
        if pref == "self_employment" and o["type"] in SELF_TYPES:
            score += 2; why.append("fits self-employment")
        elif pref == "employment" and o["type"] in EMPLOYMENT_TYPES:
            score += 2; why.append("fits a job search")
        kept.append({**o, "score": score, "match_reasons": why})
    kept.sort(key=lambda r: -r["score"])
    return kept


def find_opportunities(profile: dict, qualification_titles: List[str] = None) -> dict:
    skill_tokens = expand_tokens(tokens(" ".join((profile.get("skills") or []) + (qualification_titles or []))))

    status, collected = {}, []
    with ThreadPoolExecutor(max_workers=len(RETRIEVERS)) as ex:
        futures = {r.name: ex.submit(r.search, profile) for r in RETRIEVERS}
    for name, fut in futures.items():
        try:
            rows = fut.result()
            collected.extend(rows)
            status[name] = {"ok": True, "count": len(rows)}
        except Exception as e:  # noqa: BLE001  one failing source must not break the pipeline
            status[name] = {"ok": False, "error": str(e)}

    seen, unique = set(), []
    for o in collected:
        key = (o["title"].lower(), o["source_url"])
        if key not in seen:
            seen.add(key)
            unique.append(o)

    ranked = _rank(unique, profile, skill_tokens)[:TOP_N]

    notes = ["Always confirm eligibility and dates on the official source before applying."]
    if not any(o["type"] == "job" for o in ranked):
        notes.append("No direct job listings found for your area; showing schemes and self-employment support instead.")
    if any(o["is_sample"] for o in ranked):
        notes.append("Some results are placeholder sample listings because live source retrievers are not connected yet.")
    return {"opportunities": ranked, "source_status": status, "notes": notes}


def _fallback_text(opps: List[dict]) -> str:
    if not opps:
        return "I could not find matching opportunities yet."
    return "I found options for you, such as: " + ", ".join(o["title"] for o in opps[:3]) + ". Full details and links are on your screen."


class FindRequest(BaseModel):
    session_id: str


@router.post("/find")
def find(req: FindRequest):
    s = require_session(req.session_id)
    if not s.get("profile_confirmed"):
        raise HTTPException(409, "Profile must be confirmed before searching for opportunities.")

    titles = [q["qualification_title"] for q in s.get("qualifications", [])[:3]]
    result = find_opportunities(s["profile"], titles)
    opps = result["opportunities"]
    slim = [{k: o[k] for k in ("title", "type", "location", "eligibility", "source")} for o in opps[:5]]
    explanation = llm.grounded_explain(
        "Tell the user in simple words what these livelihood options are and which type each one is (job, scheme, self-employment).",
        {"preference": s["profile"].get("work_preference"), "opportunities": slim, "notes": result["notes"]},
        language_name(s["language"]),
        _fallback_text(opps),
    )
    s["opportunities"] = opps
    store.save(s)
    return {"session_id": s["id"], "explanation": explanation, **result}
