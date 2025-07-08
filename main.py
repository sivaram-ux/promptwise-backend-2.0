
from fastapi import FastAPI, Request
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import datetime
import uuid
from prompt_engine import (
    optimize_prompt as run_pipeline,
    explain_prompt as synth_meta,
    log_prompt_to_supabase as log_event,
    deep_research_questions as follow_up_probe,
    save_deep_research_questions_separately as cache_trace,
    save_explanation_separately as store_metadata
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

class TaskInput(BaseModel):
    qtext: str
    variant: str

class InsightInput(BaseModel):
    original_q: str
    improved_q: str
    variant: str

class DeepTraceInput(BaseModel):
    ref_id: str
    qcontext: str
    feedback: str
    choices: str = None

@app.post("/process")
async def process_data(input_data: TaskInput):
    result = ""
    for chunk in run_pipeline(input_data.qtext, input_data.variant):
        result += chunk.content

    if os.environ.get("SUPABASE_KEY") and os.environ.get("SUPABASE_URL"):
        log_event(
            input_data.qtext,
            result,
            input_data.variant,
            model_used="gemini-2.5-flash"
        )
    return {"response": result}

@app.post("/reflect")
async def reflect_on_data(input_data: InsightInput):
    explanation = ""
    for chunk in synth_meta(input_data.original_q, input_data.improved_q, input_data.variant):
        explanation += chunk.content
    return {"feedback": explanation}

@app.post("/trace")
async def trace_detail(input_data: DeepTraceInput):
    response = ""
    for chunk in (
        follow_up_probe(
            input_data.qcontext,
            input_data.feedback,
            input_data.choices or ""
        )
    ):
        response += chunk.content

    if input_data.ref_id:
        cache_trace(
            prompt_id=input_data.ref_id,
            questions_asked=input_data.qcontext,
            answers=response,
            preferences=input_data.choices
        )

    return {"insight": response}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
