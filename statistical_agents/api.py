import json
import io
from email import policy
from email.parser import BytesParser
from pathlib import Path
from http.server import BaseHTTPRequestHandler
from typing import Any

from .analysis import run_analysis, suggest_theme_config
from .providers import create_provider
from .reporting import create_docx

ROOT = Path(__file__).parent.parent


def _json_default(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def sample_rows() -> list[dict[str, Any]]:
    return [
        {"şehir": "Ankara", "segment": "A", "yaş": 24, "puan": 78},
        {"şehir": "Ankara", "segment": "B", "yaş": 31, "puan": 64},
        {"şehir": "İzmir", "segment": "A", "yaş": 27, "puan": 82},
        {"şehir": "İzmir", "segment": "B", "yaş": 42, "puan": 55},
        {"şehir": "İstanbul", "segment": "A", "yaş": 35, "puan": 71},
        {"şehir": "İstanbul", "segment": "B", "yaş": 29, "puan": 68},
    ]


def validate(payload: Any) -> tuple[str, list[dict[str, Any]], list[str]]:
    if not isinstance(payload, dict):
        raise ValueError("Gövde bir JSON nesnesi olmalıdır.")
    question = payload.get("question")
    rows = payload.get("rows")
    columns = payload.get("columns")
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question zorunlu ve boş olmayan bir metin olmalıdır.")
    if not isinstance(rows, list) or not rows or not all(isinstance(row, dict) for row in rows):
        raise ValueError("rows, en az bir satır içeren nesne listesi olmalıdır.")
    if not isinstance(columns, list) or not columns or not all(isinstance(column, str) and column for column in columns):
        raise ValueError("columns, en az bir kolon adı içeren liste olmalıdır.")
    missing = [column for column in columns if any(column not in row for row in rows)]
    if missing:
        raise ValueError(f"Kolonlar bazı satırlarda eksik: {', '.join(missing)}")
    return question.strip(), rows, list(dict.fromkeys(columns))


def validate_pairs(payload: Any, columns: list[str]) -> list[tuple[str, str]]:
    raw_pairs = payload.get("relationship_pairs", [])
    if raw_pairs is None:
        return []
    if not isinstance(raw_pairs, list):
        raise ValueError("relationship_pairs liste olmalıdır.")
    pairs = []
    for pair in raw_pairs:
        if not isinstance(pair, list) or len(pair) != 2 or pair[0] not in columns or pair[1] not in columns or pair[0] == pair[1]:
            raise ValueError("Her ilişki çifti seçili iki farklı kolondan oluşmalıdır.")
        pairs.append((pair[0], pair[1]))
    return list(dict.fromkeys(pairs))


def validate_theme_config(payload: Any, available_columns: list[str]) -> list[dict[str, Any]] | None:
    raw = payload.get("theme_config")
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise ValueError("theme_config liste olmalıdır.")
    for entry in raw:
        if not isinstance(entry, dict) or entry.get("column") not in available_columns:
            raise ValueError("Her tema yapılandırması geçerli bir kolon içermelidir.")
        if not isinstance(entry.get("enabled", True), bool) or not isinstance(entry.get("themes", []), list):
            raise ValueError("Tema yapılandırması enabled ve themes alanlarını doğru taşımalıdır.")
        for theme in entry.get("themes", []):
            if not isinstance(theme, dict) or not isinstance(theme.get("name"), str) or not isinstance(theme.get("keywords", []), list):
                raise ValueError("Her tema name ve keywords alanlarını taşımalıdır.")
    return raw


def read_excel(file_bytes: bytes, filename: str, content_type: str = "") -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".xls":
        raise ValueError(".xls dosyaları doğrudan desteklenmiyor; dosyayı .xlsx olarak kaydedin.")
    if suffix != ".xlsx" or content_type not in ("", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"):
        raise ValueError("Yalnızca .xlsx Excel dosyaları kabul edilir.")
    try:
        from openpyxl import load_workbook
    except ImportError as error:
        raise ValueError("Excel desteği için openpyxl kurulmalı: pip install -r requirements.txt") from error
    try:
        workbook = load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
        sheet = workbook.active
        values = list(sheet.values)
    except Exception as error:
        raise ValueError(f"Excel dosyası okunamadı: {error}") from error
    if not values:
        raise ValueError("Excel çalışma sayfası boş.")
    headers = [str(value).strip() if value is not None else "" for value in values[0]]
    normalized_headers, mappings = normalize_headers(headers)
    rows = [dict(zip(normalized_headers, row)) for row in values[1:] if any(value is not None for value in row)]
    return rows, mappings


def normalize_headers(headers: list[str]) -> tuple[list[str], list[dict[str, str]]]:
    normalized: list[str] = []
    mappings: list[dict[str, str]] = []
    used: dict[str, int] = {}
    for index, original in enumerate(headers, 1):
        base = original or f"Column {index}"
        count = used.get(base, 0) + 1
        used[base] = count
        name = base if count == 1 else f"{base} ({count})"
        normalized.append(name)
        mappings.append({"original": original or f"(boş başlık {index})", "normalized": name})
    return normalized, mappings


class ApplicationHandler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: Any, content_type: str = "application/json",
              extra_headers: dict[str, str] | None = None) -> None:
        encoded = body if isinstance(body, bytes) else json.dumps(
            body, ensure_ascii=False, default=_json_default
        ).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:
        if self.path == "/api/sample":
            rows = sample_rows()
            columns = list(rows[0])
            self._send(200, {"rows": rows, "columns": columns, "headers": columns,
                             "theme_config": suggest_theme_config(rows, columns)})
            return
        if self.path in ("/", "/index.html"):
            self._send(200, (ROOT / "web" / "index.html").read_bytes(), "text/html")
            return
        self._send(404, {"error": {"code": "not_found", "message": "Kaynak bulunamadı."}})

    def do_POST(self) -> None:
        if self.path not in ("/api/upload", "/api/analyze", "/api/report"):
            self._send(404, {"error": {"code": "not_found", "message": "Kaynak bulunamadı."}})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = self._read_payload(length)
            if self.path == "/api/upload":
                _, rows, _ = validate({"question": "upload", "rows": payload["rows"],
                                       "columns": list(payload["rows"][0]) if payload["rows"] else ["value"]})
                current_columns = list(rows[0]) if rows else []
                self._send(200, {"rows": rows, "columns": current_columns, "headers": current_columns,
                                 "header_mappings": payload.get("header_mappings", []),
                                 "theme_config": suggest_theme_config(rows, current_columns)})
                return
            question, rows, columns = validate(payload)
            pairs = validate_pairs(payload, columns)
            raw_theme_config = validate_theme_config(payload, list(rows[0]))
            response = run_analysis(question, rows, columns, create_provider(), pairs,
                                    payload.get("header_mappings"), raw_theme_config)
            if self.path == "/api/report":
                self._send(200, create_docx(response), "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                           {"Content-Disposition": 'attachment; filename="istatistik-raporu.docx"'})
                return
            self._send(200, response.as_dict())
        except (ValueError, json.JSONDecodeError) as error:
            self._send(400, {"error": {"code": "invalid_request", "message": str(error)}})
        except Exception:
            self._send(500, {"error": {"code": "internal_error", "message": "Analiz sırasında beklenmeyen hata oluştu."}})

    def _read_payload(self, length: int) -> dict[str, Any]:
        content_type = self.headers.get("Content-Type", "")
        if content_type.startswith("multipart/form-data"):
            raw = self.rfile.read(length)
            message = BytesParser(policy=policy.default).parsebytes(
                f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode() + raw
            )
            fields: dict[str, str] = {}
            upload_bytes: bytes | None = None
            upload_name = ""
            upload_type = ""
            for part in message.walk():
                if part.is_multipart():
                    continue
                name = part.get_param("name", header="content-disposition")
                filename = part.get_filename()
                if name == "file" and filename:
                    upload_bytes, upload_name, upload_type = part.get_payload(decode=True), filename, part.get_content_type()
                elif name:
                    fields[name] = (part.get_payload(decode=True) or b"").decode("utf-8")
            if upload_bytes is None or not upload_name:
                raise ValueError("multipart isteğinde file alanı zorunludur.")
            rows, mappings = read_excel(upload_bytes, upload_name, upload_type)
            columns = json.loads(fields.get("columns", "[]"))
            pairs = json.loads(fields.get("relationship_pairs", "[]"))
            return {"question": fields.get("question", "Excel analizi"),
                    "rows": rows, "columns": columns, "relationship_pairs": pairs,
                    "header_mappings": mappings}
        raw = self.rfile.read(length)
        return json.loads(raw)

    def log_message(self, format: str, *args: Any) -> None:
        return
