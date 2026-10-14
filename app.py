"""YouTube music copyright risk assessor.

This app provides evidence-aware guidance, not a copyright clearance guarantee.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import requests
import streamlit as st
from google import genai
from google.genai import types

APP_TITLE = "YouTube Music Copyright Checker"
MAX_AUDIO_MB = 20
ALLOWED_AUDIO_TYPES = {"mp3", "wav", "m4a", "aac", "ogg", "flac"}
YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtube-nocookie.com"}
OFFICIAL_RESOURCES = [
    ("YouTube Audio Library", "https://www.youtube.com/audiolibrary"),
    ("YouTube copyright help", "https://support.google.com/youtube/answer/2797466"),
    ("YouTube Content ID overview", "https://support.google.com/youtube/answer/2797370"),
    ("Creative Commons licenses", "https://creativecommons.org/share-your-work/cclicenses/"),
]


def get_secret(name: str) -> str | None:
    """Read a secret from Streamlit secrets first, then environment variables."""
    try:
        value = st.secrets.get(name)
        if value:
            return str(value).strip()
    except Exception:
        pass
    value = os.getenv(name)
    return value.strip() if value else None


def validate_youtube_url(value: str) -> bool:
    """Accept common YouTube URL forms without claiming to inspect the video."""
    if not value or len(value) > 2048:
        return False
    try:
        parsed = urlparse(value.strip())
        host = (parsed.hostname or "").lower()
        return parsed.scheme in {"http", "https"} and host in YOUTUBE_HOSTS and bool(parsed.path)
    except ValueError:
        return False


def validate_audio(uploaded_file: Any) -> tuple[bool, str]:
    if uploaded_file is None:
        return False, "No audio file was uploaded."
    filename = getattr(uploaded_file, "name", "")
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix not in ALLOWED_AUDIO_TYPES:
        return False, "Unsupported file extension. Use MP3, WAV, M4A, AAC, OGG, or FLAC."
    data = uploaded_file.getvalue()
    if not data:
        return False, "The uploaded file is empty."
    if len(data) > MAX_AUDIO_MB * 1024 * 1024:
        return False, f"File is too large. Maximum size is {MAX_AUDIO_MB} MB."
    return True, "Audio file passed basic extension and size checks. This does not verify the file's actual format."


def identify_with_audd(uploaded_file: Any, api_token: str) -> dict[str, Any]:
    """Optionally identify a track using AudD. A token and network access are required."""
    data = uploaded_file.getvalue()
    filename = getattr(uploaded_file, "name", "audio-upload")
    try:
        response = requests.post(
            "https://api.audd.io/",
            data={"api_token": api_token, "return": "spotify,apple_music"},
            files={"file": (filename, data, getattr(uploaded_file, "type", None) or "application/octet-stream")},
            timeout=35,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "success":
            return {"status": "unavailable", "message": "The recognition service did not return a successful result."}
        result = payload.get("result")
        if not result:
            return {"status": "not_found", "message": "No matching track was returned by the recognition service."}
        return {
            "status": "matched",
            "title": result.get("title"),
            "artist": result.get("artist"),
            "album": result.get("album"),
            "release_date": result.get("release_date"),
            "external_links": {
                key: result.get(key, {}).get("url")
                for key in ("spotify", "apple_music")
                if isinstance(result.get(key), dict) and result.get(key, {}).get("url")
            },
            "message": "Track match returned by AudD. Verify the match independently; identification is not proof of copyright ownership or license status.",
        }
    except requests.Timeout:
        return {"status": "unavailable", "message": "Music recognition timed out. Try again later."}
    except requests.RequestException as exc:
        return {"status": "unavailable", "message": f"Music recognition request failed: {type(exc).__name__}. Check the token and service availability."}
    except (ValueError, json.JSONDecodeError):
        return {"status": "unavailable", "message": "Music recognition returned an unreadable response."}


def build_prompt(*, title: str, artist: str, youtube_url: str, license_url: str,
                 license_text: str, recognition: dict[str, Any] | None) -> str:
    evidence = {
        "song_title_entered_by_user": title or None,
        "artist_entered_by_user": artist or None,
        "youtube_url_entered_by_user": youtube_url or None,
        "license_url_entered_by_user_not_independently_verified": license_url or None,
        "license_text_supplied_by_user": license_text or None,
        "music_recognition_result": recognition,
        "analysis_timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    return f"""You are an evidence-aware assistant helping a creator assess possible music copyright risks on YouTube.
