# Learn It Your Way: Unit and Component Testing (Assignment 4)

CSCI 5801 Software Engineering. Team: Ritu Tripathi, Topendra Singh.
Requirement IDs (FR-, NFR-, DR-, US-) refer to `REQUIREMENTS.md`. The test design follows its Appendix A (Chapter 8 test plan).

## 1. Summary

| What | Where | Tests | Result |
|---|---|---|---|
| **4 units** (Assignment 4) | `tests/test_unit.py` | 50 | 50 pass |
| **2 components** (Assignment 4) | `tests/test_component.py` | 24 | 24 pass |
| Additional units: `create_user`, daily limit | `tests/test_unit.py` | 14 | 14 pass |
| Additional component: saved study sets | `tests/test_component.py` | 8 | 8 pass |
| Older tests written before Assignment 4 | `tests/test_core.py` | 6 | 6 pass |
| **Total** | | **102** | **102 pass, 0 fail** |

All results are from `backend/venv`, using Python 3.13.11 with OpenSSL 3.0.18 on macOS. Three real bugs were found and fixed with the team's approval (B1–B3, [Section 9](#9-bugs-requirement-discrepancies-remaining-failures-and-limitations)). Six places where `REQUIREMENTS.md` or the README no longer matched the code were found and have been resolved (R1–R6, Section 9.2).

| Unit / component | Test class | Tests | Normal / success | Edge / boundary | Invalid / failure |
|---|---|---|---|---|---|
| Unit 1: File validation | `TestUploadValidation` | 13 | 2 | 5 | 6 |
| Unit 2: Text extraction | `TestTextExtraction` | 7 | 2 | 3 | 2 |
| Unit 3: AI response parsing | `TestParseResponse` | 14 | 3 | 4 | 7 |
| Unit 4: Password hashing | `TestPasswordHashing` | 16 | 3 | 2 | 11 |
| Component 1: Upload pipeline | `TestGenerationComponent` | 13 | 3 | 1 (timeout) | 9 |
| Component 2: Accounts | `TestAccountsComponent` | 11 | 1 | 2 (rate limit, deleted user) | 8 |

Regression tests for B1 and B3 are counted with failure and edge cases respectively.

---

## 2. How the tests are isolated

These rules come from `REQUIREMENTS.md` Appendix B. They are enforced in `tests/conftest.py`, before any app module is imported and again for every test.

- **No real database.** `database.DB_PATH` is read when the module is imported, and `main.py` creates the tables as soon as it is imported. So `conftest.py` points `DATABASE_PATH` at a throwaway file first. Then every test gets its own empty SQLite file under pytest's `tmp_path`, set with `monkeypatch.setattr(db, "DB_PATH", ...)`. A check fails the test if that path is ever the real `learn_it.db`, and the real file's modification time did not change during the runs.
- **No `.env`.** `dotenv.load_dotenv` is replaced with a no-op. `GEMINI_API_KEY` is empty and `JWT_SECRET` is a fixed test value.
- **No real Gemini.** `google.genai.Client` is replaced with a guard that fails any test that tries to create it. Tests that need AI use a `FakeGemini` client, which records each request and returns canned text or raises a chosen error. Only the network call is faked, so the real `generate_pack()`, `build_parts()`, `parse_response()` and `finish_pack()` run.
- **Unit isolation with mocks and fakes:**
  - Unit 1 uses a `FakeUpload` object in place of `UploadFile`, and the PDF/PPTX parser is mocked.
  - Unit 2 builds sample PDF/PPTX files in memory.
  - Unit 3 is a pure function, given fixed reply strings.
  - Unit 4 mocks `os.urandom` and `hashlib.scrypt`.
  - The daily-limit tests mock `time.time`.
  - The login rate limiter is reset for every test.

---

## 3. The 4 units and 2 components

These are the units and components that `REQUIREMENTS.md` A.1 gives as examples, and they match the rows of the A.3 traceability matrix.

### Units

| # | Unit | Location | What it does | Requirements |
|---|---|---|---|---|
| **Unit 1** | File validation: `read_lecture` | `main.py` | Accepts only `.pdf`/`.pptx` (case-insensitive). Rejects empty files (400), files over 20 MB (413) and unsupported types (415) before the parser runs. Then enforces the PDF page limit (413) and the "some readable content" rule (422). | FR-1, FR-7, NFR-3, DR-2, US-2 |
| **Unit 2** | Text extraction: `read_lecture` / `read_pdf` / `read_pptx` | `study_ai.py` | Turns file bytes into a `Lecture`: text for each page or slide in order, pptx tables as `a \| b` rows, speaker notes, and whether visuals exist. | FR-2, DR-1, DR-2 |
| **Unit 3** | AI response parsing: `parse_response` (+ `sanitize_diagram`) | `study_ai.py` | Parses Gemini's tagged-text reply into flashcards, quiz questions (exactly 4 distinct choices) and a Mermaid concept map. Drops malformed items, duplicate questions and unsafe or non-Mermaid lines. | FR-3, FR-4, FR-6, NFR-2 |
| **Unit 4** | Password hashing: `hash_password` / `verify_password` | `security.py` | Hashes with scrypt and a random 16-byte salt, and checks in constant time. Returns `False` for a wrong password or a malformed hash. Raises real server errors. Refuses to start on a Python without scrypt. | FR-8, NFR-4 |

