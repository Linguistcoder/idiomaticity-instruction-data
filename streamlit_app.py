#!/usr/bin/env python3
"""
Streamlit UI for the idiomaticity fluency annotation task.

Data flow:
- Reads the source items straight from the JSON files in this repo
  (magpie_*_annotation.json).
- Every submitted annotation is appended as a row to a shared Google
  Sheet, so multiple annotators can work at the same time without
  overwriting a shared local file.
- The list of "already annotated" item IDs is re-read from the sheet
  whenever the annotator loads/reloads their queue, so two people
  working concurrently mostly won't be handed the same item twice.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# ── Config ────────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).parent

LANGUAGE_FILES = {
    "Swedish":   "magpie_swe_annotation.json",
    "Danish":    "magpie_dan_annotation.json",
    "Norwegian": "magpie_nob_annotation.json",
    "Icelandic": "magpie_isl_annotation.json",
}

CATEGORIES = {
    "grammar": "Grammar",
    "awkward phrasing": "Awkward phrasing",
    "punctuation": "Punctuation",
    "word choice": "Word choice",
    "flow": "Flow",
    "spelling": "Spelling",
    "translationese": "Translationese",
    "other language": "Other language",
    "unclear": "Unclear",
}

RESPONSE_PREVIEW_CHARS = 1200

SHEET_HEADER = [
    "timestamp_utc", "annotator", "language", "item_id",
    "task_category", "difficulty", "has_issues", "issues_json", "notes",
]

# ── Google Sheets connection ────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def get_worksheet():
    """Connect to the configured Google Sheet using service-account creds
    stored in Streamlit secrets. Creates the header row if the sheet is empty.
    """
    creds_dict = dict(st.secrets["gcp_service_account"])
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(st.secrets["sheet_id"])
    ws = sheet.sheet1
    if not ws.get_all_values():
        ws.append_row(SHEET_HEADER)
    return ws


def fetch_annotated_ids(ws, language):
    """Return the set of item_ids already annotated for this language,
    by anyone, according to the sheet."""
    records = ws.get_all_records()
    return {
        str(r["item_id"]) for r in records if r.get("language") == language
    }


def append_annotation(ws, annotator, language, item, issues, notes):
    row = [
        datetime.now(timezone.utc).isoformat(timespec="seconds"),
        annotator,
        language,
        str(item["id"]),
        item.get("task_category", ""),
        item.get("difficulty", ""),
        "yes" if issues else "no",
        json.dumps(issues, ensure_ascii=False),
        notes,
    ]
    ws.append_row(row, value_input_option="RAW")


# ── Data loading ─────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def load_items(filename):
    path = DATA_DIR / filename
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── Session state helpers ───────────────────────────────────────────────

def reset_queue():
    for key in ["queue", "queue_pos", "current_issues", "show_full_response"]:
        st.session_state.pop(key, None)


def build_queue(items, done_ids):
    return [it for it in items if str(it["id"]) not in done_ids]


# ── UI ───────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Fluency Annotation", layout="centered")

if "authed" not in st.session_state:
    st.session_state.authed = False

if not st.session_state.authed:
    pw = st.text_input("Access code", type="password")
    if pw == st.secrets.get("access_code", ""):
        st.session_state.authed = True
        st.rerun()
    st.stop()

st.title("Fluency Annotation")

with st.sidebar:
    st.header("Session")
    annotator = st.text_input("Your name (or initials)", key="annotator")
    language = st.selectbox("Language", list(LANGUAGE_FILES.keys()))

    if not annotator.strip():
        st.info("Enter your name to start annotating.")
        st.stop()

    if st.button("Load / refresh my queue", use_container_width=True):
        reset_queue()

# Connect to the sheet once we know the annotator wants to work.
try:
    ws = get_worksheet()
except Exception as e:
    st.error(
        "Couldn't connect to the Google Sheet. Check that `gcp_service_account` "
        "and `sheet_id` are set correctly in Streamlit secrets, and that the "
        "sheet is shared with the service account's email.\n\n"
        f"Details: {e}"
    )
    st.stop()

items = load_items(LANGUAGE_FILES[language])

# Build (or reuse) the queue for this language + session.
if "queue" not in st.session_state or st.session_state.get("queue_lang") != language:
    with st.spinner("Checking what's already annotated..."):
        done_ids = fetch_annotated_ids(ws, language)
    st.session_state.queue = build_queue(items, done_ids)
    st.session_state.queue_pos = 0
    st.session_state.queue_lang = language
    st.session_state.current_issues = []
    st.session_state.show_full_response = False

queue = st.session_state.queue
pos = st.session_state.queue_pos

st.sidebar.metric("Remaining in queue", max(len(queue) - pos, 0))
st.sidebar.metric("Total items", len(items))

if pos >= len(queue):
    st.success("No items left in the queue for this language. 🎉")
    st.caption("Someone may have just finished the last ones, or refresh to check for new work.")
    st.stop()

item = queue[pos]

st.progress(pos / max(len(queue), 1))
st.caption(
    f"Item ID {item['id']} · {item.get('task_category', '—')} · "
    f"{item.get('difficulty', '—')} · {pos + 1} of {len(queue)} in your queue"
)

st.subheader(":blue[Instruction]")
with st.container(border=True):
    st.write(item["instruction"])

st.subheader(":blue[Response]")
with st.container(border=True):
    response = item["response"]
    if len(response) > RESPONSE_PREVIEW_CHARS and not st.session_state.show_full_response:
        st.write(response[:RESPONSE_PREVIEW_CHARS] + " …")
        if st.button("Show full response"):
            st.session_state.show_full_response = True
            st.rerun()
    else:
        st.write(response)

st.divider()

# ── Step 1: fluency issues ────────────────────────────────────────────────

st.subheader("Step 1 — Fluency issues")

with st.form("issue_form", clear_on_submit=True):
    quote = st.text_input("Quote the problematic text")
    cats = st.multiselect("Category (one or more)", list(CATEGORIES.values()))
    severity = st.slider("Severity", 1, 5, 3, help="1 = subtle … 5 = very grave")
    correction = st.text_area("Optional: write the corrected version", height=80,
                              help="You may rewrite the problematic text to fix the issue."
                            )
    comment = st.text_area("Comments", height=60)
    add_issue = st.form_submit_button("Add issue")

    if add_issue:
        if not cats:
            st.warning("Pick at least one category before adding the issue.")
        else:
            st.session_state.current_issues.append({
                "quote": quote,
                "categories": cats,
                "severity": severity,
                "comment": comment,
                "correction": correction,
            })

if st.session_state.current_issues:
    st.write("**Issues added so far:**")
    for i, issue in enumerate(st.session_state.current_issues):
        cols = st.columns([8, 1])
        with cols[0]:
            st.markdown(
                f"- *\"{issue['quote']}\"* — {', '.join(issue['categories'])} "
                f"(severity {issue['severity']}): {issue['comment']}"
            )
        with cols[1]:
            if st.button("✕", key=f"remove_{i}"):
                st.session_state.current_issues.pop(i)
                st.rerun()

st.divider()

# ── Step 2: notes ─────────────────────────────────────────────────────────

st.subheader("Step 2 — Idioms / slang / cultural references & notes (optional)")
notes = st.text_area(
    "Tag any idiomatic expressions, slang, or cultural references and whether "
    "each is used correctly, plus any other notes.",
    height=100,
    key="notes_box",
)

st.divider()

# ── Submit / skip controls ─────────────────────────────────────────────────

def advance():
    st.session_state.queue_pos += 1
    st.session_state.current_issues = []
    st.session_state.show_full_response = False

c1, c2 = st.columns(2)
with c1:
    if st.button("Submit and next item", type="primary", use_container_width=True):
        append_annotation(
            ws, annotator, language, item,
            st.session_state.current_issues, notes,
        )
        advance()
        st.rerun()
with c2:
    if st.button("Skip this item", use_container_width=True):
        advance()
        st.rerun()