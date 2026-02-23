# script.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import os, uuid, requests
from dotenv import load_dotenv

# Load OPENAI_API_KEY from .env
load_dotenv()
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

app = FastAPI()

# In-memory session store: session_id -> list of message dicts
_sessions: dict[str, list[dict[str, str]]] = {}


class Prompt(BaseModel):
    text: str
    session_id: Optional[str] = None  # omit to start a new session


@app.get("/")
def health_check():
    return {"status": "ok"}


@app.post("/run")
async def run(prompt: Prompt):
    """
    Receives {"text": "...", "session_id": "<optional>"} and forwards it to
    OpenAI, maintaining conversation history within the session so the model
    remembers previous exchanges.

    If no session_id is provided a new session is created automatically and
    its id is included in the response so you can continue the conversation.
    """
    # resolve / create session
    sid = prompt.session_id or str(uuid.uuid4())
    history = _sessions.setdefault(sid, [])

    # append the new user message to the session history
    history.append({"role": "user", "content": prompt.text})

    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_KEY}"},
        json={
            "model": "gpt-4o-mini",
            "messages": history,
        }
    )
    try:
        resp.raise_for_status()
    except requests.HTTPError as exc:
        # Roll back the user message so the session stays consistent
        history.pop()
        raise HTTPException(status_code=resp.status_code, detail=str(exc))
    data = resp.json()

    # store the assistant reply so future turns include it
    choices = data.get("choices") or []
    if not choices:
        history.pop()
        raise HTTPException(status_code=502, detail="OpenAI returned no choices")
    assistant_msg = choices[0]["message"]
    history.append({"role": assistant_msg["role"], "content": assistant_msg["content"]})

    data["session_id"] = sid
    return data


@app.get("/sessions")
def list_sessions():
    """Return all active session ids and how many messages each has."""
    return {
        sid: {"message_count": len(msgs)}
        for sid, msgs in _sessions.items()
    }


@app.get("/sessions/{session_id}")
def get_session(session_id: str):
    """Return the full conversation history for a session."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "history": _sessions[session_id]}


@app.delete("/sessions/{session_id}")
def clear_session(session_id: str):
    """Delete (reset) a session's conversation history."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    del _sessions[session_id]
    return {"deleted": session_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("script:app", host="127.0.0.1", port=8000, reload=True)
