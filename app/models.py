from dataclasses import dataclass


TRACKED_FORMS = {
    "13F-HR",
    "13F-HR/A",
    "SC 13D",
    "SC 13D/A",
    "SC 13G",
    "SC 13G/A",
    "4",
    "4/A",
}


@dataclass(frozen=True)
class Filing:
    cik: str
    entity_name: str
    accession_number: str
    form: str
    filing_date: str
    report_date: str | None
    accepted_at: str | None
    primary_document: str

    @property
    def accession_no_dash(self) -> str:
        return self.accession_number.replace("-", "")

    @property
    def sec_url(self) -> str:
        cik_no_zero = str(int(self.cik))
        return (
            "https://www.sec.gov/Archives/edgar/data/"
            f"{cik_no_zero}/{self.accession_no_dash}/{self.primary_document}"
        )

    @property
    def confidence(self) -> str:
        return "High"
