# Learn It Your Way

Upload a lecture (PDF or PowerPoint) and get one complete study pack: **flashcards**, a **quiz** with explained answers and unlimited retries, and a **concept map**. Sign in to save study sets and open them on any device.

## Features

- **One request, three study formats.** Flashcards, quiz and concept map come from a single AI request, which keeps usage low.
- **Reuse instead of regenerating.** The same file with the same options is served from a stored result with no new AI usage.
- **You choose the size.** Pick the number of flashcards (4-50) and quiz questions (3-30), or choose **Auto generate** and let the app size the pack to the lecture length.
- **Whole-lecture coverage.** The lecture is split into sections, and each section gets its own share of cards and questions, so later slides are not skipped.
- **Math and diagrams.** PDFs can be read as PDFs, so equations, tables, charts and diagrams are seen. PowerPoint text, tables, typed equations, speaker notes and slide pictures are read. Math is typeset with KaTeX.
- **Quiz.** Correct answers and explanations after checking, unlimited tries, tries counter and best score.
- **Accounts and sync.** Email and password sign-in. Saved sets belong to the account and are private to it.
- **Easy to use.** One tab per study format (Flashcards, Quiz, Concept map). Long flashcards scroll inside the card. The concept map scrolls and zooms. The layout works on phones.

## Project structure

```
backend/
  main.py          API routes (accounts, generation, saved sets)
  study_ai.py      reads lectures, builds the prompt, parses the AI reply
  database.py      SQLite storage (accounts, sets, cache, daily limit)
  security.py      password hashing, login tokens, rate limiter
  tests/           logic tests
  requirements.txt
  .env.example
frontend/
  src/App.jsx      the app
  src/RichText.jsx math typesetting
  src/App.css      styles
```

## Run locally

You need Python 3.9 or newer, Node.js, and a Gemini API key. Every teammate should use their own key.

### 1. Backend

From the `backend` folder:

```sh
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # Windows: copy .env.example .env
```

Open `.env` and set `GEMINI_API_KEY`. Then start the server:

```sh
uvicorn main:app --reload --port 8000
```

Check http://127.0.0.1:8000/health. It should show `"status":"ok"` and `"ai_configured":true`. The database file is created automatically.

### 2. Frontend

In a second terminal, from the `frontend` folder:

```sh
npm install
npm run dev
```

Open the link it prints (normally http://localhost:5173). If the backend is not at `http://127.0.0.1:8000`, set `VITE_API_URL` in `frontend/.env`.

## Configuration (backend `.env`)

| Variable | Purpose | Default |
| --- | --- | --- |
| `GEMINI_API_KEY` | Required for generation. Backend only, never in the browser. | none |
| `GEMINI_MODEL` | Gemini model name. Make sure it is valid for your key. | see `.env.example` |
| `GEMINI_FALLBACK_MODEL` | Used once if the main model is busy. | see `.env.example` |
| `JWT_SECRET` | Signs login tokens. **Set a long random value in production.** If empty, a local secret is created in `backend/.jwt_secret`. | auto (development) |
| `FRONTEND_ORIGINS` | Comma-separated allowed browser origins. | `http://localhost:5173,http://127.0.0.1:5173` |
| `DATABASE_PATH` | Location of the SQLite file. | `backend/learn_it.db` |
| `GENERATIONS_PER_DAY` | New study packs per user per 24 hours. Failed attempts are not counted. | `15` |
| `MAX_PDF_PAGES` | Page limit for PDFs. | `400` |
| `AI_TIMEOUT_SECONDS` | Longest wait for the AI step. | `150` |
| `LOGIN_ATTEMPTS_PER_15_MIN` | Sign-in and sign-up attempts per IP. | `15` |

Generate a secret with: `python -c "import secrets; print(secrets.token_urlsafe(48))"`

## API

All study routes need the header `Authorization: Bearer <token>`.

| Route | What it does |
| --- | --- |
| `POST /auth/register`, `POST /auth/login` | Return `{ token, email }` |
| `GET /auth/me` | Current account |
| `POST /study/generate` | Multipart form: `file`, `card_count`, `quiz_count`, `visual`. A count of `0` or no value means auto. `visual` (default true) turns on reading equations and diagrams. Returns the whole study pack. |
| `POST /study/inspect` | Reports file length and suggested counts, with no AI use |
| `GET /study/sets`, `POST /study/sets`, `DELETE /study/sets/{id}` | List, save and remove saved sets |
| `GET /health` | Server status |

## Security notes

- Never commit or share `.env`, `.jwt_secret` or the database files. If an API key is ever exposed, revoke it and create a new one.
- Passwords are stored as salted scrypt hashes. Saved sets are private to their owner.
- Uploaded lecture text is treated as untrusted content, and generated concept maps are filtered before display.
- Sign-in is rate limited, and each account has a daily limit on new study packs.

## Tests

From `backend` with the virtual environment active:

    pip install -r requirements.txt
    python -m pytest tests -v                      # all tests
    python -m pytest tests/test_unit.py -v         # unit tests
    python -m pytest tests/test_component.py -v    # component tests

Tests never call the real Gemini API and never touch learn_it.db. Gemini is mocked and each test uses a temporary database.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `uvicorn` not found | Activate the virtual environment in that terminal. |
| "Cannot reach the server" | Start the backend, or set `VITE_API_URL` to its address. |
| "AI generation is not configured" | Set `GEMINI_API_KEY` in `backend/.env`, then restart uvicorn. |
| "Model not found" | Fix `GEMINI_MODEL` in `.env`. |
| "Temporarily busy" | The free tier has per-minute and daily limits. Wait a moment and retry. |
| Math shows as raw `$...$` | Run `npm install` so KaTeX is installed, then restart `npm run dev`. |

## Limitations

- Study material is produced by an AI model and can contain mistakes, so check important answers against the lecture.
- Very large decks with many pictures are sampled, so not every image is read.
- Very large PDFs are uploaded to the model separately, and if that fails the app falls back to the PDF's text only (a notice is shown).