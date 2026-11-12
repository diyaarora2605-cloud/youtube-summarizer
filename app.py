import streamlit as st
from dotenv import load_dotenv
from youtube_utils import (
    extract_video_id, get_video_metadata, fetch_english_transcript,
    TranscriptUnavailableError, YouTubeFetchError
)
from summarizer import (
    summarize_transcript, generate_qa, generate_revision_notes,
    LLMConfigurationError, LLMRateLimitError, LLMRequestError,
    SummaryResult
)

load_dotenv()
st.set_page_config(page_title="Briefly — YouTube Summarizer", page_icon="▶️", layout="wide")

# Light SaaS theme
st.markdown("""
<style>
:root { color-scheme: light; }
.stApp { background: #f7f9fc; color: #172033; }
[data-testid="stHeader"] { background: rgba(247,249,252,.9); }
.block-container { max-width: 1180px; padding-top: 2rem; padding-bottom: 3rem; }
.hero { background: linear-gradient(115deg,#ffffff 0%,#f1f5ff 100%); border:1px solid #e3e9f5;
        padding: 1.5rem 1.7rem; border-radius: 18px; margin-bottom: 1.2rem; }
.eyebrow { color:#5865d9; font-weight:700; letter-spacing:.08em; font-size:.75rem; text-transform:uppercase; }
.hero h1 { margin:.25rem 0; color:#172033; font-size:2.15rem; }
.hero p { color:#5d687d; margin:0; font-size:1rem; }
.panel { background:#fff; border:1px solid #e5eaf2; border-radius:16px; padding:1rem 1.2rem; }
.small-muted { color:#69758a; font-size:.88rem; }
div.stButton > button[kind="primary"] { background:#5965df; border:0; border-radius:10px; }
div.stButton > button { border-radius:10px; }
[data-testid="stMetric"] { background:white; border:1px solid #e5eaf2; padding:12px; border-radius:12px; }
</style>
""", unsafe_allow_html=True)

def get_secret(name: str):
    try:
        value = st.secrets.get(name)
        if value:
            return str(value).strip()
    except Exception:
        pass
    import os
    return os.getenv(name, "").strip()

def render_result(result: SummaryResult):
    st.subheader("Your video summary")
    tabs = st.tabs(["Overview", "Detailed summary", "Takeaways", "Concepts", "Examples", "Conclusion", "Action items"])
    with tabs[0]:
        st.markdown(result.short_summary)
    with tabs[1]:
        st.markdown(result.detailed_summary)
    with tabs[2]:
        st.markdown(result.key_takeaways)
    with tabs[3]:
        st.markdown(result.important_concepts)
    with tabs[4]:
        st.markdown(result.important_examples)
    with tabs[5]:
        st.markdown(result.conclusion)
    with tabs[6]:
        st.markdown(result.action_items)

    st.divider()
    full_text = result.to_markdown()
    st.download_button("⬇️ Download summary (.txt)", data=full_text, file_name="youtube_summary.txt",
                       mime="text/plain", use_container_width=False)
    try:
        from fpdf import FPDF
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_font("Helvetica", size=11)
        # Core Helvetica handles ASCII; transliterate unsupported glyphs safely for portable PDFs.
        safe_text = full_text.encode("latin-1", "replace").decode("latin-1")
        for line in safe_text.splitlines():
            pdf.multi_cell(0, 7, line)
        pdf_bytes = bytes(pdf.output())
        st.download_button("⬇️ Download summary (.pdf)", data=pdf_bytes, file_name="youtube_summary.pdf",
                           mime="application/pdf")
    except Exception as exc:
        st.info(f"PDF export is temporarily unavailable: {exc}")
    st.text_area("Copy your summary", value=full_text, height=180, help="Select the text and copy it.")