Use ONLY the evidence in the JSON below plus general explanatory knowledge. Do not pretend to browse, verify a URL, inspect a YouTube video, access YouTube's private Content ID database, or confirm ownership. The license URL has NOT been fetched or verified. User-supplied license text may be incomplete or inaccurate.

Return a clear Markdown report with these headings:
1. Summary
2. Evidence available (separate user-provided details, recognition-service results, and unknowns)
3. Risk assessment (Low / Medium / High / Unknown, with a short rationale and confidence: Low / Medium / High)
4. Copyright and licensing considerations
5. YouTube monetization and Content ID considerations
6. License terms checklist (YouTube use, monetization/commercial use, attribution, edits/remixes, redistribution, territory/duration, and missing clauses; say “not established” where evidence is missing)
7. Recommended next steps before publishing
8. Safer alternatives and official resources
9. Limitations

Rules:
- Never state that a track is copyright-free or safe solely because no match was found.
- A recognition match identifies a likely recording; it does not establish copyright ownership or permission.
- A YouTube URL is not evidence that the uploader owns or licenses the music.
- Do not invent license clauses, ownership, claims, strikes, or detection results.
- Explain that copyright claims and strikes are different and that Content ID outcomes cannot be guaranteed.
- If the evidence is insufficient, use Unknown and explain what evidence is needed.
- Distinguish verified input facts from estimates. Do not provide legal advice.
- Recommend checking the original license and retaining proof of permission.

