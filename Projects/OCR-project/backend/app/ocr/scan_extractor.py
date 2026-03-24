from pdf2image import convert_from_path
import pytesseract
from app.ocr.preprocessor import preprocess_image

try:
    from langdetect import detect as detect_lang
except ImportError:
    def detect_lang(text): return "eng"


def extract_scanned(pdf_path: str, lang: str = "spa+eng") -> dict:
    images = convert_from_path(pdf_path, dpi=300)
    pages = []
    full_text_parts = []
    confidences = []

    for i, image in enumerate(images, start=1):
        processed = preprocess_image(image)
        data = pytesseract.image_to_data(processed, lang=lang, output_type=pytesseract.Output.DICT)
        words = [w for w, c in zip(data["text"], data["conf"]) if int(c) > 0 and w.strip()]
        confs = [int(c) for c in data["conf"] if int(c) > 0]
        page_text = " ".join(words)
        page_conf = sum(confs) / len(confs) if confs else 0.0

        full_text_parts.append(page_text)
        confidences.append(page_conf)
        pages.append({"page": i, "text": page_text, "confidence": round(page_conf, 2)})

    full_text = "\n\n".join(full_text_parts)
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

    try:
        language = detect_lang(full_text[:500])
    except Exception:
        language = None

    return {
        "extracted_text": full_text,
        "pages": pages,
        "ocr_engine": "pytesseract",
        "confidence_avg": round(avg_conf, 2),
        "language_detected": language,
    }