### Components

| # | Component | Parts working together | Requirements |
|---|---|---|---|
| **Component 1** | Upload pipeline | `POST /study/generate` → sign-in check → **file validation** → **text extraction** → card/quiz counts → cache lookup (`db.cache_get`) → daily limit (`db.reserve_generation`) → prompt (`build_parts`) → **Gemini (fake)** → **response parsing** (`finish_pack`) → `db.cache_put` → JSON. If the AI fails: error mapping (`run_ai`) and `db.refund_generation`. | FR-1, FR-2, FR-3, FR-4, FR-7, FR-10, FR-11, NFR-2, NFR-3, NFR-5, NFR-8, DR-1 |
| **Component 2** | Accounts | `POST /auth/register` → Pydantic + email check → rate limiter → **password hashing** → `db.create_user` → JWT (`make_token`) → `POST /auth/login` → `db.get_user_by_email` → `verify_password` → `GET /auth/me` → `current_user` → `read_token` → `db.get_user` | FR-8, FR-9, NFR-4, US-2 |

---

## 4. Results for the 4 units and 2 components

Each test asserts specific expected values (status codes, exact strings, row counts, number of AI calls). "Actual result: As expected" means every assertion held when the suite was run. Parametrized tests appear as one row per case, as pytest reports them. The requirement IDs match each test's docstring.

### Unit 1: File validation (`TestUploadValidation`), 13 tests

| ID | Test name | Purpose | Input | Expected result | Actual result | Pass/Fail | Req. ID |
|---|---|---|---|---|---|---|---|
| U1.1 | `test_normal_pdf_is_accepted` | Normal: a valid PDF passes and reaches the parser | `"  notes.pdf "`, 9 bytes | Returns `"notes.pdf"` (trimmed), the same bytes and the lecture; parser called with `(".pdf", 9, True)` | As expected | Pass | FR-1, FR-7 |
| U1.2 | `test_normal_uppercase_pptx_extension_is_accepted` | Normal: the extension check ignores case | `"Lecture.PPTX"`, `visual=False` | Parser called with `(".pptx", 7, False)` | As expected | Pass | FR-1, FR-7 |
| U1.3 | `test_edge_exactly_20_mb_is_accepted` | Boundary: exactly at the size limit | 20 × 1024 × 1024 bytes | Accepted; parser receives 20,971,520 bytes | As expected | Pass | FR-7, NFR-3 |
| U1.4 | `test_edge_one_byte_over_20_mb_is_rejected` | Boundary: one byte over the limit | 20 MB + 1 byte | `HTTPException` 413 mentioning "20 MB"; parser not called | As expected | Pass | FR-7, NFR-3, US-2 |
| U1.5 | `test_edge_empty_file_is_rejected` | Edge: empty input | `b""` | 400 "The selected file is empty." | As expected | Pass | FR-7, US-2 |
| U1.6 | `test_edge_pdf_page_limit_boundary` | Boundary: PDF page limit | `MAX_PDF_PAGES=3`; 3 pages, then 4 pages | 3 pages accepted; 4 pages gives 413 mentioning "4 pages" | As expected | Pass | FR-7, US-2 |
| U1.7 | `test_edge_no_text_and_no_visuals_is_rejected` | Edge: no extractable text (scanned file) | Lecture with units `["", "   "]`, no images | 422 "No readable text…" | As expected | Pass | DR-2, US-2 |
| U1.8 | `test_invalid_file_type_is_rejected[essay.docx]` | Invalid: unsupported type | `essay.docx` | 415; parser not called | As expected | Pass | FR-1, FR-7, US-2 |
| U1.9 | `…[notes.pdf.exe]` | Invalid: double extension | `notes.pdf.exe` | 415; parser not called | As expected | Pass | FR-1, FR-7, US-2 |
| U1.10 | `…[README]` | Invalid: no extension | `README` | 415; parser not called | As expected | Pass | FR-1, FR-7, US-2 |
| U1.11 | `…[]` | Invalid: empty filename | `""` | 415; parser not called | As expected | Pass | FR-1, FR-7, US-2 |
| U1.12 | `…[None]` | Invalid: missing filename | `None` | 415; parser not called | As expected | Pass | FR-1, FR-7, US-2 |
| U1.13 | `test_invalid_corrupted_file_is_reported` | Invalid: the parser fails | Parser raises `ValueError` | 400 "We couldn't read this file…" | As expected | Pass | FR-2, NFR-2, US-2 |

### Unit 2: Text extraction (`TestTextExtraction`), 7 tests

