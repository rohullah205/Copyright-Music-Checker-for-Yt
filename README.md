# Copyright-Music-Checker-for-Yt
# YouTube Music Copyright Checker

A beginner-friendly Streamlit app that creates an AI-assisted report about possible YouTube music copyright risks using user-provided song details, license text, and optional audio-recognition results.

> **Important:** This app does not provide copyright clearance, legal advice, or guaranteed predictions about Content ID. A low-risk or no-match result does not mean that music is safe to publish. Verify permission with the rights holder or original license provider.

## Features

- Upload an audio clip (MP3, WAV, M4A, AAC, OGG, or FLAC; up to 20 MB).
- Enter a song title, artist, YouTube URL, license URL, or pasted license terms.
- Use Gemini Flash to create an evidence-aware risk and license checklist report.
- Optionally use AudD for audio track recognition when `AUDD_API_TOKEN` is configured.
- Download the report as Markdown.
- Show official YouTube and Creative Commons resources.
- Keep API keys out of source code.

## What this app can and cannot verify

- **Gemini:** explains the evidence you provide. It does not independently verify a license URL in this app.
- **AudD (optional):** attempts to identify a recording. A match is not proof of copyright ownership, license terms, or permission.
- **YouTube URL:** the app validates the URL's general form but does not download or inspect the video.
- **Content ID:** the app does not access YouTube's private Content ID database and cannot guarantee whether a claim, block, monetization restriction, or strike will occur.
- **Audio file:** basic extension and size checks are performed. This is not full media-file validation.

## Technology

- Python
- Streamlit
- Google Gen AI SDK (`google-genai`)
- Gemini Flash
- Requests
- Optional AudD music-recognition API

## Project structure

```text
youtube-music-copyright-checker/
├── app.py
├── requirements.txt
└── README.md
```

## 1. Get a Gemini API key

