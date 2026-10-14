import os
import re
import time
from typing import Any

import requests
import streamlit as st
from google import genai
from google.genai import errors as genai_errors


# ------------------------------------------------------------
# Page setup
# ------------------------------------------------------------
st.set_page_config(
    page_title="YouTube Copyright Music Checker",
    page_icon="🎵",
    layout="centered",
)

st.title("🎵 YouTube Copyright Music Checker")
st.caption("Check music information and identify potential copyright or licensing risks.")

st.info(
    "This tool provides an informational risk assessment only. It cannot access "
    "YouTube Content ID, guarantee that a track is copyright-free, or replace legal advice."
)


# ------------------------------------------------------------
# Secrets and helpers
# ------------------------------------------------------------
def get_secret(name: str, default: str = "") -> str:
    """Read a Streamlit secret first, then an environment variable."""
    try:
        value = st.secrets.get(name, "")
        if value:
            return str(value).strip()
    except Exception:
        # Local runs may not have a Streamlit secrets file.
        pass
    return os.getenv(name, default).strip()


def is_valid_youtube_url(value: str) -> bool:
    """Accept common YouTube watch, short, shorts, live, and embed URLs."""
    if not value:
        return True  # An empty URL is allowed.
    value = value.strip()
    pattern = re.compile(
        r"^(https?://)?(www\.|m\.)?"
        r"(youtube\.com|youtu\.be|youtube-nocookie\.com)/",
        re.IGNORECASE,
    )
    return bool(pattern.match(value))


def call_gemini(prompt: str, api_key: str, model: str, max_attempts: int = 3) -> str:
    """Generate a report, retrying temporary service overload errors."""
    client = genai.Client(api_key=api_key)

    for attempt in range(1, max_attempts + 1):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config={
                    "temperature": 0.2,
                    "max_output_tokens": 1400,
                },
            )
            text = getattr(response, "text", None)
            if not text:
                raise RuntimeError(
                    "Gemini returned an empty response. Check the model name and API access."
                )
            return text.strip()

        except genai_errors.APIError as exc:
            code = getattr(exc, "code", None)
            # Retry only temporary server overload/service availability errors.
            if code in (500, 502, 503, 504) and attempt < max_attempts:
                time.sleep(2 ** attempt)  # 2 seconds, then 4 seconds
                continue
            raise

    raise RuntimeError("Gemini remained unavailable after several attempts. Please try again later.")


def identify_with_audd(audio_bytes: bytes, filename: str, token: str) -> dict[str, Any]:
    """Ask AudD to identify an uploaded audio file. Audio is sent to AudD."""
    response = requests.post(
        "https://api.audd.io/",
        data={"api_token": token, "return": "spotify"},
        files={"file": (filename, audio_bytes)},
        timeout=45,
    )
    response.raise_for_status()
    result = response.json()
    if result.get("status") != "success":
        raise RuntimeError(str(result.get("error", {}).get("error_message", "AudD could not identify this audio.")))
    return result.get("result") or {}