| ID | Test name | Purpose | Input | Expected result | Actual result | Pass/Fail | Req. ID |
|---|---|---|---|---|---|---|---|
| U2.1 | `test_normal_pdf_text_per_page` | Normal: known PDF text, pages in order | 2-page PDF | `kind="pdf"`, `label="page"`, units equal the 2 page strings in order, `words == 6`, PDF bytes kept | As expected | Pass | FR-2, DR-1 |
| U2.2 | `test_normal_pptx_title_table_and_notes` | Normal: several slides in order, with title, table and notes | 2-slide pptx | Slide 1 lines are `["Derivatives", "x \| f(x)", "2 \| 4", "[speaker notes: explain slope]"]`; slide 2 is `"Integrals"` | As expected | Pass | FR-2, DR-1 |
| U2.3 | `test_edge_visual_off_drops_pdf_bytes` | Edge: text-only mode | PDF, `visual=False` | Text kept; `pdf_bytes is None`; `has_visuals is False` | As expected | Pass | FR-2 |
| U2.4 | `test_edge_empty_presentation_and_blank_slide` | Edge: empty input | pptx with 0 slides; pptx with 1 blank slide | `[]`; `[""]` with `words == 0` | As expected | Pass | FR-2, DR-2 |
| U2.5 | `test_edge_pdf_with_zero_pages` | Edge: empty PDF | Valid PDF with 0 pages | `units == []`, `words == 0` | As expected | Pass | FR-2, DR-2 |
| U2.6 | `test_invalid_corrupted_bytes_raise[.pdf]` | Invalid: not a real PDF | Plain text bytes | Raises an exception (reported as 400 by Unit 1) | As expected | Pass | FR-2 |
| U2.7 | `test_invalid_corrupted_bytes_raise[.pptx]` | Invalid: not a real PPTX | Plain text bytes | Raises an exception | As expected | Pass | FR-2 |

### Unit 3: AI response parsing (`TestParseResponse`), 14 tests

| ID | Test name | Purpose | Input | Expected result | Actual result | Pass/Fail | Req. ID |
|---|---|---|---|---|---|---|---|
| U3.1 | `test_normal_card_quiz_and_map` | Normal: well-formed reply | 1 card (p=3), 1 quiz (p=1), 2-node map | Exact card dict; quiz answer `"Chloroplast"` with all 4 choices, explanation, `source=1`; exact diagram string | As expected | Pass | FR-3, FR-4 |
| U3.2 | `test_normal_markdown_bold_labels_and_multiline_answer` | Normal: Markdown bold labels and LaTeX | `**Q:**` / `**A:**`, `\frac`, answer over 2 lines | `{"question": "Define $\\frac{a}{b}$", "answer": "A ratio of a to b.", "source": 2}` | As expected | Pass | FR-3 |
| U3.3 | `test_normal_items_sorted_by_page_and_missing_page_last` | Normal: lecture order kept | Cards with no page, p=7, p=2 | Sources `[2, 7, None]` | As expected | Pass | FR-3, DR-1 |
| U3.4 | `test_edge_empty_reply` | Edge: empty input | `""` | `{"flashcards": [], "quiz": [], "diagram": ""}` | As expected | Pass | FR-3, NFR-2 |
| U3.5 | `test_edge_duplicate_questions_are_removed_case_insensitively` | Edge: repeated input | "What is ATP?" and "what is atp?" | 1 card (the first) | As expected | Pass | FR-3 |
| U3.6 | `test_edge_extra_text_around_blocks_is_ignored` | Edge: extra text around the output (A.3) | A chat greeting before and a sign-off after a valid reply | Same card, quiz and diagram as U3.1; the sign-off is **not** in the diagram | As expected (failed before the B3 fix) | Pass | FR-3, FR-4, FR-6 |
| U3.7 | `test_regression_text_after_fenced_map_is_dropped` | Regression B3: fenced map followed by chatter | ` ```mermaid ` map with `subgraph`, `---`, `-.->`, then ` ``` ` and a sentence | Exactly `flowchart LR\nsubgraph Cell\nA("Nucleus") --- B{"DNA"}\nend\nB -.-> C["RNA"]` | As expected (failed before the B3 fix) | Pass | FR-4, FR-6 |
| U3.8 | `test_invalid_reply_without_headers_is_ignored` | Invalid: wrong format | Chat text with no `===` headers | Empty pack | As expected | Pass | FR-3, NFR-2 |
| U3.9 | `test_invalid_quiz_blocks_are_dropped[three-choices]` | Invalid: malformed quiz | Choices A–C only | `quiz == []` | As expected | Pass | FR-3, NFR-2 |
| U3.10 | `…[duplicate-choices]` | Invalid: choices not distinct | `"same"` / `"Same"` | `quiz == []` | As expected | Pass | FR-3, NFR-2 |
| U3.11 | `…[no-answer]` | Invalid: missing answer | No `ANSWER:` line | `quiz == []` | As expected | Pass | FR-3, NFR-2 |
| U3.12 | `…[answer-E]` | Invalid: answer out of range | `ANSWER: E` | `quiz == []` | As expected | Pass | FR-3, NFR-2 |
| U3.13 | `…[no-question]` | Invalid: missing question | Choices only | `quiz == []` | As expected | Pass | FR-3, NFR-2 |
| U3.14 | `test_invalid_card_without_answer_and_bad_map_are_dropped` | Invalid: half a card, non-Mermaid map | Card without `A:`; map "This is not mermaid" | Empty pack | As expected | Pass | FR-3, FR-4, NFR-2 |

