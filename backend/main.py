from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
from groq import Groq
import google.generativeai as genai
from schema import RESUME_SCHEMA_TEMPLATE, EXTRACTION_PROMPT
from database import init_db, get_session, save_session, session_exists
from optimizer import search_role_insights, format_search_results_for_prompt, OPTIMIZATION_PROMPT, should_search_and_what
import json

def call_llm(messages, temperature=0.7):
    """Try Groq first; fall back to Gemini if rate-limited or fails."""
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=temperature
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Groq failed ({type(e).__name__}), falling back to Gemini...")
        # Convert messages format for Gemini (it doesn't use the same role structure)
        prompt_text = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        gemini_response = gemini_model.generate_content(prompt_text)
        return gemini_response.text

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
gemini_model = genai.GenerativeModel("gemini-2.0-flash")

init_db()

class ChatMessage(BaseModel):
    session_id: str
    message: str

SYSTEM_PROMPT = """You are a friendly, warm resume-building assistant having a natural conversation. Your job is to collect information for the user's resume, then extract it into structured JSON.

You need to collect, in this order:
1. Target role (what job they're building this resume for)
2. Personal info (full name, email, phone, location, linkedin, portfolio)
3. Work experience (company, role, employment_type, paid/unpaid, dates or duration, bullets/achievements)
4. Education (institution, degree, field of study, dates)
5. Skills (technical, soft, tools)
6. Projects (name, description, tech stack, link)
7. Certifications (name, issuer, date)

STYLE RULES:
- Ask exactly ONE question per reply — never stack two questions together.
- Sound like a real person, not a form. React naturally to what they just said (a short comment, light encouragement, or relevant observation) before asking the next question.
- Keep it brief: 1-2 sentences of natural reaction + 1 question. Total reply should be 2-3 sentences max, not more.
- Occasionally (not every time) you can add a small helpful tip related to what they just shared — e.g. if they mention a role, you can briefly note what's usually good to highlight for it. Keep this to a single short sentence when you do it, and don't do it every turn.
- Don't summarize or repeat back everything they've told you so far. No recaps.
- When you've collected enough information across all sections, say: "I have everything I need! Type 'generate' to see your resume data." Nothing else after that.

Example of GOOD reply: "A Google internship is a great foundation. How long were you there, and was it paid?"
Wait, that's two questions — correct version: "A Google internship is a great foundation — nice pick. How long were you there?"

Another GOOD example: "Nice, Software Engineer roles are in high demand right now. What's your full name?"

Example of BAD reply (too robotic): "What is your full name?"

Example of BAD reply (too much): "That's amazing, Google is such a prestigious company and this internship will really strengthen your resume! Can you tell me more about your role, what team you were on, what technologies you used, and how long you worked there?"
"""

@app.post("/chat")
async def chat(msg: ChatMessage):
    session = get_session(msg.session_id)
    if session is None:
        session = {
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}],
            "resume_data": {},
            "research_notes": ""
        }

    session["messages"].append({"role": "user", "content": msg.message})

    # Step A: check if this message is worth researching (every message, not just once)
    existing_research = session.get("research_notes", "")

    search_topic = should_search_and_what(msg.message, call_llm)
    if search_topic and search_topic not in existing_research:
        print(f"Triggering search for: {search_topic}")
        search_results = search_role_insights(search_topic)
        new_research = format_search_results_for_prompt(search_results)

        existing_research = existing_research + f"\n\n--- Research on: {search_topic} ---\n{new_research}"
        session["research_notes"] = existing_research
    
    # Step B: build the actual system prompt, with research if we have it
    messages_to_send = list(session["messages"])  # copy, don't mutate original
    if existing_research:
        research_note = {
            "role": "system",
            "content": f"You have this accumulated research available, covering multiple topics the user has mentioned:\n{existing_research}\n\nWhen it naturally fits the current topic being discussed, weave in ONE short, specific, actionable tip drawn from the MOST RELEVANT section above. Don't force it into every reply, and don't list multiple tips at once."
        }
        messages_to_send.append(research_note)

    

    reply = call_llm(messages_to_send, temperature=0.7)
    session["messages"].append({"role": "assistant", "content": reply})

    save_session(msg.session_id, session["messages"], session.get("resume_data"), session.get("research_notes"))

    return {"reply": reply}


@app.post("/get-conversation")
async def get_conversation(msg: ChatMessage):
    session = get_session(msg.session_id)
    if session is None:
        return {"messages": []}
    # Skip the system prompt when sending back to frontend
    visible_messages = [m for m in session["messages"] if m["role"] != "system"]
    return {"messages": visible_messages}

