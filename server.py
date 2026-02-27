"""Project Omni — FastAPI gateway for WeCom & Feishu (飞书) bots.

Receives messages from IM webhooks, forwards them to the ReAct Agent,
and pushes replies back via each platform's send-message API.

Usage:
    uvicorn server:app --reload --port 8000
"""
from __future__ import annotations

import base64
import hashlib
import json as _json
import logging
import os
import struct
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any

import httpx
from Crypto.Cipher import AES
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Query, Request, Response

load_dotenv()

from agent import Agent  # noqa: E402

import tools  # noqa: E402, F401

try:
    import tools_browser  # noqa: F401
except Exception:  # noqa: BLE001
    pass

log = logging.getLogger("omni.gateway")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Shared helpers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

app = FastAPI(title="Project Omni Gateway")

_sessions: dict[str, Agent] = {}


def _get_agent(user_id: str) -> Agent:
    if user_id not in _sessions:
        model = os.environ.get("OMNI_MODEL", "gpt-4o-mini")
        _sessions[user_id] = Agent(model=model)
    return _sessions[user_id]


def _split_text(text: str, max_bytes: int = 2000) -> list[str]:
    """Split text into chunks that fit within a byte-size limit."""
    chunks: list[str] = []
    current: list[str] = []
    current_size = 0
    for line in text.splitlines(keepends=True):
        line_size = len(line.encode("utf-8"))
        if current_size + line_size > max_bytes and current:
            chunks.append("".join(current))
            current, current_size = [], 0
        current.append(line)
        current_size += line_size
    if current:
        chunks.append("".join(current))
    return chunks or [""]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  WeCom (企业微信)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _pkcs7_pad(data: bytes, block_size: int = 32) -> bytes:
    n = block_size - (len(data) % block_size)
    return data + bytes([n] * n)


def _pkcs7_unpad(data: bytes) -> bytes:
    return data[: -data[-1]]


@dataclass(frozen=True, slots=True)
class WeComCrypto:
    token: str
    aes_key: bytes
    corp_id: str

    @classmethod
    def from_env(cls) -> WeComCrypto:
        encoding_aes_key = os.environ["WECOM_ENCODING_AES_KEY"]
        return cls(
            token=os.environ["WECOM_TOKEN"],
            aes_key=base64.b64decode(encoding_aes_key + "="),
            corp_id=os.environ["WECOM_CORP_ID"],
        )

    def verify(self, signature: str, timestamp: str, nonce: str, encrypt: str) -> bool:
        digest = hashlib.sha1(
            "".join(sorted([self.token, timestamp, nonce, encrypt])).encode()
        ).hexdigest()
        return digest == signature

    def decrypt(self, ciphertext_b64: str) -> str:
        cipher = AES.new(self.aes_key, AES.MODE_CBC, self.aes_key[:16])
        plain = _pkcs7_unpad(cipher.decrypt(base64.b64decode(ciphertext_b64)))
        msg_len = struct.unpack("!I", plain[16:20])[0]
        return plain[20 : 20 + msg_len].decode("utf-8")

    def encrypt(self, plaintext: str) -> str:
        random_prefix = os.urandom(16)
        msg_bytes = plaintext.encode("utf-8")
        corp_bytes = self.corp_id.encode("utf-8")
        body = random_prefix + struct.pack("!I", len(msg_bytes)) + msg_bytes + corp_bytes
        cipher = AES.new(self.aes_key, AES.MODE_CBC, self.aes_key[:16])
        return base64.b64encode(cipher.encrypt(_pkcs7_pad(body))).decode()

    def make_signature(self, timestamp: str, nonce: str, encrypt: str) -> str:
        return hashlib.sha1(
            "".join(sorted([self.token, timestamp, nonce, encrypt])).encode()
        ).hexdigest()


@dataclass
class WeComClient:
    corp_id: str = field(default_factory=lambda: os.environ.get("WECOM_CORP_ID", ""))
    app_secret: str = field(default_factory=lambda: os.environ.get("WECOM_APP_SECRET", ""))
    agent_id: int = field(default_factory=lambda: int(os.environ.get("WECOM_AGENT_ID", "0")))
    _token: str = ""
    _token_expires: float = 0.0

    async def _ensure_token(self) -> str:
        if self._token and time.time() < self._token_expires:
            return self._token
        async with httpx.AsyncClient() as c:
            r = await c.get(
                "https://qyapi.weixin.qq.com/cgi-bin/gettoken",
                params={"corpid": self.corp_id, "corpsecret": self.app_secret},
            )
            data = r.json()
        if data.get("errcode", 0) != 0:
            raise RuntimeError(f"WeCom token error: {data}")
        self._token = data["access_token"]
        self._token_expires = time.time() + data.get("expires_in", 7200) - 300
        return self._token

    async def send_text(self, user_id: str, content: str) -> dict[str, Any]:
        token = await self._ensure_token()
        chunks = _split_text(content, max_bytes=2000)
        last_resp: dict[str, Any] = {}
        async with httpx.AsyncClient() as c:
            for chunk in chunks:
                r = await c.post(
                    f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}",
                    json={
                        "touser": user_id,
                        "msgtype": "text",
                        "agentid": self.agent_id,
                        "text": {"content": chunk},
                    },
                )
                last_resp = r.json()
        return last_resp


