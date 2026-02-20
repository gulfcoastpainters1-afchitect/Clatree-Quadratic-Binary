Bashinapi.sh

#!/usr/bin/env bash
set -e

# 1) Install/upgrades
python3 -m pip install --upgrade pip
python3 -m pip install fastapi uvicorn python-dotenv requests

# 2) Ensure working dir
cd "$(dirname "$0")"

# 3) Create/edit .env
cat > .env << 'EOF'
# Paste your real key after the =
OPENAI_API_KEY=
EOF
echo ".env created – edit it and add your OPENAI_API_KEY"

# 4) Write the FastAPI app
cat > script.py << 'EOF'
from fastapi import FastAPI
from pydantic import BaseModel
import os, requests
from dotenv import load_dotenv

# load your key from .env
load_dotenv()
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

app = FastAPI()

class Prompt(BaseModel):
    text: str

@app.get("/")
def health():
    return {"status": "running"}

@app.post("/run")
async def run(prompt: Prompt):
    # echo test until you put your key in .env
    if not OPENAI_KEY:
        return {"you_sent": prompt.text}
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={ "Authorization": f"Bearer {OPENAI_KEY}" },
        json={ "model":"gpt-4o-mini","messages":[{"role":"user","content":prompt.text}] }
    )
    resp.raise_for_status()
    return resp.json()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("script:app", host="127.0.0.1", port=8000, reload=True)
EOF
echo "script.py written"

# 5) Launch Uvicorn in background
nohup python3 -m uvicorn script:app --host 127.0.0.1 --port 8000 --reload \
    > api.log 2>&1 &
echo $! > api.pid
echo "FastAPI started (PID=$(cat api.pid)), logging to api.log"
echo "→ Visit http://127.0.0.1:8000/docs to test"
