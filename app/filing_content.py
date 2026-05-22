from __future__ import annotations

from html.parser import HTMLParser

import httpx

from app.models import Filing


class SecArchiveClient:
    def __init__(self, user_agent: str) -> None:
        self.headers = {
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
        }

    async def build_reader_input(self, filing: Filing, max_chars: int = 30000) -> dict[str, object]:
        documents = await self._list_documents(filing)
        selected = self._select_readable_documents(filing, documents)
        parts: list[str] = []
        skipped: list[str] = []

        async with httpx.AsyncClient(timeout=30.0, headers=self.headers) as client:
            for document in selected:
                name = document["name"]
                url = self._document_url(filing, name)
                response = await client.get(url)
                response.raise_for_status()
                text = _normalize_document_text(name, response.text)
                if not text.strip():
                    skipped.append(name)
                    continue
                remaining = max_chars - sum(len(part) for part in parts)
                if remaining <= 0:
                    break
                parts.append(f"--- Document: {name} ---\n{text[:remaining]}")

        readable_names = [document["name"] for document in selected]
        skipped.extend(
            document["name"]
            for document in documents
            if document["name"] not in readable_names and not _is_readable(document["name"])
        )
        return {
            "documents": documents,
            "readable_documents": readable_names,
            "skipped_documents": skipped,
            "text": "\n\n".join(parts),
        }

    async def fetch_13f_information_table(self, filing: Filing) -> str | None:
        documents = await self._list_documents(filing)
        candidates = [
            document["name"]
            for document in documents
            if document["name"].lower().endswith(".xml")
            and document["name"] != filing.primary_document
        ]
        if not candidates:
            return None

        async with httpx.AsyncClient(timeout=30.0, headers=self.headers) as client:
            for name in candidates:
                url = self._document_url(filing, name)
                response = await client.get(url)
                response.raise_for_status()
                text = response.text
                if "informationTable" in text and "infoTable" in text:
                    return text
        return None

    async def _list_documents(self, filing: Filing) -> list[dict[str, str]]:
        url = (
            "https://www.sec.gov/Archives/edgar/data/"
            f"{int(filing.cik)}/{filing.accession_no_dash}/index.json"
        )
        async with httpx.AsyncClient(timeout=30.0, headers=self.headers) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()

        items = payload.get("directory", {}).get("item", [])
        return [
            {
                "name": item.get("name", ""),
                "type": item.get("type", ""),
                "size": item.get("size", ""),
            }
            for item in items
            if item.get("name")
        ]

    def _select_readable_documents(
        self, filing: Filing, documents: list[dict[str, str]]
    ) -> list[dict[str, str]]:
        by_name = {document["name"]: document for document in documents}
        selected: list[dict[str, str]] = []
        primary = by_name.get(filing.primary_document)
        if primary and _is_readable(primary["name"]):
            selected.append(primary)

        for document in documents:
            name = document["name"]
            if name == filing.primary_document:
                continue
            if _is_readable(name):
                selected.append(document)
            if len(selected) >= 4:
                break
        return selected

    def _document_url(self, filing: Filing, name: str) -> str:
        return (
            "https://www.sec.gov/Archives/edgar/data/"
            f"{int(filing.cik)}/{filing.accession_no_dash}/{name}"
        )


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if text:
            self.parts.append(text)

    def text(self) -> str:
        return "\n".join(self.parts)


def _is_readable(name: str) -> bool:
    lowered = name.lower()
    return lowered.endswith((".html", ".htm", ".xml", ".txt"))


def _normalize_document_text(name: str, content: str) -> str:
    lowered = name.lower()
    if lowered.endswith((".html", ".htm")):
        parser = _TextExtractor()
        parser.feed(content)
        return parser.text()
    return content