### Unit 4: Password hashing (`TestPasswordHashing`), 16 tests

| ID | Test name | Purpose | Input | Expected result | Actual result | Pass/Fail | Req. ID |
|---|---|---|---|---|---|---|---|
| U4.1 | `test_round_trip_normal_password` | Normal: hash and verify | `"correct horse battery"` | Format `scrypt$32768$8$1$<16-byte salt>$<32-byte key>`; no plain text in the hash; verifies as `True` | As expected | Pass | FR-8, NFR-4 |
| U4.2 | `test_salt_comes_from_os_urandom` | Normal (mock): the salt is used and stored | `os.urandom` mocked to return zero bytes | Two hashes identical; salt field is `base64(16 zero bytes)` | As expected | Pass | NFR-4 |
| U4.3 | `test_two_hashes_of_same_password_differ` | Normal: hashes are salted | Same password hashed twice | Hashes differ; both verify | As expected | Pass | NFR-4 |
| U4.4 | `test_edge_empty_password` | Edge: empty input | `""` | `""` gives `True`; `" "` gives `False` | As expected | Pass | FR-8, NFR-4 |
| U4.5 | `test_edge_unicode_password` | Edge: non-ASCII | `"pässwörd-🔑-密码"` | `True`; one changed letter gives `False` | As expected | Pass | FR-8, NFR-4 |
| U4.6 | `test_invalid_wrong_password_rejected` | Invalid: wrong password | Last character changed; all upper case | `False` for both | As expected | Pass | FR-8, NFR-4 |
| U4.7 | `test_invalid_malformed_stored_hash_returns_false[empty]` | Invalid: malformed stored hash | `""` | `False`, no exception | As expected | Pass | FR-8, NFR-4 |
| U4.8 | `…[garbage]` | Invalid | `"not-a-hash"` | `False`, no exception | As expected | Pass | FR-8, NFR-4 |
| U4.9 | `…[too-few-fields]` | Invalid | `"scrypt$1$2$3"` | `False`, no exception | As expected | Pass | FR-8, NFR-4 |
| U4.10 | `…[wrong-algorithm]` | Invalid | `"bcrypt$…"` | `False`, no exception | As expected | Pass | FR-8, NFR-4 |
| U4.11 | `…[non-numeric-n]` | Invalid | `N = "abc"` | `False`, no exception | As expected | Pass | FR-8, NFR-4 |
| U4.12 | `…[bad-base64]` | Invalid | salt `"!!!"`, key `"???"` | `False`, no exception | As expected | Pass | FR-8, NFR-4 |
| U4.13 | `test_invalid_non_string_stored_hash_returns_false` | Invalid: wrong type | stored = `None` | `False`, no exception | As expected | Pass | FR-8, NFR-4 |
| U4.14 | `test_regression_server_error_is_not_reported_as_wrong_password` | Regression B1 (mock) | Valid hash; `hashlib.scrypt` mocked to raise `RuntimeError` | `RuntimeError` is raised, not turned into `False` | As expected | Pass | FR-8, NFR-2 |
| U4.15 | `test_regression_startup_check_rejects_python_without_scrypt` | Regression B1 (mock) | `_require_scrypt()` with scrypt present, then removed | First call passes; second raises `RuntimeError` "no hashlib.scrypt…" | As expected | Pass | NFR-4, NFR-6 |
| U4.16 | `test_invalid_tampered_hash_rejected` | Invalid: tampered hash | Valid hash with its key replaced | `False` | As expected | Pass | FR-8, NFR-4 |

### Component 1: Upload pipeline (`TestGenerationComponent`), 13 tests

