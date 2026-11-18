# Learn It Your Way: Software Requirements Document

Team: Ritu Tripathi, Topendra Singh
Course: CSCI 5801 Software Engineering, Youngstown State University
Instructor / Project Manager: Dr. Debojyoti Biswas

The structure of this document follows the requirements document outline from
Chapter 4 (Requirements Engineering). The test plan in the appendix follows
Chapter 8 (Software Testing). The rules for AI agents follow the Agent
Architectures lecture.

---

## 1. Preface

**Intended readers:** the development team, the instructor, and AI coding agents
(Claude Code) that build and test the system.

**Version history**

| Version | Date | Change |
| --- | --- | --- |
| 1.0 | Assignment 1 | First user, system, functional, non-functional, and usability requirements. |
| 1.1 | Nov 2026 | Requirements given unique IDs for traceability (Ch4). Non-functional requirements split into product, organisational, and external types and rewritten as verifiable statements. Requirements-based test plan added (Ch8). |
| 1.2 | Nov 2026 | Updated to match the current implementation (requirements change management, Ch4): one `/study/generate` request returns flashcards, quiz, and concept map; quiz, accounts, saved sets, cache, daily limit, and sign-in rate limit recorded as FR-8 to FR-14. |

---

## 2. Introduction

Learn It Your Way is a web application that turns lecture materials (PDF and
PowerPoint files) into interactive study formats. A student uploads a file; the
system reads the lecture, sends it to an AI model (Google Gemini) in a single
request, and returns one study pack: flashcards, a quiz with explained answers,
and a visual concept map. Users sign in to save study sets and open them on any
device.

**Need for the system:** students spend a lot of time turning lecture slides into
study material by hand. The system automates this so students can study more
efficiently.

**System type (Ch6 application architectures):** an interactive
transaction-processing system. Each upload is one transaction: the user submits
a file, the system processes it, and a result is returned.

**Stakeholders**

| Stakeholder | Role |
| --- | --- |
| Students | End users who upload lectures and study. |
| Development team | Ritu Tripathi (backend, AI pipeline), Topendra Singh (frontend, design). |
| Project manager | Dr. Debojyoti Biswas. |
| Third-party provider | Google, provider of the Gemini API the system depends on. |

**Development method:** Agile (Ch3). Requirements are developed incrementally;
features added after Assignment 1 are recorded in Section 6.4 and in the
version history (Ch4 requirements change management).

---

## 3. Glossary

| Term | Meaning |
| --- | --- |
| Lecture file | A PDF (.pdf) or PowerPoint (.pptx) file uploaded by a student. |
| Flashcard | A question/answer pair generated from the lecture content. |
| Concept map | A diagram showing how the lecture's main ideas connect, written in Mermaid syntax and drawn by Mermaid.js. |
| Study pack | The flashcards, quiz, and concept map produced from one lecture by one AI request. |
| Study set | A saved study pack that belongs to one account. |
| Gemini | Google's AI model API used to generate content. The model name is set by `GEMINI_MODEL` in `.env`. |
| Auto generate | Option where the app chooses the number of cards and questions from the lecture length. |
| Login token | A signed token (JWT) returned at sign-in and sent with every study request. |
| Rate limit (429) | Error returned by Gemini when the free-tier quota is used up. |
| Daily generation limit | Maximum number of AI generations one user may request per day. |
| Mock / fake | A test replacement for an external dependency such as Gemini or the database. |

---

## 4. User requirements definition

User requirements are written in natural language for non-technical readers
(Ch4).

| ID | User requirement |
| --- | --- |
| UR-1 | A student can upload a lecture file (PDF or PowerPoint) through a simple interface. |
| UR-2 | A student can generate flashcards from the uploaded file's content. |
| UR-3 | A student can generate a concept map showing how the lecture's main ideas connect. |
| UR-4 | A student receives a clear message if a file is unsupported or too large. |
| UR-5 | A student can review flashcards in a flip-card format. |
| UR-7 | A student can take a quiz on the lecture, see the correct answers with explanations, and retry as often as they like. *(added after Assignment 1)* |
| UR-6 | A student can create an account, log in, and come back later to saved study sets. *(added after Assignment 1)* |

---

## 5. System architecture

The system uses a **client-server** architecture (Ch6). The backend is organised
in **layers**, and the frontend follows a view/controller split.

