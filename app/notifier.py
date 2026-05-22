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

    async def send_filing_alert(self, filing: Filing, analysis: dict[str, object] | None = None) -> None:
        if not self.enabled:
            return

        message = build_filing_alert_message(filing, analysis)
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


def build_filing_alert_message(
    filing: Filing,
    analysis: dict[str, object] | None = None,
) -> str:
    summary = ""
    if analysis and analysis.get("status") == "complete":
        key_points = analysis.get("key_points") or []
        rendered_points = "\n".join(f"- {point}" for point in key_points)
        summary = (
            "\n\nAI 整理:\n"
            f"{analysis.get('summary')}\n"
            f"重要性: {analysis.get('importance')}\n"
            f"{rendered_points}"
        )
    elif analysis and analysis.get("error"):
        summary = f"\n\nAI 整理暫不可用: {analysis.get('error')}"

    return (
        "SEC 新資料\n\n"
        f"{filing.entity_name} 提交 {filing.form}\n"
        f"報告期: {filing.report_date or 'N/A'}\n"
        f"SEC 接收: {filing.accepted_at or filing.filing_date}\n"
        f"{summary}\n"
        f"來源: {filing.sec_url}"
    )
