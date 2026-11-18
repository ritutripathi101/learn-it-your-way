import asyncio
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

import database as db  # noqa: E402
import security  # noqa: E402
import study_ai  # noqa: E402

MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024
AI_REQUEST_TIMEOUT_SECONDS = int(os.getenv("AI_TIMEOUT_SECONDS", "150"))
DAILY_LIMIT = int(os.getenv("GENERATIONS_PER_DAY", "15"))  # new AI study packs per user per 24 hours
MAX_PDF_PAGES = int(os.getenv("MAX_PDF_PAGES", "400"))
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("learn-it")

db.init_db()
app = FastAPI(title="Learn It Your Way API", version="2.0.0")
allowed_origins = [
    o.strip()
    for o in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)
# Sign-in / sign-up attempts per IP per 15 minutes (per server process). The daily AI limit lives in the database.
login_limiter = security.RateLimiter(int(os.getenv("LOGIN_ATTEMPTS_PER_15_MIN", "15")), 900)


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    field = str(first.get("loc", ["input"])[-1])
    return JSONResponse(status_code=422, content={"detail": f"Please check the {field} field. {first.get('msg', '')}".strip()})


@app.get("/health")
def health_check():
    return {"status": "ok", "ai_configured": bool(os.getenv("GEMINI_API_KEY"))}


# ----------------------------------------------------------------------------- accounts
class Credentials(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=8, max_length=200)


def current_user(authorization: Optional[str] = Header(None)) -> dict:
    token = authorization[7:] if authorization and authorization.lower().startswith("bearer ") else ""
    user_id = security.read_token(token) if token else None
    user = db.get_user(user_id) if user_id else None
    if not user:
        raise HTTPException(status_code=401, detail="Please sign in again.")
    return user


def _auth_response(user_id: int, email: str):
    return {"token": security.make_token(user_id), "email": email}


@app.post("/auth/register")
def register(body: Credentials, request: Request):
    email = body.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="Enter a valid email address.")
    if not login_limiter.hit(f"reg:{request.client.host if request.client else '?'}"):
        raise HTTPException(status_code=429, detail="Too many attempts. Try again in a few minutes.")
    user_id = db.create_user(email, security.hash_password(body.password))
    if user_id is None:
        raise HTTPException(status_code=409, detail="An account with this email already exists. Sign in instead.")
    return _auth_response(user_id, email)


@app.post("/auth/login")
def login(body: Credentials, request: Request):
    email = body.email.strip().lower()
    if not login_limiter.hit(f"login:{request.client.host if request.client else '?'}"):
        raise HTTPException(status_code=429, detail="Too many attempts. Try again in a few minutes.")
    user = db.get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="No account found for this email. Create an account first.")
    if not security.verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect password. Try again.")
    return _auth_response(user["id"], user["email"])


@app.get("/auth/me")
def me(user: dict = Depends(current_user)):
    return {"email": user["email"]}


# ----------------------------------------------------------------------------- reading uploads
async def read_lecture(file: UploadFile, visual: bool):
    filename = (file.filename or "").strip()
    extension = os.path.splitext(filename)[1].lower()
    if extension not in {".pdf", ".pptx"}:
        raise HTTPException(status_code=415, detail="Unsupported file type. Upload a PDF or PowerPoint (.pptx) file.")
    data = await file.read(MAX_FILE_SIZE_BYTES + 1)
    if len(data) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="This file is larger than 20 MB. Choose a smaller lecture file.")
    if not data:
        raise HTTPException(status_code=400, detail="The selected file is empty.")
    try:
        lecture = await asyncio.to_thread(study_ai.read_lecture, extension, data, visual)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="We couldn't read this file. It may be corrupted or password-protected.") from exc
    if lecture.kind == "pdf" and len(lecture.units) > MAX_PDF_PAGES:
        raise HTTPException(status_code=413, detail=f"This PDF has {len(lecture.units)} pages. The limit is {MAX_PDF_PAGES}; split it into parts.")
    if not any(u.strip() for u in lecture.units) and not lecture.has_visuals:
        raise HTTPException(status_code=422, detail="No readable text was found. Turn on 'Read equations and diagrams' or try another file.")
    return filename, data, lecture


@app.post("/study/inspect")
async def inspect(file: UploadFile = File(...), user: dict = Depends(current_user)):
    """Free (no AI): how long is this file and how many cards and questions suit it."""
    _filename, _data, lecture = await read_lecture(file, True)
    cards, quiz = study_ai.suggest_counts(lecture)
    return {
        "units": len(lecture.units), "unitLabel": lecture.label, "words": lecture.words,
        "visualAvailable": lecture.has_visuals, "suggestedCards": cards, "suggestedQuiz": quiz,
        "minCards": study_ai.MIN_CARDS, "maxCards": study_ai.MAX_CARDS,
        "minQuiz": study_ai.MIN_QUIZ, "maxQuiz": study_ai.MAX_QUIZ,
    }