| Layer / component | Implementation | Responsibility |
| --- | --- | --- |
| Presentation (client) | React + Vite, Mermaid.js, KaTeX (`frontend/src/App.jsx`, `RichText.jsx`) | Upload form, tabs for flashcards, quiz, and concept map; math typesetting. |
| API layer | FastAPI, `backend/main.py` | Routes for accounts, generation, and saved sets; validates input; returns JSON or error responses. |
| AI pipeline | `backend/study_ai.py` | Reads PDF and PPTX lectures, builds the prompt, calls Gemini, parses the reply into a study pack. |
| Security | `backend/security.py` | scrypt password hashing, login tokens (JWT), sign-in rate limiter. |
| Data layer | `backend/database.py` (SQLite) | Users, study sets, cached results, daily generation counts. |
| External service | Google Gemini API | Generates the study pack. |

Configuration (the Gemini API key, the login-token secret, the database path,
limits) is read from a `.env` file that is not stored in version control.

---

## 6. System requirements specification

### 6.1 Functional requirements

Functional requirements state the services the system provides and how it
reacts to inputs (Ch4). Each one traces back to a user requirement.

| ID | The system shall... | Traces to |
| --- | --- | --- |
| FR-1 | accept an uploaded lecture file in PDF or PPTX format. | UR-1 |
| FR-2 | extract the text content from the uploaded file, using pypdf for PDF and python-pptx for PPTX. | UR-1, UR-2 |
| FR-3 | send the lecture content to the Gemini API in one request (`POST /study/generate`) and return a study pack with flashcards, quiz questions, and a concept map. | UR-2, UR-3, UR-7 |
| FR-4 | return the concept map in Mermaid syntax, filtered before display. | UR-3 |
| FR-5 | display flashcards in a flippable card interface. | UR-5 |
| FR-6 | render the concept map visually on the frontend with Mermaid.js. | UR-3 |
| FR-7 | reject unsupported file types and files over 20 MB with a descriptive error message, without calling the AI. | UR-4 |

### 6.2 Non-functional requirements

Non-functional requirements are grouped as product, organisational, and
external requirements (Ch4). Each is written as a verifiable statement with a
measurable criterion, not just a goal. Numbers marked "proposed" are targets
the team should confirm.

| ID | Type | Requirement (verifiable form) | Measure |
| --- | --- | --- | --- |
| NFR-1 | Product: performance | A study pack for a typical lecture (about 20 slides) is shown within 30 seconds of upload, including AI response time. *(proposed)* The AI step never waits longer than `AI_TIMEOUT_SECONDS` (default 150). | Response time (seconds) |
| NFR-2 | Product: reliability | When the Gemini API fails (for example a 429 rate limit or a timeout), the backend returns an error response with a readable message instead of crashing; 0 unhandled server errors (HTTP 500) in tests. Failed attempts do not count toward the daily limit. | Percentage of AI failure cases handled |
| NFR-3 | Product: size | Files up to and including 20 MB are accepted; larger files are rejected. PDFs over `MAX_PDF_PAGES` (default 400) are rejected. | File size (MB), page count |
| NFR-4 | Product: security | Passwords are stored only as salted scrypt hashes, never as plain text. Study routes require a valid login token. | Database inspection / unit test |
| NFR-5 | Organisational: security | API keys, the login-token secret (`.jwt_secret`), and database files never appear in version control or in the frontend code. | Listed in `.gitignore`; repository search finds no key |
| NFR-6 | Organisational: portability | The backend installs and runs on both Mac and Windows with the commands in the README. | Number of target platforms (2) |
| NFR-7 | Organisational: maintainability | Backend, frontend, and AI pipeline code are kept in separate modules (Section 5). | Code review |
| NFR-8 | External: third-party service | The system works within the Gemini free-tier rate limits by caching repeated requests and limiting generations per user per day. | Number of AI calls per repeated upload |

### 6.3 Usability requirements (product)

| ID | Requirement | Measure |
| --- | --- | --- |
| US-1 | A new user can upload a document and create flashcards without instructions. | First-time user completes the task without help |
| US-2 | Error messages state what went wrong and what to do (for example, "Only PDF and PPTX files are supported"). | Review of all error messages |
| US-3 | Creating a study pack takes only clicks or taps after sign-in; no typing is required. | Number of typed inputs (0) |
| US-4 | The concept map can be scrolled and zoomed, and long flashcards scroll inside the card. | Manual check |
| US-5 | The layout works on phones. | Manual check on a phone-sized screen |

