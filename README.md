# Briefly — AI YouTube Video Summarizer

A light-theme Streamlit app that turns a public YouTube transcript into a structured summary, Q&A and revision notes. Groq is the default LLM provider.

## What it does

- Accepts standard YouTube, `youtu.be`, `/shorts/`, `/embed/` and `/live/` links.
- Fetches an English transcript, preferring manually-created captions; falls back to generated English or translates an available caption track to English.
- Shows public video title and thumbnail when YouTube oEmbed makes them available.
- Produces short and detailed summaries, takeaways, concepts, examples, conclusion and action items.
- Offers English, Hindi and Hinglish output; short, medium and detailed summary styles.
- Generates Q&A and revision notes on demand.
- Displays the retrieved transcript and provides TXT/PDF exports.
- Splits long transcripts into chunks and merges segment notes. It processes all retrieved transcript text rather than silently truncating it.

## Important limitations

- This app summarizes **transcripts**, not video pixels/audio. If YouTube does not expose captions or blocks transcript access, the app will explain that it cannot summarize that video.
- “Any public video” cannot be guaranteed: captions can be disabled, restricted, missing, or inaccessible from the cloud host's IP.
- YouTube metadata may be unavailable for some videos; the app then shows a fallback title and thumbnail URL.
- Groq free-tier model access, quotas and rate limits can change. The default model is `llama-3.3-70b-versatile`; if Groq changes availability, update `MODEL` in `summarizer.py` to a model enabled for your account.
- PDF export uses a built-in core font. Hindi/other non-Latin scripts may not render correctly in the PDF. Use TXT or the on-screen copy area for those languages.
- Long transcripts require multiple Groq requests and may hit account rate limits. Retry after the quota resets.

## Project files

```text
youtube-summarizer/
├── app.py
├── summarizer.py
├── youtube_utils.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
└── .streamlit/
    └── config.toml
```

## 1. Get a Groq API key

1. Open [Groq Console](https://console.groq.com/).
2. Sign in or create an account.
3. Open the API Keys section and create a key.
4. Copy it once and keep it private. Never paste it into source code or commit it to GitHub.

Groq offers access subject to its current account terms, model availability, and rate limits. Check the console for current quotas and enabled models.

## 2. Run locally (Windows PowerShell)

Install Python 3.10 or newer, then:

```powershell
cd youtube-summarizer
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `.env` in a text editor and replace the sample value:

```env
GROQ_API_KEY=gsk_your_real_key
```

Run:

```powershell
streamlit run app.py
```

The app opens in your browser, usually at `http://localhost:8501`.

### macOS / Linux

```bash
cd youtube-summarizer
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set GROQ_API_KEY
streamlit run app.py
```

## 3. Upload to GitHub

1. Create a new **public** GitHub repository, for example `youtube-summarizer`.
2. Extract this ZIP file.
3. Open a terminal in the extracted project folder.
4. Confirm `.env` is not present or is ignored. Do not upload API keys.
5. Run:

```bash
git init
git add .
git commit -m "Build AI YouTube summarizer"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/youtube-summarizer.git
git push -u origin main
```

Replace the remote URL with your own repository URL. You can also upload files through GitHub's website.

## 4. Deploy on Streamlit Community Cloud

1. Open [Streamlit Community Cloud](https://share.streamlit.io/) and sign in with GitHub.
2. Choose **Create app**.
3. Select your repository, branch (`main`) and main file path (`app.py`).
4. Open **Advanced settings / Secrets** before deploying.
5. Add this TOML secret:

```toml
GROQ_API_KEY = "gsk_your_real_key"
```

6. Select **Deploy**. Streamlit installs packages from `requirements.txt`.
7. Open the app URL after deployment completes.

If the app is already deployed, open the app's settings → Secrets, add/update `GROQ_API_KEY`, save, then reboot the app.

## 5. Streamlit secrets vs local environment

- Local: put `GROQ_API_KEY=...` in `.env`.
- Streamlit Cloud: put `GROQ_API_KEY = "..."` in the app's Secrets settings.
- The app checks `st.secrets` first and then the local environment variable.
- `.env` and `.streamlit/secrets.toml` are excluded by `.gitignore`.

## 6. Quick verification checklist

- [ ] App starts with `streamlit run app.py`.
- [ ] A valid public video with English captions displays title/thumbnail and transcript status.
- [ ] Summary is generated in the chosen length and language.
- [ ] Q&A and revision-notes buttons produce content.
- [ ] Transcript expander displays the retrieved transcript.
- [ ] TXT download works; PDF download works for Latin-script output.
- [ ] Invalid URL displays a helpful validation message.
- [ ] A video without captions displays a transcript-unavailable message.
- [ ] Missing/invalid API key displays a configuration/authentication error.
- [ ] Cloud Secrets contain `GROQ_API_KEY`; no key is committed to GitHub.

## Troubleshooting

**`ModuleNotFoundError`:** confirm Streamlit Cloud is deploying from the folder containing `requirements.txt` and `app.py`.

**Groq authentication error:** create a new key in Groq Console, update Cloud Secrets, and reboot.

**Rate limit:** wait for quota reset or reduce repeated requests. Long videos use multiple model calls.

**Transcript blocked on Streamlit Cloud:** YouTube may block automated requests from the cloud IP. This is an upstream access limitation; try again later or test another captioned public video.

**No transcript:** the video owner may have disabled captions or YouTube may not expose a supported caption track.

## Security

Never commit `.env`, `secrets.toml`, API keys, or credentials. Rotate a key immediately if it is accidentally exposed.
