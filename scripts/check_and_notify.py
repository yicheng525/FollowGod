import asyncio
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from app.notifier import build_filing_alert_message
from app.service import PollService
from app.storage import FilingStore


DEFAULT_STATE_PATH = PROJECT_ROOT / "data" / "notified_accessions.json"


async def main() -> None:
    state_path = Path(os.getenv("FOLLOWGOD_STATE_PATH", DEFAULT_STATE_PATH))
    state = _load_state(state_path)
    notified_accessions = set(state.get("notified_accessions", []))

    settings = get_settings()
    store = FilingStore(settings.database_path)
    service = PollService(settings, store)

    filings = await service.sec_client.fetch_recent_filings(settings.normalized_cik)
    store.insert_new(filings)
    holdings_results = await service.parse_missing_holdings(filings)

    new_filings = [
        filing for filing in filings if filing.accession_number not in notified_accessions
    ]
    new_filings.sort(key=lambda filing: filing.accepted_at or filing.filing_date)

    notifications: list[dict[str, object]] = []
    for filing in new_filings:
        analysis = await service.analyze_filing(filing.accession_number)
        message = build_filing_alert_message(filing, analysis)

        sent = False
        error = None
        try:
            await service.notifier.send_filing_alert(filing, analysis)
            sent = service.notifier.enabled
            if not service.notifier.enabled:
                error = "Telegram is not configured; preview generated but not sent."
        except Exception as exc:  # noqa: BLE001
            error = str(exc)

        # Only mark as handled after Telegram is actually sent.
        # If Telegram is missing or fails, the next run can retry.
        if sent:
            notified_accessions.add(filing.accession_number)

        notifications.append(
            {
                "accession_number": filing.accession_number,
                "form": filing.form,
                "accepted_at": filing.accepted_at,
                "analysis_status": analysis.get("status"),
                "telegram_sent": sent,
                "error": error,
                "message_preview": message[:1200],
            }
        )

    state["notified_accessions"] = sorted(notified_accessions)
    _save_state(state_path, state)

    print(
        json.dumps(
            {
                "target_cik": settings.normalized_cik,
                "tracked_filings_seen": len(filings),
                "new_filings": len(new_filings),
                "telegram_enabled": service.notifier.enabled,
                "ai_enabled": service.ai_reader.enabled,
                "holdings_results": holdings_results,
                "notifications": notifications,
                "state_path": str(state_path),
            },
            indent=2,
            ensure_ascii=False,
        )
    )


def _load_state(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        return {"notified_accessions": []}
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _save_state(path: Path, state: dict[str, list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(state, file, indent=2, ensure_ascii=False)
        file.write("\n")


if __name__ == "__main__":
    asyncio.run(main())
