from collections import Counter, defaultdict
from math import sqrt
from statistics import mean
from typing import Any

from .models import AgentResult, AnalysisResponse, CleaningReport
from .providers import AnalysisProvider

AGE_LABELS = ["18 yaş altı", "18-24", "25-34", "35-44", "45-54", "55-64", "65+"]
PERSONAL_HINTS = ("tc", "kimlik", "ad soyad", "iletişim", "telefon", "doğum", "email", "e-posta")
THEME_HINTS = (
    ("Olumlu", ("iyi", "memnun", "olumlu", "harika", "başarılı", "yüksek")),
    ("Olumsuz", ("kötü", "memnun değil", "olumsuz", "şikayet", "yetersiz", "düşük")),
    ("Ulaşım", ("ulaşım", "servis", "otobüs", "araç", "otopark")),
)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(str(value).replace(",", ".").strip())
        return int(number) if number.is_integer() else number
    except (TypeError, ValueError):
        return None


def clean_rows(rows: list[dict[str, Any]], header_mappings: list[dict[str, str]] | None = None) -> tuple[list[dict[str, Any]], CleaningReport]:
    cleaned: list[dict[str, Any]] = []
    empty_values = numeric_conversions = invalid_types = duplicate_rows = 0
    for original in rows:
        normalized: dict[str, Any] = {}
        for raw_key, raw_value in original.items():
            key = str(raw_key).strip()
            value = raw_value.strip() if isinstance(raw_value, str) else raw_value
            if value == "" or value is None:
                value = None
                empty_values += 1
            elif isinstance(value, str):
                number = _number(value)
                if number is not None:
                    value = number
                    numeric_conversions += 1
                elif any(char.isdigit() for char in value) and value.replace(".", "").replace(",", "").strip().isdigit():
                    invalid_types += 1
            normalized[key] = value
        fingerprint = tuple(sorted((key, repr(value)) for key, value in normalized.items()))
        if any(tuple(sorted((key, repr(value)) for key, value in row.items())) == fingerprint for row in cleaned):
            duplicate_rows += 1
            continue
        cleaned.append(normalized)
    report = CleaningReport(
        original_rows=len(rows),
        cleaned_rows=len(cleaned),
        removed_duplicates=duplicate_rows,
        empty_values_normalized=empty_values,
        numeric_values_converted=numeric_conversions,
        invalid_types_flagged=invalid_types,
        header_mappings=header_mappings or [{"original": column, "normalized": column}
                                           for column in (list(rows[0]) if rows else [])],
        notes=["Kolon adları ve metin değerleri trim edildi.", "Boş metinler null olarak işaretlendi.",
               "İlk Excel satırı başlık kabul edildi; başlık satırı veri olarak analiz edilmedi.",
               "Nedensellik çıkarımı yapılmadı; yalnızca güvenli betimsel ölçümler üretildi."],
    )
    return cleaned, report


def _display(value: Any) -> str:
    return "Yanıt yok" if value is None else str(value)


def _is_numeric(rows: list[dict[str, Any]], column: str) -> bool:
    values = [row.get(column) for row in rows if row.get(column) is not None]
    return bool(values) and all(_number(value) is not None for value in values)


def _age_bucket(value: Any) -> str:
    age = _number(value)
    if age is None:
        return "(geçersiz)"
    if age < 18:
        return "18 yaş altı"
    if age <= 24:
        return "18-24"
    if age <= 34:
        return "25-34"
    if age <= 44:
        return "35-44"
    if age <= 54:
        return "45-54"
    if age <= 64:
        return "55-64"
    return "65+"


def _age_label(value: Any) -> str | None:
    text = _display(value).strip().lower()
    aliases = {
        "18 yaş altı": "18 yaş altı", "18 alti": "18 yaş altı", "0-17": "18 yaş altı",
        "18-24": "18-24", "25-34": "25-34", "35-44": "35-44",
        "45-54": "45-54", "55-64": "55-64", "65+": "65+",
    }
    return aliases.get(text)


def _is_age_column(column: str) -> bool:
    lowered = column.lower()
    return "yaş" in lowered or "yas" in lowered or "age" in lowered


def _is_metadata_column(column: str) -> bool:
    lowered = column.lower()
    return "zaman damgası" in lowered or "timestamp" in lowered or "time stamp" in lowered


def _is_personal_column(column: str) -> bool:
    lowered = column.lower()
    return any(hint in lowered for hint in PERSONAL_HINTS)


