import json
import sqlite3
from datetime import datetime, timezone

DB_PATH = "recruitool.db"


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT,
            headline TEXT,
            about TEXT,
            current_company TEXT,
            location_text TEXT,
            skills TEXT,
            experience TEXT,
            education TEXT,
            certifications TEXT,
            projects TEXT,
            languages TEXT,
            publications TEXT,
            profile_image_url TEXT,
            linkedin_url TEXT UNIQUE,
            raw_data TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()


def save_candidate(profile: dict, raw_data: list | None = None) -> int:
    init_db()
    conn = _get_connection()
    cursor = conn.execute(
        """
        INSERT INTO candidates
            (full_name, headline, about, current_company, location_text,
             skills, experience, education, certifications, projects,
             languages, publications, profile_image_url, linkedin_url, raw_data)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(linkedin_url) DO UPDATE SET
            full_name       = excluded.full_name,
            headline        = excluded.headline,
            about           = excluded.about,
            current_company = excluded.current_company,
            location_text   = excluded.location_text,
            skills          = excluded.skills,
            experience      = excluded.experience,
            education       = excluded.education,
            certifications  = excluded.certifications,
            projects        = excluded.projects,
            languages       = excluded.languages,
            publications    = excluded.publications,
            profile_image_url = excluded.profile_image_url,
            raw_data        = excluded.raw_data,
            created_at      = datetime('now')
        """,
        (
            profile.get("full_name"),
            profile.get("headline"),
            profile.get("about"),
            profile.get("current_company"),
            profile.get("location_text"),
            json.dumps(profile.get("skills", [])),
            json.dumps(profile.get("experience", [])),
            json.dumps(profile.get("education", [])),
            json.dumps(profile.get("certifications", [])),
            json.dumps(profile.get("projects", [])),
            json.dumps(profile.get("languages", [])),
            json.dumps(profile.get("publications", [])),
            profile.get("photo"),
            profile.get("linkedin_url"),
            json.dumps(raw_data) if raw_data else None,
        ),
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return row_id


def get_all_candidates() -> list[dict]:
    init_db()
    conn = _get_connection()
    rows = conn.execute(
        "SELECT id, full_name, headline, linkedin_url, created_at FROM candidates ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_candidate_by_id(candidate_id: int) -> dict | None:
    init_db()
    conn = _get_connection()
    row = conn.execute(
        "SELECT * FROM candidates WHERE id = ?", (candidate_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return _deserialize_row(dict(row))


def get_candidate_by_linkedin_url(url: str) -> dict | None:
    init_db()
    conn = _get_connection()
    row = conn.execute(
        "SELECT * FROM candidates WHERE linkedin_url = ?", (url,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return _deserialize_row(dict(row))


def _deserialize_row(row: dict) -> dict:
    for field in ("skills", "experience", "education", "certifications", "projects", "languages", "publications"):
        val = row.get(field)
        if isinstance(val, str):
            row[field] = json.loads(val)
    raw = row.get("raw_data")
    if isinstance(raw, str):
        row["raw_data"] = json.loads(raw)
    if row.get("profile_image_url"):
        row["photo"] = row["profile_image_url"]
    return row
