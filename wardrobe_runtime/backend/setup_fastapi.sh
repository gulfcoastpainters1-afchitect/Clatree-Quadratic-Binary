#!/usr/bin/env bash
set -e

# 1. Prepare working directory
cd ~/wardrobe_runtime/backend

# 2. Install tools
python3 -m pip install --upgrade pip
python3 -m pip install fastapi uvicorn python-dotenv requests dos2unix

# 3. Generate backend_service.py
cat > backend_service.py << 'SCRIPT'
from fastapi import FastAPI
from pydantic import BaseModel
import os, requests
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()
KEY = os.getenv("OPENAI_API_KEY")

class Prompt(BaseModel):
    text: str

@app.post("/run")
async def run(prompt: Prompt):
    headers = {"Authorization": f"Bearer {KEY}"}
    data = {
        "model": "gpt-4o-mini",
        "messages": [{"role":"user","content":prompt.text}]
    }
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers=headers,
        json=data
    )
    return r.json()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend_service:app", host="127.0.0.1", port=8000, reload=True)
SCRIPT

# 4. Clean up line endings and indentation
dos2unix backend_service.py
expand -t 4 backend_service.py > tmp && mv tmp backend_service.py

# 5. Make the script executable & run it
chmod +x setup_fastapi.sh
./setup_fastapi.sh
