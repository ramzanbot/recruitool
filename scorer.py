import json

from langchain_google_genai import ChatGoogleGenerativeAI

from parser import (
    format_certifications,
    format_education,
    format_experience,
    format_languages,
)


def build_scoring_prompt(profile: dict, jd_text: str) -> str:
    """Build the job-fit scoring prompt for a candidate against a job description."""
    return f"""You are a recruiting analyst. Score this candidate against the job description on a scale of 1-10 for each dimension, then give an overall score out of 100.

CANDIDATE PROFILE:
Name: {profile['full_name']}
Current Role: {profile['headline']}
Current Company: {profile['current_company']}
Location: {profile['location_text']}

Experience: {format_experience(profile['experience'])}
Education: {format_education(profile['education'])}
Skills: {', '.join(profile['skills']) if profile['skills'] else 'None'}
Languages: {format_languages(profile['languages'])}
Certifications: {format_certifications(profile['certifications'])}

JOB DESCRIPTION:
{jd_text}

Return ONLY a JSON object (no markdown, no code fences) with:
{{
  "overall_score": <1-100>,
  "dimensions": {{
    "experience_match": <1-10>,
    "skills_match": <1-10>,
    "education_match": <1-10>,
    "location_match": <1-10>
  }},
  "summary": "<2-3 sentence explanation>",
  "key_matches": ["<match 1>", "<match 2>", ...],
  "potential_gaps": ["<gap 1>", "<gap 2>", ...]
}}"""


def score_candidate(gemini_key: str, profile: dict, jd_text: str) -> dict:
    """Run the scoring LLM and parse the JSON result.

    Raises json.JSONDecodeError if the LLM returns malformed JSON (the raw
    response is available on the exception's `doc` attribute). Other failures
    propagate as exceptions.
    """
    scoring_prompt = build_scoring_prompt(profile, jd_text)

    scoring_llm = ChatGoogleGenerativeAI(
        google_api_key=gemini_key, model="gemini-2.5-flash-lite"
    )
    response = scoring_llm.invoke(scoring_prompt)
    raw_response = response.content.strip()

    # Strip code fences if present
    if raw_response.startswith("```"):
        raw_response = raw_response.split("\n", 1)[1] if "\n" in raw_response else raw_response[3:]
        if raw_response.endswith("```"):
            raw_response = raw_response[:-3]
        raw_response = raw_response.strip()
        if raw_response.lower().startswith("json"):
            raw_response = raw_response[4:].strip()

    return json.loads(raw_response)
