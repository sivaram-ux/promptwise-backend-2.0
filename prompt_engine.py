import os
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
#from keys import key,SUPABASE_KEY,SUPABASE_URL#Get these from environment variables

# Secure API Key Input
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
print("🔍 SUPABASE_URL:", os.getenv("SUPABASE_URL"))
print("🔍 SUPABASE_KEY:", os.getenv("SUPABASE_KEY")[:5], "..." if os.getenv("SUPABASE_KEY") else None)
# Init model
model = init_chat_model("gemini-2.5-flash", model_provider="google_genai")

modes = {
    "deep_research":"the prompt will be used by deep researching agent, it should enhance the quality such I get best research report covering each and every detail",
    "clarity": "Rewrite the prompt so that the LLM will produce an extremely clear and unambiguous response. Eliminate vagueness, add specific details, and enforce a logical structure.",
    "depth": "Rewrite the prompt to guide the LLM toward a thoughtful, multi-layered response. Encourage analysis, rationale, and contextual depth.",
    "creative": "Rewrite the prompt so the LLM delivers a highly imaginative and expressive response. Encourage the use of vivid examples, analogies, metaphors, and creative language.",
    "technical": "Rewrite the prompt so that the LLM generates precise, technically accurate content using domain-specific terminology, clear step-by-step logic, and relevant technical context.",
    "concise": "Rewrite the prompt to guide the LLM toward a brief, direct, and efficient response that retains clarity while reducing unnecessary verbosity.",
    "structured": "Rewrite the prompt to instruct the LLM to format the response cleanly, using bullet points, markdown tables, hierarchical sections, and clear headings.",
    "teaching": "Rewrite the prompt so that the LLM explains the topic progressively, with simple analogies, examples, and concepts tailored for a learning audience, including beginners.",
    "executive_summary": "Rewrite the prompt to elicit a high-level summary optimized for decision-makers. Prioritize key takeaways, actionable insights, and strategic framing.",
    "contrarian": "Rewrite the prompt to guide the LLM toward challenging conventional thinking. Encourage it to provide counterpoints, critique assumptions, and present alternative perspectives.",
    "step_by_step": "Rewrite the prompt to instruct the LLM to break down the response into clear, ordered steps or phases, with detailed explanations for each.",
    "journalistic": "Rewrite the prompt to elicit a response in the tone and structure of investigative or analytical journalism, including critical analysis, source-based reasoning, and consideration of bias.",
    "socratic": "Rewrite the prompt to instruct the LLM to ask probing, thought-provoking questions instead of providing direct answers—encouraging reflective or critical thinking from the user.",
    "controversial": "Rewrite the prompt to provoke the most controversial, unconventional, or polarizing response the LLM can generate. Push against mainstream assumptions while maintaining logical structure and factual support. Do not avoid sensitive or taboo perspectives unless ethically restricted.",
    "devil_advocate": "Rewrite the prompt to make the LLM take a strong opposing stance or play devil’s advocate. Encourage it to argue against popular opinion or the user's assumed position using logic, evidence, or satire.",
    "debate_ready": "Rewrite the prompt so that the LLM structures its answer like a formal argument — clearly outlining opposing viewpoints, rebuttals, and conclusion. Suitable for use in debates or persuasive writing.",
    "startup_pitch": "Rewrite the prompt to generate a polished, concise startup pitch. Include value proposition, problem/solution, market fit, and potential differentiation. Use persuasive, high-conviction tone.",
    "real_world_applications": "Rewrite the prompt to guide the LLM toward output that maps theoretical ideas to real-world use cases, industries, or everyday scenarios.",
    "personal_growth": "Rewrite the prompt so the LLM provides actionable advice, reflection prompts, and behavioral frameworks for improving mindset, habits, or emotional resilience.",
    "marketing_landing_page": "Rewrite the prompt to produce marketing copy suitable for a product or service landing page. Include headline, problem/solution framing, benefits, CTA, and testimonials if applicable.",
    "socratic_reverse": "Rewrite the prompt to make the LLM ask a sequence of layered, increasingly specific questions back to the user in order to clarify the problem or uncover blind spots.",
    "satirical": "Rewrite the prompt so that the LLM responds with sarcasm, exaggeration, or parody — in the style of satirical commentary or mockery of the topic.",
}
# Optimizer function
def optimize_prompt(raw_prompt, mode="clarity"):

    
    if mode == "deep_research":
        system = SystemMessage(
        f"""
    Act as a world-class prompt engineering expert.

    Your task is to transform a raw, basic user query into a fully optimized, detailed, and highly effective prompt designed for use with deep researching agents from gemini or chatgpt.

    🎯 Your optimized prompt must retain the original intent but dramatically expand its scope, specificity, and structure.

    ⚠️ CRITICAL INSTRUCTION: Do NOT output any commentary, apologies, or explanations. Output ONLY the **final refined prompt** as plain text.
    """.strip()
    )
    elif mode in modes:
        system = SystemMessage(
        f"""
    Act as a world-class prompt engineering expert.

    Your task is to transform a raw, basic user query into a fully optimized, detailed, and highly effective prompt designed for use with advanced LLMs like Gemini 1.5 Pro or Claude 3 Opus.

    🎯 Your optimized prompt must retain the original intent but dramatically expand its scope, specificity, and structure.

    🧠 Apply the following techniques where appropriate:

    1. **Role & Persona** — Assign an expert identity to the AI (e.g., “You are a veteran data scientist with 15 years of industry experience.”)
    2. **Context** — Add background info or assumptions to frame the task meaningfully.
    3. **Audience** — Define who the output is intended for (e.g., beginner, developer, executive).
    4. **Structure & Format** — Specify how the answer should be organized (e.g., "Use a three-part breakdown with bullets and a markdown table").
    5. **Goals & Intent** — State what the user wants to achieve (e.g., “The goal is to create a step-by-step learning plan...”).
    6. **Key Elements** — Include concepts, examples, analogies, pitfalls, comparisons, and optional depth levels.
    7. **Constraints** — Add exclusions if appropriate (e.g., “Do not include political commentary”).

    🎯 MOST IMPORTANT INSTRUCTION: **{modes[mode]}**

    ⚠️ CRITICAL INSTRUCTION: Do NOT output any commentary, apologies, or explanations. Output ONLY the **final refined prompt** as plain text.
    """.strip()
    )

    user = HumanMessage(f"Optimise this: {raw_prompt}")
    return model.stream([system, user])

