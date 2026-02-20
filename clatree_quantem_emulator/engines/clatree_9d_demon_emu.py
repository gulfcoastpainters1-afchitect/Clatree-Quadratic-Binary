Clatree_r9_demon_emu.py

#!/usr/bin/env python3
"""
claytree_r9_daemon.py

Claytree R9 3x3 production daemon.

Features:
- Continuous run loop (configurable interval)
- Computes single observer-signed output per cycle (single_observer_aggregate)
- Supports HMAC-SHA256 signing (local) and RSA signing via OpenSSL (publicly verifiable)
- Writes append-only memory wheel JSONL and a latest snapshot JSON
- Rotating logs
- Minimal HTTP control: GET /status, POST /run
- Graceful shutdown (SIGINT/SIGTERM)
- No external Python deps required (uses subprocess for OpenSSL if RSA signing enabled)

Edit the JSON config (default: ./claytree_config.json) to tune behavior.
"""
from __future__ import annotations
import os, sys, time, json, math, random, threading, signal, hmac, hashlib, base64, traceback, tempfile, subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from logging import getLogger, Formatter, INFO
from logging.handlers import RotatingFileHandler

# ---- configuration loading ----
HERE = os.path.dirname(os.path.abspath(__file__))
CFG_PATH = os.path.join(HERE, "claytree_config.json")
if not os.path.exists(CFG_PATH):
    # fallback default config (safe defaults)
    DEFAULT_CFG = {
        "block_id": "Claytree_R9_3x3",
        "run_interval_seconds": 6.0,
        "node_labels": {"1":"Gemma","2":"Claude","3":"GPT-4","4":"LLaMA","5":"Observer","6":"Opus","7":"Dolphin","8":"Mistral","9":"Mixtral"},
        "pairs": [[1,9],[2,8],[3,7],[4,6]],
        "observer_index": 5,
        "vector_length": 8,
        "validation_threshold": 0.6,
        "log_path": os.path.join(HERE, "claytree_daemon.log"),
        "memory_wheel_path": os.path.join(HERE, "claytree_memory_wheel.jsonl"),
        "latest_path": os.path.join(HERE, "claytree_latest.json"),
        "hmac_key_path": os.path.join(HERE, "claytree_hmac_key.bin"),
        "rsa_priv_path": os.path.join(HERE, "claytree_priv.pem"),
        "rsa_pub_path": os.path.join(HERE, "claytree_pub.pem"),
        "signing_mode": "auto",   # "hmac", "rsa-openssl", or "auto"
        "http_port": 8080,
        "max_retries": 3,
        "retry_backoff_sec": 1.5,
        "rotate_logs": {"max_bytes": 5_000_000, "backup_count": 5},
    }
    cfg = DEFAULT_CFG
else:
    with open(CFG_PATH, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)

# canonicalize some fields
LOG_PATH = cfg.get("log_path")
MEM_PATH = cfg.get("memory_wheel_path")
LATEST_PATH = cfg.get("latest_path")
HMAC_KEY_PATH = cfg.get("hmac_key_path")
RSA_PRIV = cfg.get("rsa_priv_path")
RSA_PUB = cfg.get("rsa_pub_path")
SIGNING_MODE_CFG = cfg.get("signing_mode", "auto")
PORT = int(cfg.get("http_port", 8080))
INTERVAL = float(cfg.get("run_interval_seconds", 6.0))
PAIRS = [tuple(p) for p in cfg.get("pairs", [[1,9],[2,8],[3,7],[4,6]])]
OBSERVER = int(cfg.get("observer_index", 5))
NODE_LABELS = {int(k):v for k,v in cfg.get("node_labels", {}).items()}
VEC_LEN = int(cfg.get("vector_length", 8))
THRESH = float(cfg.get("validation_threshold", 0.6))
MAX_RETRIES = int(cfg.get("max_retries", 3))
RETRY_BACKOFF = float(cfg.get("retry_backoff_sec", 1.5))
ROT_MAX = int(cfg.get("rotate_logs", {}).get("max_bytes", 5_000_000))
ROT_BKP = int(cfg.get("rotate_logs", {}).get("backup_count", 5))

