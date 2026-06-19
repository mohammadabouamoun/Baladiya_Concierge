#!/usr/bin/env python3
"""Lightweight LOCAL demo API for Baladiya Concierge.

PURPOSE: give the host page's chat bubble REAL bilingual AI answers + a working
phone/OTP flow on a laptop, WITHOUT Docker, RAG, Vault, Postgres, or the classifier.

This is a DEMO AID ONLY. It is intentionally not part of the real architecture:
- chat answers come straight from Gemini (no RAG grounding, no guardrails sidecar)
- OTP is an in-memory dict (no Redis, no SMS provider) — the code is returned in the
  response so it can be shown on screen during a live demo
Nothing in docker-compose references this file. The real pipeline still runs in Docker.

Zero third-party deps — pure standard library. Run it with:

    python3 scripts/demo_api.py            # reads GEMINI_API_KEY from .env

Then open the host page (python3 -m http.server 3000 from ./host) and the bubble
will call http://localhost:8787 automatically.
"""
from __future__ import annotations

import json
import os
import random
import tempfile
import threading
import time
import urllib.request
import urllib.error
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = int(os.environ.get("DEMO_API_PORT", "8787"))
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
OTP_TTL_SECONDS = 300

# Captured reports are written here so the (separate) Streamlit requests page can
# read them. A plain JSON file on a stable temp path keeps both processes in sync
# without a DB. Override with DEMO_REQUESTS_FILE if you want a custom location.
REQUESTS_FILE = Path(
    os.environ.get(
        "DEMO_REQUESTS_FILE",
        os.path.join(tempfile.gettempdir(), "baladiya_demo_requests.json"),
    )
)
_REQUESTS_LOCK = threading.Lock()

# ── Load GEMINI_API_KEY from the environment or the project .env ────────────