### 6.4 Requirements added after Assignment 1 (incremental development)

These were added during development (Ch3 agile, Ch4 requirements change) and
are implemented in the current version.

| ID | The system shall... | Traces to |
| --- | --- | --- |
| FR-8 | let a user register with an email and password (`POST /auth/register`) and log in (`POST /auth/login`), returning a login token. A duplicate email is rejected. | UR-6, NFR-4 |
| FR-9 | let a logged-in user list, save, and delete study sets (`/study/sets`). A user cannot see or delete another user's study set. | UR-6 |
| FR-10 | reuse the stored result when the same file is uploaded with the same options, without calling Gemini again (cache). | NFR-8 |
| FR-11 | limit new study packs per user per 24 hours (`GENERATIONS_PER_DAY`, default 15) and return a clear message when the limit is reached. | NFR-8 |
| FR-12 | let the user choose 4 to 50 flashcards and 3 to 30 quiz questions, or Auto generate, where the counts follow the lecture length. Out-of-range counts are rejected or clamped. | UR-2, UR-7 |
| FR-13 | show the correct answer and an explanation for each quiz question after checking, allow unlimited retries, and track tries and best score. | UR-7 |
| FR-14 | limit sign-in and sign-up attempts per IP address (`LOGIN_ATTEMPTS_PER_15_MIN`, default 15 per 15 minutes). | NFR-4 |
| FR-15 | report file length and suggested counts without using the AI (`POST /study/inspect`). | UR-2 |

### 6.5 Domain requirements

| ID | Requirement |
| --- | --- |
| DR-1 | Lecture slides often contain little text per slide. Content from all slides and pages (text, tables, typed equations, speaker notes) must be combined in order, and the lecture split into sections so later slides also get cards and questions. |
| DR-2 | Lecture files may contain no extractable text (for example, scanned images). The system must report this instead of sending empty text to the AI. |

---

## 7. Structured specifications for key requirements

Form-based specifications (Ch4) for the requirements most important to test.

**FR-7: Validate uploaded file**

| Field | Value |
| --- | --- |
| Function | Validate an uploaded lecture file. |
| Description | Checks the file type and size before any processing. |
| Inputs | File name, file content (bytes). Source: user upload form. |
| Outputs | Accepted file passed on to text extraction, or an error response. Destination: API caller. |
| Action | If the extension is not .pdf or .pptx, reject the file. If the size is over 20 MB, reject it. Otherwise accept it. |
| Precondition | A file was uploaded. |
| Postcondition | Only valid files reach text extraction and the AI. |
| Side effects | None. A rejected file never calls Gemini or counts toward the daily limit. |

**FR-3: Generate study pack**

| Field | Value |
| --- | --- |
| Function | Generate a study pack from a lecture (`POST /study/generate`). |
| Inputs | Lecture file; `card_count`, `quiz_count` (0 means auto); `visual` option; login token. |
| Outputs | Flashcards (question, answer), quiz questions (choices, correct answer, explanation), and a Mermaid concept map. |
| Action | If a cached result exists, return it (FR-10). Otherwise build the prompt, call Gemini once, and parse the reply into a study pack. |
| Precondition | The user is signed in; the file is valid; the lecture has content; the user is under the daily limit. |
| Postcondition | The study pack is returned and cached. |
| Side effects | One generation is recorded for the user only if it succeeds (FR-11, NFR-2). |
| Failure | If Gemini fails or returns output that cannot be parsed, an error message is returned (NFR-2). |

---

## 8. Usage scenario

A scenario is a structured story: starting situation, normal flow, what can go
wrong, and end state (Ch4).

**Scenario: Maya studies for an exam**

- **Starting situation:** Maya is signed in and has the Chapter 8 slides saved as a .pptx file.
- **Normal flow:** She uploads the file and chooses 15 flashcards and 10 quiz questions. The system checks the file, reads the lecture, calls Gemini once, and shows tabs for Flashcards, Quiz, and Concept map. She takes the quiz twice, sees the explanations, and saves the study set.
- **What can go wrong:** (1) She uploads a .docx file, and the system says only PDF and PPTX are supported. (2) The Gemini quota is used up (429), and the system says the AI service is busy and to try again later. (3) She reaches the daily limit, and the system tells her so.
- **End state:** The study set is saved under her account, and she can reopen it the next day from any device.