def explain_prompt(original_prompt, optimized_prompt, mode="clarity"):
    explanation_request = HumanMessage(f"""
Act as a world-class prompt engineering expert.

Compare the following two prompts and return a structured analysis in **valid JSON format** using the schema below.

📌 Original Prompt:
"{original_prompt}"

🎯Final Goal of optimized prompt:
"{modes[mode]}"

✨ Optimized Prompt:
"{optimized_prompt}"

Return exactly this JSON object structure:

{{
  "original_prompt": {{
    "strengths": ["..."],
    "weaknesses": ["..."]
  }},
  "llm_understanding_improvements": ["..."],
  "tips_for_future_prompts": ["..."]
}}

🧠 Section Guidance:
👍 Original Prompt Strengths  
• (State what the user’s original prompt did well.)  
• (Be generous but honest.)

👎 Original Prompt Weaknesses  
• (Point out key missing elements or flaws in the original.)  
• (Explain the impact of those weaknesses.)

🧠 What LLMs Understand Better Now  
• (Explain how the refined prompt improves LLM comprehension.)  
• (Focus on structure, role, clarity, and specificity.)

💡 Tips for Future Prompts  
• (Give practical suggestions to improve prompt writing skills.)  
• (Focus on what to try next time — structure, constraints, or specificity.)

⚠️ Important Instructions:
- Do NOT output anything other than the JSON object.
- Make sure the response is valid JSON and not a markdown code block.
""")

    system = SystemMessage("You are a prompt engineer. You need to explain your own work.")
    return model.stream([system, explanation_request])
    

def deep_research_questions(original_prompt,optimised_prompt,questions_asked,preferences=""):
    if preferences:
        new_message_from_human= HumanMessage(
            f"""The model has asked the following questions:{questions_asked}
            My preferences:{preferences}
            Please answer them generally
            ⚠️ CRITICAL INSTRUCTION: Do NOT output any commentary, apologies, or explanations. Output ONLY the answers as plain text.
            """.strip()
        )
    else:
        new_message_from_human= HumanMessage(
            f"""The model has asked the following questions:{questions_asked}
            Please answer them generally
            ⚠️ CRITICAL INSTRUCTION: Do NOT output any commentary, apologies, or explanations. Output ONLY the answers as plain text.
            """.strip()
        )
    system = SystemMessage(
        f"""
    Act as a world-class prompt engineering expert.

    Your task is to transform a raw, basic user query into a fully optimized, detailed, and highly effective prompt designed for use with deep researching agents from gemini or chatgpt.

    🎯 Your optimized prompt must retain the original intent but dramatically expand its scope, specificity, and structure.

    ⚠️ CRITICAL INSTRUCTION: Do NOT output any commentary, apologies, or explanations. Output ONLY the **final refined prompt** as plain text.
    """.strip()
    )
    return model.stream([system,HumanMessage(f"Optimise this: {original_prompt}"),AIMessage(optimised_prompt),new_message_from_human])


import json
import re

def extract_json_from_response(response_text: str):
    # Strip code block formatting (e.g., ```json ... ```)
    json_str = re.search(r"```json\s+(.*?)```", response_text, re.DOTALL)
    if json_str:
        try:
            return json.loads(json_str.group(1))
        except json.JSONDecodeError as e:
            print(f"⚠️ JSON decode error: {e}")
    else:
        print("⚠️ JSON block not found.")
    return None