def make_prompt(
    song_title: str,
    artist: str,
    youtube_url: str,
    license_text: str,
    license_url: str,
    recognition: dict[str, Any],
) -> str:
    recognition_text = "No AudD identification result is available."
    if recognition:
        recognition_text = (
            f"AudD title: {recognition.get('title', 'Unknown')}\n"
            f"AudD artist: {recognition.get('artist', 'Unknown')}\n"
            f"Album: {recognition.get('album', 'Unknown')}\n"
            f"Release date: {recognition.get('release_date', 'Unknown')}\n"
            f"AudD song-link/metadata: {recognition.get('song_link', 'Not provided')}"
        )

    return f"""
You are a careful music copyright and licensing information assistant.
Prepare a practical preliminary risk report using only the details supplied below.

IMPORTANT LIMITATIONS:
- Do not claim you checked YouTube Content ID or any private copyright database.
- Do not say a track is definitely copyright-free unless reliable license evidence is supplied.
- A song being available online, identified by AudD, or having a credit line does not by itself grant permission.
- Explain that rights can differ for composition, sound recording, synchronization, public performance, and monetization.
- Clearly separate known facts from unknowns and recommendations.
- Do not invent license terms or ownership details.
- This is not legal advice.

USER-SUPPLIED DETAILS
Song title: {song_title or "Not provided"}
Artist: {artist or "Not provided"}
YouTube URL: {youtube_url or "Not provided"}
License / permission text supplied by user: {license_text or "Not provided"}
License / permission URL supplied by user: {license_url or "Not provided"}

OPTIONAL AUDD AUDIO IDENTIFICATION
{recognition_text}

Write the report with these headings:
1. Summary
2. Identification confidence (state if there is not enough evidence)
3. Copyright and licensing risk (Low / Medium / High / Unknown, with reasons)
4. What is still unverified
5. Recommended next steps before publishing or monetizing
6. Suggested evidence to keep

Be cautious and concise. If the license is missing or unclear, explain that permission has not been established.
""".strip()


# ------------------------------------------------------------
# User inputs
# ------------------------------------------------------------
st.subheader("1. Music details")

song_title = st.text_input("Song title", placeholder="e.g., Desert ...")
artist = st.text_input("Artist (if known)", placeholder="e.g., Kenny ...")

youtube_url = st.text_input(
    "YouTube video URL (optional)",
    placeholder="https://www.youtube.com/watch?v=...",
    help="Leave this empty if you only want to check an uploaded audio file or enter song details.",
).strip()

license_text = st.text_area(
    "License or permission details (optional)",
    placeholder="Paste the license terms, permission email text, or source details here.",
    height=100,
)

license_url = st.text_input(
    "License / source URL (optional)",
    placeholder="https://...",
    help="Use the actual license page if you have one.",
).strip()

st.subheader("2. Optional audio upload")
audio_file = st.file_uploader(
    "Upload an audio file for optional song recognition",
    type=["mp3", "wav", "m4a", "flac", "ogg", "aac"],
    help="The file is only sent to AudD if AUDD_API_TOKEN is configured. Otherwise, the app does not identify the uploaded audio.",
)

if audio_file is not None:
    max_bytes = 25 * 1024 * 1024
    if audio_file.size > max_bytes:
        st.error("This file is larger than 25 MB. Please upload a smaller audio file.")
        audio_file = None
    else:
        st.caption(f"Uploaded: {audio_file.name} ({audio_file.size / (1024 * 1024):.1f} MB)")

st.caption(
    "Optional integrations and privacy: Gemini receives the text and metadata you submit when "
    "you generate a report. If AUDD_API_TOKEN is configured and you upload audio, the audio file "
    "is sent to AudD for recognition. The app does not download or inspect audio directly from a "
    "YouTube URL. Do not submit confidential material unless you have permission to share it."
)


