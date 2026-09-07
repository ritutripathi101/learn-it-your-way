import os
import json
from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pypdf import PdfReader
from pptx import Presentation
import google.generativeai as genai
import io

load_dotenv()  # reads your .env file

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-flash-latest")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "ok"}

def extract_text_from_pdf(file_bytes):
    reader = PdfReader(io.BytesIO(file_bytes))
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text

def extract_text_from_pptx(file_bytes):
    prs = Presentation(io.BytesIO(file_bytes))
    text = ""
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    for run in paragraph.runs:
                        text += run.text + " "
    return text

def generate_flashcards(text):
    prompt = f"""You are an expert study coach helping a student prepare for an exam.
Based on the lecture content below, generate 6 to 10 flashcards that test real understanding —
not just definitions. Include a mix of:
- Concept explanation questions ("Why does X happen?", "What is the difference between X and Y?")
- Application questions ("What would happen if...?")
- A few straightforward recall questions for key terms/definitions

Avoid vague or overly broad questions. Each answer should be concise (1-3 sentences), clear, and accurate based only on the content given.

Respond ONLY with valid JSON in this exact format, no other text, no markdown formatting:
[
  {{"question": "...", "answer": "..."}}
]

Lecture content:
{text[:8000]}
"""
    response = model.generate_content(prompt)
    raw = response.text.strip()

    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]

    return json.loads(raw)

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    contents = await file.read()
    filename = file.filename.lower()

    if filename.endswith(".pdf"):
        extracted_text = extract_text_from_pdf(contents)
    elif filename.endswith(".pptx"):
        extracted_text = extract_text_from_pptx(contents)
    else:
        return {"error": "Unsupported file type. Please upload a PDF or PPTX."}

    if not extracted_text.strip():
        return {"error": "No text could be extracted from this file."}

    try:
        flashcards = generate_flashcards(extracted_text)
    except Exception as e:
        return {"error": f"Failed to generate flashcards: {str(e)}"}

    return {
        "filename": file.filename,
        "flashcards": flashcards
    }