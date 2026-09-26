import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from groq import Groq
from dotenv import load_dotenv

# Loads variables from a local .env file if one exists.
# On Vercel there's no .env file, so this just does nothing there —
# Vercel injects the env vars you set in the dashboard directly.
load_dotenv()

app = FastAPI()
client = Groq(api_key=os.environ["GROQ_API_KEY"])

STATIC_DIR = Path(__file__).parent / "static"

# Serve the Graphics folder (Jarvis.gif, icons) at /Graphics/*
app.mount("/Graphics", StaticFiles(directory=STATIC_DIR / "Graphics"), name="graphics")

SYSTEM_PROMPT = "You are a helpful voice assistant. Keep replies short and conversational, since they'll be read aloud."


class ChatRequest(BaseModel):
    message: str


@app.get("/")
def home():
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/chat")
def chat(req: ChatRequest):
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": req.message},
        ],
        temperature=0.7,
    )
    return {"reply": completion.choices[0].message.content}