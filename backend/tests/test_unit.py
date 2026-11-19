"""Unit tests: each unit is tested on its own, with collaborators replaced by mocks/fakes.

The 4 units submitted for Assignment 4 (see TESTING.md, Section 3):
  Unit 1  main.read_lecture                          file validation         TestUploadValidation   FR-1, FR-7, NFR-3
  Unit 2  study_ai.read_lecture                      text extraction         TestTextExtraction     FR-2, DR-1, DR-2
  Unit 3  study_ai.parse_response                    AI response parsing     TestParseResponse      FR-3, FR-4, NFR-2
  Unit 4  security.hash_password / verify_password   password hashing        TestPasswordHashing    FR-8, NFR-4

Additional units (also run, listed in TESTING.md, Section 6):
  database.create_user                               account storage         TestCreateUser         FR-8
  database.reserve_generation / refund_generation    daily generation limit  TestDailyLimit         FR-11, NFR-8

Each test's docstring names the requirement IDs it covers (REQUIREMENTS.md, Appendix B).
"""
import asyncio
import base64
import re
import sqlite3

import pytest
from fastapi import HTTPException

import database as db
import main
import security
import study_ai


# =========================================================================== Unit 4: password hashing
class TestPasswordHashing:
    def test_round_trip_normal_password(self):
        """Covers FR-8, NFR-4."""
        stored = security.hash_password("correct horse battery")
        parts = stored.split("$")
        assert parts[:4] == ["scrypt", "32768", "8", "1"]
        assert len(base64.b64decode(parts[4])) == 16          # 16-byte salt
        assert len(base64.b64decode(parts[5])) == 32          # 32-byte key
        assert "correct horse battery" not in stored          # never stored in plain text
        assert security.verify_password("correct horse battery", stored) is True

    def test_salt_comes_from_os_urandom(self, monkeypatch):
        """Covers NFR-4. Mock the random source: the same salt must give the same hash, and the salt is stored."""
        monkeypatch.setattr(security.os, "urandom", lambda n: b"\x00" * n)
        first, second = security.hash_password("same-password"), security.hash_password("same-password")
        assert first == second
        assert first.split("$")[4] == base64.b64encode(b"\x00" * 16).decode()

    def test_two_hashes_of_same_password_differ(self):
        """Covers NFR-4."""
        a, b = security.hash_password("repeat-me-123"), security.hash_password("repeat-me-123")
        assert a != b
        assert security.verify_password("repeat-me-123", a) and security.verify_password("repeat-me-123", b)

    def test_edge_empty_password(self):
        """Covers FR-8, NFR-4."""
        stored = security.hash_password("")
        assert security.verify_password("", stored) is True
        assert security.verify_password(" ", stored) is False

    def test_edge_unicode_password(self):
        """Covers FR-8, NFR-4."""
        stored = security.hash_password("pässwörd-🔑-密码")
        assert security.verify_password("pässwörd-🔑-密码", stored) is True
        assert security.verify_password("passwOrd-🔑-密码", stored) is False

    def test_invalid_wrong_password_rejected(self):
        """Covers FR-8, NFR-4."""
        stored = security.hash_password("hunter2hunter2")
        assert security.verify_password("hunter2hunter3", stored) is False
        assert security.verify_password("HUNTER2HUNTER2", stored) is False

    @pytest.mark.parametrize("stored", [
        "", "not-a-hash", "scrypt$1$2$3", "bcrypt$32768$8$1$AAAA$AAAA",
        "scrypt$abc$8$1$AAAAAAAAAAAAAAAAAAAAAA==$AAAA", "scrypt$32768$8$1$!!!$???",
    ], ids=["empty", "garbage", "too-few-fields", "wrong-algorithm", "non-numeric-n", "bad-base64"])
    def test_invalid_malformed_stored_hash_returns_false(self, stored):
        """Covers FR-8, NFR-4."""
        assert security.verify_password("anything", stored) is False   # no exception escapes

    def test_invalid_non_string_stored_hash_returns_false(self):
        """Covers FR-8, NFR-4."""
        assert security.verify_password("anything", None) is False

    def test_regression_server_error_is_not_reported_as_wrong_password(self, monkeypatch):
        """Covers FR-8, NFR-2. Bug B1: a broken scrypt used to be swallowed and look like 'Incorrect password'."""
        stored = security.hash_password("right-password")

        def broken_scrypt(*args, **kwargs):
            raise RuntimeError("scrypt backend unavailable")

        monkeypatch.setattr(security.hashlib, "scrypt", broken_scrypt)
        with pytest.raises(RuntimeError, match="scrypt backend unavailable"):
            security.verify_password("right-password", stored)

    def test_regression_startup_check_rejects_python_without_scrypt(self, monkeypatch):
        """Covers NFR-4, NFR-6."""
        security._require_scrypt()                            # passes on a proper Python
        monkeypatch.delattr(security.hashlib, "scrypt")
        with pytest.raises(RuntimeError, match="no hashlib.scrypt"):
            security._require_scrypt()

    def test_invalid_tampered_hash_rejected(self):
        """Covers FR-8, NFR-4."""
        stored = security.hash_password("tamper-test-1")
        parts = stored.split("$")
        parts[5] = base64.b64encode(b"\x01" * 32).decode()
        assert security.verify_password("tamper-test-1", "$".join(parts)) is False


