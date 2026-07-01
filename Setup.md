# Setup: Fluency Annotation Streamlit app

This app replaces the terminal `annotate.py` script with a web page.
Annotations are written to a shared Google Sheet, so several people can
annotate at the same time without overwriting each other's work.

## 1. Create the Google Sheet + service account (one-time, ~5 min)

1. Go to https://console.cloud.google.com/ and create a new project
   (or reuse one).
2. Enable two APIs for that project: **Google Sheets API** and
   **Google Drive API** (search for each in "APIs & Services" and click
   Enable).
3. Go to **APIs & Services > Credentials > Create Credentials > Service
   account**. Give it any name. After creation, open it, go to the
   **Keys** tab, **Add Key > Create new key > JSON**, and download it.
   This file contains a private key — treat it like a password, never
   commit it to GitHub.
4. Create a new Google Sheet (sheets.new). Copy its ID from the URL:
   `https://docs.google.com/spreadsheets/d/THIS_PART_IS_THE_ID/edit`
5. Share that Sheet with the service account's email address (found in
   the downloaded JSON as `client_email`, looks like
   `something@your-project.iam.gserviceaccount.com`) — give it **Editor**
   access.

## 2. Push this folder to GitHub

Create a repo (can be public or private — Streamlit Community Cloud can
deploy from either) and push the contents of this `streamlit_app/`
folder to it. **Do not commit a real `secrets.toml`** — only the
`.streamlit/secrets.toml.example` template is meant to go in git; the
`.gitignore` already excludes the real one.

## 3. Deploy on Streamlit Community Cloud

1. Go to https://share.streamlit.io and sign in with GitHub.
2. Click **New app**, pick your repo/branch, and set the main file path
   to `streamlit_app.py`.
3. Before (or right after) deploying, open **Settings > Secrets** for
   the app and paste in the contents of your downloaded service-account
   JSON plus the sheet ID, formatted like
   `.streamlit/secrets.toml.example` — i.e.:

   ```toml
   sheet_id = "the-id-you-copied-from-the-sheet-url"

   [gcp_service_account]
   type = "service_account"
   project_id = "..."
   private_key_id = "..."
   private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
   client_email = "...@....iam.gserviceaccount.com"
   client_id = "..."
   auth_uri = "https://accounts.google.com/o/oauth2/auth"
   token_uri = "https://oauth2.googleapis.com/token"
   auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
   client_x509_cert_url = "..."
   ```

   Tip: copy these values directly out of the downloaded JSON file field
   by field — don't retype the private key, just paste it as-is (keep
   the `\n` characters literal, exactly as they appear in the JSON).

4. Save. Streamlit will build and give you a public URL like
   `https://your-app-name.streamlit.app`. That's the link you share with
   annotators.

## 4. (Optional) Add a simple access gate

Since the URL above is public to anyone who has it, if you'd rather it
not be fully open, add this near the top of `streamlit_app.py`, right
after `st.set_page_config(...)`:

```python
if "authed" not in st.session_state:
    st.session_state.authed = False

if not st.session_state.authed:
    pw = st.text_input("Access code", type="password")
    if pw == st.secrets.get("access_code", ""):
        st.session_state.authed = True
        st.rerun()
    st.stop()
```

Then add `access_code = "whatever-you-want"` to your Secrets. It's not
strong security (a determined person could still work around it) but
it keeps the page off Google and stops casual drive-bys.

## 5. Local testing before you deploy

```bash
cd streamlit_app
pip install -r requirements.txt
mkdir -p .streamlit
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# edit .streamlit/secrets.toml with your real values
streamlit run streamlit_app.py
```

## How data ends up in the Sheet

Each submitted item becomes one row: timestamp, annotator name,
language, item ID, task category, difficulty, whether issues were
found, the issues themselves (as a JSON string, since one item can have
several issues, each with its own quote/categories/severity/comment),
and the free-text notes. You (or anyone with Sheet access) can open it
in Google Sheets at any time, or export it to CSV/JSON from there.

## Notes on concurrency

The app re-checks the Sheet for "already annotated" item IDs whenever
someone starts or refreshes their queue. If two people happen to open
an item within the same few seconds before either submits, they could
both annotate it — that just means an occasional duplicate row, not
lost or corrupted data. If that becomes a real problem at your scale,
the fix is splitting the item list into per-annotator ranges instead of
a shared pool, which I can add if you want.