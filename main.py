import asyncio
import uvicorn
from promptwise_telegram_bot import main_bot  # assume this is async
from main2 import app  # FastAPI app

async def start_uvicorn():
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    # Run both main_bot() and uvicorn concurrently
    await asyncio.gather(
        main_bot(),         # your telegram bot loop
        start_uvicorn(),    # FastAPI server
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down servers gracefully...")
