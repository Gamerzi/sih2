import os
import sys
from fastapi import FastAPI
from pydantic import BaseModel
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise ValueError("GROQ_API_KEY is not set in environment or .env file.")

app = FastAPI()
client = Groq(api_key=api_key)

SYSTEM_PROMPT = "You are a helpful voice assistant. Keep replies short and conversational, since they'll be read aloud."


class ChatRequest(BaseModel):
    message: str


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


if __name__ == "__main__":
    import uvicorn

    # Supports running `python index.py` or `python index.py serve`
    uvicorn.run("index:app", host="127.0.0.1", port=8000, reload=True)