def suggest_theme_config(rows: list[dict[str, Any]], columns: list[str]) -> list[dict[str, Any]]:
    config = []
    for column in columns:
        if _is_metadata_column(column) or _is_personal_column(column) or _is_age_column(column):
            continue
        values = [str(row.get(column)).strip() for row in rows if row.get(column) not in (None, "")]
        if not values or all(_number(value) is not None for value in values):
            continue
        long_text = max((len(value) for value in values), default=0) >= 24
        if long_text or len(set(values)) <= max(30, len(rows) // 2):
            themes = [{"name": name, "keywords": list(keywords)} for name, keywords in THEME_HINTS
                      if any(any(keyword in value.lower() for keyword in keywords) for value in values)]
            config.append({"column": column, "enabled": bool(themes), "themes": themes})
    return config


def classify_themes(rows: list[dict[str, Any]], theme_config: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    results = []
    for entry in theme_config or []:
        column = entry.get("column")
        if not isinstance(column, str) or not entry.get("enabled", True):
            continue
        themes = entry.get("themes", [])
        if not isinstance(themes, list):
            continue
        counts = Counter()
        examples: dict[str, list[str]] = defaultdict(list)
        for row in rows:
            value = row.get(column)
            if value is None or str(value).strip() == "":
                labels = ["Yanıt yok"]
            else:
                text = str(value).strip()
                labels = [str(theme.get("name", "")).strip() for theme in themes
                          if str(theme.get("name", "")).strip() and any(
                              str(keyword).strip().lower() in text.lower()
                              for keyword in theme.get("keywords", []) if str(keyword).strip())]
                if not labels:
                    labels = ["Diğer"]
            for label in labels:
                counts[label] += 1
                if len(examples[label]) < 3:
                    examples[label].append(str(value) if value is not None else "")
        total = len(rows) or 1
        distribution = [{"theme": label, "count": count, "percentage": round(count / total * 100, 2),
                         "examples": examples[label]} for label, count in counts.items()]
        results.append({"column": column, "multi_match": True, "distribution": distribution,
                        "unclassified": counts.get("Diğer", 0)})
    return results


def _numeric_bucket(value: Any, values: list[float]) -> str:
    number = _number(value)
    if number is None or not values:
        return "(geçersiz)"
    low, high = min(values), max(values)
    if low == high:
        return str(low)
    width = (high - low) / 3
    index = min(2, int((number - low) / width))
    starts = [low, low + width, low + width * 2]
    ends = [low + width, low + width * 2, high]
    return f"{starts[index]:g}-{ends[index]:g}"


def statistician(question: str, rows: list[dict[str, Any]], columns: list[str]) -> AgentResult:
    questions: list[dict[str, Any]] = []
    findings: list[str] = []
    for column in columns:
        is_metadata = _is_metadata_column(column)
        is_age = _is_age_column(column)
        values = [_display(row.get(column)) for row in rows]
        counts = Counter(values)
        if is_metadata:
            ordered = []
            distribution = []
        elif is_age and any(_age_label(row.get(column)) for row in rows):
            age_counts = Counter(_age_label(row.get(column)) or "Yanıt yok" for row in rows)
            ordered = [(label, age_counts.get(label, 0)) for label in AGE_LABELS]
            if age_counts.get("Yanıt yok"):
                ordered.append(("Yanıt yok", age_counts["Yanıt yok"]))
            distribution = [{"value": value, "count": count,
                             "percentage": round(count / len(rows) * 100, 2)}
                            for value, count in ordered if count]
        else:
            ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
            distribution = [{"value": value, "count": count,
                             "percentage": round(count / len(rows) * 100, 2)}
                            for value, count in ordered]
        ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        item = {
            "question": question,
            "column": column,
            "total_responses": len(rows),
            "answered_responses": len([value for value in values if value != "Yanıt yok"]),
            "unique_values": len(counts),
            "most_frequent": {"value": ranked[0][0], "count": ranked[0][1]} if ranked else None,
            "least_frequent": {"value": ranked[-1][0], "count": ranked[-1][1]} if ranked else None,
            "distribution": distribution,
            "type": "metadata" if is_metadata else ("age_range" if is_age and distribution else
                    ("numeric" if _is_numeric(rows, column) else "categorical")),
            "excluded_from_frequency": is_metadata,
        }
        questions.append(item)
        findings.append(f"{column}: {item['total_responses']} yanıt, {item['unique_values']} benzersiz değer.")
    return AgentResult("statistician", "Agent 1 — Excel Okuyucu ve İstatistikçi",
                       "Excel başlık satırı şema olarak okundu; her sütunun altındaki tüm veri değerleri topluca analiz edildi.",
                       findings, {"header_row": 1, "row_count": len(rows), "columns": columns,
                                  "questions": questions})


def relationship_analyst(rows: list[dict[str, Any]], pairs: list[tuple[str, str]]) -> AgentResult:
    comparisons: list[dict[str, Any]] = []
    findings: list[str] = []
    for left, right in pairs:
        left_numeric, right_numeric = _is_numeric(rows, left), _is_numeric(rows, right)
        if left_numeric and right_numeric:
            values = [(float(_number(row.get(left))), float(_number(row.get(right)))) for row in rows
                      if _number(row.get(left)) is not None and _number(row.get(right)) is not None]
            correlation = _pearson([x for x, _ in values], [y for _, y in values])
            comparisons.append({"left": left, "right": right, "kind": "numeric_numeric", "pearson": correlation,
                                "pairs": len(values)})
            findings.append(f"{left}–{right}: Pearson korelasyonu {correlation}.")
            continue
        if not left_numeric and not right_numeric:
            table: dict[str, Counter[str]] = defaultdict(Counter)
            for row in rows:
                table[_display(row.get(left))][_display(row.get(right))] += 1
            keys = list(table)
            if _is_age_column(left):
                keys = [key for key in AGE_LABELS if key in table] + [key for key in keys if key not in AGE_LABELS]
            serializable = {key: dict(table[key]) for key in keys}
            comparisons.append({"left": left, "right": right, "kind": "categorical_categorical", "table": serializable})
            findings.append(f"{left}–{right}: kategorik contingency tablosu üretildi.")
            continue
        numeric, categorical = (left, right) if left_numeric else (right, left)
        numeric_values = [float(_number(row.get(numeric))) for row in rows if _number(row.get(numeric)) is not None]
        is_age = "yaş" in numeric.lower() or "yas" in numeric.lower() or "age" in numeric.lower()
        table: dict[str, Counter[str]] = defaultdict(Counter)
        for row in rows:
            value = row.get(numeric)
            bucket = _age_bucket(value) if is_age else _numeric_bucket(value, numeric_values)
            table[bucket][_display(row.get(categorical))] += 1
        serializable = {bucket: dict(counter) for bucket, counter in table.items()}
        comparisons.append({"left": left, "right": right, "kind": "numeric_categorical",
                            "numeric_column": numeric, "categorical_column": categorical,
                            "numeric_bucketing": "age_ranges" if is_age else "three_equal_ranges", "table": serializable})
        findings.append(f"{numeric} aralıkları ile {categorical} kategorileri çaprazlandı.")
    if not pairs:
        findings.append("İlişki analizi için en az bir kolon çifti seçilmedi.")
    return AgentResult("relationship_analyst", "Agent 2 — Çapraz İlişki Analisti",
                       "Seçilen kolon çiftleri güvenli çapraz tablolar ve temel korelasyonla karşılaştırıldı.",
                       findings, {"comparisons": comparisons})


def _pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) < 2:
        return None
    left_mean, right_mean = mean(left), mean(right)
    denominator = sqrt(sum((x - left_mean) ** 2 for x in left) * sum((y - right_mean) ** 2 for y in right))
    return round(sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right)) / denominator, 4) if denominator else None


def run_analysis(question: str, rows: list[dict[str, Any]], columns: list[str], provider: AnalysisProvider,
                 relationship_pairs: list[tuple[str, str]] | None = None,
                 header_mappings: list[dict[str, str]] | None = None,
                 theme_config: list[dict[str, Any]] | None = None) -> AnalysisResponse:
    cleaned, cleaning = clean_rows(rows, header_mappings)
    pairs = relationship_pairs if relationship_pairs is not None else [(columns[i], columns[j])
             for i in range(len(columns)) for j in range(i + 1, len(columns))]
    first, second = statistician(question, cleaned, columns), relationship_analyst(cleaned, pairs)
    first.metrics["theme_analysis"] = classify_themes(cleaned, theme_config)
    sources = [first, second]
    return AnalysisResponse(question, columns, len(cleaned), cleaning, sources + [provider.summarize(question, sources)])