class ATSCheckRequest(BaseModel):
    session_id: str
    job_description: str

@app.post("/ats-check")
async def ats_check(req: ATSCheckRequest):
    session = get_session(req.session_id)
    if session is None:
        return {"error": "No session found. Start a conversation first."}

    resume_data = session.get("resume_data")
    if not resume_data:
        return {"error": "No resume data found. Generate your resume data first."}

    resume_text = json.dumps(resume_data)

    ats_prompt = f"""You are an ATS (Applicant Tracking System) keyword matcher. Compare the job description below against the candidate's resume data.

Job Description:
{req.job_description}

Candidate's Resume Data:
{resume_text}

Instructions:
1. Extract the 15-20 most important keywords/skills/qualifications from the job description (technical skills, tools, certifications, soft skills, years of experience, etc.)
2. Check which of these keywords are present (even if worded slightly differently) in the resume data.
3. Calculate a match percentage: (keywords found / total keywords) * 100
4. List the specific keywords that are MISSING from the resume.

Respond in EXACTLY this JSON format, nothing else, no markdown fences:
{{
  "match_score": <number 0-100>,
  "total_keywords": <number>,
  "keywords_found": ["keyword1", "keyword2", ...],
  "keywords_missing": ["keyword3", "keyword4", ...],
  "recommendation": "<1-2 sentence summary of what to add to improve the score>"
}}"""

    raw_output = call_llm([{"role": "user", "content": ats_prompt}], temperature=0).strip()

    if raw_output.startswith("```"):
        raw_output = raw_output.strip("`")
        if raw_output.startswith("json"):
            raw_output = raw_output[4:]

    try:
        ats_result = json.loads(raw_output)
        return ats_result
    except json.JSONDecodeError:
        return {"error": "Failed to parse ATS result", "raw_output": raw_output}

@app.post("/optimize-resume")
async def optimize_resume(msg: ChatMessage):
    session = get_session(msg.session_id)
    if session is None:
        return {"error": "No session found. Start a conversation first."}

    resume_data = session.get("resume_data")


    if not resume_data or not resume_data.get("target_role", {}).get("title"):
        return {"error": "No target role found yet. Complete the conversation and generate resume data first."}

    role_title = resume_data["target_role"]["title"]

    # Step 1: Web search
    search_results = search_role_insights(role_title)
    research_text = format_search_results_for_prompt(search_results)

    # Step 2: Build the optimization prompt
    prompt = OPTIMIZATION_PROMPT.format(
        role=role_title,
        research=research_text,
        resume_data=json.dumps(resume_data, indent=2)
    )

    # Step 3: Ask the LLM for suggestions
    suggestions = call_llm([{"role": "user", "content": prompt}], temperature=0.4)


    return {
        "role": role_title,
        "sources_used": list(dict.fromkeys([r["source"] for r in search_results])),
        "suggestions": suggestions
    }

@app.post("/generate-resume-data")
async def generate_resume_data(msg: ChatMessage):
    session = get_session(msg.session_id)
    if session is None:
        return {"error": "No session found. Start a conversation first."}


    # Build a plain-text version of the conversation (skip the system prompt)
    conversation_text = ""
    for m in session["messages"]:
        if m["role"] == "user":
            conversation_text += f"User: {m['content']}\n"
        elif m["role"] == "assistant":
            conversation_text += f"Assistant: {m['content']}\n"

    prompt = EXTRACTION_PROMPT.format(
        schema=json.dumps(RESUME_SCHEMA_TEMPLATE, indent=2),
        conversation=conversation_text
    )

    print("=== CONVERSATION SENT FOR EXTRACTION ===")
    print(conversation_text)
    print("=========================================")

    raw_output = call_llm([{"role": "user", "content": prompt}], temperature=0)

    print("=== RAW LLM OUTPUT ===")
    print(raw_output)
    print("=======================")

    # Clean up in case the model wraps it in markdown fences anyway
    if raw_output.startswith("```"):
        raw_output = raw_output.strip("`")
        if raw_output.startswith("json"):
            raw_output = raw_output[4:]

    try:
        extracted_data = json.loads(raw_output)
        session["resume_data"] = extracted_data
        save_session(msg.session_id, session["messages"], extracted_data)
        return {"resume_data": extracted_data}
    except json.JSONDecodeError:
        return {"error": "Failed to parse JSON", "raw_output": raw_output}

@app.get("/")
async def root():
    return {"status": "backend is running"}