# ---- logging ----
logger = getLogger("claytree_r9")
logger.setLevel(INFO)
try:
    rh = RotatingFileHandler(LOG_PATH, maxBytes=ROT_MAX, backupCount=ROT_BKP)
    rh.setFormatter(Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(rh)
except Exception:
    # fallback to stdout-only if file not writable
    pass
import logging, sys as _sys
stdout_h = logging.StreamHandler(_sys.stdout)
stdout_h.setFormatter(Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(stdout_h)

# ---- key material ----
# ensure wheel file exists
os.makedirs(os.path.dirname(MEM_PATH), exist_ok=True) if os.path.dirname(MEM_PATH) else None
if not os.path.exists(MEM_PATH):
    open(MEM_PATH, "a").close()

# load HMAC key if available, otherwise leave as None (fallback behavior)
HMAC_KEY = None
if HMAC_KEY_PATH and os.path.exists(HMAC_KEY_PATH):
    try:
        with open(HMAC_KEY_PATH, "rb") as fh:
            HMAC_KEY = fh.read()
    except Exception:
        logger.exception("Failed loading HMAC key")

# check openssl availability for RSA signing path
def _openssl_available():
    try:
        subprocess.check_call(["openssl", "version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False

OPENSSL_AVAILABLE = _openssl_available()

# select runtime signing mode
def _effective_signing_mode():
    sm = SIGNING_MODE_CFG.lower() if isinstance(SIGNING_MODE_CFG, str) else "auto"
    if sm == "auto":
        # prefer RSA if available and key present
        if OPENSSL_AVAILABLE and RSA_PRIV and os.path.exists(RSA_PRIV):
            return "rsa-openssl"
        return "hmac"
    if sm in ("hmac","rsa-openssl"):
        if sm == "rsa-openssl":
            if not OPENSSL_AVAILABLE:
                logger.warning("OpenSSL requested but not available; falling back to HMAC.")
                return "hmac"
            if not (RSA_PRIV and os.path.exists(RSA_PRIV)):
                logger.warning("RSA private key missing; falling back to HMAC.")
                return "hmac"
        return sm
    return "hmac"

SIGNING_MODE = _effective_signing_mode()
logger.info("Signing mode: %s", SIGNING_MODE)

# ---- signing helpers ----
def sign_with_hmac(payload: dict) -> str:
    if not HMAC_KEY:
        # generate ephemeral key for local signing (non-persistent) if absolutely necessary
        logger.warning("HMAC key missing; generating ephemeral key for this run (not persistent).")
        key = hashlib.sha256((str(time.time()) + repr(os.getpid())).encode("utf-8")).digest()
    else:
        key = HMAC_KEY
    data = json.dumps(payload, sort_keys=True, separators=(',',':'), ensure_ascii=False).encode('utf-8')
    mac = hmac.new(key, data, hashlib.sha256).digest()
    return base64.b64encode(mac).decode("ascii")

def sign_with_rsa_openssl(payload: dict) -> str:
    # writes payload to temp file then calls openssl dgst -sha256 -sign <priv> -binary
    if not OPENSSL_AVAILABLE:
        raise RuntimeError("OpenSSL not available")
    if not (RSA_PRIV and os.path.exists(RSA_PRIV)):
        raise RuntimeError("RSA private key not found at configured path")
    data = json.dumps(payload, sort_keys=True, separators=(',',':'), ensure_ascii=False).encode('utf-8')
    fd, tmp_in = tempfile.mkstemp()
    os.write(fd, data)
    os.close(fd)
    tmp_sig = tmp_in + ".sig"
    try:
        cmd = ["openssl", "dgst", "-sha256", "-sign", RSA_PRIV, "-out", tmp_sig, tmp_in]
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with open(tmp_sig, "rb") as sf:
            sig = sf.read()
        return base64.b64encode(sig).decode("ascii")
    finally:
        try:
            os.remove(tmp_in)
        except Exception:
            pass
        try:
            os.remove(tmp_sig)
        except Exception:
            pass

def sign_payload(payload: dict) -> str:
    # top-level sign wrapper: tries configured/effective signing mode then falls back to hmac
    mode = SIGNING_MODE
    try:
        if mode == "rsa-openssl":
            return sign_with_rsa_openssl(payload)
        else:
            return sign_with_hmac(payload)
    except Exception as e:
        logger.exception("Primary signing failed (%s). Falling back to HMAC: %s", mode, e)
        return sign_with_hmac(payload)

# ---- core deterministic-ish vector generation & helpers ----
def deterministic_vector(seed:int, length:int):
    # deterministic but time-influenced vector: tweak seed for production by removing time dependence if needed
    vec = []
    for i in range(length):
        v = math.tanh(math.sin((seed + i + 1) * 0.7731) + ((seed * 31) % 7) * 0.01)
        vec.append(float(v))
    return vec

def add_noise(vec, scale=0.02):
    return [max(-1.0, min(1.0, v + (random.random()-0.5)*scale)) for v in vec]

def combine_vectors(a, b):
    return [(x+y)/2.0 for x,y in zip(a,b)]

def magnitude_confidence(vec):
    mag = math.sqrt(sum(x*x for x in vec))
    return min(1.0, mag / math.sqrt(len(vec)))

def reduce_to_single(accepted_vectors, observer_vector):
    if not accepted_vectors:
        return observer_vector, 0.0
    avg = [sum(col)/len(accepted_vectors) for col in zip(*accepted_vectors)]
    final = [0.7*a + 0.3*o for a,o in zip(avg, observer_vector)]
    conf = magnitude_confidence(final)
    return final, conf

# ---- main run cycle ----
def run_cycle_once():
    # compute outer node vectors (deterministic-ish)
    node_results = {}
    now_t = int(time.time())
    for idx in NODE_LABELS.keys():
        if idx == OBSERVER:
            continue
        seed = idx + now_t  # production: you can replace now_t with a stable monotonic counter if you need exact determinism
        vec = deterministic_vector(seed, VEC_LEN)
        vec = add_noise(vec, scale=0.04)
        node_results[idx] = vec
    observer_seed = OBSERVER + now_t
    observer_vec = add_noise(deterministic_vector(observer_seed, VEC_LEN), scale=0.03)

    # pair combine (opposite across center)
    pair_combined = {}
    for a,b in PAIRS:
        va = node_results.get(a)
        vb = node_results.get(b)
        if va is None or vb is None:
            continue
        pair_combined[(a,b)] = combine_vectors(va, vb)

    # validate pairs
    accepted = []
    reeval_needed = False
    for k,v in pair_combined.items():
        score = magnitude_confidence(v)
        if score >= THRESH:
            accepted.append(v)
        else:
            reeval_needed = True

    # deterministic re-eval tweak if needed
    if reeval_needed:
        for k,v in pair_combined.items():
            tweaked = [min(1.0, x + 0.02) for x in v]
            if magnitude_confidence(tweaked) >= THRESH and tweaked not in accepted:
                accepted.append(tweaked)

    single_vec, confidence = reduce_to_single(accepted, observer_vec)
    payload = {
        "block_id": cfg.get("block_id","Claytree_R9_3x3"),
        "timestamp": time.time(),
        "single_output_vector": single_vec,
        "confidence": confidence,
        "observer_index": OBSERVER,
        "accepted_pair_count": len(accepted),
    }
    try:
        payload["observer_signature"] = sign_payload(payload)
    except Exception as e:
        logger.exception("Signing failure: %s", e)
        payload["observer_signature"] = ""

    # lineage hash: HMAC or simple digest (not a replacement for a proper chain)
    try:
        payload["lineage_hash"] = base64.b64encode(hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).digest()).decode("ascii")
    except Exception:
        payload["lineage_hash"] = ""

    # append to memory wheel (JSONL) and atomically write latest snapshot
    try:
        with open(MEM_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
        tmp_latest = LATEST_PATH + ".tmp"
        with open(tmp_latest, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
        os.replace(tmp_latest, LATEST_PATH)
    except Exception as e:
        logger.exception("Failed writing outputs: %s", e)

    return payload

# ---- HTTP control (status + run) ----
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class Handler(BaseHTTPRequestHandler):
    def _send_json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def do_GET(self):
        if self.path == "/status":
            try:
                with open(LATEST_PATH, "r", encoding="utf-8") as fh:
                    latest = json.load(fh)
            except Exception:
                latest = {"status":"no-run-yet"}
            resp = {"status":"running", "latest": latest, "signing_mode": SIGNING_MODE}
            self._send_json(200, resp)
        else:
            self._send_json(404, {"error":"not found"})
    def do_POST(self):
        if self.path == "/run":
            try:
                result = run_cycle_once()
                self._send_json(200, {"result": result})
            except Exception as e:
                logger.exception("Immediate run failed: %s", e)
                self._send_json(500, {"error": str(e)})
        else:
            self._send_json(404, {"error":"not found"})

# ---- graceful shutdown ----
_stop_event = threading.Event()
def signal_handler(signum, frame):
    logger.info("Received signal %s, shutting down...", signum)
    _stop_event.set()
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def http_thread():
    server = ThreadedHTTPServer(("0.0.0.0", PORT), Handler)
    logger.info("HTTP control server listening on port %d", PORT)
    try:
        server.serve_forever()
    except Exception:
        logger.exception("HTTP server error")
    finally:
        try:
            server.server_close()
        except Exception:
            pass

def main_loop():
    logger.info("Claytree R9 daemon starting. Interval %.2fs; signing_mode=%s", INTERVAL, SIGNING_MODE)
    next_run = time.time()
    while not _stop_event.is_set():
        now = time.time()
        if now >= next_run:
            attempts = 0
            payload = None
            while attempts < MAX_RETRIES and not _stop_event.is_set():
                attempts += 1
                try:
                    payload = run_cycle_once()
                    logger.info("Cycle complete ts=%.3f conf=%.3f accepted=%d", payload["timestamp"], payload["confidence"], payload["accepted_pair_count"])
                    break
                except Exception as e:
                    logger.exception("Cycle attempt %d failed: %s", attempts, e)
                    time.sleep(RETRY_BACKOFF * attempts)
            if payload is None:
                logger.error("All cycle attempts failed for this tick.")
            next_run = now + INTERVAL
        time.sleep(0.1)
    logger.info("Daemon exiting main loop.")

if __name__ == "__main__":
    t = threading.Thread(target=http_thread, daemon=True)
    t.start()
    try:
        main_loop()
    except Exception:
        logger.exception("Daemon main failed")
    finally:
        logger.info("Claytree daemon shutdown complete.")