def _extract_xml_field(xml_str: str, tag: str) -> str:
    root = ET.fromstring(xml_str)
    el = root.find(tag)
    return el.text or "" if el is not None else ""


_wecom_client: WeComClient | None = None
_wecom_crypto: WeComCrypto | None = None


def _get_wecom_crypto() -> WeComCrypto:
    global _wecom_crypto
    if _wecom_crypto is None:
        _wecom_crypto = WeComCrypto.from_env()
    return _wecom_crypto


def _get_wecom_client() -> WeComClient:
    global _wecom_client
    if _wecom_client is None:
        _wecom_client = WeComClient()
    return _wecom_client


@app.get("/webhook/wecom")
async def wecom_verify(
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(...),
) -> Response:
    crypto = _get_wecom_crypto()
    if not crypto.verify(msg_signature, timestamp, nonce, echostr):
        return Response("signature mismatch", status_code=403)
    return Response(crypto.decrypt(echostr), media_type="text/plain")


@app.post("/webhook/wecom")
async def wecom_receive(
    request: Request,
    background_tasks: BackgroundTasks,
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
) -> Response:
    body = (await request.body()).decode("utf-8")
    encrypt_text = _extract_xml_field(body, "Encrypt")

    crypto = _get_wecom_crypto()
    if not crypto.verify(msg_signature, timestamp, nonce, encrypt_text):
        return Response("signature mismatch", status_code=403)

    inner_xml = crypto.decrypt(encrypt_text)
    msg_type = _extract_xml_field(inner_xml, "MsgType")
    user_id = _extract_xml_field(inner_xml, "FromUserName")

    if msg_type != "text":
        return Response("success")

    content = _extract_xml_field(inner_xml, "Content")
    if not content:
        return Response("success")

    background_tasks.add_task(_handle_wecom_message, user_id, content)
    return Response("success")


async def _handle_wecom_message(user_id: str, content: str) -> None:
    agent = _get_agent(f"wecom:{user_id}")
    try:
        reply = await agent.chat(content)
    except Exception as exc:  # noqa: BLE001
        reply = f"⚠️ Agent error: {exc}"
    await _get_wecom_client().send_text(user_id, reply)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Feishu / Lark (飞书)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _feishu_decrypt(encrypt_key: str, encrypted: str) -> str:
    """Decrypt Feishu event body (AES-256-CBC, key = SHA256(encrypt_key))."""
    key = hashlib.sha256(encrypt_key.encode("utf-8")).digest()
    ciphertext = base64.b64decode(encrypted)
    iv, payload = ciphertext[:16], ciphertext[16:]
    cipher = AES.new(key, AES.MODE_CBC, iv)
    plain = cipher.decrypt(payload)
    pad = plain[-1]
    return plain[:-pad].decode("utf-8")


@dataclass
class FeishuClient:
    """Handles Feishu tenant_access_token refresh and message send/update."""

    app_id: str = field(default_factory=lambda: os.environ.get("FEISHU_APP_ID", ""))
    app_secret: str = field(default_factory=lambda: os.environ.get("FEISHU_APP_SECRET", ""))
    _token: str = ""
    _token_expires: float = 0.0

    async def _ensure_token(self) -> str:
        if self._token and time.time() < self._token_expires:
            return self._token
        async with httpx.AsyncClient() as c:
            r = await c.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": self.app_id, "app_secret": self.app_secret},
            )
            data = r.json()
        if data.get("code", 0) != 0:
            raise RuntimeError(f"Feishu token error: {data}")
        self._token = data["tenant_access_token"]
        self._token_expires = time.time() + data.get("expire", 7200) - 300
        return self._token

    async def _headers(self) -> dict[str, str]:
        token = await self._ensure_token()
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}

    async def send_text(self, chat_id: str, text: str) -> str:
        """Send a text message, return message_id for later updates."""
        headers = await self._headers()
        body = {
            "receive_id": chat_id,
            "msg_type": "text",
            "content": _json.dumps({"text": text}),
        }
        async with httpx.AsyncClient() as c:
            r = await c.post(
                "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
                headers=headers,
                json=body,
            )
            data = r.json()
        msg_id: str = data.get("data", {}).get("message_id", "")
        if data.get("code", 0) != 0:
            log.error("Feishu send failed: %s", data)
        return msg_id

    async def update_text(self, message_id: str, text: str) -> None:
        """PATCH an existing message — used for 'streaming' effect."""
        headers = await self._headers()
        body = {
            "msg_type": "text",
            "content": _json.dumps({"text": text}),
        }
        async with httpx.AsyncClient() as c:
            r = await c.put(
                f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}",
                headers=headers,
                json=body,
            )
            data = r.json()
        if data.get("code", 0) != 0:
            log.error("Feishu update failed: %s", data)

    async def reply_text(self, message_id: str, text: str) -> str:
        """Reply to a specific message (threaded)."""
        headers = await self._headers()
        body = {
            "msg_type": "text",
            "content": _json.dumps({"text": text}),
        }
        async with httpx.AsyncClient() as c:
            r = await c.post(
                f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/reply",
                headers=headers,
                json=body,
            )
            data = r.json()
        return data.get("data", {}).get("message_id", "")


