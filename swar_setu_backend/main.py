"""Swar Setu backend entry point.  Run:  uvicorn main:app --reload --port 8000
Pure JSON API — it serves no HTML, so your Vercel frontend is untouched. Point the frontend's
fetch() calls at this server's URL and add the frontend origin to ALLOWED_ORIGINS."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
import llm
from agents import agent1_interview, agent2_profile, agent3_nsqf_matcher, agent4_livelihood
from nqr_repository import nqr_repo
from session_store import require_session

app = FastAPI(title="Swar Setu Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agent1_interview.router)
app.include_router(agent2_profile.router)
app.include_router(agent3_nsqf_matcher.router)
app.include_router(agent4_livelihood.router)


@app.get("/health")
def health():
    return {"status": "ok", "llm_enabled": llm.llm_available(), "model": config.LLM_MODEL,
            "nqr_records": len(nqr_repo.all()), "nqr_source": nqr_repo.source}


@app.get("/api/session/{session_id}")
def get_session(session_id: str):
    """Full journey state, handy for reloading the frontend mid-way."""
    return require_session(session_id)
