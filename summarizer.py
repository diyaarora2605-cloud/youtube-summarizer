"""Provider-agnostic transcript summarization; Groq is the default provider."""
from dataclasses import dataclass
import json
import re
import time
from typing import List
from groq import Groq
from groq import RateLimitError, AuthenticationError, APIConnectionError, APIStatusError

class LLMConfigurationError(Exception): pass
class LLMRateLimitError(Exception): pass
class LLMRequestError(Exception): pass

MODEL = "llama-3.3-70b-versatile"

@dataclass
class SummaryResult:
    short_summary: str
    detailed_summary: str
    key_takeaways: str
    important_concepts: str
    important_examples: str
    conclusion: str
    action_items: str
    language: str

    def to_markdown(self) -> str:
        labels = [
            ("Short Summary", self.short_summary), ("Detailed Summary", self.detailed_summary),
            ("Key Takeaways", self.key_takeaways), ("Important Concepts", self.important_concepts),
            ("Important Examples", self.important_examples), ("Conclusion", self.conclusion),
            ("Action Items", self.action_items)
        ]
        return "\n\n".join(f"## {heading}\n\n{content}" for heading, content in labels)

def _client(api_key: str) -> Groq:
    if not api_key:
        raise LLMConfigurationError("Groq API key is missing. Set GROQ_API_KEY in .env or Streamlit Secrets.")
    return Groq(api_key=api_key, timeout=90, max_retries=2)

def _ask(client: Groq, messages: list, max_tokens: int = 1800) -> str:
    try:
        response = client.chat.completions.create(
            model=MODEL, messages=messages, temperature=0.25,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content or ""
    except AuthenticationError as exc:
        raise LLMConfigurationError("Groq rejected the API key. Check that GROQ_API_KEY is valid and active.") from exc
    except RateLimitError as exc:
        raise LLMRateLimitError("Groq rate limit or free-tier quota reached. Wait a little and try again.") from exc
    except (APIConnectionError, APIStatusError) as exc:
        raise LLMRequestError(f"Groq request failed: {exc}") from exc
    except Exception as exc:
        raise LLMRequestError(f"Could not generate the response: {exc}") from exc

def _chunks(text: str, max_chars: int = 18000) -> List[str]:
    """Split on sentence/paragraph boundaries without dropping source text."""
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        raise ValueError("The retrieved transcript is empty.")
    chunks, start = [], 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            boundary = max(text.rfind(". ", start, end), text.rfind("? ", start, end), text.rfind("! ", start, end), text.rfind(" ", start, end))
            if boundary > start + int(max_chars * .65):
                end = boundary + 1
        chunks.append(text[start:end].strip())
        start = end
    return chunks

def _language_instruction(language: str) -> str:
    return {
        "English": "Write in clear, simple English.",
        "Hindi": "Write in natural, easy-to-understand Hindi using Devanagari script.",
        "Hinglish": "Write in natural conversational Hinglish using Roman script."
    }.get(language, "Write in clear English.")

def summarize_transcript(transcript: str, api_key: str, length: str = "medium", language: str = "English") -> SummaryResult:
    client = _client(api_key)
    chunks = _chunks(transcript)
    instruction = _language_instruction(language)
    detail = {"short": "Be concise.", "medium": "Use moderate detail.", "detailed": "Be comprehensive and explain each major topic."}.get(length, "Use moderate detail.")
    partials = []
    # Each chunk is processed; no silent truncation. The merge call synthesizes all chunk notes.
    for index, chunk in enumerate(chunks, 1):
        prompt = (
            f"Analyze transcript segment {index} of {len(chunks)}. {instruction} {detail}\n"
            "Extract factual notes, topics, claims, examples, definitions and practical advice. "
            "Do not invent facts or assume missing context. If a detail is unclear, say so.\n\n"
            f"TRANSCRIPT SEGMENT:\n{chunk}"
        )
        partials.append(_ask(client, [
            {"role": "system", "content": "You are a careful video transcript analyst. Ground every statement in the supplied transcript."},
            {"role": "user", "content": prompt}
        ], max_tokens=1800))
        if index < len(chunks):
            time.sleep(0.15)
    combined = "\n\n".join(f"SEGMENT NOTES {i+1}:\n{p}" for i, p in enumerate(partials))
    schema = {
        "short_summary": "5–7 concise lines covering the whole video",
        "detailed_summary": "major topics in a coherent order, with headings",
        "key_takeaways": "bullet list of important points",
        "important_concepts": "difficult/technical concepts explained simply; say None if absent",
        "important_examples": "examples actually mentioned; say None if absent",
        "conclusion": "main message of the video",
        "action_items": "practical steps grounded in the video; say None if no actionable advice"
    }
    prompt = (
        f"{instruction} {detail}\nCombine all segment notes into one coherent, non-repetitive summary of the COMPLETE video. "
        "Do not add unsupported details. Distinguish the speaker's claims from established facts. "
        "Return ONLY valid JSON with these string keys and no markdown fences: "
        + json.dumps(schema, ensure_ascii=False) + "\n\n"
        + combined
    )
    raw = _ask(client, [
        {"role": "system", "content": "You create accurate structured summaries from transcript-derived notes. Never fabricate."},
        {"role": "user", "content": prompt}
    ], max_tokens=5000)
    try:
        match = re.search(r"\{.*\}", raw, re.S)
        data = json.loads(match.group(0) if match else raw)
        return SummaryResult(**{key: str(data.get(key, "Not covered in the transcript.")) for key in schema}, language=language)
    except Exception as exc:
        raise LLMRequestError("The AI returned an unreadable summary. Please retry; no summary was saved.") from exc

def _summarize_for_extra(transcript: str, api_key: str, task: str, language: str) -> str:
    client = _client(api_key)
    pieces = []
    for i, chunk in enumerate(_chunks(transcript), 1):
        pieces.append(_ask(client, [
            {"role": "system", "content": "Use only information supported by the transcript."},
            {"role": "user", "content": f"{_language_instruction(language)} Create {task} from segment {i}. Be accurate and avoid repetition.\n\n{chunk}"}
        ], max_tokens=1600))
    merged = "\n\n".join(pieces)
    return _ask(client, [
        {"role": "system", "content": "You are a precise study assistant. Do not invent content."},
        {"role": "user", "content": f"{_language_instruction(language)} Combine these segment outputs into one clear, non-repetitive result:\n\n{merged}"}
    ], max_tokens=3000)

def generate_qa(transcript: str, api_key: str, language: str = "English") -> str:
    return _summarize_for_extra(transcript, api_key, "8–12 useful study questions and their answers", language)

def generate_revision_notes(transcript: str, api_key: str, language: str = "English") -> str:
    return _summarize_for_extra(transcript, api_key, "well-organized revision notes with headings, definitions and key points", language)
