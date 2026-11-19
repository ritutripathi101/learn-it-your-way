"""Component tests: several real parts working together through the FastAPI app (TestClient).

The 2 components submitted for Assignment 4 (see TESTING.md, Section 3):
  Component 1  Upload pipeline (TestGenerationComponent): /study/generate upload -> type/size checks
               -> PDF/PPTX text extraction -> daily limit -> prompt building -> Gemini (FAKE client)
               -> reply parsing -> cache -> JSON response                    FR-1..FR-4, FR-7, FR-10, FR-11, NFR-2
  Component 2  Accounts (TestAccountsComponent): /auth/register -> email check -> scrypt hashing -> SQLite
               -> JWT -> /auth/login, /auth/me                                FR-8, NFR-4

Additional component (also run, listed in TESTING.md, Section 6):
  Saved sets (TestSavedSetsComponent): /study/sets save -> diagram sanitising -> SQLite ownership -> list -> delete   FR-9

Each test's docstring names the requirement IDs it covers (REQUIREMENTS.md, Appendix B).

Only the network edge is faked: google.genai.Client is replaced, so the real generate_pack(), build_parts(),
parse_response() and finish_pack() still run. Every test uses its own temporary SQLite file (see conftest.py).
"""
import time

import pytest
from fastapi.testclient import TestClient
from google import genai

import database as db
import main
import security

PASSWORD = "Sup3r-secret-pw"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "login_limiter", security.RateLimiter(100, 900))  # fresh limiter per test
    with TestClient(main.app) as test_client:
        yield test_client


def register(client, email="student@example.com", password=PASSWORD):
    return client.post("/auth/register", json={"email": email, "password": password})


@pytest.fixture
def auth(client):
    token = register(client).json()["token"]
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------- fake Gemini
GEMINI_REPLY = """=== CARD | p=1
Q: What do plants turn light into?
A: Chemical energy stored as glucose.
=== CARD | p=2
Q: What pigment absorbs light?
A: Chlorophyll.
=== QUIZ | p=2
Q: Which gas do plants release?
A) Oxygen
B) Nitrogen
C) Helium
D) Argon
ANSWER: A
WHY: Oxygen is a by-product of splitting water.
=== MAP
flowchart TD
A["Light"] -->|powers| B["Photosynthesis"]
B -->|makes| C["Glucose"]
"""


class BusyError(Exception):
    code, status = 429, "RESOURCE_EXHAUSTED"


class FakeGemini:
    """Records every request. `reply` is either the text to return or an exception to raise."""

    def __init__(self):
        self.reply, self.delay, self.requests, self.clients = GEMINI_REPLY, 0, [], 0
        fake = self

        class _Models:
            def generate_content(self, model, contents, config):
                fake.requests.append({"model": model, "contents": contents})
                if fake.delay:
                    time.sleep(fake.delay)
                if isinstance(fake.reply, Exception):
                    raise fake.reply
                return type("Response", (), {"text": fake.reply})()

        class _Client:
            def __init__(self, api_key=None, http_options=None):
                assert api_key == "test-key-not-real"
                fake.clients += 1
                self.models, self.files = _Models(), None

            def close(self):
                pass

        self.client_class = _Client


@pytest.fixture
def gemini(monkeypatch):
    fake = FakeGemini()
    monkeypatch.setattr(genai, "Client", fake.client_class)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    return fake


def upload(client, headers, data, name="lecture.pdf", **form):
    return client.post("/study/generate", headers=headers, files={"file": (name, data, "application/octet-stream")},
                       data={k: str(v).lower() if isinstance(v, bool) else str(v) for k, v in form.items()})


