RESUME_SCHEMA_TEMPLATE = {
    "personal_info": {
        "full_name": "",
        "email": "",
        "phone": "",
        "location": "",
        "linkedin": "",
        "portfolio_url": ""
    },
    "target_role": {
        "title": "",
        "industry": "",
        "job_description_pasted": ""
    },
    "summary": {
        "text": ""
    },
    "experience": [],
    "education": [],
    "skills": {
        "technical": [],
        "soft": [],
        "tools": []
    },
    "projects": [],
    "certifications": [],
    "meta": {
        "template_choice": "",
        "created_at": "",
        "last_updated": ""
    }
}
EXTRACTION_PROMPT = """You are a data extraction engine. Read the conversation below between a resume-building assistant and a user. Extract all the information the user has provided into this EXACT JSON structure. 

Rules:
- Output ONLY valid JSON. No explanations, no markdown code fences, no extra text.
- If a field wasn't mentioned, leave it as an empty string or empty array.
- For "experience", each entry should have: company, role, start_date, end_date, is_current (true/false), bullets (array of strings).
- For "education", each entry should have: institution, degree, field_of_study, start_date, end_date, gpa.
- For "projects", each entry should have: name, description, tech_stack (array), link.
- For "certifications", each entry should have: name, issuer, date.

JSON structure to fill:
{schema}

Conversation:
{conversation}

Output the filled JSON now:"""