# =========================================================================== Additional: create_user
class TestCreateUser:
    def test_normal_creates_user_and_returns_id(self, isolated_db):
        """Covers FR-8."""
        user_id = db.create_user("ada@example.com", "scrypt$fake-hash")
        assert user_id == 1
        row = db.get_user_by_email("ada@example.com")
        assert row["id"] == 1 and row["email"] == "ada@example.com" and row["password_hash"] == "scrypt$fake-hash"
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", row["created_at"])
        assert db.DB_PATH == isolated_db                      # stored in the temp DB, not learn_it.db

    def test_normal_ids_increase_per_user(self):
        """Covers FR-8."""
        assert db.create_user("one@example.com", "h1") == 1
        assert db.create_user("two@example.com", "h2") == 2
        assert db.get_user(2)["email"] == "two@example.com"

    def test_edge_email_is_stored_exactly_as_given(self):
        """Covers FR-8. The DB layer does not normalise case; main.register lower-cases before calling it."""
        assert db.create_user("Mixed@Example.com", "h") == 1
        assert db.get_user_by_email("mixed@example.com") is None
        assert db.get_user_by_email("Mixed@Example.com")["id"] == 1

    def test_edge_lookup_of_missing_user_returns_none(self):
        """Covers FR-8."""
        assert db.get_user_by_email("nobody@example.com") is None
        assert db.get_user(12345) is None

    def test_invalid_duplicate_email_returns_none_and_keeps_original(self, count_rows):
        """Covers FR-8."""
        assert db.create_user("dup@example.com", "original-hash") == 1
        assert db.create_user("dup@example.com", "attacker-hash") is None
        assert db.get_user_by_email("dup@example.com")["password_hash"] == "original-hash"
        assert count_rows("users") == 1

    def test_invalid_null_values_raise_instead_of_looking_like_duplicates(self, count_rows):
        """Covers FR-8. Bug B2: a NOT NULL violation used to return None, i.e. 'email already exists'."""
        with pytest.raises(sqlite3.IntegrityError, match="NOT NULL constraint failed: users.email"):
            db.create_user(None, "h")
        with pytest.raises(sqlite3.IntegrityError, match="NOT NULL constraint failed: users.password_hash"):
            db.create_user("x@example.com", None)
        assert count_rows("users") == 0


# =========================================================================== Unit 1: file validation
class FakeUpload:
    """Stands in for FastAPI's UploadFile: only .filename and async .read(size) are used."""

    def __init__(self, filename, data):
        self.filename, self._data = filename, data

    async def read(self, size=-1):
        return self._data if size < 0 else self._data[:size]


@pytest.fixture
def fake_parser(monkeypatch):
    """Replace the real PDF/PPTX parser so only main.read_lecture's own checks are tested."""
    calls, result = [], {"lecture": study_ai.Lecture("pdf", ["some readable text"])}

    def fake_read(extension, data, visual):
        calls.append((extension, len(data), visual))
        if isinstance(result["lecture"], Exception):
            raise result["lecture"]
        return result["lecture"]

    monkeypatch.setattr(main.study_ai, "read_lecture", fake_read)
    return calls, result


def run_validation(filename, data, visual=True):
    return asyncio.run(main.read_lecture(FakeUpload(filename, data), visual))


