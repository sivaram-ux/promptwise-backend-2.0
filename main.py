import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

from telegram import Update, InputFile
from io import StringIO

from prompt_engine import (
    optimize_prompt,
    explain_prompt,
    log_prompt_to_supabase,
    deep_research_questions,
    save_deep_research_questions_separately,
    save_explanation_separately,
    extract_json_from_response,
)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# === FastAPI ===
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.post("/optimize")
async def optimize_endpoint(data: OptimizeRequest):
    optimized = "".join([chunk.content for chunk in optimize_prompt(data.prompt, data.mode)])
    prompt_id = log_prompt_to_supabase(
        original_prompt=data.prompt,
        optimized_prompt=optimized,
        mode=data.mode
    )
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
ASK_PROMPT, ASK_MODE, ASK_FOLLOWUP, ASK_EXPLAIN = range(4)

def get_send_strategy(response_text: str, filename: str = "response.txt"):
    MAX = 4000
    if len(response_text) <= MAX:
        return "text", response_text
    elif len(response_text) <= MAX * 5:
        return "chunks", [response_text[i:i + MAX] for i in range(0, len(response_text), MAX)]
    else:
        return "file", InputFile(StringIO(response_text), filename)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome! Send your raw prompt.")
    return ASK_PROMPT

async def handle_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["prompt"] = update.message.text
    await update.message.reply_text("🔧 Enter the mode (e.g., clarity, deep_research):")
    return ASK_MODE

async def handle_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = update.message.text
    await update.message.reply_text("⚙️ Optimizing your prompt...")

    optimized = "".join([chunk.content for chunk in optimize_prompt(context.user_data["prompt"], context.user_data["mode"])])
    context.user_data["optimized"] = optimized
    context.user_data["id"] = log_prompt_to_supabase(
        original_prompt=context.user_data["prompt"],
        optimized_prompt=optimized,
        mode=context.user_data["mode"]
    )

    strategy, output = get_send_strategy(optimized)
    if strategy == "text":
        await update.message.reply_text(output)
    elif strategy == "chunks":
        for chunk in output:
            await update.message.reply_text(chunk)
    else:
        await update.message.reply_document(output)

    await update.message.reply_text("📘 Want explanation of the optimization? (yes/no)")
    return ASK_EXPLAIN

async def handle_explain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.lower().startswith("y"):
        explanation = "".join([chunk.content for chunk in explain_prompt(
            context.user_data["prompt"],
            context.user_data["optimized"],
            context.user_data["mode"]
        )])
        parsed = extract_json_from_response(explanation)
        if parsed:
            save_explanation_separately(context.user_data["id"], parsed)
            await update.message.reply_text(str(parsed))
        else:
            await update.message.reply_text(explanation)
    else:
        await update.message.reply_text("✅ Done. Use /start to begin again.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END

async def run_bot():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_prompt)],
            ASK_MODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_mode)],
            ASK_EXPLAIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_explain)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    application.add_handler(conv)
    await application.run_polling()

# === Run API + Bot ===
if __name__ == "__main__":
    import uvicorn
    async def main():
        await asyncio.gather(
            run_bot(),
            uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=8000)).serve()
        )

    asyncio.run(main())