_feishu_client: FeishuClient | None = None
_feishu_seen_events: dict[str, float] = {}  # event_id -> timestamp for dedup


def _get_feishu_client() -> FeishuClient:
    global _feishu_client
    if _feishu_client is None:
        _feishu_client = FeishuClient()
    return _feishu_client


def _feishu_dedup(event_id: str) -> bool:
    """Return True if this event was already processed (dedup within 5 min)."""
    now = time.time()
    # Prune old entries
    stale = [k for k, v in _feishu_seen_events.items() if now - v > 300]
    for k in stale:
        del _feishu_seen_events[k]
    if event_id in _feishu_seen_events:
        return True
    _feishu_seen_events[event_id] = now
    return False


@app.post("/webhook/feishu")
async def feishu_receive(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    raw = await request.json()

    # ── Encrypted events ──────────────────────────────────────────────────
    if "encrypt" in raw:
        encrypt_key = os.environ.get("FEISHU_ENCRYPT_KEY", "")
        if not encrypt_key:
            return {"code": 1, "msg": "FEISHU_ENCRYPT_KEY not configured"}
        decrypted = _feishu_decrypt(encrypt_key, raw["encrypt"])
        raw = _json.loads(decrypted)

    # ── URL verification challenge ────────────────────────────────────────
    if raw.get("type") == "url_verification":
        verification_token = os.environ.get("FEISHU_VERIFICATION_TOKEN", "")
        if verification_token and raw.get("token") != verification_token:
            return {"code": 1, "msg": "token mismatch"}
        return {"challenge": raw.get("challenge", "")}

    # ── Event v2.0 schema ─────────────────────────────────────────────────
    header = raw.get("header", {})
    event = raw.get("event", {})
    event_type = header.get("event_type", "")
    event_id = header.get("event_id", "")

    # Token verification
    verification_token = os.environ.get("FEISHU_VERIFICATION_TOKEN", "")
    if verification_token and header.get("token") != verification_token:
        return {"code": 1, "msg": "token mismatch"}

    # Dedup — Feishu may retry the same event
    if event_id and _feishu_dedup(event_id):
        return {"code": 0, "msg": "duplicate"}

    if event_type != "im.message.receive_v1":
        return {"code": 0, "msg": "ignored"}

    msg = event.get("message", {})
    msg_type = msg.get("message_type", "")
    if msg_type != "text":
        return {"code": 0, "msg": "non-text ignored"}

    # Parse text content (JSON-encoded string)
    try:
        content_obj = _json.loads(msg.get("content", "{}"))
        text = content_obj.get("text", "").strip()
    except (_json.JSONDecodeError, AttributeError):
        text = ""

    if not text:
        return {"code": 0, "msg": "empty"}

    chat_id: str = msg.get("chat_id", "")
    sender_id: str = event.get("sender", {}).get("sender_id", {}).get("open_id", "unknown")
    user_msg_id: str = msg.get("message_id", "")

    background_tasks.add_task(
        _handle_feishu_message,
        sender_id=sender_id,
        chat_id=chat_id,
        text=text,
        user_msg_id=user_msg_id,
    )
    return {"code": 0, "msg": "ok"}


async def _handle_feishu_message(
    *,
    sender_id: str,
    chat_id: str,
    text: str,
    user_msg_id: str,
) -> None:
    """
    Process a Feishu message with a 'streaming' UX:
    1. Immediately send a "⏳ Thinking..." placeholder.
    2. Run the agent.
    3. Update the placeholder message with the final answer.
    """
    client = _get_feishu_client()

    # Step 1 — send placeholder
    placeholder_id = await client.reply_text(user_msg_id, "⏳ Thinking...")

    # Step 2 — run agent
    agent = _get_agent(f"feishu:{sender_id}")
    try:
        reply = await agent.chat(text)
    except Exception as exc:  # noqa: BLE001
        reply = f"⚠️ Agent error: {exc}"

    # Step 3 — update placeholder with final answer (streaming feel)
    if placeholder_id:
        await client.update_text(placeholder_id, reply)
    else:
        # Fallback: send as new message if reply failed
        await client.send_text(chat_id, reply)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Health
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "project-omni"}