# =========================================================================== Component 2: accounts
class TestAccountsComponent:
    def test_success_register_then_login_then_me(self, client, count_rows):
        """Covers FR-8, NFR-4."""
        reg = register(client, email="  Student@Example.COM ")
        assert reg.status_code == 200 and reg.json()["email"] == "student@example.com"
        stored = db.get_user_by_email("student@example.com")
        assert stored["password_hash"].startswith("scrypt$") and PASSWORD not in stored["password_hash"]
        assert security.read_token(reg.json()["token"]) == stored["id"]

        login = client.post("/auth/login", json={"email": "STUDENT@example.com", "password": PASSWORD})
        assert login.status_code == 200 and login.json()["email"] == "student@example.com"
        me = client.get("/auth/me", headers={"Authorization": f"Bearer {login.json()['token']}"})
        assert me.status_code == 200 and me.json() == {"email": "student@example.com"}
        assert count_rows("users") == 1

    def test_failure_duplicate_email_in_different_case(self, client, count_rows):
        """Covers FR-8."""
        assert register(client, email="dup@example.com").status_code == 200
        second = register(client, email="DUP@example.com", password="another-password")
        assert second.status_code == 409 and "already exists" in second.json()["detail"]
        assert count_rows("users") == 1
        # the original password still works, the second one does not
        assert client.post("/auth/login", json={"email": "dup@example.com", "password": PASSWORD}).status_code == 200
        assert client.post("/auth/login", json={"email": "dup@example.com", "password": "another-password"}).status_code == 401

    def test_failure_wrong_password_and_unknown_email(self, client):
        """Covers FR-8, US-2."""
        register(client)
        wrong = client.post("/auth/login", json={"email": "student@example.com", "password": "not-the-password"})
        assert wrong.status_code == 401 and wrong.json()["detail"] == "Incorrect password. Try again."
        unknown = client.post("/auth/login", json={"email": "ghost@example.com", "password": PASSWORD})
        assert unknown.status_code == 404 and "No account found" in unknown.json()["detail"]

    @pytest.mark.parametrize("body, fragment", [
        ({"email": "not-an-email", "password": PASSWORD}, "valid email"),
        ({"email": "short@example.com", "password": "1234567"}, "password field"),
        ({"email": "x@example.com"}, "password field"),
    ], ids=["bad-email", "7-char-password", "missing-password"])
    def test_failure_invalid_input_creates_no_user(self, client, count_rows, body, fragment):
        """Covers FR-8, US-2."""
        response = client.post("/auth/register", json=body)
        assert response.status_code == 422 and fragment in response.json()["detail"]
        assert count_rows("users") == 0

    @pytest.mark.parametrize("header", [None, "Bearer junk.token.value", "Token abc",
                                        f"Bearer {security.make_token(999)}"],
                             ids=["no-header", "junk-token", "wrong-scheme", "token-for-missing-user"])
    def test_failure_protected_route_rejects_bad_tokens(self, client, header):
        """Covers FR-8, FR-9."""
        response = client.get("/auth/me", headers={"Authorization": header} if header else {})
        assert response.status_code == 401 and response.json()["detail"] == "Please sign in again."

    def test_unusual_login_rate_limit(self, client, monkeypatch):
        """Covers FR-8."""
        register(client)
        monkeypatch.setattr(main, "login_limiter", security.RateLimiter(2, 900))
        body = {"email": "student@example.com", "password": PASSWORD}
        assert [client.post("/auth/login", json=body).status_code for _ in range(3)] == [200, 200, 429]


