from __future__ import annotations

import httpx

from app.models import Filing, TRACKED_FORMS


SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"


class SecClient:
    def __init__(self, user_agent: str) -> None:
        self._headers = {
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Host": "data.sec.gov",
        }

    async def fetch_recent_filings(self, cik: str) -> list[Filing]:
        url = SEC_SUBMISSIONS_URL.format(cik=cik)
        async with httpx.AsyncClient(timeout=30.0, headers=self._headers) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()

        entity_name = payload.get("name") or "Unknown entity"
        recent = payload.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        accession_numbers = recent.get("accessionNumber", [])
        filing_dates = recent.get("filingDate", [])
        report_dates = recent.get("reportDate", [])
        accepted_dates = recent.get("acceptanceDateTime", [])
        primary_documents = recent.get("primaryDocument", [])

        filings: list[Filing] = []
        for index, form in enumerate(forms):
            if form not in TRACKED_FORMS:
                continue
            primary_document = _safe_get(primary_documents, index)
            if not primary_document:
                continue
            filings.append(
                Filing(
                    cik=cik,
                    entity_name=entity_name,
                    accession_number=_safe_get(accession_numbers, index),
                    form=form,
                    filing_date=_safe_get(filing_dates, index),
                    report_date=_safe_get(report_dates, index) or None,
                    accepted_at=_safe_get(accepted_dates, index) or None,
                    primary_document=primary_document,
                )
            )
        return filings


def _safe_get(values: list[str], index: int) -> str:
    if index >= len(values):
        return ""
    return values[index] or ""
