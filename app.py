import json
import os
import datetime
import requests
import streamlit as st
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

DEBUG_LOG_DIR = "debug_logs"

def _log_api_call(endpoint: str, request_body: dict, response, label: str = ""):
    """Save the raw API request and response to a timestamped JSON file for debugging."""
    os.makedirs(DEBUG_LOG_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"{timestamp}_{label}.json" if label else f"{timestamp}_api_call.json"
    filepath = os.path.join(DEBUG_LOG_DIR, filename)

    try:
        response_body = response.json()
    except Exception:
        response_body = {"_raw_text": response.text[:10000]}

    log_entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "endpoint": endpoint,
        "status_code": response.status_code,
        "request_body": request_body,
        "response_body": response_body,
        "response_headers": dict(response.headers),
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(log_entry, f, indent=2, ensure_ascii=False, default=str)
    return filepath, log_entry


def scrape_with_apify(url: str):
    url = url.strip()
    if "linkedin.com/in/" not in url:
        st.error("Invalid URL: must be a LinkedIn profile URL containing 'linkedin.com/in/'.")
        return {"status": "error", "data": []}

    token = st.secrets.get("APIFY_KEY")
    if not token:
        st.error("Apify API key is missing. Add APIFY_KEY to your secrets.")
        return {"status": "error", "data": []}

    endpoint = "https://api.apify.com/v2/acts/harvestapi~linkedin-profile-scraper/run-sync-get-dataset-items"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    body = {
        "profileScraperMode": "Profile details no email ($4 per 1k)",
        "queries": [url],
    }

    try:
        response = requests.post(endpoint, headers=headers, json=body, timeout=300)
        log_path, log_entry = _log_api_call(endpoint, body, response, label="apify_scrape")

        if response.status_code == 429:
            st.error("Rate limit hit. Please wait a moment and try again.")
            st.session_state["_last_debug_log"] = log_path
            st.session_state["_last_debug_entry"] = log_entry
            return {"status": "error", "data": []}

        if response.status_code == 404:
            st.error("Apify actor not found. Please check the actor ID.")
            st.session_state["_last_debug_log"] = log_path
            st.session_state["_last_debug_entry"] = log_entry
            return {"status": "error", "data": []}

        if response.status_code not in (200, 201):
            st.error(f"Apify Error {response.status_code}: {response.text}")
            st.session_state["_last_debug_log"] = log_path
            st.session_state["_last_debug_entry"] = log_entry
            return {"status": "error", "data": []}

        items = response.json()
        if not items:
            st.warning("Apify returned empty results for this profile.")
            return {"status": "complete", "data": [], "_debug_log": log_path}

        return {"status": "complete", "data": items, "_debug_log": log_path}

    except requests.exceptions.Timeout:
        st.error("Request timed out after 300 seconds. Apify may be overloaded — try again later.")
        return {"status": "error", "data": []}
    except Exception as e:
        st.error(f"Request failed: {e}")
        return {"status": "error", "data": []}
    
def format_experience(experience: list) -> str:
    if not experience:
        return "None listed"
    lines = []
    for exp in experience:
        position = exp.get("position") or "Unknown Position"
        company = exp.get("company_name") or "Unknown Company"
        duration = exp.get("duration") or ""
        line = f"- {position} at {company}"
        if duration:
            line += f" ({duration})"
        lines.append(line)
    return "\n".join(lines)


def format_education(education: list) -> str:
    if not education:
        return "None listed"
    lines = []
    for edu in education:
        degree = edu.get("degree") or "Unknown Degree"
        institution = edu.get("institution") or "Unknown Institution"
        period = edu.get("period") or ""
        line = f"- {degree} from {institution}"
        if period:
            line += f" ({period})"
        lines.append(line)
    return "\n".join(lines)


def format_languages(languages: list) -> str:
    if not languages:
        return "None listed"
    parts = []
    for lang in languages:
        if isinstance(lang, dict):
            name = lang.get("language") or "Unknown"
            proficiency = lang.get("proficiency")
            if proficiency:
                parts.append(f"{name} ({proficiency})")
            else:
                parts.append(name)
    return ", ".join(parts) if parts else "None listed"


def format_certifications(certifications: list) -> str:
    if not certifications:
        return "None listed"
    parts = []
    for cert in certifications:
        if isinstance(cert, dict):
            title = cert.get("title") or "Unknown"
            parts.append(title)
    return ", ".join(parts) if parts else "None listed"


def parse_apify_profile(raw_items: list) -> dict:
    """Transform a rich structured Apify response into a flat dict."""
    if not raw_items or not isinstance(raw_items, list):
        return None

    item = raw_items[0]
    if not isinstance(item, dict):
        return None

    element = item.get("element") if isinstance(item.get("element"), dict) else item
    if not element or not isinstance(element, dict):
        return None

    first_name = element.get("firstName")
    last_name = element.get("lastName")
    full_name = f"{first_name or ''} {last_name or ''}".strip() or None

    location = element.get("location") or {}
    location_text = location.get("linkedinText")
    country_code = location.get("countryCode")
    parsed_loc = location.get("parsed") or {}
    location_city = parsed_loc.get("city")
    location_state = parsed_loc.get("state")
    location_country = parsed_loc.get("countryFull")
    if not location_text:
        location_text = element.get("geoLocationName")

    current_positions = element.get("currentPosition") or []
    current_company = None
    if isinstance(current_positions, list) and current_positions:
        current_company = current_positions[0].get("companyName")

    experience_raw = element.get("experience") or []
    experience = []
    if isinstance(experience_raw, list):
        for exp in experience_raw:
            if not isinstance(exp, dict):
                continue
            start_date = exp.get("startDate") or {}
            end_date = exp.get("endDate") or {}
            experience.append({
                "position": exp.get("position"),
                "company_name": exp.get("companyName"),
                "description": exp.get("description"),
                "duration": exp.get("duration"),
                "employment_type": exp.get("employmentType"),
                "start_date_text": start_date.get("text") if isinstance(start_date, dict) else None,
                "end_date_text": end_date.get("text") if isinstance(end_date, dict) else None,
                "location": exp.get("location"),
                "company_linkedin_url": exp.get("companyLinkedinUrl"),
            })

    education_raw = element.get("education") or []
    education = []
    if isinstance(education_raw, list):
        for edu in education_raw:
            if not isinstance(edu, dict):
                continue
            start_date = edu.get("startDate") or {}
            end_date = edu.get("endDate") or {}
            education.append({
                "institution": edu.get("title") or edu.get("schoolName"),
                "degree": edu.get("degree") or edu.get("degreeName"),
                "period": edu.get("period"),
                "start_date_text": start_date.get("text") if isinstance(start_date, dict) else None,
                "end_date_text": end_date.get("text") if isinstance(end_date, dict) else None,
                "link": edu.get("link") or edu.get("schoolLinkedinUrl"),
            })

    certifications_raw = element.get("certifications") or []
    certifications = []
    if isinstance(certifications_raw, list):
        for cert in certifications_raw:
            if not isinstance(cert, dict):
                continue
            issued_at = cert.get("issuedAt") or {}
            certifications.append({
                "title": cert.get("title"),
                "issued_at": issued_at.get("text") if isinstance(issued_at, dict) else None,
                "issued_by": cert.get("issuedBy"),
                "issued_by_link": cert.get("issuedByLink"),
            })

    skills_raw = element.get("skills") or []
    skills = []
    if isinstance(skills_raw, list):
        for skill in skills_raw:
            if isinstance(skill, dict):
                name = skill.get("name")
                if name:
                    skills.append(name)

    languages_raw = element.get("languages") or []
    languages = []
    if isinstance(languages_raw, list):
        for lang in languages_raw:
            if isinstance(lang, dict):
                languages.append({
                    "language": lang.get("language"),
                    "proficiency": lang.get("proficiency"),
                })

    projects_raw = element.get("projects") or []
    projects = []
    if isinstance(projects_raw, list):
        for proj in projects_raw:
            if not isinstance(proj, dict):
                continue
            start_date = proj.get("startDate") or {}
            end_date = proj.get("endDate") or {}
            projects.append({
                "title": proj.get("title"),
                "description": proj.get("description"),
                "duration": proj.get("duration"),
                "start_date_text": start_date.get("text") if isinstance(start_date, dict) else None,
                "end_date_text": end_date.get("text") if isinstance(end_date, dict) else None,
            })

    publications_raw = element.get("publications") or []
    publications = []
    if isinstance(publications_raw, list):
        for pub in publications_raw:
            if not isinstance(pub, dict):
                continue
            published_at = pub.get("publishedAt") or {}
            publications.append({
                "title": pub.get("title"),
                "published_at": published_at.get("text") if isinstance(published_at, dict) else None,
                "link": pub.get("link"),
            })

    return {
        "first_name": first_name,
        "last_name": last_name,
        "full_name": full_name,
        "headline": element.get("headline"),
        "about": element.get("about"),
        "photo": element.get("photo") or (element.get("profilePicture") or {}).get("url"),
        "linkedin_url": element.get("linkedinUrl"),
        "location_text": location_text,
        "location_city": location_city,
        "location_state": location_state,
        "location_country": location_country,
        "country_code": country_code,
        "current_company": current_company,
        "connections_count": element.get("connectionsCount"),
        "follower_count": element.get("followerCount"),
        "open_to_work": element.get("openToWork"),
        "hiring": element.get("hiring"),
        "verified": element.get("verified"),
        "top_skills": element.get("topSkills"),
        "websites": element.get("websites") or [],
        "registered_at": element.get("registeredAt"),
        "experience": experience,
        "education": education,
        "certifications": certifications,
        "skills": skills,
        "languages": languages,
        "projects": projects,
        "publications": publications,
        "received_recommendations": element.get("receivedRecommendations") or [],
    }

# --- STREAMLIT UI START ---
st.set_page_config(page_title="Recruiter AI", layout="wide")
st.title("🤖 LinkedIn Profile Analyzer")

# 1. Sidebar: Inputs
with st.sidebar:
    st.header("Configuration")

    gemini_key = st.secrets.get("GEMINI_API_KEY", None)
    if not gemini_key:
        gemini_key = st.text_input("Enter Gemini API Key", type="password")

    url_input = st.text_input(
        "Enter LinkedIn Profile URL",
        value="https://www.linkedin.com/in/sundarpichai/",
    )

    fetch_btn = st.button("🚀 Fetch Profile")

# 2. Main Area: Data & Chat
if fetch_btn and gemini_key:
    if "APIFY_KEY" not in st.secrets:
        st.error("Apify API key is missing from environment variables!")
    else:
        with st.spinner("Scraping LinkedIn profile via Apify..."):
            raw_data = scrape_with_apify(url_input)

        if raw_data and raw_data["status"] == "complete":
            st.session_state["apify_items"] = raw_data["data"]
            st.session_state["_last_debug_log"] = raw_data.get("_debug_log")
            profile = parse_apify_profile(raw_data["data"])
            st.session_state["profile"] = profile
            st.session_state.messages = []
            system_prompt = f"""You are an expert recruiter assistant analyzing this LinkedIn profile:

Name: {profile['full_name']}
Headline: {profile['headline']}
About: {profile['about']}
Current Company: {profile['current_company']}
Location: {profile['location_text']}

Experience:
{format_experience(profile['experience'])}

Education:
{format_education(profile['education'])}

Skills: {', '.join(profile['skills']) if profile['skills'] else 'None listed'}
Languages: {format_languages(profile['languages'])}
Certifications: {format_certifications(profile['certifications'])}

Answer questions about this candidate specifically. Reference their actual experience, skills, and achievements. Be specific and actionable."""
            st.session_state["system_prompt"] = system_prompt
            st.success("Profile loaded successfully!")

# 3. Persistent View (Data + Chat)
if "profile" in st.session_state:
    profile = st.session_state["profile"]

    # --- HEADER: Photo | Name/Headline/Location/Company/Stats ---
    col_photo, col_info = st.columns([1, 4])

    with col_photo:
        if profile.get("photo"):
            st.image(profile["photo"], width=120)

    with col_info:
        full_name = profile.get("full_name") or f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip()
        if full_name:
            st.header(full_name)
        if profile.get("headline"):
            st.subheader(profile["headline"])

        location_parts = [p for p in [profile.get("location_city"), profile.get("location_state"), profile.get("location_country")] if p]
        location_str = ", ".join(location_parts) if location_parts else profile.get("location_text")
        company_str = profile.get("current_company")

        meta_parts = []
        if location_str:
            meta_parts.append(f"📍 {location_str}")
        if company_str:
            meta_parts.append(f"🏢 {company_str}")
        if meta_parts:
            st.markdown("  |  ".join(meta_parts))

        stats_parts = []
        if profile.get("connections_count"):
            stats_parts.append(f"👥 {profile['connections_count']} connections")
        if profile.get("follower_count"):
            stats_parts.append(f"{profile['follower_count']} followers")
        if stats_parts:
            st.markdown("  |  ".join(stats_parts))

        badges = []
        if profile.get("open_to_work"):
            badges.append("🟢 Open to Work")
        if profile.get("hiring"):
            badges.append("🟢 Hiring")
        if profile.get("verified"):
            badges.append("✅ Verified")
        if badges:
            st.markdown("  |  ".join(badges))

        if profile.get("linkedin_url"):
            st.markdown(f"🔗 [LinkedIn Profile]({profile['linkedin_url']})")

    # --- ABOUT ---
    if profile.get("about"):
        st.subheader("About")
        st.write(profile["about"])

    # --- TOP SKILLS ---
    if profile.get("top_skills"):
        st.subheader("Top Skills")
        top_skills = profile["top_skills"]
        if isinstance(top_skills, list):
            badges_html = "".join(
                f"<span style='background:#e0e0e0;color:#000;border-radius:12px;padding:3px 10px;margin:2px;display:inline-block;font-size:0.85em'>{s}</span>"
                for s in top_skills if s
            )
            st.markdown(badges_html, unsafe_allow_html=True)
        elif isinstance(top_skills, str):
            st.markdown(f"<span style='background:#e0e0e0;color:#000;border-radius:12px;padding:3px 10px;margin:2px;display:inline-block;font-size:0.85em'>{top_skills}</span>", unsafe_allow_html=True)

    # --- EXPERIENCE ---
    if profile.get("experience"):
        st.subheader("Experience")
        exp_list = profile["experience"]
        max_visible = 10
        visible_exp = exp_list[:max_visible]
        overflow_exp = exp_list[max_visible:]

        for i, exp in enumerate(visible_exp):
            with st.container():
                position = exp.get("position") or "Unknown Position"
                company = exp.get("company_name") or ""
                if company:
                    st.markdown(f"**{position}** at *{company}*")
                else:
                    st.markdown(f"**{position}**")

                detail_parts = [p for p in [exp.get("duration"), exp.get("location"), exp.get("employment_type")] if p]
                if detail_parts:
                    st.markdown(f"<span style='color:gray'>{' · '.join(detail_parts)}</span>", unsafe_allow_html=True)

                if exp.get("description"):
                    with st.expander("Description"):
                        st.write(exp["description"])

                if i < len(visible_exp) - 1:
                    st.divider()

        if overflow_exp:
            with st.expander("Show more experience..."):
                for exp in overflow_exp:
                    position = exp.get("position") or "Unknown Position"
                    company = exp.get("company_name") or ""
                    if company:
                        st.markdown(f"**{position}** at *{company}*")
                    else:
                        st.markdown(f"**{position}**")
                    detail_parts = [p for p in [exp.get("duration"), exp.get("location"), exp.get("employment_type")] if p]
                    if detail_parts:
                        st.markdown(f"<span style='color:gray'>{' · '.join(detail_parts)}</span>", unsafe_allow_html=True)
                    if exp.get("description"):
                        st.write(exp["description"])
                    st.divider()

    # --- EDUCATION ---
    if profile.get("education"):
        st.subheader("Education")
        for edu in profile["education"]:
            with st.container():
                parts = []
                if edu.get("degree"):
                    parts.append(f"**{edu['degree']}**")
                if edu.get("institution"):
                    parts.append(edu["institution"])
                if edu.get("period"):
                    parts.append(f"*{edu['period']}*")
                st.markdown("  ·  ".join(parts) if parts else "Unknown")
                st.divider()

    # --- CERTIFICATIONS ---
    if profile.get("certifications"):
        st.subheader("Certifications")
        with st.expander("View Certifications"):
            for cert in profile["certifications"]:
                cert_parts = [cert.get("title") or "Unknown"]
                if cert.get("issued_at"):
                    cert_parts.append(cert["issued_at"])
                if cert.get("issued_by"):
                    cert_parts.append(cert["issued_by"])
                st.markdown("  ·  ".join(cert_parts))
                st.divider()

    # --- SKILLS ---
    if profile.get("skills"):
        st.subheader("Skills")
        with st.expander("View All Skills"):
            skills_html = "".join(
                f"<span style='background:#e0e0e0;color:#000;border-radius:12px;padding:3px 10px;margin:2px;display:inline-block;font-size:0.85em'>{s}</span>"
                for s in profile["skills"] if s
            )
            st.markdown(skills_html, unsafe_allow_html=True)

    # --- LANGUAGES ---
    if profile.get("languages"):
        st.subheader("Languages")
        with st.expander("View Languages"):
            for lang in profile["languages"]:
                lang_str = lang.get("language") or "Unknown"
                if lang.get("proficiency"):
                    lang_str += f" ({lang['proficiency']})"
                st.markdown(f"- {lang_str}")

    # --- PROJECTS ---
    if profile.get("projects"):
        st.subheader("Projects")
        with st.expander("View Projects"):
            for proj in profile["projects"]:
                st.markdown(f"**{proj.get('title', 'Unknown')}**")
                if proj.get("description"):
                    st.write(proj["description"])
                if proj.get("duration"):
                    st.markdown(f"*{proj['duration']}*")
                st.divider()

    # --- PUBLICATIONS ---
    if profile.get("publications"):
        st.subheader("Publications")
        with st.expander("View Publications"):
            for pub in profile["publications"]:
                pub_parts = [pub.get("title") or "Unknown"]
                if pub.get("published_at"):
                    pub_parts.append(pub["published_at"])
                st.markdown("  ·  ".join(pub_parts))
                if pub.get("link"):
                    st.markdown(f"[Link]({pub['link']})")
                st.divider()

    # --- WEBSITES ---
    if profile.get("websites"):
        st.subheader("Websites")
        for site in profile["websites"]:
            if isinstance(site, dict):
                url = site.get("url") or site.get("link")
                label = site.get("label") or url
                if url:
                    st.markdown(f"- [{label}]({url})")
            elif isinstance(site, str) and site:
                st.markdown(f"- [{site}]({site})")

    # --- JOB-FIT SCORING ---
    st.divider()
    st.subheader("Job Fit Scoring")

    if "score_result" not in st.session_state:
        st.session_state["score_result"] = None
    if "job_description" not in st.session_state:
        st.session_state["job_description"] = None

    jd_text = st.text_area(
        "Paste a job description to score this candidate's fit:",
        value=st.session_state.get("job_description_text") or "",
        height=150,
        key="jd_input",
    )

    if st.button("Score Fit", key="score_fit_btn"):
        if not jd_text.strip():
            st.warning("Please paste a job description first.")
        else:
            with st.spinner("Scoring candidate..."):
                scoring_prompt = f"""You are a recruiting analyst. Score this candidate against the job description on a scale of 1-10 for each dimension, then give an overall score out of 100.

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

                try:
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

                    try:
                        score_result = json.loads(raw_response)
                        st.session_state["score_result"] = score_result
                        st.session_state["job_description_text"] = jd_text
                        st.session_state["job_description"] = jd_text
                        # Append JD to system prompt so chat becomes JD-aware
                        st.session_state["system_prompt"] = (
                            st.session_state["system_prompt"] + "\n\nJOB CONTEXT:\n" + jd_text
                        )
                        st.rerun()
                    except json.JSONDecodeError:
                        st.error("LLM returned malformed JSON. Raw response:")
                        st.code(raw_response, language="text")
                except Exception as e:
                    st.error(f"Scoring failed: {e}")

    # Display scoring results if available
    if st.session_state["score_result"]:
        score = st.session_state["score_result"]
        st.markdown("---")
        st.markdown(f"## Overall Fit: {score['overall_score']}/100")

        if "dimensions" in score:
            st.markdown("### Dimension Breakdown")
            dims = score["dimensions"]
            dim_labels = {
                "experience_match": "Experience",
                "skills_match": "Skills",
                "education_match": "Education",
                "location_match": "Location",
            }
            for key, label in dim_labels.items():
                val = dims.get(key, 0)
                st.markdown(f"**{label}** ({val}/10)")
                st.progress(val / 10)

        if score.get("summary"):
            st.markdown("### Summary")
            st.markdown(score["summary"])

        if score.get("key_matches"):
            st.markdown("### Key Matches")
            for match in score["key_matches"]:
                st.markdown(f"- {match}")

        if score.get("potential_gaps"):
            st.markdown("### Potential Gaps")
            for gap in score["potential_gaps"]:
                st.markdown(f"- {gap}")

    # --- CHAT INTERFACE ---
    st.divider()
    full_name = profile.get("full_name") or "Candidate"
    st.subheader(f"Chat with {full_name}")

    llm = ChatGoogleGenerativeAI(google_api_key=gemini_key, model="gemini-2.5-flash-lite")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    shortcut_prompt = None
    cols = st.columns(3)
    with cols[0]:
        if st.button("Summarize experience", use_container_width=True):
            shortcut_prompt = "Provide a concise summary of this person's professional experience, highlighting key roles and career progression."
    with cols[1]:
        if st.button("Key strengths & weaknesses", use_container_width=True):
            shortcut_prompt = "What are this candidate's key strengths and potential weaknesses based on their profile?"
    with cols[2]:
        if st.button("Draft outreach message", use_container_width=True):
            shortcut_prompt = "Draft a personalized LinkedIn outreach message for this candidate. Be warm but professional."

    user_prompt = None
    if shortcut_prompt:
        user_prompt = shortcut_prompt
    elif prompt := st.chat_input("Ask anything about this candidate..."):
        user_prompt = prompt

    if user_prompt and "system_prompt" in st.session_state:
        st.session_state.messages.append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.markdown(user_prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    response = llm.invoke([
                        SystemMessage(content=st.session_state["system_prompt"]),
                        HumanMessage(content=user_prompt),
                    ])
                    output_text = response.content
                    st.markdown(output_text)
                    st.session_state.messages.append({"role": "assistant", "content": output_text})
                except Exception as e:
                    st.error(f"Error generating response: {e}")