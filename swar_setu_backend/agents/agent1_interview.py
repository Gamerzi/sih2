"""AGENT 1 — Voice Interview / Question Generator
Asks ONE short question at a time, in the user's language. After every answer it asks Agent 2 to
re-extract the profile, works out which fields are still missing, and generates the next question.
The interview ends when nothing required is missing (or the turn cap is hit).

Speech-to-text / text-to-speech stay in the frontend (or Sarvam later): this file is text in, text out.

Endpoints
  POST /api/interview/start    {"language": "te"}            -> session_id + first question
  POST /api/interview/answer   {"session_id", "message"}     -> next question | done
"""
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

import config
import llm
from agents import agent2_profile as profile_agent
from session_store import require_session, store
from utils import language_name

router = APIRouter(prefix="/api/interview", tags=["Agent 1 - Interview"])

FIELD_HINTS = {
    "education": "their education / highest class passed",
    "skills": "the skills or trades they already know",
    "experience": "how much work experience they have in that skill",
    "district": "which district they live in",
    "state": "which state they live in",
    "work_preference": "whether they prefer a job (employment) or their own work/business (self-employment)",
}

GREETING = {
    "en": "Namaste! I am Swar Setu. I will ask a few simple questions. ",
    "hi": "नमस्ते! मैं स्वर सेतु हूँ। मैं आपसे कुछ आसान सवाल पूछूँगा। ",
    "te": "నమస్తే! నేను స్వర సేతు. మీకు కొన్ని సులభమైన ప్రశ్నలు అడుగుతాను. ",
}

FALLBACK_QUESTIONS = {
    "en": {
        "education": "What is your education? For example, which class have you passed?",
        "skills": "What skills or work do you know?",
        "experience": "How much experience do you have in that work?",
        "district": "Which district do you live in?",
        "state": "Which state do you live in?",
        "work_preference": "Do you want a job, or to start your own work?",
    },
    "hi": {
        "education": "आपकी पढ़ाई कितनी है?",
        "skills": "आपके पास कौन-कौन से हुनर या काम का ज्ञान है?",
        "experience": "उस काम का आपको कितना अनुभव है?",
        "district": "आप किस जिले से हैं?",
        "state": "आप किस राज्य में रहते हैं?",
        "work_preference": "क्या आप नौकरी करना चाहते हैं या अपना काम शुरू करना चाहते हैं?",
    },
    "te": {
        "education": "మీ చదువు ఎంత?",
        "skills": "మీకు ఏ నైపుణ్యాలు లేదా పనులు తెలుసు?",
        "experience": "ఆ పనిలో మీకు ఎంత అనుభవం ఉంది?",
        "district": "మీది ఏ జిల్లా?",
        "state": "మీది ఏ రాష్ట్రం?",
        "work_preference": "మీరు ఉద్యోగం చేయాలనుకుంటున్నారా లేక సొంత పని మొదలుపెట్టాలనుకుంటున్నారా?",
    },
}

DONE_MESSAGE = {
    "en": "Thank you! Please check your profile on the screen and confirm it.",
    "hi": "धन्यवाद! कृपया स्क्रीन पर अपनी प्रोफ़ाइल देखें और पुष्टि करें।",
    "te": "ధన్యవాదాలు! దయచేసి స్క్రీన్ పై మీ ప్రొఫైల్ చూసి నిర్ధారించండి.",
}

QUESTION_SYSTEM = (
    "You are Swar Setu, a warm voice interviewer for low-literacy Indian beneficiaries of skilling programmes. "
    "Ask exactly ONE short, simple question in {lang}. Maximum 25 words. "
    "Briefly acknowledge the user's last answer if there is one. Never repeat a question already asked. "
    "Do not ask about caste, religion, income or any other sensitive detail. Output only the question."
)


def _lang(code: str, table: dict) -> dict:
    return table.get(code) or table["en"]


def _generate_question(session: dict, field: str) -> str:
    code = session["language"]
    if llm.llm_available():
        try:
            convo = profile_agent.transcript_text(session["transcript"][-8:]) or "(interview just started)"
            q = llm.chat(
                QUESTION_SYSTEM.format(lang=language_name(code)),
                f"Conversation so far:\n{convo}\n\nNow ask about: {FIELD_HINTS[field]}.",
                temperature=0.5,
            )
            if q:
                return q.strip().strip('"')
        except Exception as e:  # noqa: BLE001
            print(f"[agent1] LLM question failed, using template: {e}")
    return _lang(code, FALLBACK_QUESTIONS)[field]


def _advance(session: dict, greeting: str = "") -> dict:
    """Decide the next question or finish."""
    user_turns = sum(1 for t in session["transcript"] if t["role"] == "user")
    missing = profile_agent.missing_fields(session)

    # never nag: after two asks for the same field, skip it
    while missing and session["ask_count"].get(missing[0], 0) >= 2:
        session["skip"].append(missing[0])
        missing = profile_agent.missing_fields(session)

    if not missing or user_turns >= config.MAX_INTERVIEW_TURNS:
        session["interview_done"] = True
        text = _lang(session["language"], DONE_MESSAGE)
        session["transcript"].append({"role": "assistant", "text": text, "field": None})
        store.save(session)
        return _payload(session, text, None)

    field = missing[0]
    session["ask_count"][field] = session["ask_count"].get(field, 0) + 1
    text = greeting + _generate_question(session, field)
    session["transcript"].append({"role": "assistant", "text": text, "field": field})
    store.save(session)
    return _payload(session, text, field)


def _payload(session: dict, question: str, field: Optional[str]) -> dict:
    return {
        "session_id": session["id"],
        "question": question,
        "field": field,
        "done": session["interview_done"],
        "profile_preview": session.get("profile", {}),
        "missing": profile_agent.missing_fields(session),
    }


class StartRequest(BaseModel):
    language: str = "en"


class AnswerRequest(BaseModel):
    session_id: str
    message: str


@router.post("/start")
def start(req: StartRequest):
    session = store.create(language=(req.language or "en").lower())
    return _advance(session, greeting=_lang(session["language"], GREETING))


@router.post("/answer")
def answer(req: AnswerRequest):
    session = require_session(req.session_id)
    if session["interview_done"]:
        return _payload(session, _lang(session["language"], DONE_MESSAGE), None)
    session["transcript"].append({"role": "user", "text": req.message.strip(), "field": None})
    profile_agent.update_profile(session)
    return _advance(session)