| ID | Test name | Purpose (interaction tested) | Input | Expected result | Actual result | Pass/Fail | Req. ID |
|---|---|---|---|---|---|---|---|
| C1.1 | `test_success_pdf_text_flows_through_to_ai_and_back` | Success: upload → extraction → prompt → AI → parsing → response | 2-page PDF, `card_count=4`, `quiz_count=3`, `visual=false`; fake returns 2 cards, 1 quiz and a map | 200, `cached=false`; the 2 card questions; quiz answer `"Oxygen"` with 4 choices; flowchart map; warning "Only 2 of 4 flashcards…". The fake received `[Page 1]\n…`, `[Page 2]\n…` and "exactly 4 flashcards and 3…". 1 AI call; 1 generation counted | As expected | Pass | FR-1, FR-2, FR-3, FR-4, DR-1 |
| C1.2 | `test_success_pptx_upload` | Success: PPTX path through the same pipeline | pptx with a title and speaker notes | 200; prompt contains `[Slide 1]\nCell biology\n[speaker notes: …]` | As expected | Pass | FR-1, FR-2, FR-3, DR-1 |
| C1.3 | `test_success_same_file_is_served_from_cache` | Success: cache ↔ AI ↔ daily limit | Same PDF and options uploaded twice | 2nd response `cached=true` with identical flashcards; **AI called once**; 1 generation counted; 1 cache row | As expected | Pass | FR-10, NFR-8 |
| C1.4 | `test_failure_ai_busy_tries_fallback_then_refunds` | Failure: Gemini 429 → fallback model → error mapping → refund | Fake raises `code=429` | 503 "temporarily busy"; main model then fallback model tried; 0 generations (refunded); nothing cached | As expected | Pass | FR-3, FR-11, NFR-2 |
| C1.5 | `test_failure_unreadable_ai_reply_is_502_and_refunded` | Failure: AI returns unusable output (interface misunderstanding) | Fake replies "I'm sorry, I can't help with that." | 502 "could not be generated"; 0 generations; 0 cache rows | As expected | Pass | FR-3, NFR-2 |
| C1.6 | `test_failure_daily_limit_blocks_ai_call` | Failure: daily limit stops the AI call | `DAILY_LIMIT=1`; two different PDFs | First 200; second 429 "Daily limit of 1…"; only 1 AI call | As expected | Pass | FR-11, NFR-8 |
| C1.7 | `test_failure_bad_upload_never_reaches_ai[wrong-type]` | Failure: validation stops the pipeline | `notes.docx` | 415; 0 AI calls; 0 generations counted | As expected | Pass | FR-7, NFR-3, US-2 |
| C1.8 | `…[corrupted-pdf]` | Failure: extraction error stops the pipeline | `broken.pdf`, garbage bytes | 400; 0 AI calls; 0 generations | As expected | Pass | FR-7, NFR-3, US-2 |
| C1.9 | `…[empty-file]` | Failure: empty upload | `empty.pdf`, 0 bytes | 400; 0 AI calls; 0 generations | As expected | Pass | FR-7, NFR-3, US-2 |
| C1.10 | `…[over-20-mb]` | Failure (boundary): file too large, through the endpoint | `huge.pdf`, 20 MB + 1 byte | 413; 0 AI calls; 0 generations | As expected | Pass | FR-7, NFR-3, US-2 |
| C1.11 | `test_failure_missing_api_key_is_503_and_refunded` | Failure: AI not configured | `GEMINI_API_KEY=""` | 503 "not configured"; no client created; 0 generations | As expected | Pass | NFR-2, NFR-5 |
| C1.12 | `test_unusual_timeout_is_504_and_stays_counted` | Unusual: AI too slow | Timeout 0.2 s, fake takes 1 s | 504 "took too long"; generation stays counted (1 row), as designed | As expected | Pass | FR-11, NFR-2 |
| C1.13 | `test_failure_requires_sign_in` | Failure: no account | No token | 401; 0 AI calls | As expected | Pass | FR-8 |

### Component 2: Accounts (`TestAccountsComponent`), 11 tests

| ID | Test name | Purpose (interaction tested) | Input | Expected result | Actual result | Pass/Fail | Req. ID |
|---|---|---|---|---|---|---|---|
| C2.1 | `test_success_register_then_login_then_me` | Success: register → hash → DB → token → login → me | Register `"  Student@Example.COM "`, log in as `"STUDENT@example.com"`, call `/auth/me` | 200 each time; email stored as `student@example.com`; DB holds a `scrypt$` hash, not the password; token decodes to the user id; `/auth/me` returns `{"email": "student@example.com"}`; 1 user row | As expected | Pass | FR-8, NFR-4 |
| C2.2 | `test_failure_duplicate_email_in_different_case` | Failure: duplicate email | `dup@…`, then `DUP@…` with another password | 409 "already exists"; 1 row; original password logs in (200); the second password gets 401 | As expected | Pass | FR-8 |
| C2.3 | `test_failure_wrong_password_and_unknown_email` | Failure: bad credentials | Wrong password; unregistered email | 401 "Incorrect password. Try again."; 404 "No account found…" | As expected | Pass | FR-8, US-2 |
| C2.4 | `test_failure_invalid_input_creates_no_user[bad-email]` | Failure: invalid email | `"not-an-email"` | 422 "valid email"; 0 users | As expected | Pass | FR-8, US-2 |
| C2.5 | `…[7-char-password]` | Failure (boundary: minimum is 8) | `"1234567"` | 422 "…password field…"; 0 users | As expected | Pass | FR-8, US-2 |
| C2.6 | `…[missing-password]` | Failure: missing value | No password | 422 "…password field…"; 0 users | As expected | Pass | FR-8, US-2 |
| C2.7 | `test_failure_protected_route_rejects_bad_tokens[no-header]` | Failure: not signed in | No `Authorization` header | 401 "Please sign in again." | As expected | Pass | FR-8, FR-9 |
| C2.8 | `…[junk-token]` | Failure: forged token | `Bearer junk.token.value` | 401 | As expected | Pass | FR-8, FR-9 |
| C2.9 | `…[wrong-scheme]` | Failure: wrong header format | `Token abc` | 401 | As expected | Pass | FR-8, FR-9 |
| C2.10 | `…[token-for-missing-user]` | Unusual: token valid, user gone | Valid token for user id 999 | 401 | As expected | Pass | FR-8, FR-9 |
| C2.11 | `test_unusual_login_rate_limit` | Unusual: too many attempts | Limit 2 per 15 min; 3 correct logins | `[200, 200, 429]` | As expected | Pass | FR-8 |

