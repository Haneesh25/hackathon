# meet_gmail_direct.py
# Call Google Meet + Gmail using a hardcoded ACCESS TOKEN (no OAuth flow).
# If you prefer env vars, set GOOGLE_ACCESS_TOKEN / GMAIL_ACCESS_TOKEN and this will use them instead.

import os
import requests
from typing import Optional, Dict, List

# ---------- YOUR TEST TOKENS (fake, as requested) ----------
ACCESS_TOKEN = os.getenv("GOOGLE_ACCESS_TOKEN") or "ya29.a0ATi6K2vAED8Hpfvyp7dm4OhSpg8unzf2eU0isjsXyaSxQvYyKYpxkRdSRU8aLrLi0pFwbMsGx7jvXVYYVbDp1EjYL-SMywGtVm0HEAothvbTtTMSNeLfGW3grFfU9Q4dBiI5Rj3Ll8fswJMZJRvynK8DpWqtcfwh5Fs3hJ45UxctU7Ko3O1inopjsW03h4ia9Q1cdEgaCgYKAZISARcSFQHGX2MihvRKyP3f5tJ_9NfdGdBFVg0206"
GMAIL_ACCESS_TOKEN = os.getenv("GMAIL_ACCESS_TOKEN") or ACCESS_TOKEN

MEET_BASE  = "https://meet.googleapis.com/v2"
GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1"

def _bearer(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}

# -------------------- GOOGLE MEET --------------------
def meet_list_conference_records(page_size: int = 10, page_token: Optional[str] = None) -> Dict:
    params = {"pageSize": page_size}
    if page_token: params["pageToken"] = page_token
    r = requests.get(f"{MEET_BASE}/conferenceRecords", headers=_bearer(ACCESS_TOKEN), params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def meet_list_transcripts(conference_record_name: str, page_token: Optional[str] = None) -> Dict:
    params = {}
    if page_token: params["pageToken"] = page_token
    r = requests.get(f"{MEET_BASE}/{conference_record_name}/transcripts", headers=_bearer(ACCESS_TOKEN), params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def meet_list_transcript_entries(transcript_name: str, page_token: Optional[str] = None) -> Dict:
    params = {}
    if page_token: params["pageToken"] = page_token
    r = requests.get(f"{MEET_BASE}/{transcript_name}/entries", headers=_bearer(ACCESS_TOKEN), params=params, timeout=30)
    r.raise_for_status()
    return r.json()

# -------------------- GMAIL --------------------
def gmail_list_message_ids(query: Optional[str] = None, max_results: int = 100, page_token: Optional[str] = None) -> Dict:
    params = {"maxResults": max_results}
    if query: params["q"] = query
    if page_token: params["pageToken"] = page_token
    r = requests.get(f"{GMAIL_BASE}/users/me/messages", headers=_bearer(GMAIL_ACCESS_TOKEN), params=params, timeout=30)
    r.raise_for_status()
    return r.json()   # contains 'messages': [{'id':...}], and maybe 'nextPageToken'

def gmail_get_message(msg_id: str, fmt: str = "full") -> Dict:
    r = requests.get(f"{GMAIL_BASE}/users/me/messages/{msg_id}", headers=_bearer(GMAIL_ACCESS_TOKEN), params={"format": fmt}, timeout=30)
    r.raise_for_status()
    return r.json()

if __name__ == "__main__":
    # --- Meet sample ---
    try:
        cr = meet_list_conference_records(page_size=1)
        print("Meet conferenceRecords sample:", cr)
        if cr.get("conferenceRecords"):
            name = cr["conferenceRecords"][0]["name"]  # e.g., 'conferenceRecords/abc123'
            ts = meet_list_transcripts(name)
            print("Meet transcripts sample:", ts)
            if ts.get("transcripts"):
                tname = ts["transcripts"][0]["name"]     # e.g., 'conferenceRecords/abc123/transcripts/def456'
                entries = meet_list_transcript_entries(tname)
                print("Meet transcript entries sample:", entries)
    except requests.HTTPError as e:
        print("Meet HTTP error:", e.response.status_code, e.response.text[:400])
    except Exception as e:
        print("Meet error:", e)

    # --- Gmail sample ---
    try:
        ids_page = gmail_list_message_ids(query="newer_than:7d", max_results=5)
        print("Gmail message ids sample:", ids_page)
        if ids_page.get("messages"):
            first_id = ids_page["messages"][0]["id"]
            msg = gmail_get_message(first_id, fmt="full")
            print("Gmail first message sample:", {k: msg.get(k) for k in ["id","labelIds","snippet"]})
    except requests.HTTPError as e:
        print("Gmail HTTP error:", e.response.status_code, e.response.text[:400])
    except Exception as e:
        print("Gmail error:", e)
