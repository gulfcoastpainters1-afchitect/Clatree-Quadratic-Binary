# rasta_dave_core_v2.py

# daemon assistant runtime for modular wardrobe ai system

# includes: file crawling, memory wheel logging, spo (state polarity orientator), chat interface handler

import os
import json
import time
import logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from threading import Thread
from datetime import datetime

# initialize app and logger

app = FastAPI()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rasta_dave")

# state memory & spo

memory_log = []
state_file = "state_log.json"


class Message(BaseModel):
    user: str
    text: str


# state polarity orientator

class SPO:
    def __init__(self):
        self.state = {}

    def update_state(self, name, value):
        self.state[name] = {
            "value": value,
            "light": self._light_form(value),
            "dark": self._dark_form(value)
        }

    def _light_form(self, val):
        return max(0, min(1, val))

    def _dark_form(self, val):
        return -1 * max(0, min(1, -val))

    def get_state(self, name):
        return self.state.get(name, {})


spo = SPO()

# file crawler


def crawl_files(root="/", keywords=["ruby", "ai", "daemon", "runtime"]):
    matched = []
    for dirpath, _, filenames in os.walk(root):
        for file in filenames:
            if any(k in file.lower() for k in keywords):
                full_path = os.path.join(dirpath, file)
                matched.append(full_path)
    return matched

# persistent memory


def save_memory():
    with open(state_file, "w") as f:
        json.dump(memory_log, f, indent=2)


def load_memory():
    global memory_log
    try:
        with open(state_file) as f:
            memory_log = json.load(f)
    except FileNotFoundError:
        memory_log = []

# chat endpoint


@app.post("/chat")
async def chat(request: Message):
    ts = datetime.utcnow().isoformat()
    memory_entry = {"user": request.user, "message": request.text, "timestamp": ts}
    memory_log.append(memory_entry)
    save_memory()
    response = f"yo {request.user}, dave here. heard you say: '{request.text}'"
    logger.info(response)
    return JSONResponse(content={"reply": response})

# file query endpoint


@app.get("/files")
def get_ai_files():
    files = crawl_files("/", ["ruby", "ai", "gguf", "daemon"])
    return {"files": files[:25]}  # limit for speed

# state update


@app.post("/state/{name}/{value}")
def update_state(name: str, value: float):
    spo.update_state(name, value)
    return {"updated": name, "state": spo.get_state(name)}

# background memory refresher


class MemoryThread(Thread):
    def run(self):
        while True:
            save_memory()
            time.sleep(60)


if __name__ == "__main__":
    load_memory()
    MemoryThread().start()
    logger.info("rasta dave core v2, online and learnin")