---

## 5. Requirement traceability (REQUIREMENTS.md A.3)

| Requirement | Unit tests | Component tests |
|---|---|---|
| FR-1, FR-7, NFR-3 | U1.1–U1.12 (type, 20 MB boundary, empty) | C1.7–C1.10 (bad files never reach Gemini) |
| FR-2, DR-1, DR-2 | U2.1–U2.7, U1.7, U1.13 | C1.1, C1.2 (extracted text is what Gemini receives) |
| FR-3, FR-4, NFR-2 | U3.1–U3.14 | C1.1, C1.4 (429), C1.5 (bad output), C1.11, C1.12 |
| FR-6 (map must render) | U3.6, U3.7 | additional S.2 |
| FR-8, NFR-4 | U4.1–U4.16 | C2.1–C2.11 |
| FR-9 | | C2.7–C2.10; additional S.1–S.8 |
| FR-10, FR-11, NFR-8 | additional D.1–D.8 | C1.3 (cache: AI called once), C1.6 (limit), C1.4 (refund) |
| NFR-5 | | C1.11; `.env` and `.jwt_secret` are in `.gitignore` |
| FR-5, FR-6 (drawing), NFR-1, US-1, US-3, US-4 | Not automated: frontend and timing (manual, see Section 9.4) | |

---

## 6. Additional tests (run with the suite, not part of the 4 + 2)

| ID | Test name | Purpose | Input | Expected result | Actual result | Pass/Fail | Req. ID |
|---|---|---|---|---|---|---|---|
| A.1 | `TestCreateUser::test_normal_creates_user_and_returns_id` | Normal | `("ada@example.com", "scrypt$fake-hash")` | Id `1`; row matches; `created_at` is `YYYY-MM-DD HH:MM:SS`; temp DB used | As expected | Pass | FR-8 |
| A.2 | `…::test_normal_ids_increase_per_user` | Normal | Two emails | Ids `1`, `2` | As expected | Pass | FR-8 |
| A.3 | `…::test_edge_email_is_stored_exactly_as_given` | Edge | `"Mixed@Example.com"` | Stored as given; lower-case lookup returns `None` | As expected | Pass | FR-8 |
| A.4 | `…::test_edge_lookup_of_missing_user_returns_none` | Edge | Empty DB | Both lookups return `None` | As expected | Pass | FR-8 |
| A.5 | `…::test_invalid_duplicate_email_returns_none_and_keeps_original` | Invalid | Same email twice | 2nd returns `None`; original hash kept; 1 row | As expected | Pass | FR-8 |
| A.6 | `…::test_invalid_null_values_raise_instead_of_looking_like_duplicates` | Regression B2 | `email=None`; `password_hash=None` | `IntegrityError` "NOT NULL constraint failed: users.email" / "…password_hash"; 0 rows | As expected | Pass | FR-8 |
| D.1 | `TestDailyLimit::test_normal_reservations_until_limit` | Normal | limit 3, 3 calls | Ids `[1, 2, 3]` | As expected | Pass | FR-11, NFR-8 |
| D.2 | `…::test_boundary_request_after_limit_is_refused` | Boundary | limit 2, 3 calls | 3rd call returns `None`; 2 rows | As expected | Pass | FR-11, NFR-8 |
| D.3 | `…::test_edge_limit_zero_refuses_immediately` | Edge | limit 0 | `None` | As expected | Pass | FR-11 |
| D.4 | `…::test_edge_limit_is_per_user` | Edge | User A at limit 1 | A gets `None`; B gets an id | As expected | Pass | FR-11 |
| D.5 | `…::test_edge_24_hour_window_boundary` | Boundary (mocked clock) | T, T+86,399 s, T+86,400 s | Refused, then allowed at exactly 24 h | As expected | Pass | FR-11 |
| D.6 | `…::test_refund_frees_a_slot` | Normal | Reserve, refund, reserve | 2nd reservation succeeds | As expected | Pass | FR-11, NFR-2 |
| D.7 | `…::test_invalid_refund_of_unknown_id_is_harmless` | Invalid | `refund_generation(9999)` | No error; 1 row kept | As expected | Pass | FR-11 |
| D.8 | `…::test_invalid_unknown_user_raises_and_releases_lock` | Invalid | `reserve_generation(9999, 5)` | `IntegrityError`; next reservation still works | As expected | Pass | FR-11 |
| S.1 | `TestSavedSetsComponent::test_success_save_list_update_delete` | Success | Save, update, list, delete | Same id on update; list `[(id, "renamed.pdf")]`; `{"ok": true}`; then empty list | As expected | Pass | FR-9 |
| S.2 | `…::test_success_unsafe_diagram_lines_are_stripped` | Success | Map with `click`, `style`, `<img>` | Saved as `flowchart TD\nA["x"] --> B["y"]` | As expected | Pass | FR-6, FR-9 |
| S.3 | `…::test_failure_other_user_cannot_read_change_or_delete` | Failure | User B uses user A's set id | B's list empty; delete 404; save gets a new id; A's set unchanged | As expected | Pass | FR-9 |
| S.4 | `…::test_failure_invalid_set_is_rejected_and_not_saved[answer-not-in-choices]` | Failure | Answer `"Z"` | 422 "does not match its choices"; 0 rows | As expected | Pass | FR-9, US-2 |
| S.5 | `…[not-a-flowchart]` | Failure | `sequenceDiagram…` | 422 "readable concept map"; 0 rows | As expected | Pass | FR-9, US-2 |
| S.6 | `…[three-choices]` | Failure | 3 choices | 422 "…choices field…"; 0 rows | As expected | Pass | FR-9, US-2 |
| S.7 | `…[empty-filename]` | Failure | `filename=""` | 422 "…filename field…"; 0 rows | As expected | Pass | FR-9, US-2 |
| S.8 | `…::test_unusual_saved_set_limit` | Unusual | Limit 1: save, save, update | 200, 409, 200 | As expected | Pass | FR-9 |
| O.1–O.6 | `test_core.py`: `test_parse`, `test_finish_and_even_selection`, `test_quotas_cover_everything`, `test_pptx_reading`, `test_db_and_security`, `test_daily_limit_refund_and_dedupe` | Older tests from before Assignment 4 (several checks each) | Varied | Their own assertions | As expected | Pass (6/6) | FR-2, FR-3, FR-8, FR-9, FR-10, FR-11 |

