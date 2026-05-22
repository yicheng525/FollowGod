from __future__ import annotations

import json

import httpx

from app.models import Filing


ANALYSIS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {"type": "string"},
        "importance": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
        "key_points": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 6,
        },
        "parsed_facts": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "form_type": {"type": "string"},
                "entity": {"type": "string"},
                "period_or_report_date": {"type": "string"},
                "notable_securities": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 10,
                },
                "ownership_or_position_change": {"type": "string"},
                "source_limitations": {"type": "string"},
            },
            "required": [
                "form_type",
                "entity",
                "period_or_report_date",
                "notable_securities",
                "ownership_or_position_change",
                "source_limitations",
            ],
        },
    },
    "required": ["summary", "importance", "key_points", "parsed_facts"],
}


class AiFilingReader:
    def __init__(self, api_key: str | None, model: str) -> None:
        self.api_key = api_key
        self.model = model

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    async def analyze(self, filing: Filing, reader_input: dict[str, object]) -> dict[str, object]:
        if not self.enabled:
            return {
                "status": "skipped",
                "error": "OPENAI_API_KEY is not configured.",
            }

        filing_text = str(reader_input.get("text") or "")
        if not filing_text.strip():
            return {
                "status": "skipped",
                "error": "No readable SEC document text was found.",
            }

        prompt = _build_prompt(filing, reader_input, filing_text)
        payload = {
            "model": self.model,
            "instructions": (
                "You are a careful SEC filing analyst. Use only the supplied filing text. "
                "Do not infer trades that are not present. If a fact is missing, say it is not available. "
                "Keep the summary concise and useful for a mobile alert."
            ),
            "input": prompt,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "filing_analysis",
                    "strict": True,
                    "schema": ANALYSIS_SCHEMA,
                }
            },
            "max_output_tokens": 1200,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/responses",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            body = response.json()

        output_text = _extract_output_text(body)
        analysis = json.loads(output_text)
        analysis["status"] = "complete"
        analysis["model"] = self.model
        return analysis


def _build_prompt(filing: Filing, reader_input: dict[str, object], filing_text: str) -> str:
    return f"""
SEC filing metadata:
- Entity: {filing.entity_name}
- CIK: {filing.cik}
- Form: {filing.form}
- Filing date: {filing.filing_date}
- Report date: {filing.report_date or "N/A"}
- Accepted at: {filing.accepted_at or "N/A"}
- Accession: {filing.accession_number}
- Source: {filing.sec_url}
- Readable documents: {reader_input.get("readable_documents")}
- Skipped documents: {reader_input.get("skipped_documents")}

Analyze the filing for an investor tracking this entity. Focus on:
- what the filing says,
- whether it suggests a new position, changed position, ownership disclosure, or routine filing,
- securities/tickers/names explicitly visible,
- limitations from the supplied text.

Filing text:
{filing_text}
""".strip()


def _extract_output_text(body: dict[str, object]) -> str:
    if isinstance(body.get("output_text"), str):
        return str(body["output_text"])

    chunks: list[str] = []
    for item in body.get("output", []) or []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []) or []:
            if not isinstance(content, dict):
                continue
            if isinstance(content.get("text"), str):
                chunks.append(str(content["text"]))
    if chunks:
        return "".join(chunks)
    raise ValueError("OpenAI response did not contain output text.")