---

## 9. System evolution

Planned changes that the design should allow for: deployment to a public server
with a persistent disk; moving `database.py` to a shared database such as
Postgres for more than one server; a shared rate limiter across server
processes; support for more file types; lecture videos as input.

---

## Appendix A. Test plan (Chapter 8)

### A.1 Testing levels

| Level | What is tested | What is replaced |
| --- | --- | --- |
| Unit | One function or class in isolation (for example file validation, lecture reading, AI reply parsing, password hashing, count limits). | Gemini and the database are replaced by fakes or mocks. |
| Component | Several units working together through their interface (for example `/study/generate` with validation, lecture reading, mocked AI, cache, and daily limit; the account flow with security and database). | Gemini is mocked; the database is a temporary test database. |
| System / release | The whole app end to end, including the frontend. | Nothing; manual, outside Assignment 4. |

### A.2 How test cases are chosen

- **Requirements-based testing:** every requirement in Sections 6.1 to 6.5 that the backend implements has at least one test.
- **Partition testing:** inputs are split into equivalence partitions, and at least one test is chosen from each. For example, for file size: 0 bytes, normal size, exactly 20 MB (boundary), and just over 20 MB.
- **Guideline-based testing:** choose inputs that force every error message, test empty input and single-item input, and repeat the same input to check the cache (FR-10) and the daily limit (FR-11).
- **Interface testing (components):** test the parameter and procedural interfaces between layers. Make the called component fail (Gemini raises a 429 error), pass missing values (no file, empty password), and check for interface misunderstanding (the AI returns malformed or unreadable output instead of the tagged text format).
- **Automated tests:** each test has a setup part, a call part, and an assertion part that compares the actual result with a specific expected result. Run them all as a regression suite after every change.

### A.3 Traceability matrix (requirement to test)

| Requirement | Unit tests | Component tests |
| --- | --- | --- |
| FR-1, FR-7, NFR-3 | File validation: valid PDF/PPTX, wrong type, size boundary | Upload endpoint rejects bad files without calling Gemini |
| FR-2, DR-1, DR-2 | Text extraction: known text, multiple slides in order, empty file | |
| FR-3, FR-4, NFR-2 | AI reply parsing: valid output, extra text around the tagged output, malformed output; concept map filtering | `/study/generate` with mocked Gemini: success, 429 error, bad output |
| FR-8, FR-14, NFR-4 | Password hashing and verification; login token; rate limiter | Register and log in through the API with a temporary database; duplicate email; study route without a token is refused |
| FR-9 | | Save and list a study set; another user cannot see or delete it |
| FR-10, FR-11, NFR-8 | Daily limit counter: under, at, and over the limit | Second identical upload uses the cache (mock called once); failed generation is not counted |
| FR-12 | Count limits: 4 and 50 cards, 3 and 30 questions (boundaries), 0 = auto, out of range | |
| FR-5, FR-6, FR-13, US-1 to US-5, NFR-1 | Manual testing (frontend and timing are outside automated tests) | |

---

## Appendix B. Rules for AI agents (Claude Code)

Based on the Agent Architectures lecture (least privilege, sandboxing, safety).

- Read this file and the assignment before writing code or tests.
- Only the tools the task needs: read and edit files in `backend/`, run `python -m pytest`. No web access is needed.
- Never read, print, or commit `.env` or any API key.
- Never call the real Gemini API in tests. Use mocks or fakes.
- Never modify the real database file (`learn_it.db`) or `.jwt_secret`. Use a temporary database (for example pytest `tmp_path` with `DATABASE_PATH`).
- Put unit tests in `backend/tests/test_unit.py` and component tests in `backend/tests/test_component.py`.
- In each test's docstring, name the requirement IDs it covers (for example "Covers FR-7, NFR-3").
- Each test must assert a specific expected result. Avoid tests that always pass.
- Report failing tests honestly. Ask the team before changing application code to fix a bug.
- Run the full suite from `backend/` with: `python -m pytest tests -v`