async def run_ai(lecture, cards: int, quiz: int):
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(study_ai.generate_pack, lecture, cards, quiz), timeout=AI_REQUEST_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail="The study pack took too long to generate. Please try again.") from exc
    except Exception as exc:
        message = str(exc).casefold()
        code = getattr(exc, "code", None)
        status = str(getattr(exc, "status", "")).casefold()
        logger.error("Generation failed (%s, code=%s, status=%s): %s", type(exc).__name__, code, status or "unknown", str(exc)[:600])
        if "api key" in message or "not configured" in message or "unauthorized" in message:
            raise HTTPException(status_code=503, detail="AI generation is not configured correctly. Check the backend API key.") from exc
        if code in (429, 503) or status in {"resource_exhausted", "unavailable"} or any(
            p in message for p in ("quota", "rate limit", "429", "high demand", "unavailable")
        ):
            raise HTTPException(status_code=503, detail="The AI service is temporarily busy. Please try again in a moment.") from exc
        if code == 404 or "not found" in message:
            raise HTTPException(status_code=502, detail="The configured Gemini model was not found. Check GEMINI_MODEL in the backend .env file.") from exc
        raise HTTPException(status_code=502, detail="The study pack could not be generated. Please try again with a different file.") from exc


# ----------------------------------------------------------------------------- study packs
@app.post("/study/generate")
async def generate(
    file: UploadFile = File(...),
    card_count: Optional[int] = Form(None),
    quiz_count: Optional[int] = Form(None),
    visual: bool = Form(True),
    user: dict = Depends(current_user),
):
    filename, data, lecture = await read_lecture(file, visual)
    suggested_cards, suggested_quiz = study_ai.suggest_counts(lecture)
    cards = study_ai.clamp(card_count or suggested_cards, study_ai.MIN_CARDS, study_ai.MAX_CARDS)
    quiz = study_ai.clamp(quiz_count or suggested_quiz, study_ai.MIN_QUIZ, study_ai.MAX_QUIZ)
    key = study_ai.cache_key(data, cards, quiz, visual)
    pack = db.cache_get(key)  # same file + same options: reuse, no AI tokens spent
    cached = pack is not None
    if not cached:
        generation_id = db.reserve_generation(user["id"], DAILY_LIMIT)
        if generation_id is None:
            raise HTTPException(
                status_code=429,
                detail=f"Daily limit of {DAILY_LIMIT} new study packs reached. Saved and previously generated sets are still free to open.",
            )
        try:
            pack = await run_ai(lecture, cards, quiz)
        except HTTPException as exc:
            if exc.status_code != 504:  # a timeout may still have used the AI, so it stays counted
                db.refund_generation(generation_id)
            raise
        db.cache_put(key, pack)
    return {"id": uuid.uuid4().hex, "filename": filename, "cached": cached,
            "createdAt": datetime.now(timezone.utc).isoformat(), **pack}


# ----------------------------------------------------------------------------- saved sets
class CardIn(BaseModel):
    question: str = Field(max_length=4000)
    answer: str = Field(max_length=4000)
    source: Optional[int] = None


class QuizIn(BaseModel):
    question: str = Field(max_length=4000)
    choices: List[str] = Field(min_length=4, max_length=4)
    answer: str = Field(max_length=2000)
    explanation: str = Field("", max_length=4000)
    source: Optional[int] = None


class StudySetIn(BaseModel):
    id: Optional[str] = Field(None, max_length=64)
    filename: str = Field(min_length=1, max_length=255)
    flashcards: List[CardIn] = Field(max_length=100)
    quiz: List[QuizIn] = Field(max_length=100)
    diagram: str = Field(max_length=12_000)


@app.get("/study/sets")
def list_sets(user: dict = Depends(current_user)):
    return db.list_sets(user["id"])


@app.post("/study/sets")
def save_set(body: StudySetIn, user: dict = Depends(current_user)):
    try:
        diagram = study_ai.sanitize_diagram(body.diagram)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    for item in body.quiz:
        if item.answer not in item.choices:
            raise HTTPException(status_code=422, detail="A quiz answer does not match its choices.")
    data = body.model_dump()
    data["diagram"] = diagram
    try:
        return db.save_set(user["id"], data)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.delete("/study/sets/{set_id}")
def delete_set(set_id: str, user: dict = Depends(current_user)):
    if not db.delete_set(user["id"], set_id):
        raise HTTPException(status_code=404, detail="That study set was not found.")
    return {"ok": True}