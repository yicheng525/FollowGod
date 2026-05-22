from __future__ import annotations

import httpx

from app.models import Filing


class TelegramNotifier:
    def __init__(self, bot_token: str | None, chat_id: str | None) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id

    @property
    def enabled(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    async def send_filing_alert(self, filing: Filing) -> None:
        if not self.enabled:
            return

        message = (
            "CRITICAL: New SEC Filing Detected\n\n"
            f"Entity: {filing.entity_name}\n"
            f"Filing: {filing.form}\n"
            f"Accepted: {filing.accepted_at or filing.filing_date}\n"
            f"Accession: {filing.accession_number}\n"
            f"Confidence: {filing.confidence}\n"
            f"Source: {filing.sec_url}"
        )
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                url,
                json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "disable_web_page_preview": True,
                },
            )
            response.raise_for_status()
