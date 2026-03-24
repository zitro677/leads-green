from typing import Optional, List
from pdf2image import convert_from_path
import numpy as np
from app.config import settings


def extract_easyocr(pdf_path: str, languages: Optional[List[str]] = None) -> dict:
    import easyocr
    languages = languages or ["es", "en"]
    reader = easyocr.Reader(languages, gpu=settings.easyocr_gpu)

    images = convert_from_path(pdf_path, dpi=300)
    pages = []
    full_text_parts = []
    confidences = []

    for i, image in enumerate(images, start=1):
        img_array = np.array(image)
        raw_results = reader.readtext(img_array, detail=1)

        texts = [r[1] for r in raw_results]
        confs = [r[2] for r in raw_results]
        page_text = " ".join(texts)
        page_conf = (sum(confs) / len(confs) * 100) if confs else 0.0

        full_text_parts.append(page_text)
        confidences.append(page_conf)
        pages.append({"page": i, "text": page_text, "confidence": round(page_conf, 2)})

    full_text = "\n\n".join(full_text_parts)
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

    return {
        "extracted_text": full_text,
        "pages": pages,
        "ocr_engine": "easyocr",
        "confidence_avg": round(avg_conf, 2),
        "language_detected": None,
    }
