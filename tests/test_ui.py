from pathlib import Path
import unittest


UI = Path(__file__).parent.parent / "web" / "index.html"


class UiFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = UI.read_text(encoding="utf-8")

    def test_initial_ui_has_no_context_or_default_header_render(self):
        self.assertNotIn('id="question"', self.source)
        self.assertNotIn("Soru / analiz bağlamı", self.source)
        self.assertNotIn("$('sample').click();", self.source)
        self.assertIn("let rows=[],columns=[],headerMappings=[],themeConfig=[],lastPayload=null", self.source)

    def test_sample_click_rebuilds_current_header_list(self):
        self.assertIn("$('sample').onclick=async()=>", self.source)
        self.assertIn("headerMappings=(d.rows.length?Object.keys(d.rows[0]):[])", self.source)
        self.assertIn("setRows(d.rows);$('message').textContent='Örnek veri yüklendi.'", self.source)
        self.assertIn("function clearData()", self.source)

    def test_upload_and_analysis_use_current_normalized_headers(self):
        self.assertIn("columns=d.headers||d.columns||[]", self.source)
        self.assertIn("data-i", self.source)
        self.assertIn("querySelectorAll('.column:checked')", self.source)

    def test_upload_clears_then_shows_loading_and_error_states(self):
        self.assertIn("clearForLoading('Excel yükleniyor...')", self.source)
        self.assertIn("Excel yüklenemedi.", self.source)
        self.assertIn("clearForLoading('Örnek veri yükleniyor...')", self.source)
        self.assertIn("Örnek veri yüklenemedi.", self.source)

    def test_theme_editor_resets_and_is_sent_with_analysis(self):
        self.assertIn("themeConfig=[]", self.source)
        self.assertIn("themeConfig=d.theme_config||[]", self.source)
        self.assertIn("function renderThemes()", self.source)
        self.assertIn("theme_config:themeConfig", self.source)
        self.assertIn("theme-add", self.source)
