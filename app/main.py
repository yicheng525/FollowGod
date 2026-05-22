from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from app.config import get_settings
from app.service import PollService
from app.storage import FilingStore

settings = get_settings()
store = FilingStore(settings.database_path)
app = FastAPI(title="FollowGod", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "target_cik": settings.normalized_cik}


@app.get("/api/filings")
def api_filings() -> list[dict[str, str | None]]:
    return store.list_filings()


@app.post("/api/poll")
async def api_poll() -> dict[str, object]:
    service = PollService(settings, store)
    return await service.poll_once()


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    filings = store.list_filings(limit=100)
    rows = "\n".join(_filing_card(row) for row in filings)
    empty_state = ""
    if not rows:
        empty_state = """
        <section class="empty">
          <h2>No filings stored yet</h2>
          <p>Run <code>python .\\scripts\\poll_once.py</code> or call <code>POST /api/poll</code>.</p>
        </section>
        """

    telegram_status = "On" if settings.telegram_bot_token and settings.telegram_chat_id else "Off"
    return f"""
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>FollowGod</title>
        <style>
          :root {{
            color-scheme: dark;
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background: #080b12;
            color: #edf2f7;
          }}
          body {{
            margin: 0;
            background: #080b12;
          }}
          header {{
            position: sticky;
            top: 0;
            z-index: 2;
            padding: 18px 16px 14px;
            background: rgba(8, 11, 18, 0.94);
            border-bottom: 1px solid #1f2937;
            backdrop-filter: blur(14px);
          }}
          main {{
            max-width: 860px;
            margin: 0 auto;
            padding: 14px 12px 32px;
          }}
          h1 {{
            margin: 0 0 8px;
            font-size: 24px;
            line-height: 1.1;
            letter-spacing: 0;
          }}
          .meta {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
          }}
          .pill {{
            border: 1px solid #344054;
            border-radius: 999px;
            color: #cbd5e1;
            font-size: 12px;
            padding: 5px 9px;
            background: #111827;
          }}
          .toolbar {{
            display: flex;
            gap: 8px;
            margin-top: 14px;
          }}
          button, a.button {{
            appearance: none;
            border: 1px solid #2f3a4a;
            border-radius: 8px;
            background: #162032;
            color: #f8fafc;
            font-size: 14px;
            padding: 10px 12px;
            text-decoration: none;
          }}
          .feed {{
            display: grid;
            gap: 10px;
          }}
          article {{
            border: 1px solid #253044;
            border-radius: 8px;
            background: #101722;
            padding: 14px;
          }}
          .card-top {{
            display: flex;
            justify-content: space-between;
            gap: 10px;
            align-items: flex-start;
          }}
          .form {{
            color: #34d399;
            font-weight: 700;
            font-size: 13px;
          }}
          .date {{
            color: #94a3b8;
            font-size: 12px;
            text-align: right;
          }}
          .entity {{
            margin: 8px 0 10px;
            font-size: 17px;
            font-weight: 650;
          }}
          dl {{
            display: grid;
            grid-template-columns: 110px 1fr;
            gap: 7px 10px;
            margin: 0;
            font-size: 13px;
          }}
          dt {{
            color: #94a3b8;
          }}
          dd {{
            margin: 0;
            color: #e2e8f0;
            overflow-wrap: anywhere;
          }}
          a {{
            color: #60a5fa;
          }}
          .empty {{
            border: 1px solid #253044;
            border-radius: 8px;
            padding: 16px;
            background: #101722;
          }}
          code {{
            color: #fbbf24;
          }}
        </style>
      </head>
      <body>
        <header>
          <h1>FollowGod SEC Tracker</h1>
          <div class="meta">
            <span class="pill">CIK {settings.normalized_cik}</span>
            <span class="pill">Telegram {telegram_status}</span>
            <span class="pill">{len(filings)} stored filings</span>
          </div>
          <div class="toolbar">
            <button onclick="pollNow()">Poll SEC</button>
            <a class="button" href="/api/filings">JSON</a>
          </div>
        </header>
        <main>
          {empty_state}
          <section class="feed">{rows}</section>
        </main>
        <script>
          async function pollNow() {{
            const button = document.querySelector("button");
            button.disabled = true;
            button.textContent = "Polling...";
            try {{
              const response = await fetch("/api/poll", {{ method: "POST" }});
              if (!response.ok) throw new Error(await response.text());
              location.reload();
            }} catch (error) {{
              alert(error.message);
              button.disabled = false;
              button.textContent = "Poll SEC";
            }}
          }}
        </script>
      </body>
    </html>
    """


def _filing_card(row: dict[str, str | None]) -> str:
    accepted = row.get("accepted_at") or row.get("filing_date") or "Unknown"
    return f"""
    <article>
      <div class="card-top">
        <div class="form">{_escape(row.get("form"))}</div>
        <div class="date">{_escape(accepted)}</div>
      </div>
      <div class="entity">{_escape(row.get("entity_name"))}</div>
      <dl>
        <dt>Accession</dt><dd>{_escape(row.get("accession_number"))}</dd>
        <dt>Filing date</dt><dd>{_escape(row.get("filing_date"))}</dd>
        <dt>Report date</dt><dd>{_escape(row.get("report_date") or "N/A")}</dd>
        <dt>Confidence</dt><dd>{_escape(row.get("confidence"))}</dd>
        <dt>Source</dt><dd><a href="{_escape(row.get("sec_url"))}" target="_blank" rel="noreferrer">SEC filing</a></dd>
      </dl>
    </article>
    """


def _escape(value: str | None) -> str:
    if value is None:
        return ""
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
