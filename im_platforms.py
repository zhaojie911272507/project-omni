"""IM Platform integrations for Project Omni.

Telegram, Slack, and Discord bot support.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from agent import Agent


# ─────────────────────────────────────────────────────────────────────────────
# Telegram Bot
# ─────────────────────────────────────────────────────────────────────────────

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")


async def handle_telegram_update(update: dict[str, Any], agent_cache: dict) -> dict:
    """Handle Telegram webhook update."""
    if not TELEGRAM_BOT_TOKEN:
        return {"error": "Telegram bot not configured"}

    message = update.get("message", {})
    if not message:
        return {"ok": True}

    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")

    if not chat_id or not text:
        return {"ok": True}

    # Get or create agent for this chat
    session_id = f"telegram:{chat_id}"
    if session_id not in agent_cache:
        agent_cache[session_id] = Agent(model=os.getenv("OMNI_MODEL", "gpt-4o-mini"))

    agent = agent_cache[session_id]

    try:
        reply = await agent.chat(text)
    except Exception as exc:  # noqa: BLE001
        reply = f"Error: {exc}"

    # Send reply
    import httpx

    async with httpx.AsyncClient() as client:
        await client.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": reply,
                "parse_mode": "Markdown",
            },
        )

    return {"ok": True}


# ─────────────────────────────────────────────────────────────────────────────
# Slack Bot
# ─────────────────────────────────────────────────────────────────────────────

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN", "")


def verify_slack_request(
    body: bytes,
    timestamp: str,
    signature: str,
) -> bool:
    """Verify Slack request signature."""
    if not SLACK_SIGNING_SECRET:
        return True  # Skip verification if not configured

    base_string = f"v0:{timestamp}:{body.decode()}"
    hmac_obj = hmac.new(
        SLACK_SIGNING_SECRET.encode(),
        base_string.encode(),
        hashlib.sha256,
    )
    expected_signature = f"v0={hmac_obj.hexdigest()}"

    return hmac.compare_digest(expected_signature, signature)


async def handle_slack_event(event: dict[str, Any], agent_cache: dict) -> dict:
    """Handle Slack event."""
    if not SLACK_BOT_TOKEN:
        return {"error": "Slack bot not configured"}

    event_type = event.get("type")
    if event_type != "message":
        return {"ok": True}

    # Ignore bot messages
    if event.get("bot_id"):
        return {"ok": True}

    channel = event.get("channel")
    user = event.get("user")
    text = event.get("text", "")
    ts = event.get("ts")

    if not text or not channel:
        return {"ok": True}

    # Get or create agent
    session_id = f"slack:{channel}:{user}"
    if session_id not in agent_cache:
        agent_cache[session_id] = Agent(model=os.getenv("OMNI_MODEL", "gpt-4o-mini"))

    agent = agent_cache[session_id]

    try:
        reply = await agent.chat(text)
    except Exception as exc:  # noqa: BLE001
        reply = f"Error: {exc}"

    # Send reply to Slack
    import httpx

    async with httpx.AsyncClient() as client:
        await client.post(
            "https://slack.com/api/chat.postMessage",
            json={
                "channel": channel,
                "text": reply,
                "thread_ts": ts,
            },
            headers={
                "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
                "Content-Type": "application/json",
            },
        )

    return {"ok": True}


# ─────────────────────────────────────────────────────────────────────────────
# Discord Bot
# ─────────────────────────────────────────────────────────────────────────────

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
DISCORD_PUBLIC_KEY = os.getenv("DISCORD_PUBLIC_KEY", "")


def verify_discord_request(
    body: bytes,
    signature: str,
    timestamp: str,
) -> bool:
    """Verify Discord request signature."""
    if not DISCORD_PUBLIC_KEY:
        return True

    import hmac

    message = timestamp.encode() + body
    hmac_obj = hmac.new(
        DISCORD_PUBLIC_KEY.encode(),
        message,
        hashlib.sha256,
    )
    expected_signature = hmac_obj.hexdigest()

    return hmac.compare_digest(expected_signature, signature)


async def handle_discord_interaction(interaction: dict[str, Any], agent_cache: dict) -> dict:
    """Handle Discord interaction."""
    if not DISCORD_BOT_TOKEN:
        return {"error": "Discord bot not configured"}

    interaction_type = interaction.get("type")

    # Ping (health check)
    if interaction_type == 1:
        return {"type": 1}

    # Message component or command
    if interaction_type in (2, 3, 4, 5):
        # Get the data
        data = interaction.get("data", {})
        options = data.get("options", [])

        # Get message from various sources
        if interaction_type == 2:  # Application command
            text = " ".join(
                o.get("value", "") for o in options
            ) if options else ""
        elif interaction_type == 3:  # Message component
            text = interaction.get("message", {}).get("content", "")
        else:
            text = ""

        # Get channel and user
        channel_id = interaction.get("channel_id")
        user = interaction.get("member", {}).get("user", {})
        user_id = user.get("id", "unknown")

        # Get or create agent
        session_id = f"discord:{channel_id}:{user_id}"
        if session_id not in agent_cache:
            agent_cache[session_id] = Agent(
                model=os.getenv("OMNI_MODEL", "gpt-4o-mini")
            )

        agent = agent_cache[session_id]

        try:
            reply = await agent.chat(text)
        except Exception as exc:  # noqa: BLE001
            reply = f"Error: {exc}"

        # Return as Discord message
        return {
            "type": 4,  # Channel message with source
            "data": {
                "content": reply,
            },
        }

    return {"error": "Unknown interaction type"}


# ─────────────────────────────────────────────────────────────────────────────
# IM Platform Manager
# ─────────────────────────────────────────────────────────────────────────────

class IMPlatformManager:
    """Manages multiple IM platform connections."""

    def __init__(self):
        self.agent_cache: dict[str, Agent] = {}

    async def handle_telegram(self, update: dict) -> dict:
        return await handle_telegram_update(update, self.agent_cache)

    async def handle_slack(self, event: dict) -> dict:
        return await handle_slack_event(event, self.agent_cache)

    async def handle_discord(self, interaction: dict) -> dict:
        return await handle_discord_interaction(interaction, self.agent_cache)


# Global manager
_im_manager: IMPlatformManager | None = None


def get_im_manager() -> IMPlatformManager:
    """Get or create IM platform manager."""
    global _im_manager
    if _im_manager is None:
        _im_manager = IMPlatformManager()
    return _im_manager