"""
Multi-tenant Telegram bot — each merchant runs their own bot with their own token.

Usage:
    from telegram_bot.bot import start_bot, stop_bot, is_running
    start_bot("merchant@example.com", "BOT_TOKEN_123")  # starts a bot for this merchant
    stop_bot("merchant@example.com")                     # stops that merchant's bot
    is_running("merchant@example.com")                   # check status
"""
from __future__ import annotations

import asyncio
import logging
import threading
from collections import defaultdict
from typing import Optional

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from agent.core import chat
from agent.sanitizer import sanitize
from services.db import get_merchant

logger = logging.getLogger(__name__)

# Per-user conversation history (keyed by Telegram chat_id)
_MAX_HISTORY = 20
_conversations: dict[int, list[dict]] = defaultdict(list)

# Per-merchant bot instances: email -> {app, thread, loop, gateway}
_bots: dict[str, dict] = {}


# ── Handlers ─────────────────────────────────────────────────────────────────

async def _cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start — welcome the merchant."""
    chat_id = update.effective_chat.id
    _conversations[chat_id] = []
    await update.message.reply_text(
        "Welcome to Blocko Agent! I'm your payment assistant.\n\n"
        "Ask me anything about:\n"
        "- Payment troubleshooting\n"
        "- Store setup (WooCommerce, PrestaShop, etc.)\n"
        "- Transaction lookups\n"
        "- Fee advice\n\n"
        "Type /reset to clear conversation history."
    )


async def _cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /reset — clear conversation history."""
    chat_id = update.effective_chat.id
    _conversations[chat_id] = []
    await update.message.reply_text("Conversation cleared. How can I help?")


def _make_message_handler(merchant_email: str):
    """Create a message handler closure that uses the merchant's gateway."""

    async def _handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        user_text = update.message.text
        if not user_text:
            return

        history = _conversations[chat_id]
        history.append({"role": "user", "content": user_text})
        if len(history) > _MAX_HISTORY:
            history[:] = history[-_MAX_HISTORY:]

        try:
            await update.effective_chat.send_action("typing")

            # Resolve the merchant's gateway for the right system prompt
            gateway = "blockonomics"
            bot_info = _bots.get(merchant_email)
            if bot_info:
                gateway = bot_info.get("gateway", "blockonomics")

            reply = chat(list(history), gateway=gateway, merchant_email=merchant_email)
            reply = sanitize(reply)
            history.append({"role": "assistant", "content": reply})

            for i in range(0, len(reply), 4096):
                await update.message.reply_text(reply[i:i + 4096])

        except Exception as e:
            logger.error("Telegram chat error for chat_id=%s merchant=%s: %s", chat_id, merchant_email, e)
            await update.message.reply_text(
                "Sorry, something went wrong. Please try again in a moment."
            )

    return _handle_message


# ── Start / Stop ─────────────────────────────────────────────────────────────

def _run_bot(merchant_email: str, token: str) -> None:
    """Entry point for the background thread — creates event loop and runs bot."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", _cmd_start))
    app.add_handler(CommandHandler("reset", _cmd_reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _make_message_handler(merchant_email)))

    # Store references so stop_bot can shut it down
    if merchant_email in _bots:
        _bots[merchant_email]["app"] = app
        _bots[merchant_email]["loop"] = loop

    logger.info("Telegram bot starting for merchant=%s (polling)...", merchant_email)
    loop.run_until_complete(app.initialize())
    loop.run_until_complete(app.start())
    loop.run_until_complete(app.updater.start_polling(drop_pending_updates=True))

    loop.run_forever()

    # Cleanup after loop stops
    loop.run_until_complete(app.updater.stop())
    loop.run_until_complete(app.stop())
    loop.run_until_complete(app.shutdown())
    loop.close()
    logger.info("Telegram bot stopped for merchant=%s.", merchant_email)


def start_bot(token: str, merchant_email: str = "_default") -> bool:
    """Start a Telegram bot for a specific merchant. Returns True on success."""
    if merchant_email in _bots and _bots[merchant_email]["thread"].is_alive():
        logger.warning("Telegram bot already running for merchant=%s", merchant_email)
        return False

    if not token or not token.strip():
        logger.error("Cannot start Telegram bot: empty token.")
        return False

    # Resolve the merchant's gateway
    gateway = "blockonomics"
    if merchant_email != "_default":
        m = get_merchant(merchant_email)
        if m and m.get("gateways"):
            gateway = m["gateways"][0].lower()

    thread = threading.Thread(
        target=_run_bot,
        args=(merchant_email, token.strip()),
        daemon=True,
    )

    _bots[merchant_email] = {
        "thread": thread,
        "app": None,
        "loop": None,
        "gateway": gateway,
        "token": token.strip(),
    }

    thread.start()
    logger.info("Telegram bot thread started for merchant=%s (gateway=%s).", merchant_email, gateway)
    return True


def stop_bot(merchant_email: str = "_default") -> bool:
    """Gracefully stop a merchant's Telegram bot. Returns True if stopped."""
    bot = _bots.get(merchant_email)
    if not bot:
        return False

    loop = bot.get("loop")
    thread = bot.get("thread")

    if not loop or not thread or not thread.is_alive():
        _bots.pop(merchant_email, None)
        return False

    loop.call_soon_threadsafe(loop.stop)
    thread.join(timeout=10)
    _bots.pop(merchant_email, None)
    logger.info("Telegram bot thread stopped for merchant=%s.", merchant_email)
    return True


def is_running(merchant_email: str = "_default") -> bool:
    """Check if a merchant's Telegram bot is currently running."""
    bot = _bots.get(merchant_email)
    return bot is not None and bot["thread"].is_alive()


def get_running_bots() -> list[str]:
    """Return a list of merchant emails with running bots."""
    return [email for email, bot in _bots.items() if bot["thread"].is_alive()]