def _load_env_file() -> dict[str, str]:
    """Parse the project .env (KEY=VALUE lines) without any dependency."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    values: dict[str, str] = {}
    if not env_path.exists():
        return values
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        values[key.strip()] = val.strip().strip('"').strip("'")
    return values


_ENV = _load_env_file()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or _ENV.get("GEMINI_API_KEY", "")

# ── In-memory OTP store ──────────────────────────────────────────────────────
# { phone: {"code": "123456", "expires": epoch_seconds} }
_OTP: dict[str, dict] = {}


# ── Report store (JSON file shared with the Streamlit requests page) ─────────

# Order = tie-break priority (earlier wins). "roads" is last because "street/شارع"
# is generic and often appears alongside a more specific service word (e.g. a
# street LIGHT fault is electricity, a street WATER leak is water).
_CATEGORY_KEYWORDS = {
    "electricity": ["electric", "power", "lighting", "streetlight", "كهرباء", "تيار", "إنارة", "انارة", "إضاءة", "اضاءة"],
    "water": ["water", "leak", "sewage", "مياه", "ماء", "تسرب", "صرف", "مجارير"],
    "waste": ["waste", "garbage", "trash", "نفايات", "زبالة", "قمامة"],
    "permits": ["permit", "license", "تصريح", "رخصة"],
    "taxes": ["tax", "fee", "ضريبة", "ضرائب", "رسوم"],
    "roads": ["road", "street", "pothole", "حفرة", "طريق", "شارع", "رصيف"],
}


def _guess_category(text: str) -> str:
    """Pick the category with the most keyword hits; ties go to the higher-priority
    (earlier) category in _CATEGORY_KEYWORDS."""
    low = text.lower()
    best_cat, best_score = "general", 0
    for cat, words in _CATEGORY_KEYWORDS.items():
        score = sum(1 for w in words if w in low)
        if score > best_score:
            best_cat, best_score = cat, score
    return best_cat


def _load_requests() -> list[dict]:
    if not REQUESTS_FILE.exists():
        return []
    try:
        return json.loads(REQUESTS_FILE.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return []


def _save_report(record: dict) -> None:
    with _REQUESTS_LOCK:
        records = _load_requests()
        records.insert(0, record)  # newest first
        REQUESTS_FILE.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

# The model emits this exact marker once it has BOTH a location and a problem
# description for a report — the frontend strips it and opens the phone/OTP card.
VERIFY_MARKER = "[[VERIFY_PHONE]]"

SYSTEM_PROMPT = (
    "You are the Municipal Assistant for Baladiya Concierge, the civic AI agent for "
    "the Municipality of Beirut. You help residents with civic matters: reporting "
    "issues (roads, water, electricity, waste), permits and licenses, taxes, and "
    "general municipal questions. Be warm, concise, and professional — a trustworthy "
    "civic voice, never salesy. Keep replies to 2-4 short sentences. "
    "CRITICAL LANGUAGE RULE: reply in the SAME language the resident used. If they "
    "write in Arabic (MSA or Lebanese dialect), reply in Arabic. If they write in "
    "Arabizi (Lebanese Arabic in Latin letters with number substitutions like 2, 3, "
    "7 — e.g. '7afra bel tari2 2eddem el bayt' or 'kif 2addem talab rokh9e'), "
    "understand it fully and reply in clear Arabic script, NOT in Latin letters. If "
    "they write in English, reply in English. Do not mix languages in one reply. "
    "You have the full conversation so far — DO NOT ask again for information the "
    "resident has already given. Track what you already know. "
    "NEVER INVENT FACTS. You do NOT have access to the municipality's live data, so "
    "you must NOT state specific working hours, fees, tax amounts, deadlines, phone "
    "numbers, collection schedules, or required documents as if they were confirmed. "
    "When asked for such specifics, explain the general process and direct the "
    "resident to verify the exact details on the Municipality of Beirut's official "
    "website or by contacting the relevant department. Do not guess numbers or dates. "
    "Only stay within civic topics handled by the municipality; for matters outside "
    "its remit (e.g. visas, passports), briefly say so and point them to the right body. "
    "REPORT FLOW: to file a report you need (1) a location and (2) a short description "
    "of the problem. Ask only for what is still missing. The MOMENT you have BOTH the "
    "location and the description, confirm you are registering the report, tell the "
    "resident you will now verify their phone number so the municipality can follow "
    "up, and then output the exact token " + VERIFY_MARKER + " on its own at the very "
    "end of that message. Output that token ONLY once, only when both pieces are "
    "collected, and never explain or mention the token itself."
)


def _gemini_reply(history: list[dict], lang_hint: str) -> str:
    """Call the Gemini REST API directly via urllib. Raises on failure.

    `history` is a list of {"role": "user"|"model", "text": str} turns, oldest first.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY missing")

    contents = []
    for turn in history:
        role = "model" if turn.get("role") == "model" else "user"
        text = (turn.get("text") or "").strip()
        if text:
            contents.append({"role": role, "parts": [{"text": text}]})
    if not contents:
        raise RuntimeError("empty history")

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 512},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    candidates = data.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini returned no candidates")
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts).strip()
    if not text:
        raise RuntimeError("Gemini returned empty text")
    return text


