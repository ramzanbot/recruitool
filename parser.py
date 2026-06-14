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
