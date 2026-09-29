"""Central configuration. All values come from environment variables / .env"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-20b")

# Optional. If empty, sessions live in memory and NQR data is read from data/nqr_sample.json
MONGODB_URI = os.getenv("MONGODB_URI", "")
MONGODB_DB = os.getenv("MONGODB_DB", "swar_setu")

# Comma separated list of frontend origins, e.g. https://your-app.vercel.app
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]

MAX_INTERVIEW_TURNS = int(os.getenv("MAX_INTERVIEW_TURNS", "12"))