---

## 7. Checking that the tests can fail

To check that the tests catch real mistakes, bugs were planted one at a time in a **scratch copy** of the code, and the suite was run against each one. The real code was not changed by this. Every planted bug was caught:

| Planted bug | Tests that failed |
|---|---|
| Daily limit off by one (`used > limit`) | 6 |
| Failed AI call not refunded | 3 |
| Size check lets 20 MB + 1 byte through | 1 |
| `verify_password` always returns `True` | 7 |
| Duplicate quiz choices not rejected | 1 |
| A user can overwrite another user's saved set | 1 |
| B1 fix undone (`except Exception` back in `verify_password`) | 1 (U4.14) |
| B2 fix undone (`create_user` returns `None` for every `IntegrityError`) | 1 (A.6) |
| B3 fix undone (all lines kept in the Mermaid map) | 2 (U3.6, U3.7) |

---

## 8. How to install and run the tests

Run all commands from the `backend/` folder. You need Python **3.10 or newer** from python.org, Homebrew, conda or the Microsoft Store. macOS's built-in `/usr/bin/python3` will not work (see B1). No `.env` file, API key or network access is needed.

### macOS (zsh/bash)

```bash
cd learn-it-your-way/backend
python3 -c "import hashlib; print(hasattr(hashlib, 'scrypt'))"   # must print True
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt

python -m pytest tests/test_unit.py -v          # unit tests
python -m pytest tests/test_component.py -v     # component tests
python -m pytest tests -v                       # full suite (102 tests)
```

### Windows (PowerShell)

```powershell
cd learn-it-your-way\backend
py -3 -c "import hashlib; print(hasattr(hashlib, 'scrypt'))"     # must print True
py -3 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

python -m pytest tests/test_unit.py -v
python -m pytest tests/test_component.py -v
python -m pytest tests -v
```

