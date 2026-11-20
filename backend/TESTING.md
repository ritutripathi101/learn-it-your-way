# Learn It Your Way: Unit and Component Testing (Assignment 4)

CSCI 5801 Software Engineering. Team: Ritu Tripathi, Topendra Singh.

This file lists every test we wrote for Assignment 4, what each one checks, and the results.

## 1. Summary

| What | Where | Tests | Result |
|---|---|---|---|
| **4 units** (Assignment 4) | `tests/test_unit.py` | 50 | 50 pass |
| **2 components** (Assignment 4) | `tests/test_component.py` | 24 | 24 pass |
| Additional units: `create_user`, daily limit | `tests/test_unit.py` | 14 | 14 pass |
| Additional component: saved study sets | `tests/test_component.py` | 8 | 8 pass |
| Older tests written before Assignment 4 | `tests/test_core.py` | 6 | 6 pass |
| **Total** | | **102** | **102 pass, 0 fail** |

We ran all the tests on macOS with Python 3.13.11. All 102 pass. While testing, we found three real bugs and fixed them (see Section 8).

| Unit / component | Test class | Tests | Normal / success | Edge / boundary | Invalid / failure |
|---|---|---|---|---|---|
| Unit 1: File validation | `TestUploadValidation` | 13 | 2 | 5 | 6 |
| Unit 2: Text extraction | `TestTextExtraction` | 7 | 2 | 3 | 2 |
| Unit 3: AI response parsing | `TestParseResponse` | 14 | 3 | 4 | 7 |
| Unit 4: Password hashing | `TestPasswordHashing` | 16 | 3 | 2 | 11 |
| Component 1: Upload pipeline | `TestGenerationComponent` | 13 | 3 | 1 (timeout) | 9 |
| Component 2: Accounts | `TestAccountsComponent` | 11 | 1 | 2 (rate limit, deleted user) | 8 |

Every unit and component has normal cases, edge cases and error cases. Tests that check a fixed bug stays fixed (regression tests) are counted with the error and edge cases.

---

## 2. How the tests are isolated

The tests never use real data or real outside services. The setup is in `tests/conftest.py`.

- **No real database.** Each test gets its own new, empty test database. The real `learn_it.db` is never touched.
- **No real AI.** Gemini is replaced by a fake that sends back a reply we wrote, or an error we picked. No internet or API key is needed.
- **No secrets.** The `.env` file is not read. A test value is used instead.
- **Units on their own.** Unit 1 uses a fake upload and a fake file reader. Unit 2 builds small sample PDF and PowerPoint files inside the test. Unit 3 gets fixed reply text. Unit 4 fakes the random salt. The daily-limit tests use a fake clock.

---

## 3. The 4 units and 2 components

### Units

| # | Unit | File | What it does |
|---|---|---|---|
| **Unit 1** | File validation: `read_lecture` | `main.py` | Checks an uploaded file first. Only `.pdf` and `.pptx` are allowed. Empty files, files over 20 MB, PDFs over 400 pages, and files with no readable text are rejected with a clear error. |
| **Unit 2** | Text extraction: `read_pdf` / `read_pptx` | `study_ai.py` | Reads the text of each page or slide in order. For PowerPoint it also reads tables, speaker notes and pictures. |
| **Unit 3** | AI response parsing: `parse_response` | `study_ai.py` | Turns the AI's reply into flashcards, quiz questions (each with 4 different choices) and a concept map. Throws away broken items, repeated flashcard questions and unsafe map lines. |
| **Unit 4** | Password hashing: `hash_password` / `verify_password` | `security.py` | Stores passwords safely as scrypt hashes with a random salt, and checks a typed password against the stored hash. |

### Components

| # | Component | Parts working together |
|---|---|---|
| **Component 1** | Upload pipeline (`POST /study/generate`) | Sign-in check → file validation (Unit 1) → text extraction (Unit 2) → check the cache for an earlier result → daily limit → send to Gemini (fake in tests) → read the reply (Unit 3) → save to cache → send the study pack back. If the AI fails, the user gets a clear error and the attempt does not count toward the daily limit. |
| **Component 2** | Accounts (`/auth/register`, `/auth/login`, `/auth/me`) | Check the email → login attempt limit → hash the password (Unit 4) → save the user in the database → give a login token. Logging in checks the password, and protected pages check the token. |

