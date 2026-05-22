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
    added = _change_section(latest, "added")
    increased = _change_section(latest, "increased")
    reduced = _change_section(latest, "reduced")
    filing_cards = "".join(_filing_card(filing) for filing in filings)
    metrics = _metrics_section(latest, filings)
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
        padding: 18px 16px 12px;
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
      .tabs {{
        display: flex;
        gap: 6px;
        margin-top: 14px;
        overflow-x: auto;
        scrollbar-width: none;
      }}
      .tabs::-webkit-scrollbar {{
        display: none;
      }}
      .tab {{
        appearance: none;
        border: 1px solid #344054;
        border-radius: 999px;
        background: #111827;
        color: #cbd5e1;
        font-size: 13px;
        font-weight: 700;
        padding: 8px 11px;
        white-space: nowrap;
      }}
      .tab.active {{
        border-color: #34d399;
        background: #123027;
        color: #d1fae5;
      }}
      .pill {{
        border: 1px solid #344054;
        border-radius: 999px;
        color: #cbd5e1;
        font-size: 12px;
        padding: 5px 9px;
        background: #111827;
      }}
      .tab-panel {{
        display: none;
      }}
      .tab-panel.active {{
        display: block;
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
      .metrics {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
        margin: 14px 0 4px;
      }}
      .metric {{
        border: 1px solid #253044;
        border-radius: 8px;
        background: #101722;
        padding: 12px;
      }}
      .metric-label {{
        color: #94a3b8;
        font-size: 12px;
      }}
      .metric-value {{
        margin-top: 4px;
        color: #f8fafc;
        font-size: 20px;
        font-weight: 800;
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
      .bar {{
        height: 6px;
        border-radius: 999px;
        background: #1f2937;
        margin-top: 10px;
        overflow: hidden;
      }}
      .bar-fill {{
        height: 100%;
        border-radius: 999px;
        background: #34d399;
      }}
      .position-card.put .bar-fill {{
        background: #fb7185;
      }}
      .position-card.call .bar-fill {{
        background: #60a5fa;
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
      .badge {{
        display: inline-block;
        border: 1px solid #344054;
        border-radius: 999px;
        padding: 2px 7px;
        margin-right: 5px;
        color: #cbd5e1;
        font-size: 11px;
        font-weight: 700;
      }}
      .badge.long {{
        border-color: #047857;
        color: #86efac;
      }}
      .badge.put {{
        border-color: #be123c;
        color: #fda4af;
      }}
      .badge.call {{
        border-color: #2563eb;
        color: #93c5fd;
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
      <nav class="tabs" aria-label="Dashboard tabs">
        <button class="tab active" data-tab="portfolio">持倉</button>
        <button class="tab" data-tab="added">新增</button>
        <button class="tab" data-tab="increased">增加</button>
        <button class="tab" data-tab="reduced">減少</button>
        <button class="tab" data-tab="filings">Filings</button>
      </nav>
    </header>
    <main>
      {empty}
      {metrics}
      <section class="tab-panel active" data-panel="portfolio">{portfolio}</section>
      <section class="tab-panel" data-panel="added">{added}</section>
      <section class="tab-panel" data-panel="increased">{increased}</section>
      <section class="tab-panel" data-panel="reduced">{reduced}</section>
      <section class="tab-panel" data-panel="filings">
        <div class="section-title">
          <h2>Filings</h2>
          <span>Source documents</span>
        </div>
        <div class="feed">{filing_cards}</div>
      </section>
    </main>
    <script>
      const tabs = Array.from(document.querySelectorAll(".tab"));
      const panels = Array.from(document.querySelectorAll(".tab-panel"));
      function activateTab(name) {{
        tabs.forEach((tab) => tab.classList.toggle("active", tab.dataset.tab === name));
        panels.forEach((panel) => panel.classList.toggle("active", panel.dataset.panel === name));
      }}
      tabs.forEach((tab) => tab.addEventListener("click", () => activateTab(tab.dataset.tab)));
    </script>
  </body>
</html>
"""


def _metrics_section(
    latest: dict[str, object] | None,
    filings: list[dict[str, object]],
) -> str:
    if latest is None:
        return ""
    accession = str(latest.get("accession_number") or "")
    holdings = _holdings_with_changes(accession)
    total_value = int(latest.get("holdings_total_value") or 0)
    added = len([holding for holding in holdings if holding.get("change") == "NEW"])
    increased = len([holding for holding in holdings if str(holding.get("change") or "").startswith("INCREASED")])
    reduced = len([holding for holding in holdings if str(holding.get("change") or "").startswith("REDUCED")])
    return f"""
    <section class="metrics">
      <div class="metric">
        <div class="metric-label">Reported value</div>
        <div class="metric-value">{_money(total_value)}</div>
      </div>
      <div class="metric">
        <div class="metric-label">Rows</div>
        <div class="metric-value">{len(holdings)}</div>
      </div>
      <div class="metric">
        <div class="metric-label">New / Up / Down</div>
        <div class="metric-value">{added} / {increased} / {reduced}</div>
      </div>
      <div class="metric">
        <div class="metric-label">Filings</div>
        <div class="metric-value">{len(filings)}</div>
      </div>
    </section>
    """


def _portfolio_section(filing: dict[str, object] | None) -> str:
    if filing is None:
        return ""
    accession = str(filing.get("accession_number") or "")
    holdings = _holdings_with_changes(accession)
    total_value = int(filing.get("holdings_total_value") or 0)
    rows = "".join(_position_card(holding, total_value) for holding in holdings[:30])
    return f"""
    <div class="section-title">
      <h2>Latest Portfolio</h2>
      <span>{_escape(str(filing.get("report_date") or filing.get("filing_date") or ""))} / {len(holdings)} rows / {_money(total_value)}</span>
    </div>
    <section class="grid">{rows}</section>
    """


def _change_section(filing: dict[str, object] | None, mode: str) -> str:
    if filing is None:
        return ""
    accession = str(filing.get("accession_number") or "")
    holdings = _holdings_with_changes(accession)
    if mode == "added":
        title = "新增"
        subtitle = "New rows versus previous 13F"
        filtered = [holding for holding in holdings if holding.get("change") == "NEW"]
    elif mode == "increased":
        title = "增加"
        subtitle = "Increased rows versus previous 13F"
        filtered = [holding for holding in holdings if str(holding.get("change") or "").startswith("INCREASED")]
    else:
        title = "減少"
        subtitle = "Reduced rows versus previous 13F"
        filtered = [holding for holding in holdings if str(holding.get("change") or "").startswith("REDUCED")]

    notable = sorted(filtered, key=_change_sort_key)
    rows = "".join(
        _position_card(holding, int(filing.get("holdings_total_value") or 0), show_change=True)
        for holding in notable
    )
    if not rows:
        rows = '<article><div class="subtext">No rows in this category.</div></article>'
    return f"""
    <div class="section-title">
      <h2>{title}</h2>
      <span>{subtitle}</span>
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
    exposure_class = str(exposure_type).lower()
    bar_width = max(1.5, min(100, percent))
    return f"""
    <article class="position-card {exposure_class}">
      <div class="position-top">
        <div class="name">{_escape(str(holding.get("name_of_issuer") or ""))}</div>
        <div class="value">{_money(value)}</div>
      </div>
      <div class="subtext">
        <span class="badge {exposure_class}">{exposure_type}</span>
        {percent:.1f}% / {int(holding.get("shares_or_principal") or 0):,} {holding.get("share_type") or ""}
        / CUSIP {_escape(str(holding.get("cusip") or ""))}
        {change_html}
      </div>
      <div class="bar"><div class="bar-fill" style="width: {bar_width:.2f}%"></div></div>
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
