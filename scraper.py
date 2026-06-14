import json
import os
import datetime
import requests
import streamlit as st

from database import get_candidate_by_linkedin_url

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

    existing = get_candidate_by_linkedin_url(url)
    if existing:
        st.info(f"Loaded cached profile for {existing['full_name']}")
        return {"status": "complete", "data": existing.get("raw_data") or [], "_debug_log": None, "_from_cache": True}

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