class TestUploadValidation:
    def test_normal_pdf_is_accepted(self, fake_parser):
        """Covers FR-1, FR-7."""
        calls, _ = fake_parser
        filename, data, lecture = run_validation("  notes.pdf ", b"%PDF-fake")
        assert filename == "notes.pdf" and data == b"%PDF-fake" and lecture.units == ["some readable text"]
        assert calls == [(".pdf", 9, True)]

    def test_normal_uppercase_pptx_extension_is_accepted(self, fake_parser):
        """Covers FR-1, FR-7."""
        calls, result = fake_parser
        result["lecture"] = study_ai.Lecture("pptx", ["slide text"])
        run_validation("Lecture.PPTX", b"PK-fake", visual=False)
        assert calls == [(".pptx", 7, False)]

    def test_edge_exactly_20_mb_is_accepted(self, fake_parser):
        """Covers FR-7, NFR-3."""
        calls, _ = fake_parser
        run_validation("big.pdf", b"x" * main.MAX_FILE_SIZE_BYTES)
        assert calls == [(".pdf", 20 * 1024 * 1024, True)]

    def test_edge_one_byte_over_20_mb_is_rejected(self, fake_parser):
        """Covers FR-7, NFR-3, US-2."""
        calls, _ = fake_parser
        with pytest.raises(HTTPException) as err:
            run_validation("big.pdf", b"x" * (main.MAX_FILE_SIZE_BYTES + 1))
        assert err.value.status_code == 413 and "20 MB" in err.value.detail
        assert calls == []                                    # parser never ran

    def test_edge_empty_file_is_rejected(self, fake_parser):
        """Covers FR-7, US-2."""
        with pytest.raises(HTTPException) as err:
            run_validation("empty.pdf", b"")
        assert err.value.status_code == 400 and err.value.detail == "The selected file is empty."

    def test_edge_pdf_page_limit_boundary(self, fake_parser, monkeypatch):
        """Covers FR-7, US-2."""
        _, result = fake_parser
        monkeypatch.setattr(main, "MAX_PDF_PAGES", 3)
        result["lecture"] = study_ai.Lecture("pdf", ["p"] * 3)
        assert len(run_validation("ok.pdf", b"data")[2].units) == 3
        result["lecture"] = study_ai.Lecture("pdf", ["p"] * 4)
        with pytest.raises(HTTPException) as err:
            run_validation("long.pdf", b"data")
        assert err.value.status_code == 413 and "4 pages" in err.value.detail

    def test_edge_no_text_and_no_visuals_is_rejected(self, fake_parser):
        """Covers DR-2, US-2."""
        _, result = fake_parser
        result["lecture"] = study_ai.Lecture("pptx", ["", "   "])
        with pytest.raises(HTTPException) as err:
            run_validation("blank.pptx", b"data", visual=False)
        assert err.value.status_code == 422 and "No readable text" in err.value.detail

    @pytest.mark.parametrize("name", ["essay.docx", "notes.pdf.exe", "README", "", None])
    def test_invalid_file_type_is_rejected(self, fake_parser, name):
        """Covers FR-1, FR-7, US-2."""
        calls, _ = fake_parser
        with pytest.raises(HTTPException) as err:
            run_validation(name, b"data")
        assert err.value.status_code == 415
        assert calls == []

    def test_invalid_corrupted_file_is_reported(self, fake_parser):
        """Covers FR-2, NFR-2, US-2."""
        _, result = fake_parser
        result["lecture"] = ValueError("EOF marker not found")
        with pytest.raises(HTTPException) as err:
            run_validation("broken.pdf", b"not really a pdf")
        assert err.value.status_code == 400 and "couldn't read this file" in err.value.detail


# =========================================================================== Unit 2: text extraction
class TestTextExtraction:
    def test_normal_pdf_text_per_page(self, make_pdf):
        """Covers FR-2, DR-1."""
        data = make_pdf(["Photosynthesis uses light", "Chlorophyll is green"])
        lecture = study_ai.read_lecture(".pdf", data, True)
        assert lecture.kind == "pdf" and lecture.label == "page"
        assert lecture.units == ["Photosynthesis uses light", "Chlorophyll is green"]
        assert lecture.words == 6
        assert lecture.pdf_bytes == data and lecture.has_visuals is True

    def test_normal_pptx_title_table_and_notes(self, make_pptx):
        """Covers FR-2, DR-1."""
        data = make_pptx([{"title": "Derivatives", "table": [["x", "f(x)"], ["2", "4"]], "notes": "explain slope"},
                          {"title": "Integrals"}])
        lecture = study_ai.read_lecture(".pptx", data, True)
        assert lecture.kind == "pptx" and lecture.label == "slide" and len(lecture.units) == 2
        assert lecture.units[0].splitlines() == ["Derivatives", "x | f(x)", "2 | 4", "[speaker notes: explain slope]"]
        assert lecture.units[1] == "Integrals"
        assert lecture.images == [] and lecture.has_visuals is False

    def test_edge_visual_off_drops_pdf_bytes(self, make_pdf):
        """Covers FR-2."""
        lecture = study_ai.read_lecture(".pdf", make_pdf(["Only text"]), False)
        assert lecture.units == ["Only text"] and lecture.pdf_bytes is None and lecture.has_visuals is False

    def test_edge_empty_presentation_and_blank_slide(self, make_pptx):
        """Covers FR-2, DR-2."""
        assert study_ai.read_lecture(".pptx", make_pptx([]), True).units == []
        blank = study_ai.read_lecture(".pptx", make_pptx([{}]), True)
        assert blank.units == [""] and blank.words == 0

    def test_edge_pdf_with_zero_pages(self, make_pdf):
        """Covers FR-2, DR-2."""
        lecture = study_ai.read_lecture(".pdf", make_pdf([]), False)
        assert lecture.units == [] and lecture.words == 0

    @pytest.mark.parametrize("extension", [".pdf", ".pptx"])
    def test_invalid_corrupted_bytes_raise(self, extension):
        """Covers FR-2."""
        with pytest.raises(Exception):
            study_ai.read_lecture(extension, b"this is definitely not a document", True)


