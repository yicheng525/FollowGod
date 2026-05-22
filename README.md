# FollowGod

SEC-first investment tracking MVP focused on accuracy, source links, and fast mobile visibility.

## What this version does

- Polls SEC submissions for one configured CIK.
- Stores tracked filings in SQLite.
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

## Useful API endpoints

- `GET /health`
- `GET /api/filings`
- `POST /api/poll`

## Accuracy notes

This app treats SEC as the source of truth. It does not claim to know the trade date instantly. It detects and alerts when SEC publishes a tracked filing for the configured CIK.
