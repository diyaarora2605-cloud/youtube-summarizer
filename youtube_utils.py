"""YouTube URL parsing, metadata lookup and transcript retrieval."""
from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs
import re
import requests
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled, NoTranscriptFound, VideoUnavailable,
    RequestBlocked, IpBlocked, YouTubeRequestFailed
)

class TranscriptUnavailableError(Exception):
    pass

class YouTubeFetchError(Exception):
    pass

@dataclass
class TranscriptData:
    text: str
    language: str
    is_generated: bool

VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

def extract_video_id(url: str) -> str:
    if not url or not url.strip():
        raise ValueError("Paste a YouTube video URL to continue.")
    raw = url.strip()
    candidate = raw if "://" in raw else "https://" + raw
    try:
        parsed = urlparse(candidate)
        host = (parsed.hostname or "").lower()
        if host in ("youtu.be", "www.youtu.be"):
            video_id = parsed.path.strip("/").split("/")[0]
        elif host in ("youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"):
            if parsed.path == "/watch":
                video_id = parse_qs(parsed.query).get("v", [""])[0]
            else:
                parts = [p for p in parsed.path.split("/") if p]
                if len(parts) >= 2 and parts[0] in ("shorts", "embed", "live", "v"):
                    video_id = parts[1]
                else:
                    video_id = ""
        else:
            video_id = ""
    except Exception:
        video_id = ""
    if not VIDEO_ID_RE.fullmatch(video_id or ""):
        raise ValueError("That doesn't look like a valid YouTube URL. Use a youtube.com or youtu.be video link.")
    return video_id

def get_video_metadata(video_id: str) -> dict:
    """Fetch public oEmbed metadata; fallback title is explicit when unavailable."""
    endpoint = "https://www.youtube.com/oembed"
    try:
        response = requests.get(endpoint, params={"url": f"https://www.youtube.com/watch?v={video_id}", "format": "json"}, timeout=12)
        if response.ok:
            data = response.json()
            return {
                "title": data.get("title") or f"YouTube video {video_id}",
                "thumbnail": data.get("thumbnail_url") or f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                "author": data.get("author_name", "Unknown creator"),
            }
        if response.status_code in (401, 403, 404):
            return {"title": f"YouTube video {video_id}", "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg", "author": "Unknown creator"}
        response.raise_for_status()
    except requests.RequestException:
        return {"title": f"YouTube video {video_id}", "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg", "author": "Unknown creator"}

def fetch_english_transcript(video_id: str) -> TranscriptData:
    """Prefer a manually-created English track, then generated English, then translatable track."""
    api = YouTubeTranscriptApi()
    try:
        transcript_list = api.list(video_id)
        tracks = list(transcript_list)
        english = [t for t in tracks if t.language_code.lower().startswith("en")]
        manual = next((t for t in english if not t.is_generated), None)
        generated = next((t for t in english if t.is_generated), None)
        chosen = manual or generated
        if chosen:
            fetched = chosen.fetch()
            snippets = fetched.to_raw_data()
            return TranscriptData(" ".join(s.get("text", "") for s in snippets).strip(),
                                  chosen.language, chosen.is_generated)
        translatable = next((t for t in tracks if t.is_translatable), None)
        if translatable:
            translated = translatable.translate("en").fetch()
            snippets = translated.to_raw_data()
            return TranscriptData(" ".join(s.get("text", "") for s in snippets).strip(),
                                  f"{translatable.language} → English", True)
        raise TranscriptUnavailableError("No English transcript or translatable caption track is available for this video.")
    except TranscriptUnavailableError:
        raise
    except (TranscriptsDisabled, NoTranscriptFound):
        raise TranscriptUnavailableError("Captions are disabled or no transcript is available for this video.")
    except (VideoUnavailable, RequestBlocked, IpBlocked) as exc:
        raise YouTubeFetchError("YouTube could not provide this video. It may be private, deleted, age-restricted, or blocked for automated requests.") from exc
    except YouTubeRequestFailed as exc:
        raise YouTubeFetchError("YouTube request failed. Please retry later; YouTube may be temporarily rate-limiting transcript access.") from exc
    except Exception as exc:
        message = str(exc).lower()
        if "disabled" in message or "no transcript" in message:
            raise TranscriptUnavailableError("No accessible transcript was found for this video.") from exc
        raise YouTubeFetchError(f"Could not retrieve the transcript: {exc}") from exc
