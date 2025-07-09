import os
import asyncio
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler
)
from prompt_engine import (
    optimize_prompt, explain_prompt, log_prompt_to_supabase,
    deep_research_questions, save_deep_research_questions_separately,
    save_explanation_separately, extract_json_from_response
)

# === ENV VARS ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# === FASTAPI SETUP ===
app = FastAPI()
app.add_middleware(CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === PYDANTIC MODELS ===
class OptimizeRequest(BaseModel):
    prompt: str
    mode: str

class ExplainRequest(BaseModel):
    original_prompt: str
    optimized_prompt: str
    mode: str
    prompt_id: str = "external-user"

class ResearchFollowupRequest(BaseModel):
    prompt_id: str
    questions_asked: str
    answers: str
    preferences: str = None

class FeedbackLogRequest(BaseModel):
    prompt_id: str
    explanation_json: dict

# === FASTAPI ROUTES ===
@app.post("/optimize")
async def optimize_endpoint(data: OptimizeRequest):
    optimized = "".join([chunk.content for chunk in optimize_prompt(data.prompt, data.mode)])
    prompt_id = log_prompt_to_supabase(data.prompt, optimized, data.mode, "gemini-2.5-flash")
    return {"id": prompt_id, "optimized_prompt": optimized}

@app.post("/explain")
async def explain_endpoint(data: ExplainRequest):
    explanation = "".join([chunk.content for chunk in explain_prompt(data.original_prompt, data.optimized_prompt, data.mode)])
    parsed = extract_json_from_response(explanation)
    if parsed:
        save_explanation_separately(data.prompt_id, parsed)
    return {"explanation": explanation}

@app.post("/followup")
async def followup_endpoint(data: ResearchFollowupRequest):
    response = "".join([chunk.content for chunk in deep_research_questions(
        data.questions_asked, data.answers, data.preferences or "")])
    save_deep_research_questions_separately(data.prompt_id, data.questions_asked, response, data.preferences)
    return {"followup_response": response}

@app.post("/log-feedback")
async def log_feedback_endpoint(data: FeedbackLogRequest):
    save_explanation_separately(data.prompt_id, data.explanation_json)
    return {"status": "success"}

# === TELEGRAM BOT SETUP ===
logging.basicConfig(level=logging.INFO)
ASK_PROMPT, ASK_MODE, ASK_FOLLOWUP, ASK_EXPLAIN = range(4)

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
    optimized = "".join([chunk.content for chunk in optimize_prompt(context.user_data["prompt"], context.user_data["mode"])])
    context.user_data["optimized"] = optimized
    context.user_data["id"] = log_prompt_to_supabase(context.user_data["prompt"], optimized, context.user_data["mode"], "gemini-2.5-flash")
    await update.message.reply_text(optimized[:4000])
    if context.user_data["mode"] == "deep_research":
        await update.message.reply_text("🤔 Want to answer follow-up questions? (yes/no)")
        return ASK_FOLLOWUP
    await update.message.reply_text("📘 Want explanation of the optimization? (yes/no)")
    return ASK_EXPLAIN

async def handle_followup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.lower().startswith("y"):
        await update.message.reply_text("📝 Enter the questions the model asked:")
        return ASK_FOLLOWUP + 10
    await update.message.reply_text("📘 Want explanation of the optimization? (yes/no)")
    return ASK_EXPLAIN

async def collect_questions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["questions_asked"] = update.message.text
    await update.message.reply_text("📋 Any preferences or answers? (or type 'no')")
    return ASK_FOLLOWUP + 11

async def collect_answers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prefs = update.message.text if update.message.text.lower() != "no" else ""
    response = "".join([chunk.content for chunk in deep_research_questions(
        context.user_data["questions_asked"], context.user_data["optimized"], prefs)])
    save_deep_research_questions_separately(
        context.user_data["id"], context.user_data["questions_asked"], response, prefs)
    await update.message.reply_text(response[:4000])
    await update.message.reply_text("📘 Want explanation of the optimization? (yes/no)")
    return ASK_EXPLAIN

async def handle_explain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.lower().startswith("y"):
        explanation = "".join([chunk.content for chunk in explain_prompt(
            context.user_data["prompt"], context.user_data["optimized"], context.user_data["mode"])])
        parsed = extract_json_from_response(explanation)
        if parsed:
            save_explanation_separately(context.user_data["id"], parsed)
            await update.message.reply_text("\n".join([f"• {s}" for s in parsed.get("tips_for_future_prompts", [])])[:4000])
        else:
            await update.message.reply_text(explanation[:4000])
    else:
        await update.message.reply_text("✅ Done. Use /start to begin again.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END

async def run_bot():
    app_telegram = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
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
    await app_telegram.initialize()
    await app_telegram.start()
    await app_telegram.updater.start_polling()
    await app_telegram.updater.idle()

async def main():
    from uvicorn import Config, Server
    config = Config(app=app, host="0.0.0.0", port=8000)
    server = Server(config)
    await asyncio.gather(server.serve(), run_bot())

if __name__ == "__main__":
    asyncio.run(main())
