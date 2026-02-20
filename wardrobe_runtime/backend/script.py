Script.py

# script.py

from fastapi import FastAPI
from pydantic import BaseModel
import os, requests
from dotenv import load_dotenv

# Load OPENAI_API_KEY from .env
load_dotenv()
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

app = FastAPI()


class Prompt(BaseModel):
    text: str


@app.get("/")
def health_check():
    return {"status": "ok"}


@app.post("/run")
async def run(prompt: Prompt):
    """
    Receives {"text": "..."} and forwards it to OpenAI,
    returning the raw JSON response.
    """
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_KEY}"},
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt.text}]
        }
    )
    resp.raise_for_status()
    return resp.json()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("script:app", host="127.0.0.1", port=8000, reload=True)
