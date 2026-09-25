from datetime import datetime
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape

from .models import AnalysisResponse


def _paragraph(text: str, bold: bool = False) -> str:
    run = f'<w:r><w:rPr><w:b/></w:rPr><w:t>{escape(text)}</w:t></w:r>' if bold else f'<w:r><w:t>{escape(text)}</w:t></w:r>'
    return f"<w:p>{run}</w:p>"


def create_docx(response: AnalysisResponse) -> bytes:
    paragraphs = [_paragraph("İstatistik Agent Sistemi — Analiz Raporu", True),
                  _paragraph(f"Oluşturulma: {datetime.now().isoformat(timespec='seconds')}"),
                  _paragraph(f"Soru: {response.question}", True),
                  _paragraph("1. Veri temizleme", True)]
    for key, value in response.cleaning.as_dict().items():
        if key != "notes":
            paragraphs.append(_paragraph(f"{key}: {value}"))
    for note in response.cleaning.notes:
        paragraphs.append(_paragraph(f"Not: {note}"))
    for result in response.results:
        paragraphs.append(_paragraph(result.title, True))
        paragraphs.append(_paragraph(result.summary))
        for finding in result.findings:
            paragraphs.append(_paragraph(f"• {finding}"))
        for key, value in result.metrics.items():
            paragraphs.append(_paragraph(f"{key}: {value}"))
        if result.role == "statistician":
            for theme_result in result.metrics.get("theme_analysis", []):
                paragraphs.append(_paragraph(f"Tema analizi — {theme_result['column']}", True))
                for item in theme_result.get("distribution", []):
                    paragraphs.append(_paragraph(
                        f"{item['theme']}: {item['count']} ({item['percentage']}%); "
                        f"örnekler: {' | '.join(item.get('examples', []))}"
                    ))
                paragraphs.append(_paragraph(f"Diğer / sınıflandırılamayan: {theme_result.get('unclassified', 0)}"))
    body = "".join(paragraphs)
    document = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{body}<w:sectPr/></w:body></w:document>'
    content_types = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'
    rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document)
    return output.getvalue()
