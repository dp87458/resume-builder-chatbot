from ddgs import DDGS

def search_role_insights(role_title):
    """Search the web for resume tips and keywords specific to a role."""
    queries = [
        f"resume keywords for {role_title} 2026",
        f"{role_title} resume skills employers look for",
        f"ATS keywords {role_title} resume"
    ]

    all_results = []
    with DDGS() as ddgs:
        for query in queries:
            try:
                results = ddgs.text(query, max_results=3)
                for r in results:
                    all_results.append({
                        "title": r.get("title", ""),
                        "snippet": r.get("body", ""),
                        "source": r.get("href", "")
                    })
            except Exception as e:
                print(f"SEARCH FAILED for '{query}': {type(e).__name__}: {e}")

                print(f"Total search results collected: {len(all_results)}")

    return all_results


def format_search_results_for_prompt(results):
    """Turn raw search results into a compact text block for the LLM."""
    if not results:
        return "No web search results available."

    text = ""
    for r in results:
        text += f"- {r['title']}: {r['snippet']}\n"
    return text

OPTIMIZATION_PROMPT = """You are a resume optimization expert. Based on the web research below about what employers look for in a {role} role, and the user's current resume data, suggest specific improvements.

Web research findings:
{research}

User's current resume data:
{resume_data}

Give your response in this format:
1. **Missing keywords/skills**: List 5-8 relevant keywords or skills commonly expected for this role that are missing from the user's resume.
2. **Bullet point improvements**: For each experience entry, suggest 1-2 rewritten bullet points that are more specific, quantified, and aligned with what employers want (only suggest improvements based on what the user actually did — never invent achievements).
3. **Summary suggestion**: A 2-3 sentence professional summary tailored to this role, using the user's actual background.

Be specific and actionable, not generic. Base suggestions only on real patterns from the research, not assumptions."""