class Handler(BaseHTTPRequestHandler):
    # ── plumbing ────────────────────────────────────────────────────────────
    def log_message(self, fmt, *args):  # quieter, prefixed logging
        print(f"[demo-api] {self.address_string()} - {fmt % args}")

    def _send(self, code: int, body: dict):
        raw = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length == 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    def do_OPTIONS(self):  # CORS preflight
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # ── routes ────────────────────────────────────────────────────────────────
    def do_GET(self):
        if self.path == "/health":
            self._send(200, {"ok": True, "gemini": bool(GEMINI_API_KEY)})
        elif self.path == "/demo/requests":
            self._send(200, {"requests": _load_requests()})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/demo/chat":
            self._chat()
        elif self.path == "/demo/otp/request":
            self._otp_request()
        elif self.path == "/demo/otp/confirm":
            self._otp_confirm()
        elif self.path == "/demo/requests":
            self._store_request()
        else:
            self._send(404, {"error": "not found"})

    def _store_request(self):
        """Persist a verified report so it shows on the Tenant Admin requests page."""
        body = self._body()
        phone = (body.get("phone") or "").strip()
        lang = body.get("lang") or "ar"
        # Build the description from the resident's own messages in the transcript.
        messages = body.get("messages") or []
        user_texts = [
            (m.get("text") or "").strip()
            for m in messages
            if isinstance(m, dict) and m.get("role") == "user"
        ]
        user_texts = [t for t in user_texts if t]
        description = body.get("description") or " · ".join(user_texts) or "(no description)"
        location = (body.get("location") or "").strip()

        ref = f"BEY-{time.strftime('%Y')}-{random.randint(0, 99999):05d}"
        record = {
            "id": str(uuid.uuid4()),
            "ref": ref,
            "intent": "report",
            "status": "open",
            "category": _guess_category(description),
            "description": description,
            "location": location,
            "name": None,
            "contact": phone,
            # non-empty marker → requests page shows "Phone verified: Yes"
            "visitor_phone_hash": f"demo:{phone}" if phone else "",
            "session_id": str(uuid.uuid4()),
            "is_false_report": False,
            "lang": lang,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _save_report(record)
        print(f"[demo-api] stored report ref={ref} category={record['category']} phone={phone}")
        self._send(200, {"ref": ref, "id": record["id"]})

    def _chat(self):
        body = self._body()
        lang = body.get("lang") or "ar"
        history = body.get("history")
        if not isinstance(history, list) or not history:
            # backward-compatible: single-message payload
            message = (body.get("message") or "").strip()
            if not message:
                self._send(400, {"error": "message or history required"})
                return
            history = [{"role": "user", "text": message}]
        try:
            reply = _gemini_reply(history, lang)
            verify = VERIFY_MARKER in reply
            if verify:
                reply = reply.replace(VERIFY_MARKER, "").strip()
            self._send(200, {"reply": reply, "verify": verify, "source": "gemini"})
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "ignore")[:300]
            print(f"[demo-api] Gemini HTTP {exc.code}: {detail}")
            self._send(502, {"error": f"gemini http {exc.code}"})
        except Exception as exc:  # noqa: BLE001 — demo aid, surface anything
            print(f"[demo-api] chat error: {exc}")
            self._send(502, {"error": str(exc)})

    def _otp_request(self):
        body = self._body()
        phone = (body.get("phone") or "").strip()
        if not phone:
            self._send(400, {"error": "phone required"})
            return
        code = f"{random.randint(0, 999999):06d}"
        _OTP[phone] = {"code": code, "expires": time.time() + OTP_TTL_SECONDS}
        # Mirrors the real ConsoleSMSBackend — code goes to the console (and, for the
        # demo only, is returned so it can be shown on screen).
        print(f"[demo-api] sms.otp_console phone={phone} code={code}")
        self._send(200, {"sent": True, "demo_code": code, "ttl": OTP_TTL_SECONDS})

    def _otp_confirm(self):
        body = self._body()
        phone = (body.get("phone") or "").strip()
        code = (body.get("code") or "").strip()
        entry = _OTP.get(phone)
        if not entry:
            self._send(400, {"verified": False, "error": "no code requested"})
            return
        if time.time() > entry["expires"]:
            _OTP.pop(phone, None)
            self._send(400, {"verified": False, "error": "code expired"})
            return
        if code != entry["code"]:
            self._send(400, {"verified": False, "error": "wrong code"})
            return
        _OTP.pop(phone, None)
        print(f"[demo-api] otp verified phone={phone}")
        self._send(200, {"verified": True})


def main() -> None:
    if not GEMINI_API_KEY:
        print("[demo-api] WARNING: GEMINI_API_KEY not found in env or .env — "
              "/demo/chat will return 502 until it is set.")
    else:
        print(f"[demo-api] Gemini key loaded, model={GEMINI_MODEL}")
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"[demo-api] listening on http://localhost:{PORT}")
    print("[demo-api] routes: POST /demo/chat  POST /demo/otp/request  "
          "POST /demo/otp/confirm  POST/GET /demo/requests  GET /health")
    print(f"[demo-api] reports stored at: {REQUESTS_FILE}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[demo-api] shutting down")
        server.shutdown()


if __name__ == "__main__":
    main()
