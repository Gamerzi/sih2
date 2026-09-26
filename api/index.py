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

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise ValueError("GROQ_API_KEY environment variable is missing. Please set it in your .env file.")

STATIC_DIR = Path(__file__).parent / "static"


def strip_audio_and_optimize():
    video_path = STATIC_DIR / "Graphics" / "Jarvis.mp4"
    if not video_path.exists():
        return
    flag = STATIC_DIR / "Graphics" / ".optimized"
    if flag.exists():
        return

    import shutil
    import subprocess

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        win_candidates = [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\ProgramData\chocolatey\bin\ffmpeg.exe",
            str(Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe"),
        ]
        for c in win_candidates:
            if os.path.isfile(c):
                ffmpeg = c
                break

    if ffmpeg:
        out_temp = STATIC_DIR / "Graphics" / "Jarvis_temp.mp4"
        try:
            cmd = [
                ffmpeg, "-y", "-i", str(video_path),
                "-an", "-c:v", "copy", "-movflags", "+faststart",
                str(out_temp)
            ]
            r = subprocess.run(cmd, capture_output=True)
            if r.returncode == 0 and out_temp.exists() and out_temp.stat().st_size > 0:
                shutil.move(str(out_temp), str(video_path))
                flag.write_text("done")
                print("[Jarvis] Video optimized: Audio stripped and faststart applied for seamless looping.")
        except Exception as e:
            print("[Jarvis] Video optimization error:", e)


strip_audio_and_optimize()

# Sync root index.html with static index.html
try:
    root_index = Path(__file__).parent.parent / "index.html"
    static_index = STATIC_DIR / "index.html"
    if static_index.exists() and root_index.exists():
        root_index.write_bytes(static_index.read_bytes())
except Exception:
    pass

app = FastAPI()
client = Groq(api_key=api_key)

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
        model="openai/gpt-oss-20b",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": req.message},
        ],
        temperature=0.7,
    )
    return {"reply": completion.choices[0].message.content}


if __name__ == "__main__":
    import uvicorn
    import sys

    # Ensure api directory is in sys.path for uvicorn reloader
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    uvicorn.run("index:app", host="127.0.0.1", port=8000, reload=True)
