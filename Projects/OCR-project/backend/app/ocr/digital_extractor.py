import pdfplumber


def extract_digital(pdf_path: str) -> dict:
    pages = []
    full_text_parts = []

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            full_text_parts.append(text)
            pages.append({"page": i, "text": text, "confidence": None})

    return {
        "extracted_text": "\n\n".join(full_text_parts),
        "pages": pages,
        "ocr_engine": "pdfplumber",
        "confidence_avg": None,
        "language_detected": None,
    }
