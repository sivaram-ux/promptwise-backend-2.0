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

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Models ===

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

# === Routes ===

@app.post("/optimize")
async def optimize_endpoint(data: OptimizeRequest):
    optimized = ""
    for chunk in optimize_prompt(data.prompt, data.mode):
        optimized += chunk.content

    if os.environ.get("SUPABASE_KEY") and os.environ.get("SUPABASE_URL"):
        log_prompt_to_supabase(
            original_prompt=data.prompt,
            optimized_prompt=optimized,
            mode=data.mode,
            model_used="gemini-2.5-flash"
        )

    return {"optimized_prompt": optimized}

@app.post("/explain")
async def explain_endpoint(data: ExplainRequest):
    explanation = ""
    for chunk in explain_prompt(data.original_prompt, data.optimized_prompt, data.mode):
        explanation += chunk.content

    if os.environ.get("SUPABASE_KEY") and os.environ.get("SUPABASE_URL"):
        parsed = extract_json_from_response(explanation)
        if parsed:
            save_explanation_separately(
                prompt_id="external-user",  # replace with real ID if tracked
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

# === Entry Point ===

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