1. Open [Google AI Studio](https://aistudio.google.com/).
2. Sign in and create an API key according to Google's current instructions.
3. Keep the key private. Do not paste it into `app.py`, `README.md`, or a public GitHub repository.

The app defaults to `gemini-2.5-flash`. Model availability may vary by account and region; if unavailable, choose another supported Flash model in the app.

## 2. Run locally

Install a current supported Python version (Python 3.10+ recommended).

### Windows PowerShell

```powershell
mkdir youtube-music-copyright-checker
cd youtube-music-copyright-checker
# Put app.py, requirements.txt, and README.md in this folder
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
mkdir .streamlit
notepad .streamlit\secrets.toml
```

Put this in `.streamlit/secrets.toml`:

```toml
GEMINI_API_KEY = "paste-your-key-here"
# Optional: only if you have an AudD API token
# AUDD_API_TOKEN = "paste-your-audd-token-here"
```

Then run:

```powershell
streamlit run app.py
```

Open the local URL printed in the terminal, usually `http://localhost:8501`.

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
mkdir -p .streamlit
```

Create `.streamlit/secrets.toml` with the TOML shown above, then run:

```bash
streamlit run app.py
```

**Never upload `.streamlit/secrets.toml` to GitHub.** Add `.streamlit/` to `.gitignore` if you later use Git locally.

## 3. Optional AudD recognition

AudD is an external music-recognition service and may require an account, API token, payment, or usage limits under its current terms. See [AudD](https://audd.io/).

1. Obtain a token from AudD according to its current terms.
2. Add `AUDD_API_TOKEN = "your-token"` to local Streamlit secrets or Streamlit Cloud secrets.
3. Upload a supported audio file and click **Analyze music risk**.
4. The app sends the uploaded audio to AudD for recognition. Review the service's privacy policy and terms before using it.

Without this token, the app explicitly reports that audio recognition was not performed. It does not pretend Gemini has identified the track.

## 4. Upload files to GitHub using the website UI

1. Sign in at [GitHub](https://github.com/).
2. Select **New repository**. Give it a name such as `youtube-music-copyright-checker` and create it.
3. Open the repository and choose **Add file → Upload files**.
4. Upload `app.py`, `requirements.txt`, and `README.md` from your project folder.
5. Do **not** upload API keys, `.streamlit/secrets.toml`, private audio, or other sensitive files.
6. Add a commit message such as `Add initial Streamlit music checker` and select **Commit changes**.
7. Confirm the three project files appear at the repository root.

To update later, open a file on GitHub, choose the pencil/edit option, make changes, and commit them; or use **Add file → Upload files** to upload a revised file. For larger projects, Git is more convenient, but it is not required for this workflow.

## 5. Deploy on Streamlit Community Cloud

1. Push the three project files to GitHub as described above.
2. Open [Streamlit Community Cloud](https://share.streamlit.io/) and sign in with GitHub.
3. Choose **Create app** (wording may change), then select your repository and branch.
4. Set the main file path to `app.py`.
5. Before or after deployment, open the app's **Settings → Secrets** section.
6. Add secrets in TOML format:

   ```toml
   GEMINI_API_KEY = "your-gemini-api-key"
   # Optional
   AUDD_API_TOKEN = "your-audd-token"
   ```

7. Save secrets and deploy/reboot the app if requested.
8. Open the deployed URL and test with a small, non-sensitive sample and valid API key.
9. If it fails, open the app's logs in Streamlit Community Cloud and read the first relevant traceback.

Service availability, free-tier limits, supported Python versions, and deployment UI can change. Follow the current instructions shown by Streamlit.

## Troubleshooting

- **Missing API key:** add `GEMINI_API_KEY` to local `.streamlit/secrets.toml` or Cloud Secrets.
- **Authentication error:** confirm the key is correct and the Gemini API is enabled/available for the account.
- **Quota/rate limit:** wait, review account usage/limits, and retry later.
- **Model not found:** select a Gemini Flash model currently available to your account.
- **AudD did not identify the track:** try a clearer/longer clip, check the token and service status, or enter title/artist manually. A no-match result is not evidence of copyright-free music.
- **Unsupported/large file:** use one of the listed audio formats and keep it under 20 MB.
- **Streamlit deployment error:** verify that `app.py` is at the repository root and `requirements.txt` lists the dependencies.
- **Secret accidentally committed:** revoke/rotate the exposed key immediately, remove it from the repository, and review Git history. Deleting the visible line alone may not remove it from history.

## Privacy and security

When you click Analyze, the song details and pasted license text are sent to Gemini to generate the report. If AudD is configured and you upload audio, that audio is sent to AudD for recognition. Do not upload private or confidential material unless you have permission and accept the providers' applicable data handling terms. This app does not intentionally save uploaded audio to disk.

Never put API keys in source code or commit them to GitHub. Use Streamlit Secrets in deployment and local secrets files during development.

## Copyright concepts

- **Copyright claim / Content ID claim:** a rights-management action that may affect monetization, visibility, or availability. A claim is not the same thing as a copyright strike.
- **Copyright strike:** a separate enforcement outcome associated with a valid copyright removal request; consequences differ from a Content ID claim.
- **Royalty-free:** usually describes a licensing model, not a guarantee that the track is free or unrestricted.
- **Creative Commons:** different licenses have different attribution, commercial-use, and adaptation conditions. Check the exact license version and the rights attached to the specific recording.
- **Public domain:** verify both the underlying composition and the particular sound recording, as they may have different rights.

## Official resources

- [YouTube Audio Library](https://www.youtube.com/audiolibrary)
- [YouTube copyright help](https://support.google.com/youtube/answer/2797466)
- [YouTube Content ID overview](https://support.google.com/youtube/answer/2797370)
- [Creative Commons license chooser and explanations](https://creativecommons.org/share-your-work/cclicenses/)
- [Google AI Studio](https://aistudio.google.com/)
- [AudD](https://audd.io/)

## Disclaimer

This project is an educational risk-assessment aid, not a lawyer, rights registry, licensing database, or YouTube system. Its results may be incomplete or incorrect. Confirm permission with the rights holder or original provider, review the full license, retain proof of permission, and use YouTube's own checks and policies before publishing.
