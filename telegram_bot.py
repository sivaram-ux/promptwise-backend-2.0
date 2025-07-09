#telegram_bot - using promptwise-backend-2-0.onrender.com API

import logging
import aiohttp
from io import StringIO
from telegram import Update, InputFile
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from keys import TELEGRAM_BOT_TOKEN  # Place your Telegram bot token here

ASK_PROMPT, ASK_MODE, ASK_FOLLOWUP, ASK_EXPLAIN = range(4)

API_BASE = "https://promptwise-backend-2-0.onrender.com"  # Replace with your backend URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_send_strategy(response_text: str, filename: str = "response.txt"):
    MAX_LENGTH = 4000
    if len(response_text) <= MAX_LENGTH:
        return "text", response_text
    elif len(response_text) <= MAX_LENGTH * 5:
        chunks = [response_text[i:i + MAX_LENGTH] for i in range(0, len(response_text), MAX_LENGTH)]
        return "chunks", chunks
    else:
        buffer = StringIO(response_text)
        return "file", InputFile(buffer, filename)

def format_explanation_to_messages(data: dict) -> list[str]:
    messages = ["🧠 *Prompt Feedback Analysis*"]
    strengths = data.get("original_prompt", {}).get("strengths", [])
    if strengths:
        msg = "👍 *Original Prompt Strengths*"
        for s in strengths: msg += f"\n• {s}"
        messages.append(msg)
    weaknesses = data.get("original_prompt", {}).get("weaknesses", [])
    if weaknesses:
        msg = "👎 *Original Prompt Weaknesses*"
        for s in weaknesses: msg += f"\n• {s}"
        messages.append(msg)
    for title, key in [
        ("🧠 *What LLMs Understand Better Now*", "llm_understanding_improvements"),
        ("💡 *Tips for Future Prompts*", "tips_for_future_prompts")
    ]:
        values = data.get(key, [])
        if values:
            msg = title
            for v in values: msg += f"\n• {v}"
            messages.append(msg)
    return messages

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome! Please send your raw prompt.")
    return ASK_PROMPT

async def handle_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["prompt"] = update.message.text
    await update.message.reply_text("🔧 Enter the mode (e.g., clarity, deep_research, creative, etc):")
    return ASK_MODE

async def handle_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = update.message.text
    await update.message.reply_text("⚙️ Optimizing your prompt...")

    async with aiohttp.ClientSession() as session:
        async with session.post(f"{API_BASE}/optimize", json={
            "prompt": context.user_data["prompt"],
            "mode": context.user_data["mode"]
        }) as resp:
            result = await resp.json()
            context.user_data["optimized"] = result["optimized_prompt"]
            context.user_data["id"] = result["id"]

    strategy, output = get_send_strategy(context.user_data["optimized"])
    if strategy == "text":
        await update.message.reply_text(output)
    elif strategy == "chunks":
        for chunk in output: await update.message.reply_text(chunk)
    else:
        await update.message.reply_document(output)

    if context.user_data["mode"] == "deep_research":
        await update.message.reply_text("🤔 Want to answer follow-up questions? (yes/no)")
        return ASK_FOLLOWUP
    else:
        await update.message.reply_text("📘 Want explanation of the optimization? (yes/no)")
        return ASK_EXPLAIN

async def handle_followup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.lower().startswith("y"):
        await update.message.reply_text("📝 Please enter the questions the model asked:")
        return ASK_FOLLOWUP + 10
    else:
        await update.message.reply_text("📘 Want explanation of the optimization? (yes/no)")
        return ASK_EXPLAIN

async def collect_questions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["questions_asked"] = update.message.text
    await update.message.reply_text("📋 Any preferences/answers? (or type 'no')")
    return ASK_FOLLOWUP + 11

async def collect_answers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prefs = update.message.text
    if prefs.lower() == "no": prefs = ""
    context.user_data["preferences"] = prefs

    async with aiohttp.ClientSession() as session:
        async with session.post(f"{API_BASE}/followup", json={
            "prompt_id": context.user_data["id"],
            "questions_asked": context.user_data["questions_asked"],
            "answers": context.user_data["optimized"],
            "preferences": prefs
        }) as resp:
            result = await resp.json()
            response = result.get("followup_response", "")
            strategy, output = get_send_strategy(response)
            if strategy == "text":
                await update.message.reply_text(output)
            elif strategy == "chunks":
                for chunk in output: await update.message.reply_text(chunk)
            else:
                await update.message.reply_document(output)

    await update.message.reply_text("📘 Want explanation of the optimization? (yes/no)")
    return ASK_EXPLAIN

async def handle_explain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.lower().startswith("y"):
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{API_BASE}/explain", json={
                "original_prompt": context.user_data["prompt"],
                "optimized_prompt": context.user_data["optimized"],
                "mode": context.user_data["mode"]
            }) as resp:
                result = await resp.json()
                raw = result.get("explanation", "")
                import re, json
                match = re.search(r'{.*}', raw, re.DOTALL)
                try:
                    parsed = json.loads(match.group()) if match else None
                    if parsed:
                        for msg in format_explanation_to_messages(parsed):
                            await update.message.reply_text(msg, parse_mode="Markdown")
                        await session.post(f"{API_BASE}/log-feedback", json={
                            "prompt_id": context.user_data["id"],
                            "explanation_json": parsed
                        })
                    else:
                        await update.message.reply_text(raw)
                except:
                    await update.message.reply_text(raw)
    else:
        await update.message.reply_text("✅ Done. Use /start to begin again.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_prompt)],
            ASK_MODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_mode)],
            ASK_FOLLOWUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_followup)],
            ASK_FOLLOWUP + 10: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_questions)],
            ASK_FOLLOWUP + 11: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_answers)],
            ASK_EXPLAIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_explain)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    app.add_handler(conv)
    app.run_polling()

if __name__ == "__main__":
    main()