# =========================================================================== Component 1: upload pipeline
class TestGenerationComponent:
    def test_success_pdf_text_flows_through_to_ai_and_back(self, client, auth, gemini, make_pdf, count_rows):
        """Covers FR-1, FR-2, FR-3, FR-4, DR-1."""
        pdf = make_pdf(["Photosynthesis turns light into glucose", "Chlorophyll absorbs red and blue light"])
        response = upload(client, auth, pdf, card_count=4, quiz_count=3, visual=False)

        assert response.status_code == 200
        body = response.json()
        assert body["filename"] == "lecture.pdf" and body["cached"] is False
        assert [c["question"] for c in body["flashcards"]] == ["What do plants turn light into?",
                                                               "What pigment absorbs light?"]
        assert body["quiz"][0]["answer"] == "Oxygen" and len(body["quiz"][0]["choices"]) == 4
        assert body["diagram"].startswith("flowchart TD")
        assert "Only 2 of 4 flashcards could be created." in body["warnings"]
        # the text extracted from the PDF is what was sent to the model, with the requested counts
        sent = gemini.requests[0]["contents"]
        assert "[Page 1]\nPhotosynthesis turns light into glucose" in sent[0]
        assert "[Page 2]\nChlorophyll absorbs red and blue light" in sent[0]
        assert "exactly 4 flashcards and 3 multiple-choice" in sent[-1]
        assert len(gemini.requests) == 1 and count_rows("generations") == 1

    def test_success_pptx_upload(self, client, auth, gemini, make_pptx):
        """Covers FR-1, FR-2, FR-3, DR-1."""
        pptx = make_pptx([{"title": "Cell biology", "notes": "mitochondria are the powerhouse"}])
        response = upload(client, auth, pptx, name="cells.pptx", visual=False)
        assert response.status_code == 200 and response.json()["filename"] == "cells.pptx"
        assert "[Slide 1]\nCell biology\n[speaker notes: mitochondria are the powerhouse]" in gemini.requests[0]["contents"][0]

    def test_success_same_file_is_served_from_cache(self, client, auth, gemini, make_pdf, count_rows):
        """Covers FR-10, NFR-8."""
        pdf = make_pdf(["Cache me"])
        first = upload(client, auth, pdf, card_count=5, quiz_count=3)
        second = upload(client, auth, pdf, card_count=5, quiz_count=3)
        assert first.status_code == second.status_code == 200
        assert first.json()["cached"] is False and second.json()["cached"] is True
        assert second.json()["flashcards"] == first.json()["flashcards"]
        assert len(gemini.requests) == 1                     # AI called once only
        assert count_rows("generations") == 1                # cache hit did not use the daily limit
        assert count_rows("generation_cache") == 1

    def test_failure_ai_busy_tries_fallback_then_refunds(self, client, auth, gemini, make_pdf, count_rows):
        """Covers FR-3, FR-11, NFR-2."""
        gemini.reply = BusyError("429 RESOURCE_EXHAUSTED: quota exceeded")
        response = upload(client, auth, make_pdf(["Busy day"]))
        assert response.status_code == 503 and "temporarily busy" in response.json()["detail"]
        assert [r["model"] for r in gemini.requests] == [main.study_ai.MODEL_NAME, main.study_ai.FALLBACK_MODEL_NAME]
        assert count_rows("generations") == 0                # the reserved generation was refunded
        assert count_rows("generation_cache") == 0

    def test_failure_unreadable_ai_reply_is_502_and_refunded(self, client, auth, gemini, make_pdf, count_rows):
        """Covers FR-3, NFR-2."""
        gemini.reply = "I'm sorry, I can't help with that."
        response = upload(client, auth, make_pdf(["Some lecture"]))
        assert response.status_code == 502 and "could not be generated" in response.json()["detail"]
        assert count_rows("generations") == 0 and count_rows("generation_cache") == 0

    def test_failure_daily_limit_blocks_ai_call(self, client, auth, gemini, make_pdf, monkeypatch):
        """Covers FR-11, NFR-8."""
        monkeypatch.setattr(main, "DAILY_LIMIT", 1)
        assert upload(client, auth, make_pdf(["First lecture"])).status_code == 200
        blocked = upload(client, auth, make_pdf(["Second, different lecture"]))
        assert blocked.status_code == 429 and "Daily limit of 1" in blocked.json()["detail"]
        assert len(gemini.requests) == 1

    @pytest.mark.parametrize("name, data, status", [
        ("notes.docx", b"anything", 415),
        ("broken.pdf", b"%PDF-1.4 truncated garbage", 400),
        ("empty.pdf", b"", 400),
        ("huge.pdf", b"x" * (main.MAX_FILE_SIZE_BYTES + 1), 413),
    ], ids=["wrong-type", "corrupted-pdf", "empty-file", "over-20-mb"])
    def test_failure_bad_upload_never_reaches_ai(self, client, auth, gemini, count_rows, name, data, status):
        """Covers FR-7, NFR-3, US-2."""
        response = upload(client, auth, data, name=name)
        assert response.status_code == status
        assert gemini.requests == [] and count_rows("generations") == 0

    def test_failure_missing_api_key_is_503_and_refunded(self, client, auth, gemini, make_pdf, monkeypatch, count_rows):
        """Covers NFR-2, NFR-5."""
        monkeypatch.setenv("GEMINI_API_KEY", "")
        response = upload(client, auth, make_pdf(["No key"]))
        assert response.status_code == 503 and "not configured" in response.json()["detail"]
        assert gemini.clients == 0 and count_rows("generations") == 0

    def test_unusual_timeout_is_504_and_stays_counted(self, client, auth, gemini, make_pdf, monkeypatch, count_rows):
        """Covers FR-11, NFR-2."""
        monkeypatch.setattr(main, "AI_REQUEST_TIMEOUT_SECONDS", 0.2)
        gemini.delay = 1.0
        response = upload(client, auth, make_pdf(["Slow"]))
        assert response.status_code == 504 and "took too long" in response.json()["detail"]
        assert count_rows("generations") == 1                # a timeout may have used the AI, so it is kept

    def test_failure_requires_sign_in(self, client, gemini, make_pdf):
        """Covers FR-8."""
        assert upload(client, {}, make_pdf(["x"])).status_code == 401
        assert gemini.requests == []


