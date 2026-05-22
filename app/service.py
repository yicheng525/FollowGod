from __future__ import annotations

from app.config import Settings
from app.ai_reader import AiFilingReader
from app.filing_content import SecArchiveClient
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
        self.notifier = TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id)

    async def poll_once(self) -> dict[str, object]:
        filings = await self.sec_client.fetch_recent_filings(self.settings.normalized_cik)
        new_filings = self.store.insert_new(filings)

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
            "analysis_results": analysis_results,
            "notification_errors": notification_errors,
        }

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
            analysis = await self.ai_reader.analyze(filing, reader_input)
        except Exception as exc:  # noqa: BLE001
            analysis = {"status": "error", "error": str(exc), "model": self.settings.openai_model}

        self.store.save_analysis(accession_number, analysis)
        return analysis