# ------------------------------------------------------------
# Analysis
# ------------------------------------------------------------
if st.button("Analyze Music", type="primary", use_container_width=True):
    # Crucial fix: only validate the YouTube URL when the field is not empty.
    if youtube_url and not is_valid_youtube_url(youtube_url):
        st.error(
            "That does not look like a valid YouTube URL. "
            "Use a youtube.com or youtu.be URL, or clear the field."
        )
        st.stop()

    if not any([song_title, artist, youtube_url, license_text, license_url, audio_file]):
        st.warning("Enter a song title, artist, YouTube URL, license details, or upload an audio file first.")
        st.stop()

    gemini_api_key = get_secret("GEMINI_API_KEY")
    if not gemini_api_key:
        st.error(
            "Gemini is not configured. In Streamlit Cloud, open your app's Settings → Secrets "
            "and add GEMINI_API_KEY = \"your-real-key\". Do not share the key publicly."
        )
        st.stop()

    model = get_secret("GEMINI_MODEL", "gemini-2.5-flash")
    recognition: dict[str, Any] = {}

    audd_token = get_secret("AUDD_API_TOKEN")
    if audio_file is not None:
        if audd_token:
            with st.spinner("Trying optional audio recognition with AudD..."):
                try:
                    recognition = identify_with_audd(
                        audio_file.getvalue(),
                        audio_file.name,
                        audd_token,
                    )
                    if recognition:
                        st.success(
                            "AudD returned a possible match: "
                            f"{recognition.get('title', 'Unknown title')} — "
                            f"{recognition.get('artist', 'Unknown artist')}."
                        )
                    else:
                        st.warning("AudD did not identify this audio.")
                except requests.Timeout:
                    st.warning("AudD timed out. Continuing without an audio identification result.")
                except requests.RequestException as exc:
                    st.warning(
                        "AudD could not be reached. Continuing without audio identification. "
                        f"Details: {type(exc).__name__}"
                    )
                except Exception as exc:
                    st.warning(
                        "AudD could not identify the audio. Continuing without it. "
                        f"Details: {type(exc).__name__}"
                    )
        else:
            st.warning(
                "Audio file uploaded, but optional audio recognition is not configured. "
                "The app will not guess the song from the audio. You can still generate a report "
                "using the text and metadata you supplied."
            )

    prompt = make_prompt(
        song_title=song_title,
        artist=artist,
        youtube_url=youtube_url,
        license_text=license_text,
        license_url=license_url,
        recognition=recognition,
    )

    with st.spinner("Generating your preliminary report with Gemini..."):
        try:
            report = call_gemini(prompt, gemini_api_key, model)
        except genai_errors.APIError as exc:
            code = getattr(exc, "code", None)
            message = getattr(exc, "message", None) or str(exc)
            st.error("Gemini could not generate the report.")
            st.markdown("**Error details**")
            st.code(f"HTTP/API code: {code}\n{message}")
            if code == 503:
                st.warning(
                    "Gemini is temporarily overloaded. The app already retried the request. "
                    "Please wait a few minutes and try again. Your API key does not need to be "
                    "replaced just because of this 503 response."
                )
            elif code in (500, 502, 504):
                st.warning(
                    "Gemini reported a temporary service problem. The app retried automatically; "
                    "please wait a little and try again."
                )
            elif code == 429:
                st.warning(
                    "Gemini may have reached a rate limit or quota. Check usage and limits for "
                    "your Google AI project before retrying."
                )
            else:
                st.markdown(
                    "Check that the key is valid, the model is available to your project, "
                    "and your Gemini API quota has not been exhausted."
                )
            st.stop()
        except Exception as exc:
            # Avoid printing secrets or the full request. Show a useful error type and message.
            st.error("Gemini could not generate the report.")
            st.markdown("**Error details**")
            st.code(f"{type(exc).__name__}: {str(exc)[:1200]}")
            st.markdown(
                "If the message mentions an unavailable model, check GEMINI_MODEL in Secrets. "
                "If it mentions quota or rate limits, check your Gemini API usage."
            )
            st.stop()

    st.subheader("3. Preliminary report")
    st.markdown(report)
    st.download_button(
        "Download report (.md)",
        data=report,
        file_name="music_copyright_risk_report.md",
        mime="text/markdown",
        use_container_width=True,
    )

    st.warning(
        "This report is an initial assessment based on the information supplied. "
        "It does not verify ownership, permission, or YouTube Content ID status."
    )

with st.expander("Troubleshooting"):
    st.markdown(
        """
- **YouTube URL error:** Leave the optional URL field empty or use a real `youtube.com` / `youtu.be` link.
- **Gemini API key error:** Check `GEMINI_API_KEY` in Streamlit Cloud → app Settings → Secrets.
- **Model not found / 404:** Check `GEMINI_MODEL`; the default in this app is `gemini-2.5-flash`.
- **Quota / 429:** Check the Gemini API quota and rate limits for your Google AI project.
- **Audio not identified:** AudD is optional and requires `AUDD_API_TOKEN`. Gemini does not identify the uploaded audio in this app.
"""
    )