---

## 4. Results for the 4 units and 2 components

Each test checks an exact expected result, such as a status code, an error message, or how many times the AI was called. "As expected" means every check in the test passed. Tests that run with several inputs show one row per input.

### Unit 1: File validation (`TestUploadValidation`), 13 tests

| ID | Test name | Purpose | Input | Expected result | Actual result | Pass/Fail |
|---|---|---|---|---|---|---|
| U1.1 | `test_normal_pdf_is_accepted` | Normal: a valid PDF is accepted | "  notes.pdf " (two leading spaces), 9 bytes | Accepted; name trimmed to "notes.pdf"; file sent to the reader once | As expected | Pass |
| U1.2 | `test_normal_uppercase_pptx_extension_is_accepted` | Normal: the extension check ignores case | "Lecture.PPTX" (capital letters), visual mode off | Accepted as a PowerPoint | As expected | Pass |
| U1.3 | `test_edge_exactly_20_mb_is_accepted` | Boundary: exactly at the size limit | File of exactly 20 MB | Accepted | As expected | Pass |
| U1.4 | `test_edge_one_byte_over_20_mb_is_rejected` | Boundary: one byte over the limit | File of 20 MB + 1 byte | Rejected: 413 with a "20 MB" message; file never read | As expected | Pass |
| U1.5 | `test_edge_empty_file_is_rejected` | Edge: empty input | Empty file (0 bytes) | Rejected: 400 "The selected file is empty." | As expected | Pass |
| U1.6 | `test_edge_pdf_page_limit_boundary` | Boundary: PDF page limit | Page limit set to 3; a 3-page PDF, then a 4-page PDF | 3 pages accepted; 4 pages rejected: 413 "4 pages" | As expected | Pass |
| U1.7 | `test_edge_no_text_and_no_visuals_is_rejected` | Edge: no extractable text (scanned file) | File whose pages have no text and no pictures | Rejected: 422 "No readable text…" | As expected | Pass |
| U1.8 | `test_invalid_file_type_is_rejected[essay.docx]` | Invalid: unsupported type | essay.docx | Rejected: 415; file never read | As expected | Pass |
| U1.9 | `…[notes.pdf.exe]` | Invalid: double extension | notes.pdf.exe | Rejected: 415; file never read | As expected | Pass |
| U1.10 | `…[README]` | Invalid: no extension | README (no extension) | Rejected: 415; file never read | As expected | Pass |
| U1.11 | `…[]` | Invalid: empty filename | Empty file name | Rejected: 415; file never read | As expected | Pass |
| U1.12 | `…[None]` | Invalid: missing filename | No file name | Rejected: 415; file never read | As expected | Pass |
| U1.13 | `test_invalid_corrupted_file_is_reported` | Invalid: the file reader fails | A file the reader cannot open | Rejected: 400 "We couldn't read this file…" | As expected | Pass |

### Unit 2: Text extraction (`TestTextExtraction`), 7 tests

