# === BACKEND + TELEGRAM BOT (Unified) ===

from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from prompt_engine import (
    optimize_prompt,
    explain_prompt,
    log_prompt_to_supabase,
    deep_research_questions,
    save_deep_research_questions_separately,
    save_explanation_separately,
    extract_json_from_response
)

from telegram import Update, InputFile
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
import logging
from io import StringIO
from keys import TELEGRAM_BOT_TOKEN
import json
import re

# === FastAPI Setup ===
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Pydantic Models for FastAPI ===
class OptimizeRequest(BaseModel):
    prompt: str
    mode: str

class ExplainRequest(BaseModel):
    original_prompt: str
    optimized_prompt: str
    mode: str

class ResearchFollowupRequest(BaseModel):
    prompt_id: str
    questions_asked: str
    answers: str
    preferences: str = None

class FeedbackLogRequest(BaseModel):
    prompt_id: str
    explanation_json: dict

# === FastAPI Routes ===
@app.post("/optimize")
async def optimize_endpoint(data: OptimizeRequest):
    optimized = ""
    for chunk in optimize_prompt(data.prompt, data.mode):
        optimized += chunk.content

    id = None
    if os.environ.get("SUPABASE_KEY") and os.environ.get("SUPABASE_URL"):
        id = log_prompt_to_supabase(
            original_prompt=data.prompt,
            optimized_prompt=optimized,
            mode=data.mode,
            model_used="gemini-2.5-flash"
        )

    return {"id": id, "optimized_prompt": optimized}

@app.post("/explain")
async def explain_endpoint(data: ExplainRequest):
    explanation = ""
    for chunk in explain_prompt(data.original_prompt, data.optimized_prompt, data.mode):
        explanation += chunk.content

    if os.environ.get("SUPABASE_KEY") and os.environ.get("SUPABASE_URL"):
        parsed = extract_json_from_response(explanation)
        if parsed:
            save_explanation_separately(
                prompt_id=data.prompt_id if hasattr(data, 'prompt_id') else "external-user",
                explanation_dict=parsed
            )

    return {"explanation": explanation}

@app.post("/followup")
async def followup_endpoint(data: ResearchFollowupRequest):
    response = ""
    for chunk in deep_research_questions(data.questions_asked, data.answers, data.preferences or ""):
        response += chunk.content

    if data.prompt_id:
        save_deep_research_questions_separately(
            prompt_id=data.prompt_id,
            questions_asked=data.questions_asked,
            answers=response,
            preferences=data.preferences
        )

    return {"followup_response": response}

@app.post("/log-feedback")
async def log_feedback_endpoint(data: FeedbackLogRequest):
    save_explanation_separately(data.prompt_id, data.explanation_json)
    return {"status": "success"}

# === Telegram Bot ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ASK_PROMPT, ASK_MODE, ASK_FOLLOWUP, ASK_EXPLAIN = range(4)

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

    optimized = ""
    for chunk in optimize_prompt(context.user_data["prompt"], context.user_data["mode"]):
        optimized += chunk.content

    context.user_data["optimized"] = optimized
    context.user_data["id"] = log_prompt_to_supabase(
        original_prompt=context.user_data["prompt"],
        optimized_prompt=optimized,
        mode=context.user_data["mode"],
        model_used="gemini-2.5-flash"
    )

    strategy, output = get_send_strategy(optimized)
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

    response = ""
    for chunk in deep_research_questions(
        context.user_data["questions_asked"],
        context.user_data["optimized"],
        prefs
    ):
        response += chunk.content

    save_deep_research_questions_separately(
        prompt_id=context.user_data["id"],
        questions_asked=context.user_data["questions_asked"],
        answers=response,
        preferences=prefs
    )

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
        explanation = ""
        for chunk in explain_prompt(context.user_data["prompt"], context.user_data["optimized"], context.user_data["mode"]):
            explanation += chunk.content

        parsed = extract_json_from_response(explanation)
        if parsed:
            save_explanation_separately(context.user_data["id"], parsed)
            for msg in format_explanation_to_messages(parsed):
                await update.message.reply_text(msg, parse_mode="Markdown")
        else:
            await update.message.reply_text(explanation)
    else:
        await update.message.reply_text("✅ Done. Use /start to begin again.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END

def main():
    app_telegram = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
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
    app_telegram.add_handler(conv)
    app_telegram.run_polling()

if __name__ == "__main__":
    import threading
    threading.Thread(target=main).start()
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