# =========================================================================== Additional: saved sets
SET = {
    "filename": "bio.pdf",
    "flashcards": [{"question": "What is ATP?", "answer": "Energy currency.", "source": 1}],
    "quiz": [{"question": "Pick A", "choices": ["A", "B", "C", "D"], "answer": "A", "explanation": "", "source": 2}],
    "diagram": 'flowchart TD\nA["Cell"] --> B["ATP"]',
}


class TestSavedSetsComponent:
    def test_success_save_list_update_delete(self, client, auth):
        """Covers FR-9."""
        saved = client.post("/study/sets", headers=auth, json=SET)
        assert saved.status_code == 200
        set_id = saved.json()["id"]
        assert len(set_id) == 32 and saved.json()["flashcards"] == SET["flashcards"]

        updated = client.post("/study/sets", headers=auth, json={**SET, "id": set_id, "filename": "renamed.pdf"})
        assert updated.json()["id"] == set_id
        listed = client.get("/study/sets", headers=auth).json()
        assert [(s["id"], s["filename"]) for s in listed] == [(set_id, "renamed.pdf")]

        assert client.delete(f"/study/sets/{set_id}", headers=auth).json() == {"ok": True}
        assert client.get("/study/sets", headers=auth).json() == []

    def test_success_unsafe_diagram_lines_are_stripped(self, client, auth):
        """Covers FR-6, FR-9."""
        diagram = '```mermaid\nflowchart TD\nA["x"] --> B["y"]\nclick A "http://evil"\nstyle A fill:#f00\nB --> C["<img>"]\n```'
        saved = client.post("/study/sets", headers=auth, json={**SET, "diagram": diagram})
        assert saved.status_code == 200 and saved.json()["diagram"] == 'flowchart TD\nA["x"] --> B["y"]'

    def test_failure_other_user_cannot_read_change_or_delete(self, client, auth):
        """Covers FR-9."""
        set_id = client.post("/study/sets", headers=auth, json=SET).json()["id"]
        other = {"Authorization": f"Bearer {register(client, email='other@example.com').json()['token']}"}

        assert client.get("/study/sets", headers=other).json() == []
        assert client.delete(f"/study/sets/{set_id}", headers=other).status_code == 404
        hijack = client.post("/study/sets", headers=other, json={**SET, "id": set_id, "filename": "stolen.pdf"})
        assert hijack.status_code == 200 and hijack.json()["id"] != set_id      # got a new id instead
        assert client.get("/study/sets", headers=auth).json()[0]["filename"] == "bio.pdf"

    @pytest.mark.parametrize("change, fragment", [
        ({"quiz": [{**SET["quiz"][0], "answer": "Z"}]}, "does not match its choices"),
        ({"diagram": "sequenceDiagram\nA->>B: hi"}, "readable concept map"),
        ({"quiz": [{**SET["quiz"][0], "choices": ["A", "B", "C"]}]}, "choices field"),
        ({"filename": ""}, "filename field"),
    ], ids=["answer-not-in-choices", "not-a-flowchart", "three-choices", "empty-filename"])
    def test_failure_invalid_set_is_rejected_and_not_saved(self, client, auth, count_rows, change, fragment):
        """Covers FR-9, US-2."""
        response = client.post("/study/sets", headers=auth, json={**SET, **change})
        assert response.status_code == 422 and fragment in response.json()["detail"]
        assert count_rows("study_sets") == 0

    def test_unusual_saved_set_limit(self, client, auth, monkeypatch):
        """Covers FR-9."""
        monkeypatch.setattr(db, "MAX_SETS_PER_USER", 1)
        first = client.post("/study/sets", headers=auth, json=SET)
        assert first.status_code == 200
        second = client.post("/study/sets", headers=auth, json={**SET, "filename": "two.pdf"})
        assert second.status_code == 409 and "limit of saved sets" in second.json()["detail"]
        # updating the existing set is still allowed at the limit
        assert client.post("/study/sets", headers=auth, json={**SET, "id": first.json()["id"]}).status_code == 200
