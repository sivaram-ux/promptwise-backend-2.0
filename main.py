# === BACKEND (FastAPI with obfuscated API interface, real internal function names) ===
# File: main.py

from fastapi import FastAPI, Request
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import datetime
import uuid
from prompt_engine import (
    optimize_prompt,
    explain_prompt,
    log_prompt_to_supabase,
    deep_research_questions,
    save_deep_research_questions_separately,
    save_explanation_separately
)

app = FastAPI()

# Allow frontend from any origin for now
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Obfuscated API parameter schemas
class TaskInput(BaseModel):
    qtext: str  # maps to original 'prompt'
    variant: str  # maps to original 'mode'

class InsightInput(BaseModel):
    original_q: str  # maps to original 'original_prompt'
    improved_q: str  # maps to original 'optimized_prompt'
    variant: str  # maps to original 'mode'

class DeepTraceInput(BaseModel):
    ref_id: str  # maps to original 'prompt_id'
    qcontext: str  # maps to 'questions_asked'
    feedback: str  # maps to 'answers'
    choices: str = None  # maps to 'preferences'

class StoreMetaInput(BaseModel):
    ref_id: str
    data: dict

@app.post("/process")
async def process_data(input_data: TaskInput):
    result = ""
    for chunk in optimize_prompt(input_data.qtext, input_data.variant):
        result += chunk.content

    if os.environ.get("SUPABASE_KEY") and os.environ.get("SUPABASE_URL"):
        log_prompt_to_supabase(
            input_data.qtext,
            result,
            input_data.variant,
            model_used="gemini-2.5-flash"
        )
    return {"response": result}

@app.post("/reflect")
async def reflect_on_data(input_data: InsightInput):
    explanation = ""
    for chunk in explain_prompt(input_data.original_q, input_data.improved_q, input_data.variant):
        explanation += chunk.content
    return {"feedback": explanation}

@app.post("/trace")
async def trace_detail(input_data: DeepTraceInput):
    response = ""
    for chunk in (
        deep_research_questions(
            input_data.qcontext,
            input_data.feedback,
            input_data.choices or ""
        )
    ):
        response += chunk.content

    if input_data.ref_id:
        save_deep_research_questions_separately(
            prompt_id=input_data.ref_id,
            questions_asked=input_data.qcontext,
            answers=response,
            preferences=input_data.choices
        )

    return {"insight": response}

@app.post("/store-feedback")
async def store_feedback(input_data: StoreMetaInput):
    save_explanation_separately(input_data.ref_id, input_data.data)
    return {"status": "saved"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