| ID | Test name | Purpose | Input | Expected result | Actual result | Pass/Fail |
|---|---|---|---|---|---|---|
| U2.1 | `test_normal_pdf_text_per_page` | Normal: known PDF text, pages in order | 2-page PDF: "Photosynthesis uses light", "Chlorophyll is green" | Both pages read in order ("Photosynthesis uses light", "Chlorophyll is green"); 6 words; PDF kept for the AI | As expected | Pass |
| U2.2 | `test_normal_pptx_title_table_and_notes` | Normal: several slides in order, with title, table and notes | 2-slide PowerPoint with a title, a table and speaker notes | Slide 1 gives "Derivatives", the table rows "x \| f(x)" and "2 \| 4", and the notes; slide 2 gives "Integrals" | As expected | Pass |
| U2.3 | `test_edge_visual_off_drops_pdf_bytes` | Edge: text-only mode | PDF with visual mode off | Text read; PDF file not kept (no visuals) | As expected | Pass |
| U2.4 | `test_edge_empty_presentation_and_blank_slide` | Edge: empty input | PowerPoint with 0 slides; PowerPoint with 1 blank slide | No slides; one empty slide with 0 words | As expected | Pass |
| U2.5 | `test_edge_pdf_with_zero_pages` | Edge: empty PDF | Valid PDF with 0 pages | No pages; 0 words | As expected | Pass |
| U2.6 | `test_invalid_corrupted_bytes_raise[.pdf]` | Invalid: not a real PDF | Plain text saved as a .pdf | An error is raised (the user sees a 400 message) | As expected | Pass |
| U2.7 | `test_invalid_corrupted_bytes_raise[.pptx]` | Invalid: not a real PPTX | Plain text saved as a .pptx | An error is raised (the user sees a 400 message) | As expected | Pass |

### Unit 3: AI response parsing (`TestParseResponse`), 14 tests

