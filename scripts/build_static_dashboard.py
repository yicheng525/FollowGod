import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from app.storage import FilingStore


SITE_DIR = PROJECT_ROOT / "site"


def main() -> None:
    settings = get_settings()
    store = FilingStore(settings.database_path)
    filings = store.list_filings(limit=100)
    latest = _latest_filing_with_holdings(filings)

    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / ".nojekyll").write_text("", encoding="utf-8")
    (SITE_DIR / "index.html").write_text(
        _render_page(settings.target_name, settings.normalized_cik, filings, latest),
        encoding="utf-8",
    )
    print(f"Built static dashboard: {SITE_DIR / 'index.html'}")


def _render_page(
    target_name: str,
    cik: str,
    filings: list[dict[str, object]],
    latest: dict[str, object] | None,
) -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    portfolio = _portfolio_section(latest)
    changes = _changes_section(latest)
    filing_cards = "".join(_filing_card(filing) for filing in filings)
    empty = ""
    if not filings:
        empty = """
        <section class="empty">
          <h2>No filings yet</h2>
          <p>The scheduled workflow has not stored SEC filings yet.</p>
        </section>
        """

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>FollowGod SEC Dashboard</title>
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
        max-width: 920px;
        margin: 0 auto;
        padding: 14px 12px 32px;
      }}
      h1 {{
        margin: 0 0 8px;
        font-size: 24px;
        line-height: 1.1;
        letter-spacing: 0;
      }}
      .meta, .toolbar {{
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
      .grid, .feed {{
        display: grid;
        gap: 10px;
      }}
      article {{
        border: 1px solid #253044;
        border-radius: 8px;
        background: #101722;
        padding: 13px;
      }}
      .position-top, .card-top {{
        display: grid;
        grid-template-columns: 1fr auto;
        gap: 8px;
        align-items: start;
      }}
      .name, .issuer {{
        color: #f8fafc;
        font-size: 14px;
        font-weight: 750;
        overflow-wrap: anywhere;
      }}
      .value {{
        color: #c7d2fe;
        font-size: 14px;
        font-weight: 750;
        white-space: nowrap;
      }}
      .subtext {{
        margin-top: 6px;
        color: #94a3b8;
        font-size: 12px;
        line-height: 1.45;
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
      a {{
        color: #60a5fa;
      }}
      .empty {{
        border: 1px solid #253044;
        border-radius: 8px;
        padding: 16px;
        background: #101722;
      }}
      .filing-type {{
        color: #34d399;
        font-weight: 800;
        font-size: 13px;
      }}
      .date {{
        color: #94a3b8;
        font-size: 12px;
        text-align: right;
      }}
    </style>
  </head>
  <body>
    <header>
      <h1>FollowGod SEC Dashboard</h1>
      <div class="meta">
        <span class="pill">{_escape(target_name)}</span>
        <span class="pill">CIK {_escape(cik)}</span>
        <span class="pill">{len(filings)} filings</span>
        <span class="pill">Updated {generated_at}</span>
      </div>
    </header>
    <main>
      {empty}
      {portfolio}
      {changes}
      <div class="section-title">
        <h2>Filings</h2>
        <span>Source documents</span>
      </div>
      <section class="feed">{filing_cards}</section>
    </main>
  </body>
</html>
"""


def _portfolio_section(filing: dict[str, object] | None) -> str:
    if filing is None:
        return ""
    accession = str(filing.get("accession_number") or "")
    holdings = _holdings_with_changes(accession)
    total_value = int(filing.get("holdings_total_value") or 0)
    rows = "".join(_position_card(holding, total_value) for holding in holdings[:18])
    return f"""
    <div class="section-title">
      <h2>Latest Portfolio</h2>
      <span>{_escape(str(filing.get("report_date") or filing.get("filing_date") or ""))} / {len(holdings)} rows / {_money(total_value)}</span>
    </div>
    <section class="grid">{rows}</section>
    """


def _changes_section(filing: dict[str, object] | None) -> str:
    if filing is None:
        return ""
    accession = str(filing.get("accession_number") or "")
    holdings = _holdings_with_changes(accession)
    notable = sorted(
        [
            holding
            for holding in holdings
            if str(holding.get("change") or "").startswith(("NEW", "INCREASED", "REDUCED"))
        ],
        key=_change_sort_key,
    )[:18]
    rows = "".join(
        _position_card(holding, int(filing.get("holdings_total_value") or 0), show_change=True)
        for holding in notable
    )
    return f"""
    <div class="section-title">
      <h2>Latest Changes</h2>
      <span>Compared with previous 13F</span>
    </div>
    <section class="grid">{rows}</section>
    """


def _position_card(
    holding: dict[str, object],
    total_value: int,
    show_change: bool = False,
) -> str:
    value = int(holding.get("value") or 0)
    percent = value / total_value * 100 if total_value else 0
    change = str(holding.get("change") or "")
    change_html = f'<span class="change {_change_class(change)}">{_escape(change)}</span>' if show_change else ""
    exposure_type = holding.get("put_call") or "Long"
    return f"""
    <article>
      <div class="position-top">
        <div class="name">{_escape(str(holding.get("name_of_issuer") or ""))}</div>
        <div class="value">{_money(value)}</div>
      </div>
      <div class="subtext">
        {percent:.1f}% / {int(holding.get("shares_or_principal") or 0):,} {holding.get("share_type") or ""}
        / {exposure_type}
        / CUSIP {_escape(str(holding.get("cusip") or ""))}
        {change_html}
      </div>
    </article>
    """


def _filing_card(filing: dict[str, object]) -> str:
    return f"""
    <article>
      <div class="card-top">
        <div class="filing-type">{_escape(str(filing.get("form") or ""))}</div>
        <div class="date">{_escape(str(filing.get("accepted_at") or filing.get("filing_date") or ""))}</div>
      </div>
      <div class="subtext">
        Report: {_escape(str(filing.get("report_date") or "N/A"))}
        / {int(filing.get("holdings_count") or 0)} holdings
        / <a href="{_escape(str(filing.get("sec_url") or ""))}" target="_blank" rel="noreferrer">SEC source</a>
      </div>
    </article>
    """


def _latest_filing_with_holdings(filings: list[dict[str, object]]) -> dict[str, object] | None:
    for filing in filings:
        if int(filing.get("holdings_count") or 0) > 0:
            return filing
    return None


def _holdings_with_changes(accession_number: str) -> list[dict[str, object]]:
    settings = get_settings()
    store = FilingStore(settings.database_path)
    current = store.list_holdings(accession_number)
    previous_accession = store.previous_filing_accession(accession_number)
    previous = store.list_holdings(previous_accession) if previous_accession else []
    previous_by_key = {_holding_key(holding): holding for holding in previous}
    enriched: list[dict[str, object]] = []
    for holding in current:
        previous_holding = previous_by_key.get(_holding_key(holding))
        item = dict(holding)
        item["change"] = _holding_change(holding, previous_holding)
        enriched.append(item)
    return enriched


def _holding_key(holding: dict[str, object]) -> tuple[str, str]:
    return (
        str(holding.get("cusip") or ""),
        str(holding.get("put_call") or "Long"),
    )


def _holding_change(current: dict[str, object], previous: dict[str, object] | None) -> str:
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


def _change_class(change: str) -> str:
    if change.startswith("NEW") or change.startswith("INCREASED"):
        return "increased"
    if change.startswith("REDUCED") or change.startswith("EXITED"):
        return "reduced"
    return "unchanged"


def _money(value: int) -> str:
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:,}"


def _escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


if __name__ == "__main__":
    main()
