import json

import streamlit as st

from chat import build_system_prompt, generate_chat_response, get_chat_llm
from database import get_all_candidates, get_candidate_by_id, save_candidate
from parser import parse_apify_profile
from scorer import score_candidate
from scraper import scrape_with_apify

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

    st.divider()
    st.subheader("Saved Candidates")
    candidates = get_all_candidates()
    if candidates:
        for c in candidates:
            label = c["full_name"] or c["linkedin_url"]
            if st.button(label, key=f"load_{c['id']}", use_container_width=True):
                loaded = get_candidate_by_id(c["id"])
                if loaded:
                    st.session_state["profile"] = loaded
                    st.session_state["apify_items"] = loaded.get("raw_data") or []
                    st.session_state.messages = []
                    system_prompt = build_system_prompt(loaded)
                    st.session_state["system_prompt"] = system_prompt
                    st.rerun()
    else:
        st.caption("No candidates saved yet.")

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
            system_prompt = build_system_prompt(profile)
            st.session_state["system_prompt"] = system_prompt
            if not raw_data.get("_from_cache"):
                save_candidate(profile, raw_data.get("data"))
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
                try:
                    try:
                        score_result = score_candidate(gemini_key, profile, jd_text)
                        st.session_state["score_result"] = score_result
                        st.session_state["job_description_text"] = jd_text
                        st.session_state["job_description"] = jd_text
                        # Append JD to system prompt so chat becomes JD-aware
                        st.session_state["system_prompt"] = (
                            st.session_state["system_prompt"] + "\n\nJOB CONTEXT:\n" + jd_text
                        )
                        st.rerun()
                    except json.JSONDecodeError as e:
                        st.error("LLM returned malformed JSON. Raw response:")
                        st.code(e.doc, language="text")
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

    llm = get_chat_llm(gemini_key)

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
                    output_text = generate_chat_response(
                        llm, st.session_state["system_prompt"], user_prompt
                    )
                    st.markdown(output_text)
                    st.session_state.messages.append({"role": "assistant", "content": output_text})
                except Exception as e:
                    st.error(f"Error generating response: {e}")