# =========================================================================== Unit 3: AI response parsing
GOOD_REPLY = """=== CARD | p=3
Q: What does chlorophyll absorb?
A: Mostly red and blue light.
=== QUIZ | p=1
Q: Where does photosynthesis happen?
A) Chloroplast
B) Nucleus
C) Ribosome
D) Golgi body
ANSWER: A
WHY: Chloroplasts contain chlorophyll.
=== MAP
flowchart TD
A["Light"] -->|drives| B["Photosynthesis"]
"""


class TestParseResponse:
    def test_normal_card_quiz_and_map(self):
        """Covers FR-3, FR-4."""
        pack = study_ai.parse_response(GOOD_REPLY)
        assert pack["flashcards"] == [{"question": "What does chlorophyll absorb?",
                                       "answer": "Mostly red and blue light.", "source": 3}]
        quiz = pack["quiz"][0]
        assert quiz["question"] == "Where does photosynthesis happen?" and quiz["answer"] == "Chloroplast"
        assert sorted(quiz["choices"]) == ["Chloroplast", "Golgi body", "Nucleus", "Ribosome"]
        assert quiz["explanation"] == "Chloroplasts contain chlorophyll." and quiz["source"] == 1
        assert pack["diagram"] == 'flowchart TD\nA["Light"] -->|drives| B["Photosynthesis"]'

    def test_normal_markdown_bold_labels_and_multiline_answer(self):
        """Covers FR-3."""
        reply = "=== CARD | p=2\n**Q:** Define $\\frac{a}{b}$\n**A:** A ratio\nof a to b.\n"
        card = study_ai.parse_response(reply)["flashcards"][0]
        assert card == {"question": "Define $\\frac{a}{b}$", "answer": "A ratio of a to b.", "source": 2}

    def test_normal_items_sorted_by_page_and_missing_page_last(self):
        """Covers FR-3, DR-1."""
        reply = "=== CARD\nQ: no page\nA: x\n=== CARD | p=7\nQ: seven\nA: x\n=== CARD | p=2\nQ: two\nA: x\n"
        assert [c["source"] for c in study_ai.parse_response(reply)["flashcards"]] == [2, 7, None]

    def test_edge_empty_reply(self):
        """Covers FR-3, NFR-2."""
        assert study_ai.parse_response("") == {"flashcards": [], "quiz": [], "diagram": ""}

    def test_edge_duplicate_questions_are_removed_case_insensitively(self):
        """Covers FR-3."""
        reply = "=== CARD | p=1\nQ: What is ATP?\nA: Energy.\n=== CARD | p=4\nQ: what is atp?\nA: Again.\n"
        cards = study_ai.parse_response(reply)["flashcards"]
        assert len(cards) == 1 and cards[0]["answer"] == "Energy."

    def test_edge_extra_text_around_blocks_is_ignored(self):
        """Covers FR-3, FR-4, FR-6."""
        reply = "Sure! Here is your study pack.\n\n" + GOOD_REPLY + "\nHope this helps! Let me know if you need more."
        pack = study_ai.parse_response(reply)
        assert [c["question"] for c in pack["flashcards"]] == ["What does chlorophyll absorb?"]
        assert len(pack["quiz"]) == 1
        assert pack["diagram"] == 'flowchart TD\nA["Light"] -->|drives| B["Photosynthesis"]'   # chatter not in map

    def test_regression_text_after_fenced_map_is_dropped(self):
        """Covers FR-4, FR-6. Bug B3: a closing ``` and a sign-off after the map used to end up inside the Mermaid code."""
        reply = ('=== MAP\n```mermaid\nflowchart LR\nsubgraph Cell\nA("Nucleus") --- B{"DNA"}\nend\n'
                 'B -.-> C["RNA"]\n```\n\nLet me know if you want a bigger map!\n')
        assert study_ai.parse_response(reply)["diagram"] == \
            'flowchart LR\nsubgraph Cell\nA("Nucleus") --- B{"DNA"}\nend\nB -.-> C["RNA"]'

    def test_invalid_reply_without_headers_is_ignored(self):
        """Covers FR-3, NFR-2."""
        assert study_ai.parse_response("Sure! Here are your flashcards:\nQ: hi\nA: there") == \
            {"flashcards": [], "quiz": [], "diagram": ""}

    @pytest.mark.parametrize("quiz_block", [
        "Q: Only three?\nA) a\nB) b\nC) c\nANSWER: A",                    # missing choice D
        "Q: Duplicates?\nA) same\nB) Same\nC) c\nD) d\nANSWER: C",        # choices not distinct
        "Q: No answer?\nA) a\nB) b\nC) c\nD) d\nWHY: none given",         # no ANSWER line
        "Q: Bad letter?\nA) a\nB) b\nC) c\nD) d\nANSWER: E",              # answer outside A-D
        "A) a\nB) b\nC) c\nD) d\nANSWER: A",                              # no question
    ], ids=["three-choices", "duplicate-choices", "no-answer", "answer-E", "no-question"])
    def test_invalid_quiz_blocks_are_dropped(self, quiz_block):
        """Covers FR-3, NFR-2."""
        assert study_ai.parse_response("=== QUIZ | p=1\n" + quiz_block)["quiz"] == []

    def test_invalid_card_without_answer_and_bad_map_are_dropped(self):
        """Covers FR-3, FR-4, NFR-2."""
        reply = "=== CARD | p=1\nQ: Lonely question\n=== MAP\nThis is not mermaid\n"
        assert study_ai.parse_response(reply) == {"flashcards": [], "quiz": [], "diagram": ""}


