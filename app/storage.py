from __future__ import annotations

import sqlite3
from pathlib import Path

from app.models import Filing


SCHEMA = """
CREATE TABLE IF NOT EXISTS filings (
    accession_number TEXT PRIMARY KEY,
    cik TEXT NOT NULL,
    entity_name TEXT NOT NULL,
    form TEXT NOT NULL,
    filing_date TEXT NOT NULL,
    report_date TEXT,
    accepted_at TEXT,
    primary_document TEXT NOT NULL,
    sec_url TEXT NOT NULL,
    confidence TEXT NOT NULL,
    inserted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class FilingStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.init()

    def init(self) -> None:
        with self._connect() as connection:
            connection.execute(SCHEMA)

    def insert_new(self, filings: list[Filing]) -> list[Filing]:
        inserted: list[Filing] = []
        with self._connect() as connection:
            for filing in filings:
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO filings (
                        accession_number,
                        cik,
                        entity_name,
                        form,
                        filing_date,
                        report_date,
                        accepted_at,
                        primary_document,
                        sec_url,
                        confidence
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        filing.accession_number,
                        filing.cik,
                        filing.entity_name,
                        filing.form,
                        filing.filing_date,
                        filing.report_date,
                        filing.accepted_at,
                        filing.primary_document,
                        filing.sec_url,
                        filing.confidence,
                    ),
                )
                if cursor.rowcount:
                    inserted.append(filing)
        return inserted

    def list_filings(self, limit: int = 100) -> list[dict[str, str | None]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    accession_number,
                    cik,
                    entity_name,
                    form,
                    filing_date,
                    report_date,
                    accepted_at,
                    primary_document,
                    sec_url,
                    confidence,
                    inserted_at
                FROM filings
                ORDER BY COALESCE(accepted_at, filing_date) DESC, inserted_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection
