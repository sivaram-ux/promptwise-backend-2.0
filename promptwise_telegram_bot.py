
import logging
import requests
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ConversationHandler, filters, ContextTypes

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# === Bot State Definitions ===
ASK_PROMPT, ASK_MODE = range(2)

# === Backend API Endpoint ===
BACKEND_URL = "https://promptwise-backend-2-0.onrender.com/optimize"

# === Start Command ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("🧠 Welcome to PromptWise Bot!\n\nPlease send me your raw prompt.")
    return ASK_PROMPT

# === Get Prompt from User ===
async def get_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["prompt"] = update.message.text
    await update.message.reply_text("🔍 Choose the optimization mode:", reply_markup=ReplyKeyboardMarkup(
        [["clarity", "depth", "deep_research"], ["creative", "structured"]],
        one_time_keyboard=True,
        resize_keyboard=True
    ))
    return ASK_MODE

# === Get Mode and Call Backend ===
async def get_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    prompt = context.user_data["prompt"]
    mode = update.message.text

    await update.message.reply_text("⚙️ Optimizing your prompt...")

    try:
        response = requests.post(BACKEND_URL, json={"prompt": prompt, "mode": mode})
        if response.status_code == 200:
            try:
                data = response.json()
                optimized = data.get("optimized_prompt", "⚠️ Backend responded with empty output.")
                await update.message.reply_text(f"✅ Optimized Prompt:\n\n{optimized}")
            except Exception as e:
                await update.message.reply_text(f"❌ JSON error: {e}\n\nRaw response:\n{response.text[:400]}")
        else:
            await update.message.reply_text(f"❌ API Error {response.status_code}:\n{response.text[:400]}")
    except Exception as e:
        await update.message.reply_text(f"🚨 Request failed: {str(e)}")

    return ConversationHandler.END

# === Cancel Command ===
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Cancelled. Use /start to try again.")
    return ConversationHandler.END

# === Main ===
def main():
    import os
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        raise ValueError("Set TELEGRAM_BOT_TOKEN environment variable")

    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_prompt)],
            ASK_MODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_mode)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(conv_handler)
    print("🤖 Bot is polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
