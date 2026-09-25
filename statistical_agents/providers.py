from typing import Protocol

from .models import AgentResult


class AnalysisProvider(Protocol):
    def summarize(self, question: str, sources: list[AgentResult]) -> AgentResult:
        """Produce the systems-expert result from trusted source analyses."""


class MockProvider:
    """No-key provider; keeps the MVP useful and deterministic."""

    def summarize(self, question: str, sources: list[AgentResult]) -> AgentResult:
        statistician = next((source for source in sources if source.role == "statistician"), None)
        relationship = next((source for source in sources if source.role == "relationship_analyst"), None)
        sections = []
        findings = []
        for item in (statistician.metrics.get("questions", []) if statistician else []):
            if item.get("excluded_from_frequency"):
                continue
            top = item.get("most_frequent")
            sections.append({
                "column": item["column"],
                "table": item.get("distribution", []),
                "comment": f"{top['value']} değeri {top['count']} tekrar ile en sık gözlenen değerdir."
                if top else "Yanıt bulunamadı.",
            })
            findings.append(f"{item['column']}: tablo hazırlandı; {sections[-1]['comment']}")
        for comparison in (relationship.metrics.get("comparisons", []) if relationship else []):
            findings.append(f"{comparison.get('left')} × {comparison.get('right')} çapraz değerlendirmesi rapora eklendi.")
        theme_analysis = statistician.metrics.get("theme_analysis", []) if statistician else []
        for theme_result in theme_analysis:
            findings.append(f"{theme_result['column']}: tema dağılımı ve örnek yanıtlar rapora eklendi.")
        if not findings:
            findings = ["Seçilen başlıklarda raporlanabilir yanıt bulunamadı."]
        return AgentResult(
            role="reporting_expert",
            title="Agent 3 — Raporlama ve Yorum Uzmanı",
            summary=f'"{question}" için Agent 1 tabloları ve Agent 2 çaprazlamaları başlık başlık birleştirildi. '
            "Her bölüm önce tabloyu, ardından kısa ve nedensellik iddiası taşımayan yorumu içerir.",
            findings=findings,
            metrics={"source_roles": [source.role for source in sources], "sections": sections,
                     "theme_sections": theme_analysis,
                     "cross_analysis_count": len(relationship.metrics.get("comparisons", []) if relationship else [])},
        )


def create_provider() -> AnalysisProvider:
    # A real provider can be selected here without changing orchestration.
    return MockProvider()