st.markdown("""
<div class="hero">
  <div class="eyebrow">AI-powered learning companion</div>
  <h1>Turn YouTube videos into clear notes.</h1>
  <p>Paste a public video link. Get structured summaries, concepts, revision notes and questions.</p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## ⚙️ Preferences")
    length_label = st.selectbox("Summary length", ["Short", "Medium", "Detailed"], index=1)
    language_label = st.selectbox("Output language", ["English", "Hindi", "Hinglish"], index=0)
    st.markdown("---")
    st.markdown("**AI provider**")
    st.caption("Groq API · Free-tier availability and limits depend on your Groq account.")
    st.markdown("---")
    st.caption("Briefly does not download video or audio. It summarizes an accessible transcript.")
    if st.button("↻ Clear / Reset", use_container_width=True):
        for key in ("video_url", "summary_result", "transcript_text", "video_meta", "video_id", "qa_result", "notes_result"):
            st.session_state.pop(key, None)
        st.rerun()

st.markdown("### Start with a YouTube link")
with st.form("summarize_form"):
    url = st.text_input("YouTube video URL", placeholder="https://www.youtube.com/watch?v=...", label_visibility="collapsed")
    submitted = st.form_submit_button("✨ Summarize video", type="primary", use_container_width=True)

if submitted:
    st.session_state.pop("summary_result", None)
    st.session_state.pop("qa_result", None)
    st.session_state.pop("notes_result", None)
    try:
        video_id = extract_video_id(url)
        st.session_state["video_url"] = url.strip()
        st.session_state["video_id"] = video_id
        with st.spinner("Getting video information…"):
            meta = get_video_metadata(video_id)
        st.session_state["video_meta"] = meta
        with st.spinner("Checking and fetching an English transcript…"):
            transcript = fetch_english_transcript(video_id)
        st.session_state["transcript_text"] = transcript.text
        st.session_state["transcript_language"] = transcript.language
        st.session_state["transcript_generated"] = transcript.is_generated
        api_key = get_secret("GROQ_API_KEY")
        if not api_key:
            raise LLMConfigurationError("Groq API key is missing. Add GROQ_API_KEY to .env locally or Streamlit Secrets in the cloud.")
        with st.spinner("Reading the transcript and creating your structured summary… This may take a little while for long videos."):
            result = summarize_transcript(
                transcript.text, api_key=api_key,
                length=length_label.lower(), language=language_label
            )
        st.session_state["summary_result"] = result
    except ValueError as exc:
        st.error(str(exc))
    except TranscriptUnavailableError as exc:
        st.error(str(exc))
        st.info("This app only summarizes when it can retrieve a transcript. Try another public video or check whether captions are enabled.")
    except YouTubeFetchError as exc:
        st.error(str(exc))
    except LLMConfigurationError as exc:
        st.error(str(exc))
    except LLMRateLimitError as exc:
        st.error(str(exc))
    except LLMRequestError as exc:
        st.error(str(exc))
    except Exception as exc:
        st.error(f"Something unexpected happened: {exc}")

meta = st.session_state.get("video_meta")
if meta:
    left, right = st.columns([1, 2], gap="large")
    with left:
        st.image(meta["thumbnail"], use_container_width=True)
    with right:
        st.markdown(f"### {meta['title']}")
        st.markdown(f"[Open video on YouTube]({st.session_state.get('video_url', '')})")
        transcript_status = "Available" if st.session_state.get("transcript_text") else "Not fetched"
        st.caption(f"Transcript status: {transcript_status}")
        if st.session_state.get("transcript_language"):
            st.caption(f"Transcript used: {st.session_state['transcript_language']} "
                       f"({'auto-generated' if st.session_state.get('transcript_generated') else 'manually uploaded'})")

result = st.session_state.get("summary_result")
if result:
    render_result(result)
    st.divider()
    st.subheader("Study tools")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("❓ Generate questions & answers", use_container_width=True):
            try:
                with st.spinner("Creating questions from the transcript…"):
                    st.session_state["qa_result"] = generate_qa(
                        st.session_state["transcript_text"], get_secret("GROQ_API_KEY"),
                        result.language
                    )
            except Exception as exc:
                st.error(str(exc))
    with c2:
        if st.button("📝 Generate revision notes", use_container_width=True):
            try:
                with st.spinner("Preparing revision notes…"):
                    st.session_state["notes_result"] = generate_revision_notes(
                        st.session_state["transcript_text"], get_secret("GROQ_API_KEY"),
                        result.language
                    )
            except Exception as exc:
                st.error(str(exc))
    if st.session_state.get("qa_result"):
        with st.expander("Questions & answers", expanded=True):
            st.markdown(st.session_state["qa_result"])
            st.download_button("Download Q&A", st.session_state["qa_result"], "video_questions.txt", "text/plain")
    if st.session_state.get("notes_result"):
        with st.expander("Revision notes", expanded=True):
            st.markdown(st.session_state["notes_result"])
            st.download_button("Download revision notes", st.session_state["notes_result"], "revision_notes.txt", "text/plain")

transcript = st.session_state.get("transcript_text")
if transcript:
    with st.expander("View full transcript"):
        st.caption("Transcript is shown as retrieved; punctuation and speaker labels may vary.")
        st.text_area("Transcript", transcript, height=350)
