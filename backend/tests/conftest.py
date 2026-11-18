"""Shared test setup.

Safety rules enforced here, BEFORE any app module is imported:
  * DATABASE_PATH points at a throwaway temp file, and every test then gets its own fresh
    database under pytest's tmp_path. the real learn_it.db is never opened.
  * load_dotenv is replaced with a no-op, so the real .env file is never read.
  * GEMINI_API_KEY is empty and google.genai.Client is replaced with a guard that fails the
    test if anything tries to build a real Gemini client.
  * JWT_SECRET is a fixed test value, so the real .jwt_secret file is not used.
"""
import io
import os
import sqlite3
import sys
import tempfile

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BACKEND_DIR)

os.environ["DATABASE_PATH"] = os.path.join(tempfile.mkdtemp(prefix="learnit-tests-"), "import-time.db")
os.environ["JWT_SECRET"] = "unit-test-secret-not-used-in-production"
os.environ["GEMINI_API_KEY"] = ""

import dotenv  # noqa: E402

dotenv.load_dotenv = lambda *args, **kwargs: False  # never read the developer's .env

import pytest  # noqa: E402
from google import genai  # noqa: E402

import database as db  # noqa: E402

REAL_DB_FILES = {os.path.join(BACKEND_DIR, name) for name in ("learn_it.db",)}


class _NoRealGemini:
    def __init__(self, *args, **kwargs):
        raise AssertionError("A test tried to create a real Gemini client. Use the fake_gemini fixture.")


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Fresh, empty SQLite database for every test."""
    path = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", path)
    assert os.path.abspath(db.DB_PATH) not in REAL_DB_FILES
    db.init_db()
    yield path
    assert os.path.abspath(db.DB_PATH) not in REAL_DB_FILES


@pytest.fixture(autouse=True)
def block_real_gemini(monkeypatch):
    monkeypatch.setattr(genai, "Client", _NoRealGemini)
    monkeypatch.setenv("GEMINI_API_KEY", "")


@pytest.fixture
def count_rows(isolated_db):
    """count_rows("generations") -> number of rows in that table of the test database."""
    def _count(table, where="1=1", params=()):
        con = sqlite3.connect(isolated_db)
        try:
            return con.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}", params).fetchone()[0]
        finally:
            con.close()
    return _count


# --------------------------------------------------------------------------- sample files
def _pdf_escape(text):
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_pdf(pages):
    """A minimal valid PDF with one line of Helvetica text per page (no extra libraries needed)."""
    objects = {
        1: "<< /Type /Catalog /Pages 2 0 R >>",
        3: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    kids = []
    for i, text in enumerate(pages):
        page_id, content_id = 4 + 2 * i, 5 + 2 * i
        stream = f"BT /F1 12 Tf 72 720 Td ({_pdf_escape(text)}) Tj ET"
        kids.append(f"{page_id} 0 R")
        objects[page_id] = (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>")
        objects[content_id] = f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream"
    objects[2] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >>"
    out, offsets = b"%PDF-1.4\n", {}
    for number in sorted(objects):
        offsets[number] = len(out)
        out += f"{number} 0 obj\n{objects[number]}\nendobj\n".encode("latin-1")
    xref, size = len(out), max(objects) + 1
    out += f"xref\n0 {size}\n0000000000 65535 f \n".encode()
    for number in range(1, size):
        out += f"{offsets[number]:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {size} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


def build_pptx(slides):
    """slides: list of dicts with optional 'title', 'table' (list of rows) and 'notes'."""
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()
    for spec in slides:
        slide = prs.slides.add_slide(prs.slide_layouts[5 if spec.get("title") else 6])
        if spec.get("title"):
            slide.shapes.title.text = spec["title"]
        if spec.get("table"):
            rows = spec["table"]
            table = slide.shapes.add_table(len(rows), len(rows[0]), Inches(1), Inches(2), Inches(4), Inches(1)).table
            for r, row in enumerate(rows):
                for c, value in enumerate(row):
                    table.cell(r, c).text = value
        if spec.get("notes"):
            slide.notes_slide.notes_text_frame.text = spec["notes"]
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


@pytest.fixture
def make_pdf():
    return build_pdf


@pytest.fixture
def make_pptx():
    return build_pptx
