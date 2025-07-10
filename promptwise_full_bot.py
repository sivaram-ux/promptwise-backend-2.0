import logging
import aiohttp
from io import StringIO
from telegram import Update, InputFile, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from keys import TELEGRAM_BOT_TOKEN  # put your bot token here

ASK_PROMPT, ASK_MODE, ASK_FOLLOWUP, ASK_EXPLAIN = range(4)

API_BASE = "https://promptwise-backend-2-0.onrender.com"  # your backend

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
    messages = []
    messages.append("🧠 *Prompt Feedback Analysis*")

    strengths = data.get("original_prompt", {}).get("strengths", [])
    if strengths:
        text = "👍 *Original Prompt Strengths*"
        for s in strengths:
            text += f"\\n• {s}"
        messages.append(text)

    weaknesses = data.get("original_prompt", {}).get("weaknesses", [])
    if weaknesses:
        text = "👎 *Original Prompt Weaknesses*"
        for w in weaknesses:
            text += f"\\n• {w}"
        messages.append(text)

    improvements = data.get("llm_understanding_improvements", [])
    if improvements:
        text = "🧠 *What the LLM Understands Better Now*"
        for u in improvements:
            text += f"\\n• {u}"
        messages.append(text)

    tips = data.get("tips_for_future_prompts", [])
    if tips:
        text = "💡 *Tips for Future Prompts*"
        for t in tips:
            text += f"\\n• {t}"
        messages.append(text)

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
    prompt = context.user_data["prompt"]
    mode = context.user_data["mode"]

    await update.message.reply_text("⚙️ Optimizing your prompt...")

    async with aiohttp.ClientSession() as session:
        async with session.post(f"{API_BASE}/optimize", json={"prompt": prompt, "mode": mode}) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                await update.message.reply_text(f"❌ Error: {error_text}")
                return ConversationHandler.END
            result = await resp.json()
            context.user_data["optimized"] = result["optimized_prompt"]

    strategy, output = get_send_strategy(context.user_data["optimized"])
    if strategy == "text":
        await update.message.reply_text(output)
    elif strategy == "chunks":
        for part in output:
            await update.message.reply_text(part)
    else:
        await update.message.reply_document(output)

    if mode == "deep_research":
        await update.message.reply_text("🤔 Want to answer follow-up questions? (yes/no)")
        return ASK_FOLLOWUP
    else:
        await update.message.reply_text("📘 Want explanation of the optimization? (yes/no)")
        return ASK_EXPLAIN

async def handle_followup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.lower().startswith("y"):
        await update.message.reply_text("✍️ Please enter the questions asked by the model:")
        context.user_data["wants_followup"] = True
        return ASK_FOLLOWUP + 10
    else:
        await update.message.reply_text("📘 Want explanation of the optimization? (yes/no)")
        return ASK_EXPLAIN

async def collect_questions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["questions_asked"] = update.message.text
    await update.message.reply_text("💬 Any preferences/answers to the questions? (or type 'no')")
    return ASK_FOLLOWUP + 11

async def collect_answers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    preferences = update.message.text
    if preferences.lower() == "no":
        preferences = ""
    context.user_data["preferences"] = preferences

    payload = {
        "prompt_id": "telegram-user",
        "questions_asked": context.user_data["questions_asked"],
        "answers": context.user_data["optimized"],
        "preferences": preferences
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(f"{API_BASE}/followup", json=payload) as resp:
            if resp.status != 200:
                await update.message.reply_text("❌ Error in follow-up.")
                return ConversationHandler.END
            result = await resp.json()
            followup = result.get("followup_response", "")
            strategy, output = get_send_strategy(followup)
            if strategy == "text":
                await update.message.reply_text(output)
            elif strategy == "chunks":
                for part in output:
                    await update.message.reply_text(part)
            else:
                await update.message.reply_document(output)

    await update.message.reply_text("📘 Want explanation of the optimization? (yes/no)")
    return ASK_EXPLAIN

async def handle_explain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.lower().startswith("y"):
        payload = {
            "original_prompt": context.user_data["prompt"],
            "optimized_prompt": context.user_data["optimized"],
            "mode": context.user_data["mode"]
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{API_BASE}/explain", json=payload) as resp:
                if resp.status != 200:
                    await update.message.reply_text("❌ Explanation request failed.")
                    return ConversationHandler.END
                result = await resp.json()
                explanation = result.get("explanation", "")
                try:
                    import json, re
                    json_text = re.search(r'{.*}', explanation, re.DOTALL)
                    if json_text:
                        parsed = json.loads(json_text.group(0))
                        messages = format_explanation_to_messages(parsed)
                        for msg in messages:
                            await update.message.reply_text(msg, parse_mode="Markdown")
                    else:
                        await update.message.reply_text(explanation)
                except Exception:
                    await update.message.reply_text(explanation)
    else:
        await update.message.reply_text("✅ Done. You can send another prompt with /start.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Canceled.")
    return ConversationHandler.END

def main_bot():
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
    main_bot()