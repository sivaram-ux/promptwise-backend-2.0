
from fastapi import FastAPI, Request
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import datetime
import uuid
from prompt_engine import optimize_prompt, explain_prompt, log_prompt_to_supabase

app = FastAPI()

# Allow frontend from any origin for now
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class PromptRequest(BaseModel):
    prompt: str
    mode: str

class ExplainRequest(BaseModel):
    original: str
    optimized: str
    mode: str

@app.post("/optimize")
async def optimize(request: PromptRequest):
    optimized = ""
    for chunk in optimize_prompt(request.prompt, request.mode):
        optimized += chunk.content

    # Log to Supabase if keys exist
    if os.environ.get("SUPABASE_KEY") and os.environ.get("SUPABASE_URL"):
        log_prompt_to_supabase(
            request.prompt,
            optimized,
            request.mode,
            model_used="gemini-2.5-flash"
        )
    return {"optimized": optimized}

@app.post("/explain")
async def explain(request: ExplainRequest):
    explanation = ""
    for chunk in explain_prompt(request.original, request.optimized, request.mode):
        explanation += chunk.content
    return {"explanation": explanation}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)