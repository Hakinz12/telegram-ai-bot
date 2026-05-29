import os
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path('.env'))

from telegram import Update
from telegram.ext import (
    ApplicationBuilder, MessageHandler, CommandHandler,
    ContextTypes, filters
)
from openai import OpenAI

# ── Logging ───────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY   = os.getenv("GROQ_API_KEY")

# ── Groq Client ───────────────────────────────────────────
groq_client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)

# ── System Prompt ─────────────────────────────────────────
SYSTEM_PROMPT = """You are a helpful, friendly assistant in a 
Telegram community group. Keep replies concise and relevant. 
If something is unclear, ask for clarification."""

# ── Conversation Memory ───────────────────────────────────
conversation_history = {}
MAX_HISTORY = 10

def get_history(chat_id):
    return conversation_history.get(chat_id, [])

def update_history(chat_id, role, content):
    if chat_id not in conversation_history:
        conversation_history[chat_id] = []
    conversation_history[chat_id].append({"role": role, "content": content})
    if len(conversation_history[chat_id]) > MAX_HISTORY * 2:
        conversation_history[chat_id] = conversation_history[chat_id][-MAX_HISTORY * 2:]

# ── Groq Reply ────────────────────────────────────────────
def get_ai_reply(chat_id, user_message):
    history  = get_history(chat_id)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += history
    messages.append({"role": "user", "content": user_message})
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=500,
        messages=messages
    )
    return response.choices[0].message.content

# ── Handlers ──────────────────────────────────────────────
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hello! I'm your AI assistant.\n\n"
        "📌 How to talk to me:\n"
        "• In a group: mention @username or reply to my message\n"
        "• In private chat: just send me a message directly!"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return

    chat_type    = message.chat.type
    bot_username = context.bot.username
    text         = message.text.strip()
    chat_id      = message.chat_id
    sender       = message.from_user.username or message.from_user.first_name

    should_reply = False

    if chat_type == "private":
        should_reply = True
    elif f"@{bot_username}" in text:
        should_reply = True
        text = text.replace(f"@{bot_username}", "").strip()
    elif (message.reply_to_message and
          message.reply_to_message.from_user.id == context.bot.id):
        should_reply = True

    if not should_reply:
        return

    logger.info(f"[{chat_type}] @{sender}: {text}")

    try:
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        reply = get_ai_reply(chat_id, text)
        update_history(chat_id, "user", text)
        update_history(chat_id, "assistant", reply)
        await message.reply_text(reply)
        logger.info(f"Replied: {reply[:80]}...")

    except Exception as e:
        logger.error(f"Error: {e}")
        await message.reply_text("Sorry, something went wrong. Please try again.")

# ── Main ──────────────────────────────────────────────────
def main():
    if not TELEGRAM_TOKEN:
        raise ValueError("❌ TELEGRAM_BOT_TOKEN is missing!")
    if not GROQ_API_KEY:
        raise ValueError("❌ GROQ_API_KEY is missing!")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🤖 Bot is live using GROQ!")
    app.run_polling()

if __name__ == "__main__":
    main()