| ID | Test name | Purpose | Input | Expected result | Actual result | Pass/Fail |
|---|---|---|---|---|---|---|
| U3.1 | `test_normal_card_quiz_and_map` | Normal: well-formed reply | Reply with 1 flashcard, 1 quiz question and a 2-box map | 1 flashcard (page 3); quiz answer "Chloroplast" with 4 choices and an explanation; map kept exactly | As expected | Pass |
| U3.2 | `test_normal_markdown_bold_labels_and_multiline_answer` | Normal: Markdown bold labels and LaTeX | Card with bold "Q:"/"A:", a math formula and a 2-line answer | Question "Define $\frac{a}{b}$"; answer joined into "A ratio of a to b."; page 2 | As expected | Pass |
| U3.3 | `test_normal_items_sorted_by_page_and_missing_page_last` | Normal: lecture order kept | Cards from no page, page 7 and page 2 | Sorted as page 2, page 7, then no page | As expected | Pass |
| U3.4 | `test_edge_empty_reply` | Edge: empty input | Empty reply | Empty pack: 0 flashcards, 0 quiz questions, no map | As expected | Pass |
| U3.5 | `test_edge_duplicate_questions_are_removed_case_insensitively` | Edge: repeated input | "What is ATP?" and "what is atp?" | Only the first card is kept | As expected | Pass |
| U3.6 | `test_edge_extra_text_around_blocks_is_ignored` | Edge: extra text around the reply | Good reply with a greeting before it and "Hope this helps!" after it | Same card, quiz question and map as U3.1; the extra text is not in the map | As expected (failed before the B3 fix) | Pass |
| U3.7 | `test_regression_text_after_fenced_map_is_dropped` | Regression B3: map in a code fence, then chat text | Map inside a ```mermaid block, then a chat sentence | Map kept exactly; the sentence is removed | As expected (failed before the B3 fix) | Pass |
| U3.8 | `test_invalid_reply_without_headers_is_ignored` | Invalid: wrong format | Chat text with no "===" section headers | Empty pack: 0 flashcards, 0 quiz questions, no map | As expected | Pass |
| U3.9 | `test_invalid_quiz_blocks_are_dropped[three-choices]` | Invalid: malformed quiz | Quiz question with only 3 choices | Question thrown away: quiz list is empty | As expected | Pass |
| U3.10 | `…[duplicate-choices]` | Invalid: choices not distinct | Two choices that are the same ("same" and "Same") | Question thrown away: quiz list is empty | As expected | Pass |
| U3.11 | `…[no-answer]` | Invalid: missing answer | Quiz question with no answer line | Question thrown away: quiz list is empty | As expected | Pass |
| U3.12 | `…[answer-E]` | Invalid: answer out of range | Answer "E" (only A–D allowed) | Question thrown away: quiz list is empty | As expected | Pass |
| U3.13 | `…[no-question]` | Invalid: missing question | Choices but no question | Question thrown away: quiz list is empty | As expected | Pass |
| U3.14 | `test_invalid_card_without_answer_and_bad_map_are_dropped` | Invalid: half a card, non-Mermaid map | Card with no answer, and a map that is not map code | Empty pack: 0 flashcards, 0 quiz questions, no map | As expected | Pass |

### Unit 4: Password hashing (`TestPasswordHashing`), 16 tests

| ID | Test name | Purpose | Input | Expected result | Actual result | Pass/Fail |
|---|---|---|---|---|---|---|
| U4.1 | `test_round_trip_normal_password` | Normal: hash and verify | "correct horse battery" | Saved as "scrypt$32768$8$1$..." with a 16-byte salt and 32-byte key; the password is not in it; correct password returns True | As expected | Pass |
| U4.2 | `test_salt_comes_from_os_urandom` | Normal (fake salt): the salt is used and stored | Random salt replaced with all zeros | Same hash both times; the zero salt is stored in the hash | As expected | Pass |
| U4.3 | `test_two_hashes_of_same_password_differ` | Normal: hashes are salted | Same password hashed twice | Two different hashes; both return True for the password | As expected | Pass |
| U4.4 | `test_edge_empty_password` | Edge: empty input | Empty password "" | "" returns True; " " (a space) returns False | As expected | Pass |
| U4.5 | `test_edge_unicode_password` | Edge: non-ASCII | "pässwörd-🔑-密码" (accents, emoji, Chinese) | Returns True; the same password with two letters changed returns False | As expected | Pass |
| U4.6 | `test_invalid_wrong_password_rejected` | Invalid: wrong password | Last letter changed; all capital letters | Both return False | As expected | Pass |
| U4.7 | `test_invalid_malformed_stored_hash_returns_false[empty]` | Invalid: malformed stored hash | Stored hash is empty | Returns False, no crash | As expected | Pass |
| U4.8 | `…[garbage]` | Invalid | Stored hash "not-a-hash" | Returns False, no crash | As expected | Pass |
| U4.9 | `…[too-few-fields]` | Invalid | Stored hash with too few parts | Returns False, no crash | As expected | Pass |
| U4.10 | `…[wrong-algorithm]` | Invalid | Stored hash for another method ("bcrypt") | Returns False, no crash | As expected | Pass |
| U4.11 | `…[non-numeric-n]` | Invalid | Stored hash with a setting that is not a number | Returns False, no crash | As expected | Pass |
| U4.12 | `…[bad-base64]` | Invalid | Stored hash with broken salt and key text | Returns False, no crash | As expected | Pass |
| U4.13 | `test_invalid_non_string_stored_hash_returns_false` | Invalid: wrong type | Stored hash missing (None) | Returns False, no crash | As expected | Pass |
| U4.14 | `test_regression_server_error_is_not_reported_as_wrong_password` | Regression B1 | Hash function made to crash | RuntimeError is raised (not turned into False, i.e. not "wrong password") | As expected | Pass |
| U4.15 | `test_regression_startup_check_rejects_python_without_scrypt` | Regression B1 | Startup check with scrypt available, then removed | First check passes; second stops with a "no hashlib.scrypt" error | As expected | Pass |
| U4.16 | `test_invalid_tampered_hash_rejected` | Invalid: tampered hash | Real hash with its key changed | Returns False | As expected | Pass |

### Component 1: Upload pipeline (`TestGenerationComponent`), 13 tests

| ID | Test name | Purpose | Input | Expected result | Actual result | Pass/Fail |
|---|---|---|---|---|---|---|
| C1.1 | `test_success_pdf_text_flows_through_to_ai_and_back` | Success: a PDF goes through every step and comes back as a study pack | 2-page PDF; 4 cards and 3 questions asked; fake AI returns 2 cards, 1 question and a map | 200; the 2 cards, quiz answer "Oxygen" and the map come back; warning "Only 2 of 4 flashcards…"; the AI received both pages; AI called once; counted once | As expected | Pass |
| C1.2 | `test_success_pptx_upload` | Success: a PowerPoint goes through the same steps | PowerPoint with a title and speaker notes | 200; the AI received the slide title and the notes | As expected | Pass |
| C1.3 | `test_success_same_file_is_served_from_cache` | Success: the same file is reused from the cache | Same PDF uploaded twice | Second answer comes from the cache with the same cards; AI called once; counted once | As expected | Pass |
| C1.4 | `test_failure_ai_busy_tries_fallback_then_refunds` | Failure: AI is busy, backup model tried, attempt not counted | Fake AI says it is busy (429) | 503 "temporarily busy"; backup model also tried; not counted; nothing saved | As expected | Pass |
| C1.5 | `test_failure_unreadable_ai_reply_is_502_and_refunded` | Failure: AI sends back text in the wrong format | Fake AI replies "I'm sorry, I can't help with that." | 502 "could not be generated"; not counted; nothing saved | As expected | Pass |
| C1.6 | `test_failure_daily_limit_blocks_ai_call` | Failure: daily limit reached, AI not called | Daily limit set to 1; two different PDFs | First 200; second 429 "Daily limit of 1…"; AI called once | As expected | Pass |
| C1.7 | `test_failure_bad_upload_never_reaches_ai[wrong-type]` | Failure: wrong file type stops the upload | notes.docx | 415; AI not called; not counted | As expected | Pass |
| C1.8 | `…[corrupted-pdf]` | Failure: broken file stops the upload | Broken PDF (garbage bytes) | 400; AI not called; not counted | As expected | Pass |
| C1.9 | `…[empty-file]` | Failure: empty upload | Empty PDF (0 bytes) | 400; AI not called; not counted | As expected | Pass |
| C1.10 | `…[over-20-mb]` | Failure (boundary): file too large | PDF of 20 MB + 1 byte | 413; AI not called; not counted | As expected | Pass |
| C1.11 | `test_failure_missing_api_key_is_503_and_refunded` | Failure: AI not configured | No API key set | 503 "not configured"; AI never started; not counted | As expected | Pass |
| C1.12 | `test_unusual_timeout_is_504_and_stays_counted` | Unusual: AI is too slow | Time limit 0.2 s; fake AI takes 1 s | 504 "took too long"; still counted once (on purpose) | As expected | Pass |
| C1.13 | `test_failure_requires_sign_in` | Failure: not signed in | No login token | 401; AI not called | As expected | Pass |

### Component 2: Accounts (`TestAccountsComponent`), 11 tests

| ID | Test name | Purpose | Input | Expected result | Actual result | Pass/Fail |
|---|---|---|---|---|---|---|
| C2.1 | `test_success_register_then_login_then_me` | Success: sign up, log in, then open a protected page | Sign up as "  Student@Example.COM ", log in as "STUDENT@example.com", open /auth/me | All 200; email saved as "student@example.com"; database has a scrypt hash, not the password; token matches the user; 1 user saved | As expected | Pass |
| C2.2 | `test_failure_duplicate_email_in_different_case` | Failure: duplicate email | Sign up with dup@…, then DUP@… with another password | 409 "already exists"; still 1 user; first password works, second gets 401 | As expected | Pass |
| C2.3 | `test_failure_wrong_password_and_unknown_email` | Failure: bad credentials | Wrong password; email with no account | 401 "Incorrect password. Try again."; 404 "No account found…" | As expected | Pass |
| C2.4 | `test_failure_invalid_input_creates_no_user[bad-email]` | Failure: invalid email | Email "not-an-email" | 422 "valid email"; no user saved | As expected | Pass |
| C2.5 | `…[7-char-password]` | Failure (boundary): password too short, minimum is 8 | Password "1234567" (7 characters) | 422 about the password; no user saved | As expected | Pass |
| C2.6 | `…[missing-password]` | Failure: missing value | No password | 422 about the password; no user saved | As expected | Pass |
| C2.7 | `test_failure_protected_route_rejects_bad_tokens[no-header]` | Failure: not signed in | No login token | 401 "Please sign in again." | As expected | Pass |
| C2.8 | `…[junk-token]` | Failure: forged token | Fake token | 401 | As expected | Pass |
| C2.9 | `…[wrong-scheme]` | Failure: wrong header format | Wrong token format ("Token abc") | 401 | As expected | Pass |
| C2.10 | `…[token-for-missing-user]` | Unusual: valid token for a deleted user | Valid token for user 999, who does not exist | 401 | As expected | Pass |
| C2.11 | `test_unusual_login_rate_limit` | Unusual: too many attempts | Limit of 2 tries; 3 correct logins | First two 200, third 429 | As expected | Pass |

---

## 5. Other tests in the suite

These also run with the suite, but they are not part of the 4 units and 2 components.

| ID | Test name | Purpose | Input | Expected result | Actual result | Pass/Fail |
|---|---|---|---|---|---|---|
| A.1 | `TestCreateUser::test_normal_creates_user_and_returns_id` | Normal | New user "ada@example.com" | User id 1; saved with the same email and hash, and a date and time | As expected | Pass |
| A.2 | `…::test_normal_ids_increase_per_user` | Normal | Two different emails | Ids 1 and 2 | As expected | Pass |
| A.3 | `…::test_edge_email_is_stored_exactly_as_given` | Edge | "Mixed@Example.com" | Saved exactly as typed; a lowercase search finds nothing | As expected | Pass |
| A.4 | `…::test_edge_lookup_of_missing_user_returns_none` | Edge | Empty database | Both searches find nothing | As expected | Pass |
| A.5 | `…::test_invalid_duplicate_email_returns_none_and_keeps_original` | Invalid | Same email twice | Second returns nothing; first password kept; 1 user | As expected | Pass |
| A.6 | `…::test_invalid_null_values_raise_instead_of_looking_like_duplicates` | Regression B2 | Missing email; missing password | Database error raised (not "email exists"); no user saved | As expected | Pass |
| D.1 | `TestDailyLimit::test_normal_reservations_until_limit` | Normal | Limit 3, three requests | Ids 1, 2, 3 | As expected | Pass |
| D.2 | `…::test_boundary_request_after_limit_is_refused` | Boundary | Limit 2, three requests | Third refused; 2 saved | As expected | Pass |
| D.3 | `…::test_edge_limit_zero_refuses_immediately` | Edge | Limit 0 | Refused right away | As expected | Pass |
| D.4 | `…::test_edge_limit_is_per_user` | Edge | User A at limit 1, then user B | A refused; B allowed | As expected | Pass |
| D.5 | `…::test_edge_24_hour_window_boundary` | Boundary (mocked clock) | Fake clock: start, 1 second before 24 h, exactly 24 h | Refused, then allowed at exactly 24 h | As expected | Pass |
| D.6 | `…::test_refund_frees_a_slot` | Normal | Reserve, give back, reserve again | Second reservation allowed | As expected | Pass |
| D.7 | `…::test_invalid_refund_of_unknown_id_is_harmless` | Invalid | Give back an id that does not exist (9999) | No error; 1 row kept | As expected | Pass |
| D.8 | `…::test_invalid_unknown_user_raises_and_releases_lock` | Invalid | Request for user 9999, who does not exist | Database error; the next request still works | As expected | Pass |
| S.1 | `TestSavedSetsComponent::test_success_save_list_update_delete` | Success | Save, rename, list, delete | Same id after rename; list shows "renamed.pdf"; delete works; list is empty | As expected | Pass |
| S.2 | `…::test_success_unsafe_diagram_lines_are_stripped` | Success | Map with click, style and <img> lines | Saved map is exactly: flowchart TD, A["x"] --> B["y"] | As expected | Pass |
| S.3 | `…::test_failure_other_user_cannot_read_change_or_delete` | Failure | User B uses user A's set id | B sees nothing; delete gives 404; save makes a new set; A's set unchanged | As expected | Pass |
| S.4 | `…::test_failure_invalid_set_is_rejected_and_not_saved[answer-not-in-choices]` | Failure | Answer "Z" that is not one of the choices | 422 "does not match its choices"; nothing saved | As expected | Pass |
| S.5 | `…[not-a-flowchart]` | Failure | Map that is not a flowchart | 422 "readable concept map"; nothing saved | As expected | Pass |
| S.6 | `…[three-choices]` | Failure | Only 3 choices | 422 about the choices; nothing saved | As expected | Pass |
| S.7 | `…[empty-filename]` | Failure | Empty file name | 422 about the file name; nothing saved | As expected | Pass |
| S.8 | `…::test_unusual_saved_set_limit` | Unusual | Limit 1: save, save again, update | 200, 409, 200 | As expected | Pass |
| O.1–O.6 | `test_core.py`: `test_parse`, `test_finish_and_even_selection`, `test_quotas_cover_everything`, `test_pptx_reading`, `test_db_and_security`, `test_daily_limit_refund_and_dedupe` | Older tests from before Assignment 4 (several checks each) | Varied | Their own assertions | As expected | Pass (6/6) |

---

## 6. Checking that the tests can fail

To make sure the tests really catch mistakes, we put one bug at a time into a copy of the code (not the real code) and ran the tests. Every bug was caught:

| Planted bug | Tests that failed |
|---|---|
| Daily limit off by one (`used > limit`) | 7 |
| Failed AI call not refunded | 3 |
| Size check lets 20 MB + 1 byte through | 2 (U1.4, C1.10) |
| `verify_password` always returns `True` | 15 |
| Duplicate quiz choices not rejected | 1 |
| A user can overwrite another user's saved set | 2 (S.3, O.5) |
| B1 fix undone (`except Exception` back in `verify_password`) | 1 (U4.14) |
| B2 fix undone (`create_user` returns `None` for every `IntegrityError`) | 1 (A.6) |
| B3 fix undone (all lines kept in the Mermaid map) | 2 (U3.6, U3.7) |

---

## 7. How to install and run the tests

Run all commands from the `backend/` folder. You need Python **3.10 or newer** (from python.org, Homebrew, conda or the Microsoft Store). The Python built into macOS will not work (see bug B1). You do not need a `.env` file, an API key or internet.

### macOS

```bash
cd learn-it-your-way/backend
python3 -c "import hashlib; print(hasattr(hashlib, 'scrypt'))"   # must print True
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt

