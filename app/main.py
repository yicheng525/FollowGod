from __future__ import annotations

from fastapi import FastAPI, HTTPException
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


@app.get("/api/filings/{accession_number}/holdings")
def api_holdings(accession_number: str) -> list[dict[str, object]]:
    if store.get_filing(accession_number) is None:
        raise HTTPException(status_code=404, detail="Filing not found")
    return _holdings_with_changes(accession_number)


@app.post("/api/poll")
async def api_poll() -> dict[str, object]:
    service = PollService(settings, store)
    return await service.poll_once()


@app.post("/api/analyze/{accession_number}")
async def api_analyze(accession_number: str, force: bool = False) -> dict[str, object]:
    if store.get_filing(accession_number) is None:
        raise HTTPException(status_code=404, detail="Filing not found")
    service = PollService(settings, store)
    return await service.analyze_filing(accession_number, force=force)


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    filings = store.list_filings(limit=100)
    latest_filing = _latest_filing_with_holdings(filings)
    portfolio_overview = _portfolio_overview_section(latest_filing)
    change_overview = _change_overview_section(latest_filing)
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
    ai_status = "On" if settings.openai_api_key else "Off"
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
          .section-title {{
            display: flex;
            justify-content: space-between;
            gap: 10px;
            align-items: end;
            margin: 18px 0 10px;
          }}
          .section-title h2 {{
            margin: 0;
            font-size: 17px;
            letter-spacing: 0;
          }}
          .section-title span {{
            color: #94a3b8;
            font-size: 12px;
            text-align: right;
          }}
          .portfolio-grid {{
            display: grid;
            gap: 10px;
          }}
          .position-card {{
            border: 1px solid #253044;
            border-radius: 8px;
            background: #101722;
            padding: 13px;
          }}
          .position-top {{
            display: grid;
            grid-template-columns: 1fr auto;
            gap: 8px;
            align-items: start;
          }}
          .position-name {{
            color: #f8fafc;
            font-size: 14px;
            font-weight: 750;
            overflow-wrap: anywhere;
          }}
          .position-value {{
            color: #c7d2fe;
            font-size: 14px;
            font-weight: 750;
            white-space: nowrap;
          }}
          .position-meta {{
            margin-top: 6px;
            color: #94a3b8;
            font-size: 12px;
            line-height: 1.4;
          }}
          .change-grid {{
            display: grid;
            gap: 8px;
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
          .analysis {{
            margin-top: 12px;
            border-top: 1px solid #253044;
            padding-top: 12px;
          }}
          .analysis-title {{
            color: #fbbf24;
            font-size: 13px;
            font-weight: 700;
            margin-bottom: 6px;
          }}
          .analysis p {{
            margin: 0 0 8px;
            color: #dbeafe;
            font-size: 13px;
            line-height: 1.45;
          }}
          .analysis ul {{
            margin: 0;
            padding-left: 18px;
            color: #e2e8f0;
            font-size: 13px;
            line-height: 1.45;
          }}
          .analysis.pending {{
            color: #94a3b8;
          }}
          .holdings {{
            margin-top: 12px;
            border-top: 1px solid #253044;
            padding-top: 12px;
          }}
          .holdings-title {{
            display: flex;
            justify-content: space-between;
            gap: 10px;
            color: #f8fafc;
            font-size: 13px;
            font-weight: 700;
            margin-bottom: 8px;
          }}
          .holding-row {{
            display: grid;
            grid-template-columns: 1fr auto;
            gap: 6px 10px;
            padding: 8px 0;
            border-top: 1px solid #1f2937;
          }}
          .holding-row:first-of-type {{
            border-top: 0;
          }}
          .issuer {{
            font-size: 13px;
            font-weight: 650;
            color: #e2e8f0;
            overflow-wrap: anywhere;
          }}
          .holding-meta {{
            grid-column: 1 / -1;
            color: #94a3b8;
            font-size: 12px;
          }}
          .holding-value {{
            text-align: right;
            font-size: 13px;
            color: #c7d2fe;
            white-space: nowrap;
          }}
          .change {{
            display: inline-block;
            margin-left: 6px;
            color: #34d399;
            font-weight: 700;
          }}
          .change.reduced {{
            color: #fb7185;
          }}
          .change.unchanged {{
            color: #94a3b8;
          }}
        </style>
      </head>
      <body>
        <header>
          <h1>FollowGod SEC Tracker</h1>
          <div class="meta">
            <span class="pill">CIK {settings.normalized_cik}</span>
            <span class="pill">AI {ai_status}</span>
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
          {portfolio_overview}
          {change_overview}
          <div class="section-title">
            <h2>Filings</h2>
            <span>Source documents and parsed tables</span>
          </div>
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
          async function analyzeFiling(accession, force = false) {{
            const suffix = force ? "?force=true" : "";
            const response = await fetch(`/api/analyze/${{accession}}${{suffix}}`, {{ method: "POST" }});
            if (!response.ok) {{
              alert(await response.text());
              return;
            }}
            location.reload();
          }}
        </script>
      </body>
    </html>
    """


def _latest_filing_with_holdings(filings: list[dict[str, str | None]]) -> dict[str, str | None] | None:
    for filing in filings:
        if int(filing.get("holdings_count") or 0) > 0:
            return filing
    return None


def _portfolio_overview_section(filing: dict[str, str | None] | None) -> str:
    if filing is None:
        return ""
    accession = filing.get("accession_number")
    if not accession:
        return ""
    holdings = store.list_holdings(accession)
    total_value = int(filing.get("holdings_total_value") or 0)
    rows = "".join(_position_card(holding, total_value) for holding in holdings[:18])
    report_date = filing.get("report_date") or filing.get("filing_date") or ""
    return f"""
    <div class="section-title">
      <h2>Latest Portfolio</h2>
      <span>{_escape(report_date)} / {len(holdings)} rows / {_money(total_value)}</span>
    </div>
    <section class="portfolio-grid">{rows}</section>
    """


def _change_overview_section(filing: dict[str, str | None] | None) -> str:
    if filing is None:
        return ""
    accession = filing.get("accession_number")
    if not accession:
        return ""
    holdings = _holdings_with_changes(accession)
    notable = sorted(
        [
            holding
            for holding in holdings
            if str(holding.get("change") or "").startswith(("NEW", "INCREASED", "REDUCED"))
        ],
        key=_change_sort_key,
    )[:18]
    if not notable:
        return ""
    rows = "".join(_position_card(holding, int(filing.get("holdings_total_value") or 0), show_change=True) for holding in notable)
    return f"""
    <div class="section-title">
      <h2>Latest Changes</h2>
      <span>Compared with previous 13F</span>
    </div>
    <section class="change-grid">{rows}</section>
    """


def _change_sort_key(holding: dict[str, object]) -> tuple[int, int]:
    change = str(holding.get("change") or "")
    put_call = holding.get("put_call")
    value = int(holding.get("value") or 0)
    if change == "NEW" and not put_call:
        bucket = 0
    elif change.startswith("INCREASED") and not put_call:
        bucket = 1
    elif change.startswith("REDUCED") and not put_call:
        bucket = 2
    elif change == "NEW":
        bucket = 3
    elif change.startswith("INCREASED"):
        bucket = 4
    else:
        bucket = 5
    return (bucket, -value)


def _position_card(
    holding: dict[str, object],
    total_value: int,
    show_change: bool = False,
) -> str:
    value = int(holding.get("value") or 0)
    percent = value / total_value * 100 if total_value else 0
    put_call = str(holding.get("put_call") or "Long")
    change = str(holding.get("change") or "")
    change_html = f'<span class="change {_change_class(change)}">{_escape(change)}</span>' if show_change else ""
    return f"""
    <article class="position-card">
      <div class="position-top">
        <div class="position-name">{_escape(str(holding.get("name_of_issuer") or ""))}</div>
        <div class="position-value">{_money(value)}</div>
      </div>
      <div class="position-meta">
        {percent:.1f}% / {int(holding.get("shares_or_principal") or 0):,} {holding.get("share_type") or ""}
        / {put_call}
        / CUSIP {_escape(str(holding.get("cusip") or ""))}
        {change_html}
      </div>
    </article>
    """


def _filing_card(row: dict[str, str | None]) -> str:
    accepted = row.get("accepted_at") or row.get("filing_date") or "Unknown"
    analysis = _analysis_section(row)
    holdings = _holdings_section(row)
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
      {holdings}
      {analysis}
    </article>
    """


def _holdings_section(row: dict[str, str | None]) -> str:
    accession = row.get("accession_number")
    holdings_count = int(row.get("holdings_count") or 0)
    if not accession or holdings_count == 0:
        return ""

    holdings = _select_display_holdings(_holdings_with_changes(accession))
    rendered = "".join(_holding_row(holding) for holding in holdings)
    total_value = int(row.get("holdings_total_value") or 0)
    return f"""
    <div class="holdings">
      <div class="holdings-title">
        <span>Top / notable holdings</span>
        <span>{holdings_count} rows / {_money(total_value)}</span>
      </div>
      {rendered}
    </div>
    """


def _select_display_holdings(holdings: list[dict[str, object]]) -> list[dict[str, object]]:
    selected: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()

    def add(holding: dict[str, object]) -> None:
        key = _holding_key(holding)
        if key in seen:
            return
        seen.add(key)
        selected.append(holding)

    for holding in holdings[:10]:
        add(holding)

    new_longs = [
        holding
        for holding in holdings
        if holding.get("change") == "NEW" and not holding.get("put_call")
    ]
    for holding in new_longs[:10]:
        add(holding)

    important_names = ("T1 ENERGY", "BLOOM ENERGY", "COREWEAVE", "CORE SCIENTIFIC", "APPLIED DIGITAL")
    for holding in holdings:
        issuer = str(holding.get("name_of_issuer") or "").upper()
        if any(name in issuer for name in important_names):
            add(holding)

    return selected[:22]


def _holding_row(holding: dict[str, object]) -> str:
    change = str(holding.get("change") or "")
    change_class = _change_class(change)

    put_call = holding.get("put_call") or "Long"
    return f"""
    <div class="holding-row">
      <div class="issuer">{_escape(str(holding.get("name_of_issuer") or ""))}</div>
      <div class="holding-value">{_money(int(holding.get("value") or 0))}</div>
      <div class="holding-meta">
        {int(holding.get("shares_or_principal") or 0):,} {holding.get("share_type") or ""}
        / {put_call}
        / CUSIP {_escape(str(holding.get("cusip") or ""))}
        <span class="change {change_class}">{_escape(change)}</span>
      </div>
    </div>
    """


def _change_class(change: str) -> str:
    if change.startswith("NEW") or change.startswith("INCREASED"):
        return "increased"
    if change.startswith("REDUCED") or change.startswith("EXITED"):
        return "reduced"
    return "unchanged"


def _holdings_with_changes(accession_number: str) -> list[dict[str, object]]:
    current = store.list_holdings(accession_number)
    previous_accession = store.previous_filing_accession(accession_number)
    previous = store.list_holdings(previous_accession) if previous_accession else []
    previous_by_key = {_holding_key(holding): holding for holding in previous}
    enriched: list[dict[str, object]] = []
    for holding in current:
        previous_holding = previous_by_key.get(_holding_key(holding))
        enriched_holding = dict(holding)
        enriched_holding["change"] = _holding_change(holding, previous_holding)
        enriched.append(enriched_holding)
    return enriched


def _holding_key(holding: dict[str, object]) -> tuple[str, str]:
    return (
        str(holding.get("cusip") or ""),
        str(holding.get("put_call") or "Long"),
    )


def _holding_change(
    current: dict[str, object],
    previous: dict[str, object] | None,
) -> str:
    current_value = int(current.get("value") or 0)
    if previous is None:
        return "NEW"
    previous_value = int(previous.get("value") or 0)
    if previous_value == current_value:
        return "UNCHANGED"
    delta = current_value - previous_value
    percent = abs(delta) / previous_value * 100 if previous_value else 0
    if delta > 0:
        return f"INCREASED {percent:.0f}%"
    return f"REDUCED {percent:.0f}%"


def _money(value: int) -> str:
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:,}"


def _analysis_section(row: dict[str, str | None]) -> str:
    status = row.get("analysis_status")
    accession = row.get("accession_number") or ""
    if not status:
        if not settings.openai_api_key:
            return """
            <div class="analysis pending">
              <div class="analysis-title">AI analysis off</div>
              <p>Set OPENAI_API_KEY in .env to enable filing summaries.</p>
            </div>
            """
        return f"""
        <div class="analysis pending">
          <div class="analysis-title">AI analysis pending</div>
          <button onclick="analyzeFiling('{_escape(accession)}')">Analyze</button>
        </div>
        """
    if status != "complete":
        error = row.get("analysis_error") or "No analysis is available."
        if not settings.openai_api_key:
            return f"""
            <div class="analysis pending">
              <div class="analysis-title">AI analysis off</div>
              <p>{_escape(error)}</p>
            </div>
            """
        return f"""
        <div class="analysis pending">
          <div class="analysis-title">AI analysis {status}</div>
          <p>{_escape(error)}</p>
          <button onclick="analyzeFiling('{_escape(accession)}', true)">Retry</button>
        </div>
        """

    key_points = _json_list(row.get("analysis_key_points_json"))
    rendered_points = "".join(f"<li>{_escape(point)}</li>" for point in key_points)
    return f"""
    <div class="analysis">
      <div class="analysis-title">AI Summary: {_escape(row.get("analysis_importance"))}</div>
      <p>{_escape(row.get("analysis_summary"))}</p>
      <ul>{rendered_points}</ul>
    </div>
    """


def _json_list(value: str | None) -> list[str]:
    import json

    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed]


def _escape(value: str | None) -> str:
    if value is None:
        return ""
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
