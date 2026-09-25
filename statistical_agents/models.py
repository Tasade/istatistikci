from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class CleaningReport:
    original_rows: int
    cleaned_rows: int
    removed_duplicates: int
    empty_values_normalized: int
    numeric_values_converted: int
    invalid_types_flagged: int
    header_mappings: list[dict[str, str]]
    notes: list[str]

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class AgentResult:
    role: Literal["statistician", "relationship_analyst", "reporting_expert", "systems_expert"]
    title: str
    summary: str
    findings: list[str]
    metrics: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"role": self.role, "title": self.title, "summary": self.summary,
                "findings": self.findings, "metrics": self.metrics}


@dataclass(frozen=True)
class AnalysisResponse:
    question: str
    columns: list[str]
    row_count: int
    cleaning: CleaningReport
    results: list[AgentResult]

    def as_dict(self) -> dict[str, Any]:
        return {"question": self.question, "columns": self.columns, "row_count": self.row_count,
                "cleaning": self.cleaning.as_dict(), "results": [result.as_dict() for result in self.results]}
