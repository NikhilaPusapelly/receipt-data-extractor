from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import shutil

from receipt_extractor import (
    ocr_image_to_text,
    parse_receipt,
    parse_email_receipt
)

app = FastAPI()

# CORS FIX
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"message": "Receipt Extractor API Running"}


@app.post("/extract")
async def extract_receipt(file: UploadFile = File(...)):

    temp_file = f"temp_{file.filename}"

    with open(temp_file, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # HANDLE HTML FILES
    if file.filename.endswith((".html", ".htm")):

        with open(temp_file, "r", encoding="utf-8") as f:
            html_content = f.read()

        result = parse_email_receipt(html_content)

    # HANDLE IMAGE FILES
    else:
        text = ocr_image_to_text(temp_file)
        result = parse_receipt(text)

    return result