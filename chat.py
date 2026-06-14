from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from parser import (
    format_certifications,
    format_education,
    format_experience,
    format_languages,
)


def build_system_prompt(profile: dict) -> str:
    """Build the recruiter-assistant system prompt for a candidate profile."""
    return f"""You are an expert recruiter assistant analyzing this LinkedIn profile:

Name: {profile.get('full_name', 'Unknown')}
Headline: {profile.get('headline', 'N/A')}
About: {profile.get('about', 'Not provided')}
Current Company: {profile.get('current_company', 'N/A')}
Location: {profile.get('location_text', 'N/A')}

Experience:
{format_experience(profile.get('experience', []))}

Education:
{format_education(profile.get('education', []))}

Skills: {', '.join(profile.get('skills', [])) if profile.get('skills') else 'None listed'}
Languages: {format_languages(profile.get('languages', []))}
Certifications: {format_certifications(profile.get('certifications', []))}

Answer questions about this candidate specifically. Reference their actual experience, skills, and achievements. Be specific and actionable."""


def get_chat_llm(gemini_key: str) -> ChatGoogleGenerativeAI:
    """Create the chat LLM instance."""
    return ChatGoogleGenerativeAI(google_api_key=gemini_key, model="gemini-2.5-flash-lite")


def generate_chat_response(llm: ChatGoogleGenerativeAI, system_prompt: str, user_prompt: str) -> str:
    """Invoke the LLM with the system + user message and return the response text."""
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ])
    return response.content