If PowerShell blocks the activation script, run this once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`. In Command Prompt, use `venv\Scripts\activate.bat` instead.

### Only the 4 units and 2 components

```bash
python -m pytest tests/test_unit.py -v -k "UploadValidation or TextExtraction or ParseResponse or PasswordHashing"   # 50 tests
python -m pytest tests/test_component.py -v -k "GenerationComponent or AccountsComponent"                          # 24 tests
```

---

## 9. Bugs, requirement discrepancies, remaining failures and limitations

### 9.1 Bugs found and fixed

All three fixes were made only after the team approved them. Each one has a regression test that fails if the fix is undone (Section 7).

**B1 (high): sign-up and login did not work in the project's virtual environment.**
`backend/venv/bin/python` was a link to Apple's Command Line Tools Python 3.9.6, which is built with LibreSSL 2.8.3 and has no `hashlib.scrypt`. The effects were:
- `POST /auth/register` crashed with HTTP 500.
- `verify_password` swallowed every exception (`except Exception: return False`), so **every login answered "Incorrect password" and nothing was logged**.

At the time, 32 of the 96 tests failed or errored, all for this one reason.

*Fix:*
- The venv was recreated from Python 3.13.11 with OpenSSL 3.
- `security.py` now runs `_require_scrypt()` at import, which stops with a clear message on an unsuitable Python. This was checked with `/usr/bin/python3`.
- `verify_password` now catches only `ValueError`/`TypeError` (malformed hashes), so real server errors are no longer hidden.

Tests: U4.14, U4.15.

**B2 (low): `create_user` reported any database constraint error as "email already exists".**
A `NOT NULL` violation returned `None`, which the API would have turned into a misleading 409. Requests could not trigger it, because Pydantic requires both fields. *Fix:* `None` is returned only for `UNIQUE constraint failed: users.email`; other errors are raised. Tests: A.5, A.6, C2.2.

**B3 (medium): text after the concept map ended up inside the Mermaid code (found by U3.6).**
If Gemini wrote anything after the map, such as "Hope this helps!" or a closing ` ``` ` followed by a sentence, `sanitize_diagram` kept those lines. That would most likely make Mermaid.js fail to draw the map (FR-6). *Fix:* after the `flowchart` header, only lines that look like Mermaid statements are kept: edges (`-->`, `---`, `-.-`, `==>`, `~~~`), node definitions (`A[…]`, `A(…)`, `A{…}`, `A>…]`), and `subgraph`/`end`/`direction`. Tests: U3.6, U3.7; S.2 and the older `test_parse` still pass.

**Observations (not bugs):**
- `select_evenly(items, 0)` returns 1 item. This can't be reached, because the minimum is 4 cards and 3 questions.
- `card_count=0` means "use the suggested count".
- The cache is shared by all users who upload the same file with the same options. This is intended, to save AI usage (NFR-8).

### 9.2 Places where REQUIREMENTS.md no longer matched the code (resolved)

These were found while mapping tests to requirements. The code was not changed for them. Instead, the team updated `REQUIREMENTS.md` (v1.2) and the README to match the code.

| # | Requirement | Document said | Code does | Status |
|---|---|---|---|---|
| R1 | FR-4 | Concept map comes from a `/upload-map` endpoint | `/upload-map` was removed. The map comes from `POST /study/generate` together with flashcards and the quiz (one AI call). | Resolved: REQUIREMENTS.md updated to v1.2 |
| R2 | FR-3, Section 7 | Each flashcard has a question, an answer **and a question type** | Flashcards have `question`, `answer` and `source` (page). The prompt asks for mixed question types, but no type field is returned. | Resolved: REQUIREMENTS.md updated to v1.2 |
| R3 | Glossary | Model `gemini-flash-latest` | `GEMINI_MODEL` defaults to `gemini-3.8-flash`, with fallback `gemini-3.6-flash`. Both can be changed in `.env`. | Resolved: REQUIREMENTS.md updated to v1.2 |
| R4 | A.2, A.3 | "Malformed JSON", "extra text around JSON" | The AI replies in a tagged text format, not JSON, so LaTeX backslashes survive. The equivalent cases are tested (U3.6, U3.8–U3.14, C1.5). | Resolved: REQUIREMENTS.md updated to v1.2 (A.2/A.3 wording fixed in 176b505) |
| R5 | Appendix B | Real database files are `learn_it.db` and `learnit.sqlite3` | `learnit.sqlite3` was an old, unused database and has been deleted. Only `learn_it.db` is used. | Resolved: REQUIREMENTS.md updated to v1.2 |
| R6 | NFR-6 | Installs with the commands in the README | The README said "Python 3.9 or newer", but 3.10+ with OpenSSL is needed (B1). It also referred to a `.env.example` file that did not exist. | Resolved: README now requires Python 3.10+ and backend/.env.example was added (b021a9e) |

### 9.3 Remaining failures

**None.** 102 passed, 0 failed (`python -m pytest tests -v`).

### 9.4 Testing limitations

- **Gemini is always faked.** The tests prove that the app builds the right prompt and handles the replies and errors it is given. They cannot prove that the real model follows the format or that the configured model names exist.
- **Not exercised:** PDF visual mode (sending the PDF itself to Gemini) beyond checking that the bytes are kept, the Files API upload for PDFs over 12 MB, and PPTX image extraction (the sample decks have no pictures).
- **Sample files are minimal**, with one line of text per page or slide. Real lectures with columns, scanned pages or equations may extract differently.
- **Not tested here: frontend and timing.** FR-5, FR-6 (drawing the map in the browser), NFR-1 (30-second response) and US-1, US-3, US-4 need manual or system testing, which `REQUIREMENTS.md` A.1 places outside Assignment 4. B3's effect on Mermaid.js comes from reading Mermaid's syntax rules, not from running it in a browser.
- **Concurrency, multiple processes and real elapsed time are not tested.** The 24-hour window uses a mocked clock, the rate limiter is per process, and JWT expiry has no dedicated test.
- **Platforms:** the suite was run on macOS with Python 3.13.11. The Windows commands follow standard Python practice but were not run (NFR-6).