Evidence JSON:
{json.dumps(evidence, ensure_ascii=False, indent=2)}
"""


def generate_report(prompt: str, api_key: str, model: str) -> str:
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
            system_instruction="Be cautious, transparent, and evidence-based. Never invent external verification.",
        ),
    )
    text = getattr(response, "text", None)
    if not text or not text.strip():
        raise RuntimeError("Gemini returned an empty report. Please try again.")
    return text.strip()


def render_resources() -> None:
    st.markdown("#### Official resources")
    for label, url in OFFICIAL_RESOURCES:
        st.markdown(f"- [{label}]({url})")


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="🎵", layout="wide")
    st.title("🎵 YouTube Music Copyright Checker")
    st.caption("Evidence-aware music risk assessment for creators — not a copyright clearance guarantee.")

    with st.container(border=True):
        st.warning(
            "This tool cannot guarantee that music is safe to use. It does not access YouTube's private Content ID database. "
            "A low-risk result is not permission to publish. Verify the original license and keep proof of permission."
        )

    col1, col2 = st.columns(2)
    with col1:
        uploaded = st.file_uploader(
            "Upload an audio clip (optional)",
            type=sorted(ALLOWED_AUDIO_TYPES),
            help=f"Maximum {MAX_AUDIO_MB} MB. Audio is sent to AudD only if its optional API token is configured and you click Analyze.",
        )
        title = st.text_input("Song title (if known)", max_chars=200)
        artist = st.text_input("Artist / composer (if known)", max_chars=200)
        youtube_url = st.text_input("YouTube video URL (optional)", max_chars=2048, placeholder="https://www.youtube.com/watch?v=...")
    with col2:
        license_url = st.text_input("License or source URL (optional)", max_chars=2048, placeholder="Paste the original license page URL")
        license_text = st.text_area(
            "Paste license terms or permission text (optional)",
            max_chars=15000,
            height=220,
            help="Pasted text is analyzed by Gemini. A URL by itself is not fetched or independently verified.",
        )
        model = st.selectbox("Gemini Flash model", ["gemini-2.5-flash", "gemini-2.0-flash"], index=0)

    with st.expander("Optional integrations and privacy"):
        st.markdown(
            "- **Gemini** generates the explanation and report. The supplied text and metadata are sent to Google's Gemini API when you analyze.\n"
            "- **AudD** can optionally attempt audio recognition if `AUDD_API_TOKEN` is configured. The audio clip is sent to AudD.\n"
            "- The app does not download or inspect audio directly from a YouTube URL.\n"
            "- Do not upload confidential, private, or unlicensed material unless you have the right to share it with these services."
        )
        st.code("GEMINI_API_KEY = \"your-gemini-api-key\"\nAUDD_API_TOKEN = \"optional-audd-token\"", language="toml")

    analyze = st.button("Analyze music risk", type="primary", use_container_width=True)
    if not analyze:
        render_resources()
        return

    if not any([uploaded, title.strip(), artist.strip(), youtube_url.strip(), license_url.strip(), license_text.strip()]):
        st.error("Add at least one item: audio, song details, a YouTube URL, or license information.")
        return
    if youtube_url.strip() and not validate_youtube_url(youtube_url.strip()):
        st.error("That does not look like a valid YouTube URL. Use a youtube.com or youtu.be URL, or clear the field.")
        return
    if license_url.strip():
        parsed = urlparse(license_url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            st.error("The license URL must start with http:// or https:// and include a hostname.")
            return

    gemini_key = get_secret("GEMINI_API_KEY")
    if not gemini_key:
        st.error("Gemini API key not found. Add GEMINI_API_KEY to your local .streamlit/secrets.toml or Streamlit Cloud Secrets.")
        return

    recognition: dict[str, Any] | None = None
    if uploaded:
        valid, message = validate_audio(uploaded)
        if not valid:
            st.error(message)
            return
        st.info(message)
        audd_key = get_secret("AUDD_API_TOKEN")
        if audd_key:
            with st.spinner("Attempting audio recognition with AudD…"):
                recognition = identify_with_audd(uploaded, audd_key)
            if recognition.get("status") == "matched":
                st.success(f"Recognition match: {recognition.get('title', 'Unknown title')} — {recognition.get('artist', 'Unknown artist')}")
            else:
                st.info(recognition.get("message", "No recognition result available."))
        else:
            recognition = {"status": "not_configured", "message": "Audio recognition was not performed because AUDD_API_TOKEN is not configured."}
            st.info("Optional audio recognition is not configured. The app will not guess the song from the audio.")

    prompt = build_prompt(
        title=title.strip(), artist=artist.strip(), youtube_url=youtube_url.strip(),
        license_url=license_url.strip(), license_text=license_text.strip(), recognition=recognition,
    )
    try:
        with st.spinner("Gemini is preparing an evidence-based report…"):
            report = generate_report(prompt, gemini_key, model)
        st.subheader("Analysis report")
        st.markdown(report)
        report_file = f"music_copyright_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}Z.md"
        st.download_button(
            "Download report (.md)", data=report, file_name=report_file,
            mime="text/markdown", use_container_width=True,
        )
    except Exception as exc:
        message = str(exc)
        if re.search(r"api.?key|unauth|permission|403", message, re.I):
            st.error("Gemini authentication failed. Check that GEMINI_API_KEY is correct and enabled for the Gemini API.")
        elif re.search(r"quota|rate.?limit|429", message, re.I):
            st.error("Gemini API quota or rate limit reached. Wait and retry, or check your API usage limits.")
        else:
            st.error(f"Could not generate the report ({type(exc).__name__}). Check your API key, network connection, and deployment logs.")

    st.caption("Risk labels are AI-assisted estimates based on the evidence supplied. They are not a legal opinion or a guarantee of YouTube's decision.")
    render_resources()


if __name__ == "__main__":
    main()