python -m pytest tests/test_unit.py -v          # unit tests
python -m pytest tests/test_component.py -v     # component tests
python -m pytest tests -v                       # all tests (102)
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

If PowerShell blocks the activation script, run this once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

---

## 8. Bugs, remaining failures and limitations

### 8.1 Bugs found and fixed

We fixed each bug after the team agreed. Each one now has a test that would fail if the bug came back.

**B1 (high): sign-up and login did not work on our Python setup.**
Our virtual environment was using the Python built into macOS (3.9.6), which cannot do scrypt hashing. Sign-up crashed with an HTTP 500 error, and every login said "Incorrect password" because the real error was hidden. This one problem made 32 of our 96 tests fail at that time. We rebuilt the environment with Python 3.13, made the app stop at startup with a clear message if scrypt is missing, and stopped hiding real errors. Tests: U4.14, U4.15.

**B2 (low): a database error could look like "email already exists".**
`create_user` treated any database error as a duplicate email, which would show the wrong message. Now only a real duplicate email gives that message. Tests: A.6, with A.5 and C2.2 checking duplicate emails.

**B3 (medium): chat text after the concept map could break the map (found by U3.6).**
If the AI added a line like "Hope this helps!" after the map, it ended up inside the map code, which would likely stop the map from drawing. Now only real map lines are kept. Tests: U3.6, U3.7.

### 8.2 Remaining failures

**None.** 102 passed, 0 failed (`python -m pytest tests -v`).

### 8.3 Testing limitations

- **The AI is always faked.** The tests show our code handles the AI's replies and errors correctly, but not that the real Gemini always answers in the right format.
- **Some features are not tested:** sending a whole PDF to the AI, large PDFs over 12 MB, and pictures in PowerPoint slides.
- **Our sample files are small**, with one line of text per page. Real lectures may be read differently.
- **The frontend and speed are not tested here.** Flip cards, the quiz screen, drawing the map and response time need manual testing.
- **Other limits:** many users at once and real time passing (the 24-hour limit uses a fake clock) are not tested. We ran the tests on macOS; the Windows commands were not tried.