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

CREATE TABLE IF NOT EXISTS filing_analyses (
    accession_number TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    summary TEXT,
    importance TEXT,
    key_points_json TEXT,
    parsed_facts_json TEXT,
    model TEXT,
    error TEXT,
    analyzed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(accession_number) REFERENCES filings(accession_number)
);

CREATE TABLE IF NOT EXISTS holdings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    accession_number TEXT NOT NULL,
    name_of_issuer TEXT NOT NULL,
    title_of_class TEXT NOT NULL,
    cusip TEXT NOT NULL,
    value INTEGER NOT NULL,
    shares_or_principal INTEGER NOT NULL,
    share_type TEXT NOT NULL,
    put_call TEXT,
    FOREIGN KEY(accession_number) REFERENCES filings(accession_number)
);

CREATE INDEX IF NOT EXISTS idx_holdings_accession ON holdings(accession_number);
CREATE INDEX IF NOT EXISTS idx_holdings_cusip ON holdings(cusip);
"""


class FilingStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.init()

    def init(self) -> None:
        with self._connect() as connection:
            connection.executescript(SCHEMA)

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
                    f.accession_number,
                    f.cik,
                    f.entity_name,
                    f.form,
                    f.filing_date,
                    f.report_date,
                    f.accepted_at,
                    f.primary_document,
                    f.sec_url,
                    f.confidence,
                    f.inserted_at,
                    a.status AS analysis_status,
                    a.summary AS analysis_summary,
                    a.importance AS analysis_importance,
                    a.key_points_json AS analysis_key_points_json,
                    a.parsed_facts_json AS analysis_parsed_facts_json,
                    a.model AS analysis_model,
                    a.error AS analysis_error,
                    a.analyzed_at AS analyzed_at,
                    COUNT(h.id) AS holdings_count,
                    COALESCE(SUM(h.value), 0) AS holdings_total_value
                FROM filings f
                LEFT JOIN filing_analyses a ON a.accession_number = f.accession_number
                LEFT JOIN holdings h ON h.accession_number = f.accession_number
                GROUP BY f.accession_number
                ORDER BY COALESCE(f.accepted_at, f.filing_date) DESC, f.inserted_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def insert_holdings(self, accession_number: str, holdings: list[object]) -> int:
        with self._connect() as connection:
            connection.execute("DELETE FROM holdings WHERE accession_number = ?", (accession_number,))
            connection.executemany(
                """
                INSERT INTO holdings (
                    accession_number,
                    name_of_issuer,
                    title_of_class,
                    cusip,
                    value,
                    shares_or_principal,
                    share_type,
                    put_call
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        accession_number,
                        holding.name_of_issuer,
                        holding.title_of_class,
                        holding.cusip,
                        holding.value,
                        holding.shares_or_principal,
                        holding.share_type,
                        holding.put_call,
                    )
                    for holding in holdings
                ],
            )
        return len(holdings)

    def holdings_count(self, accession_number: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM holdings WHERE accession_number = ?",
                (accession_number,),
            ).fetchone()
        return int(row["count"])

    def list_holdings(self, accession_number: str) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    name_of_issuer,
                    title_of_class,
                    cusip,
                    value,
                    shares_or_principal,
                    share_type,
                    put_call
                FROM holdings
                WHERE accession_number = ?
                ORDER BY value DESC
                """,
                (accession_number,),
            ).fetchall()
        return [dict(row) for row in rows]

    def previous_filing_accession(self, accession_number: str) -> str | None:
        filing = self.get_filing(accession_number)
        if filing is None:
            return None
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT accession_number
                FROM filings
                WHERE form LIKE '13F%%'
                  AND accession_number != ?
                  AND COALESCE(report_date, filing_date) < COALESCE(?, ?)
                ORDER BY COALESCE(report_date, filing_date) DESC
                LIMIT 1
                """,
                (accession_number, filing.report_date, filing.filing_date),
            ).fetchone()
        if row is None:
            return None
        return str(row["accession_number"])

    def get_filing(self, accession_number: str) -> Filing | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    accession_number,
                    cik,
                    entity_name,
                    form,
                    filing_date,
                    report_date,
                    accepted_at,
                    primary_document
                FROM filings
                WHERE accession_number = ?
                """,
                (accession_number,),
            ).fetchone()
        if row is None:
            return None
        return Filing(
            cik=row["cik"],
            entity_name=row["entity_name"],
            accession_number=row["accession_number"],
            form=row["form"],
            filing_date=row["filing_date"],
            report_date=row["report_date"],
            accepted_at=row["accepted_at"],
            primary_document=row["primary_document"],
        )

    def get_analysis(self, accession_number: str) -> dict[str, str | None] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    accession_number,
                    status,
                    summary,
                    importance,
                    key_points_json,
                    parsed_facts_json,
                    model,
                    error,
                    analyzed_at
                FROM filing_analyses
                WHERE accession_number = ?
                """,
                (accession_number,),
            ).fetchone()
        if row is None:
            return None
        return dict(row)

    def save_analysis(self, accession_number: str, analysis: dict[str, object]) -> None:
        import json

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO filing_analyses (
                    accession_number,
                    status,
                    summary,
                    importance,
                    key_points_json,
                    parsed_facts_json,
                    model,
                    error,
                    analyzed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(accession_number) DO UPDATE SET
                    status = excluded.status,
                    summary = excluded.summary,
                    importance = excluded.importance,
                    key_points_json = excluded.key_points_json,
                    parsed_facts_json = excluded.parsed_facts_json,
                    model = excluded.model,
                    error = excluded.error,
                    analyzed_at = CURRENT_TIMESTAMP
                """,
                (
                    accession_number,
                    str(analysis.get("status") or "unknown"),
                    _optional_string(analysis.get("summary")),
                    _optional_string(analysis.get("importance")),
                    json.dumps(analysis.get("key_points") or [], ensure_ascii=False),
                    json.dumps(analysis.get("parsed_facts") or {}, ensure_ascii=False),
                    _optional_string(analysis.get("model")),
                    _optional_string(analysis.get("error")),
                ),
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
