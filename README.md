# FollowGod

SEC-first investment tracking MVP focused on accuracy, source links, and fast mobile visibility.

## What this version does

- Polls SEC submissions for one configured CIK.
- Stores tracked filings in SQLite.
- Optionally downloads new filing documents and creates an AI summary.
- Shows a mobile-friendly dashboard at `/`.
- Sends optional Telegram alerts when a new tracked filing appears.
- Deduplicates alerts by SEC accession number.

Tracked filing types:

- `13F-HR`
- `13F-HR/A`
- `SC 13D`
- `SC 13D/A`
- `SC 13G`
- `SC 13G/A`
- `4`
- `4/A`

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env`:

```text
FOLLOWGOD_TARGET_CIK=PUT_THE_REAL_CIK_HERE
FOLLOWGOD_SEC_USER_AGENT=FollowGod/0.1 your-email@example.com
```

SEC asks automated clients to send a descriptive User-Agent with contact info. Use an email you actually check.

## Optional AI filing reader

Add this to `.env`:

```text
OPENAI_API_KEY=sk-...
FOLLOWGOD_OPENAI_MODEL=gpt-5-mini
```

When AI is enabled, new filings are downloaded from SEC, summarized once, and saved in SQLite. The same filing will not be analyzed repeatedly unless you force a retry.

Manual analysis endpoint:

```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/analyze/0002045724-26-000008?force=true"
```

Cost control:

- AI only runs for filings stored by this tracker.
- The app sends trimmed filing text, not an unlimited document dump.
- Results are cached in SQLite.
- If `OPENAI_API_KEY` is empty, the app still works and marks AI as off.

## Run once and verify data

```powershell
.\.venv\Scripts\Activate.ps1
python .\scripts\poll_once.py
```

Expected result:

- The command prints how many new tracked filings were found.
- A `followgod.sqlite3` file appears.
- Re-running the command should normally print `0` new filings unless SEC has new data.

## Start the dashboard

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open on the same computer:

```text
http://localhost:8000
```

Open on your phone:

1. Put the phone on the same Wi-Fi as this computer.
2. Find this computer's LAN IP:

   ```powershell
   ipconfig
   ```

3. Open:

   ```text
   http://YOUR_LAN_IP:8000
   ```

## Optional Telegram alerts

Add these to `.env`:

```text
FOLLOWGOD_TELEGRAM_BOT_TOKEN=...
FOLLOWGOD_TELEGRAM_CHAT_ID=...
```

Then run:

```powershell
python .\scripts\poll_once.py
```

When a new tracked SEC filing is detected, the bot sends a message with filing type, accepted time, accession number, and the SEC source link.

## GitHub Actions scheduled alerts

The repository includes `.github/workflows/sec-check.yml`.

It runs:

- manually via `workflow_dispatch`
- automatically every 12 hours via cron

Add these GitHub repository secrets:

```text
FOLLOWGOD_SEC_USER_AGENT=FollowGod/0.1 your-email@example.com
OPENAI_API_KEY=sk-...
FOLLOWGOD_TELEGRAM_BOT_TOKEN=...
FOLLOWGOD_TELEGRAM_CHAT_ID=...
```

Optional repository variable:

```text
FOLLOWGOD_OPENAI_MODEL=gpt-5-mini
```

The workflow stores notification state in:

```text
data/notified_accessions.json
```

Current historical filings are already seeded into that file so the first scheduled run does not spam old filings.

The same workflow also builds and deploys a static dashboard to GitHub Pages. The deployed HTML contains only parsed SEC data, not API keys or Telegram credentials.

Enable Pages in GitHub:

```text
Settings -> Pages -> Build and deployment -> Source: GitHub Actions
```

## Useful API endpoints

- `GET /health`
- `GET /api/filings`
- `POST /api/poll`
- `POST /api/analyze/{accession_number}`

## Accuracy notes

This app treats SEC as the source of truth. It does not claim to know the trade date instantly. It detects and alerts when SEC publishes a tracked filing for the configured CIK.
