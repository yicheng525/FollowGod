from __future__ import annotations

from app.config import Settings
from app.ai_reader import AiFilingReader
from app.filing_content import SecArchiveClient
from app.holdings_parser import parse_13f_information_table
from app.models import Filing
from app.notifier import TelegramNotifier
from app.sec_client import SecClient
from app.storage import FilingStore


class PollService:
    def __init__(self, settings: Settings, store: FilingStore) -> None:
        self.settings = settings
        self.store = store
        self.sec_client = SecClient(settings.sec_user_agent)
        self.archive_client = SecArchiveClient(settings.sec_user_agent)
        self.ai_reader = AiFilingReader(settings.openai_api_key, settings.openai_model)
        self.notifier = TelegramNotifier(
            settings.telegram_bot_token,
            settings.telegram_chat_id,
            settings.dashboard_url,
        )

    async def poll_once(self) -> dict[str, object]:
        filings = await self.sec_client.fetch_recent_filings(self.settings.normalized_cik)
        new_filings = self.store.insert_new(filings)
        holdings_results = await self.parse_missing_holdings(filings)

        notified = 0
        notification_errors: list[str] = []
        analysis_results: list[dict[str, object]] = []
        for filing in new_filings:
            analysis = await self.analyze_filing(filing.accession_number)
            analysis_results.append({"accession_number": filing.accession_number, **analysis})
            try:
                await self.notifier.send_filing_alert(filing, analysis)
                if self.notifier.enabled:
                    notified += 1
            except Exception as exc:  # noqa: BLE001
                notification_errors.append(f"{filing.accession_number}: {exc}")

        return {
            "target_cik": self.settings.normalized_cik,
            "target_name": self.settings.target_name,
            "tracked_filings_seen": len(filings),
            "new_filings": len(new_filings),
            "telegram_enabled": self.notifier.enabled,
            "telegram_notifications_sent": notified,
            "ai_enabled": self.ai_reader.enabled,
            "holdings_results": holdings_results,
            "analysis_results": analysis_results,
            "notification_errors": notification_errors,
        }

    async def parse_missing_holdings(self, filings: list[Filing]) -> list[dict[str, object]]:
        results: list[dict[str, object]] = []
        for filing in filings:
            if not filing.form.startswith("13F"):
                continue
            if self.store.holdings_count(filing.accession_number) > 0:
                continue
            try:
                xml_text = await self.archive_client.fetch_13f_information_table(filing)
                if not xml_text:
                    results.append(
                        {
                            "accession_number": filing.accession_number,
                            "status": "skipped",
                            "error": "No 13F information table XML found.",
                        }
                    )
                    continue
                holdings = parse_13f_information_table(xml_text)
                count = self.store.insert_holdings(filing.accession_number, holdings)
                results.append(
                    {
                        "accession_number": filing.accession_number,
                        "status": "complete",
                        "holdings_count": count,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                results.append(
                    {
                        "accession_number": filing.accession_number,
                        "status": "error",
                        "error": str(exc),
                    }
                )
        return results

    async def analyze_filing(self, accession_number: str, force: bool = False) -> dict[str, object]:
        existing = self.store.get_analysis(accession_number)
        if existing and existing.get("status") == "complete" and not force:
            return {"status": existing.get("status") or "unknown", "cached": True}
        if existing and existing.get("status") == "skipped" and not self.ai_reader.enabled and not force:
            return {"status": existing.get("status") or "unknown", "cached": True}

        filing = self.store.get_filing(accession_number)
        if filing is None:
            return {"status": "error", "error": "Filing was not found."}

        try:
            reader_input = await self.archive_client.build_reader_input(filing)
            holdings_context = self.build_holdings_context(filing.accession_number)
            analysis = await self.ai_reader.analyze(filing, reader_input, holdings_context)
        except Exception as exc:  # noqa: BLE001
            analysis = {"status": "error", "error": str(exc), "model": self.settings.openai_model}

        self.store.save_analysis(accession_number, analysis)
        return analysis

    def build_holdings_context(self, accession_number: str) -> str:
        holdings = self.store.list_holdings(accession_number)
        if not holdings:
            return ""

        previous_accession = self.store.previous_filing_accession(accession_number)
        previous = self.store.list_holdings(previous_accession) if previous_accession else []
        previous_by_key = {_holding_key(holding): holding for holding in previous}

        enriched: list[dict[str, object]] = []
        for holding in holdings:
            current = dict(holding)
            previous_holding = previous_by_key.get(_holding_key(holding))
            current["change"] = _holding_change(holding, previous_holding)
            enriched.append(current)

        total_value = sum(int(holding.get("value") or 0) for holding in enriched)
        top_holdings = sorted(enriched, key=lambda item: int(item.get("value") or 0), reverse=True)[:15]
        changed_holdings = sorted(enriched, key=_change_sort_key)[:20]

        lines = [
            f"Total rows: {len(enriched)}",
            f"Total reported value: {_money(total_value)}",
            "Top holdings by reported value:",
        ]
        lines.extend(_holding_line(holding, total_value) for holding in top_holdings)
        lines.append("Most relevant changes versus previous 13F:")
        lines.extend(_holding_line(holding, total_value, include_change=True) for holding in changed_holdings)
        return "\n".join(lines)


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


def _holding_line(holding: dict[str, object], total_value: int, include_change: bool = False) -> str:
    value = int(holding.get("value") or 0)
    percent = value / total_value * 100 if total_value else 0
    exposure_type = holding.get("put_call") or "Long"
    change = f", change={holding.get('change')}" if include_change else ""
    return (
        f"- {holding.get('name_of_issuer')} ({exposure_type}): "
        f"value={_money(value)}, weight={percent:.1f}%, "
        f"shares/principal={int(holding.get('shares_or_principal') or 0):,}, "
        f"CUSIP={holding.get('cusip')}{change}"
    )


def _money(value: int) -> str:
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:,}"