from supabase import create_client
import datetime
import uuid

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def log_prompt_to_supabase(
    original_prompt,
    optimized_prompt,
    mode,
    model_used="gemini-2.5-flash",
    user_location="global",
    session_id=None
):
    session_id = session_id or str(uuid.uuid4())
    timestamp = datetime.datetime.utcnow().isoformat()

    data = {
        "original_prompt": original_prompt,
        "optimized_prompt": optimized_prompt,
        "mode": mode,
        "model_used": model_used,
        "timestamp": timestamp,
        "session_id": session_id,
        "user_location": user_location
    }


    try:
        response = supabase.table("optimized_prompts").insert(data).execute()
        if response.data:
            prompt_id = response.data[0]["id"]
            print("✅ Prompt logged to Supabase.")
            return prompt_id
        else:
            print(f"❌ No data returned. Raw response: {response}")
    except Exception as e:
        print(f"❌ Failed to insert prompt: {e}")

def save_deep_research_questions_separately(prompt_id: str, questions_asked: str, answers: str, preferences: str = None):
    try:
        response = supabase.table("deep_research_questions").insert({
            "prompt_id": prompt_id,
            "questions_asked": questions_asked,
            "preferences": preferences,
            "answers": answers
        }).execute()
        if response.data:
            print("🧠 Explanation saved to Supabase.")
        else:
            print("❌ Explanation save failed.")
    except Exception as e:
        print(f"❌ Error saving explanation: {e}")

def save_explanation_separately(prompt_id: str, explanation_dict: dict):
    try:
        response = supabase.table("prompt_explanations").insert({
            "prompt_id": prompt_id,
            "explanation_json": explanation_dict
        }).execute()
        if response.data:
            print("🧠 Explanation saved to Supabase.")
        else:
            print("❌ Explanation save failed.")
    except Exception as e:
        print(f"❌ Error saving explanation: {e}")


# CLI usage
if __name__ == "__main__":
    prompt = "How indian stockmarket works?"
    mode="deep_research"
    print("\nOptimized Prompt:\n")
    optimized=""
    for chunk in optimize_prompt(prompt,mode):
        optimized+=chunk.content
        print(chunk.content, end="", flush=True)
    prompt_id = log_prompt_to_supabase(prompt,optimized,mode,"2o-flash")
    if mode == "deep_research":
        choice=input("Since it's a deep_research prompt - Did the model asked any questions? (y/n):").strip().lower()
        if choice == "y":
            questions_asked= input("What are the questions it asked?")
            choice= input("Do you have any preferences(answers to the questions asked?) (y/n)").strip().lower()
            if choice=="y":
                preferences=input("Preferences>")
                answers=""
                for chunk in deep_research_questions(prompt,optimized,questions_asked,preferences):
                    answers+=chunk.content
                    print(chunk.content, end="", flush=True)
                if prompt_id:
                    save_deep_research_questions_separately(prompt_id,questions_asked,answers,preferences)
            else:
                answers=""
                for chunk in deep_research_questions(prompt,optimized,questions_asked):
                    answers+=chunk.content
                    print(chunk.content, end="", flush=True)
                if prompt_id:
                    save_deep_research_questions_separately(prompt_id,questions_asked,answers)
            
    

    choice = input("\n🤔 Want explanation? (y/n): ").strip().lower()
    if choice == "y":
        print("\n📘 Explanation:\n")
        complete_explanation = ""
        for chunk in explain_prompt(prompt, optimized, mode):
            complete_explanation+=chunk.content
        prompt_feedback = extract_json_from_response(complete_explanation)

        if prompt_feedback:
            print("\n🧠 Prompt Feedback Analysis:\n")

            # 👍 Strengths
            print("👍 Original Prompt Strengths:")
            for s in prompt_feedback["original_prompt"].get("strengths", []):
                print(f"  • {s}")
            if not prompt_feedback["original_prompt"].get("strengths"):
                print("  • (No strengths detected)")

            # 👎 Weaknesses
            print("\n👎 Original Prompt Weaknesses:")
            for w in prompt_feedback["original_prompt"].get("weaknesses", []):
                print(f"  • {w}")
            if not prompt_feedback["original_prompt"].get("weaknesses"):
                print("  • (No weaknesses detected)")

            # 🧠 Improvements
            print("\n🧠 What LLMs Understand Better Now:")
            for u in prompt_feedback.get("llm_understanding_improvements", []):
                print(f"  • {u}")
            if not prompt_feedback.get("llm_understanding_improvements"):
                print("  • (No improvements listed)")

            # 💡 Tips
            print("\n💡 Tips for Future Prompts:")
            for t in prompt_feedback.get("tips_for_future_prompts", []):
                print(f"  • {t}")
            if not prompt_feedback.get("tips_for_future_prompts"):
                print("  • (No tips available)")

            print("\n" + "="*60 + "\n")
            if prompt_id:
                save_explanation_separately(prompt_id,prompt_feedback)
        else:
            print("❌ Failed to extract prompt feedback.")
        

