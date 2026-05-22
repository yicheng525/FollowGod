from __future__ import annotations

from app.config import Settings
from app.notifier import TelegramNotifier
from app.sec_client import SecClient
from app.storage import FilingStore


class PollService:
    def __init__(self, settings: Settings, store: FilingStore) -> None:
        self.settings = settings
        self.store = store
        self.sec_client = SecClient(settings.sec_user_agent)
        self.notifier = TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id)

    async def poll_once(self) -> dict[str, object]:
        filings = await self.sec_client.fetch_recent_filings(self.settings.normalized_cik)
        new_filings = self.store.insert_new(filings)

        notified = 0
        notification_errors: list[str] = []
        for filing in new_filings:
            try:
                await self.notifier.send_filing_alert(filing)
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
            "notification_errors": notification_errors,
        }
