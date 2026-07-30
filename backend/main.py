from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
from groq import Groq
from schema import RESUME_SCHEMA_TEMPLATE, EXTRACTION_PROMPT
import json

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# In-memory storage for now (we'll add a real database later)
sessions = {}

class ChatMessage(BaseModel):
    session_id: str
    message: str

SYSTEM_PROMPT = """You are a friendly resume-building assistant. Your job is to have a natural conversation with the user to collect information for their resume, then extract it into structured JSON.

You need to collect:
- personal_info (full_name, email, phone, location, linkedin, portfolio_url)
- target_role (title, industry)
- summary (a professional summary - you can help draft this)
- experience (company, role, employment_type, whether it was paid or unpaid, start/end dates or duration, bullets - achievements/responsibilities)
- education (institution, degree, field_of_study, start_date, end_date)
- skills (technical, soft, tools)
- projects (name, description, tech_stack, link)
- certifications (name, issuer, date)

When discussing work experience, always ask whether the role was paid or unpaid, and get the specific time period (either start and end month/year, or duration like "6 months").

Ask ONE question at a time. Be conversational, not robotic. Start by asking what role they're building a resume for, then their name and contact info, then move through experience, education, skills, projects, and certifications.

After each user response, acknowledge it briefly and ask the next logical question.

When the user says they're done or you've collected enough information, say "I have everything I need! Type 'generate' to see your resume data." """

@app.post("/chat")
async def chat(msg: ChatMessage):
    if msg.session_id not in sessions:
        sessions[msg.session_id] = {
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}],
            "resume_data": {}
        }
    
    session = sessions[msg.session_id]
    session["messages"].append({"role": "user", "content": msg.message})
    
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=session["messages"],
        temperature=0.7
    )
    
    reply = response.choices[0].message.content
    session["messages"].append({"role": "assistant", "content": reply})
    
    return {"reply": reply}

@app.post("/generate-resume-data")
async def generate_resume_data(msg: ChatMessage):
    if msg.session_id not in sessions:
        return {"error": "No session found. Start a conversation first."}

    session = sessions[msg.session_id]

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

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    conversation_text = ""
    for m in session["messages"]:
        if m["role"] == "user":
            conversation_text += f"User: {m['content']}\n"
        elif m["role"] == "assistant":
            conversation_text += f"Assistant: {m['content']}\n"

    print("=== CONVERSATION SENT FOR EXTRACTION ===")
    print(conversation_text)
    print("=========================================")

    raw_output = response.choices[0].message.content.strip()

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
        return {"resume_data": extracted_data}
    except json.JSONDecodeError:
        return {"error": "Failed to parse JSON", "raw_output": raw_output}

@app.get("/")
async def root():
    return {"status": "backend is running"}