# =========================================================================== Additional: daily generation limit
class TestDailyLimit:
    @pytest.fixture
    def user_id(self):
        return db.create_user("limit@example.com", "h")

    def test_normal_reservations_until_limit(self, user_id, count_rows):
        """Covers FR-11, NFR-8."""
        ids = [db.reserve_generation(user_id, 3) for _ in range(3)]
        assert ids == [1, 2, 3]
        assert count_rows("generations", "user_id = ?", (user_id,)) == 3

    def test_boundary_request_after_limit_is_refused(self, user_id, count_rows):
        """Covers FR-11, NFR-8."""
        assert db.reserve_generation(user_id, 2) and db.reserve_generation(user_id, 2)
        assert db.reserve_generation(user_id, 2) is None
        assert count_rows("generations") == 2                 # the refused call added nothing

    def test_edge_limit_zero_refuses_immediately(self, user_id):
        """Covers FR-11."""
        assert db.reserve_generation(user_id, 0) is None

    def test_edge_limit_is_per_user(self, user_id):
        """Covers FR-11."""
        other = db.create_user("other@example.com", "h")
        assert db.reserve_generation(user_id, 1) and db.reserve_generation(user_id, 1) is None
        assert db.reserve_generation(other, 1) is not None

    def test_edge_24_hour_window_boundary(self, user_id, monkeypatch):
        """Covers FR-11. Mock the clock instead of waiting a day."""
        clock = {"now": 1_000_000.0}
        monkeypatch.setattr(db.time, "time", lambda: clock["now"])
        assert db.reserve_generation(user_id, 1) is not None
        clock["now"] += 86_399                                # 1 second before the window ends
        assert db.reserve_generation(user_id, 1) is None
        clock["now"] += 1                                     # exactly 24 h later: slot is free again
        assert db.reserve_generation(user_id, 1) is not None

    def test_refund_frees_a_slot(self, user_id):
        """Covers FR-11, NFR-2."""
        first = db.reserve_generation(user_id, 1)
        assert db.reserve_generation(user_id, 1) is None
        db.refund_generation(first)
        assert db.reserve_generation(user_id, 1) is not None

    def test_invalid_refund_of_unknown_id_is_harmless(self, user_id, count_rows):
        """Covers FR-11."""
        db.reserve_generation(user_id, 5)
        db.refund_generation(9999)
        assert count_rows("generations") == 1

    def test_invalid_unknown_user_raises_and_releases_lock(self, user_id):
        """Covers FR-11."""
        with pytest.raises(sqlite3.IntegrityError):           # foreign key: user 9999 does not exist
            db.reserve_generation(9999, 5)
        assert db.reserve_generation(user_id, 5) is not None  # the write lock was not left held
