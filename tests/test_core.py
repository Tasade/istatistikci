import unittest

from statistical_agents.analysis import run_analysis
from statistical_agents.api import validate
from statistical_agents.providers import MockProvider


class CoreFlowTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {"group": "A", "x": 1, "y": 2},
            {"group": "A", "x": 2, "y": 4},
            {"group": "B", "x": 3, "y": 6},
        ]

    def test_all_three_roles_return_typed_results(self):
        response = run_analysis("İlişki nedir?", self.rows, ["group", "x", "y"], MockProvider(), [("x", "y")])
        self.assertEqual([item.role for item in response.results], ["statistician", "relationship_analyst", "reporting_expert"])
        self.assertEqual(response.results[1].metrics["comparisons"][0]["pearson"], 1.0)
        self.assertIn("relationship_analyst", response.results[2].metrics["source_roles"])
        question = response.results[0].metrics["questions"][0]
        self.assertEqual(question["total_responses"], 3)
        self.assertEqual(question["most_frequent"], {"value": "A", "count": 2})

    def test_cleaning_normalizes_empty_numeric_and_duplicates(self):
        response = run_analysis("Temizlik", [{" yaş ": " 24 ", "grup": " A "},
                                             {" yaş ": " 24 ", "grup": " A "},
                                             {" yaş ": "", "grup": "B"}], ["yaş", "grup"], MockProvider())
        self.assertEqual(response.cleaning.removed_duplicates, 1)
        self.assertEqual(response.cleaning.empty_values_normalized, 1)
        self.assertEqual(response.cleaning.numeric_values_converted, 2)

    def test_age_categories_keep_domain_order_and_percentages(self):
        counts = {"18 yaş altı": 21, "18-24": 56, "25-34": 58, "35-44": 59,
                  "45-54": 99, "55-64": 62, "65+": 42}
        rows = [{"3- Yaş Aralığı": value, "row_id": index}
                for index, (value, count) in enumerate((entry for entry in counts.items() for _ in range(entry[1])))]
        response = run_analysis("Yaş dağılımı", rows, ["3- Yaş Aralığı"], MockProvider())
        question = response.results[0].metrics["questions"][0]
        self.assertEqual(question["total_responses"], 397)
        self.assertEqual([item["value"] for item in question["distribution"]], list(counts))
        self.assertEqual(question["distribution"][0]["count"], 21)
        self.assertEqual(question["distribution"][0]["percentage"], 5.29)

    def test_blank_and_timestamp_columns_are_explicit(self):
        rows = [{"Zaman damgası": "2026-01-01", "TC Kimlik Numarası": None},
                {"Zaman damgası": "2026-01-02", "TC Kimlik Numarası": None}]
        response = run_analysis("Kişisel alanlar", rows, list(rows[0]), MockProvider())
        questions = response.results[0].metrics["questions"]
        self.assertTrue(questions[0]["excluded_from_frequency"])
        self.assertEqual(questions[1]["distribution"], [{"value": "Yanıt yok", "count": 2, "percentage": 100.0}])

    def test_reporting_agent_has_tables_then_comments(self):
        rows = [{"şehir": "Ankara", "katılım": "İlk kez"},
                {"şehir": "Ankara", "katılım": "Tekrar"},
                {"şehir": "İzmir", "katılım": "İlk kez"}]
        response = run_analysis("Şehre göre katılım", rows, ["şehir", "katılım"], MockProvider(),
                                [("şehir", "katılım")])
        report = response.results[2]
        self.assertEqual(report.role, "reporting_expert")
        self.assertEqual(len(report.metrics["sections"]), 2)
        self.assertIn("yorum", report.summary.lower())
        self.assertEqual(report.metrics["cross_analysis_count"], 1)

    def test_validation_rejects_missing_columns(self):
        with self.assertRaises(ValueError):
            validate({"question": "x", "rows": [{"a": 1}], "columns": ["missing"]})

    def test_theme_override_supports_multi_match_other_and_no_answer(self):
        rows = [{"yorum": "Ulaşım çok iyi, servis başarılı"},
                {"yorum": "Kötü ulaşım ve yetersiz yönlendirme"},
                {"yorum": None},
                {"yorum": "Sıradan bir yanıt"}]
        config = [{"column": "yorum", "enabled": True, "themes": [
            {"name": "Ulaşım", "keywords": ["ulaşım"]},
            {"name": "Olumlu", "keywords": ["iyi", "başarılı"]},
            {"name": "Olumsuz", "keywords": ["kötü", "yetersiz"]},
        ]}]
        response = run_analysis("Tema", rows, ["yorum"], MockProvider(), theme_config=config)
        result = response.results[0].metrics["theme_analysis"][0]
        counts = {item["theme"]: item["count"] for item in result["distribution"]}
        self.assertEqual(counts["Ulaşım"], 2)
        self.assertEqual(counts["Olumlu"], 1)
        self.assertEqual(counts["Olumsuz"], 1)
        self.assertEqual(counts["Yanıt yok"], 1)
        self.assertEqual(counts["Diğer"], 1)
        self.assertTrue(all(item["examples"] for item in result["distribution"] if item["theme"] != "Diğer"))
