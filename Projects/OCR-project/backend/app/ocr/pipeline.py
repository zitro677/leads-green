from typing import Optional
from app.ocr.digital_extractor import extract_digital
from app.ocr.scan_extractor import extract_scanned
from app.ocr.easyocr_extractor import extract_easyocr
from app.ocr.token_counter import count_tokens

DIGITAL_THRESHOLD = 50  # chars per page average


class OCRPipeline:
    def run(self, pdf_path: str, options: Optional[dict] = None) -> dict:
        import pdfplumber

        with pdfplumber.open(pdf_path) as pdf:
            page_count = len(pdf.pages)
            sample_text = " ".join(
                (p.extract_text() or "") for p in pdf.pages[:3]
            )

        avg_chars = len(sample_text) / max(page_count, 1)
        is_digital = avg_chars >= DIGITAL_THRESHOLD

        if is_digital:
            result = extract_digital(pdf_path)
            file_type = "pdf_digital"
        else:
            result = extract_scanned(pdf_path)
            if result.get("confidence_avg", 100) < 60:
                result = extract_easyocr(pdf_path)
            file_type = "pdf_scanned"

        result["file_type"] = file_type
        result["page_count"] = page_count
        result["tokens_used"] = count_tokens(result["extracted_text"])
        return result
