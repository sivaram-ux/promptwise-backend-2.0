from fastapi import FastAPI, Request
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import datetime
import uuid
from prompt_engine import optimize_prompt as do_task, explain_prompt as analyze_task, log_prompt_to_supabase

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

@app.post("/process")
async def process_data(input_data: TaskInput):
    result = ""
    for chunk in do_task(input_data.qtext, input_data.variant):
        result += chunk.content

    # Log to Supabase if keys exist
    if os.environ.get("SUPABASE_KEY") and os.environ.get("SUPABASE_URL"):
        log_prompt_to_supabase(
            input_data.qtext,
            result,
            input_data.variant,
            model_used="BASIC"
        )
    return {"response": result}

@app.post("/reflect")
async def reflect_on_data(input_data: InsightInput):
    explanation = ""
    for chunk in analyze_task(input_data.original_q, input_data.improved_q, input_data.variant):
        explanation += chunk.content
    return {"feedback": explanation}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
