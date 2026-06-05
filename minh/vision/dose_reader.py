"""
Dose Reading & Interpretation Module (MERGED VERSION)

Combines:
- Teammate's PaddleOCR + fuzzy name matching + expiration parsing (fast, offline)
- Your LLM-based dosage interpretation (for frequency, timing, warnings)

Pipeline:
1. PaddleOCR → extract raw text from medicine label
2. Teammate's parsers → medicine name (fuzzy match) + expiration date (regex)
3. LLM (optional) → interpret dosage frequency, timing, warnings

Usage:
    python -m vision.dose_reader --image medicine_label.jpg
    python -m vision.dose_reader --image medicine_label.jpg --use-llm
"""

import argparse
from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class DoseInfo:
    """Structured dosage information extracted from a medicine label."""
    medicine_name: str
    dosage: str              # e.g., "500mg"
    frequency: str           # e.g., "twice daily"
    timing: str              # e.g., "after meals"
    warnings: str            # e.g., "Do not take with alcohol"
    expiration_date: str     # e.g., "09/2026"
    raw_text: str            # raw OCR text
    confidence: float        # overall confidence score


class DoseReader:
    """
    Medicine label reader combining:
    - PaddleOCR for text extraction
    - Teammate's fuzzy matching for medicine name identification
    - Teammate's regex parsing for expiration date
    - Optional LLM for dosage/frequency interpretation
    """

    def __init__(self, use_llm: bool = False, llm_backend: str = "transformers"):
        """
        Args:
            use_llm: Whether to use LLM for dosage interpretation
            llm_backend: "transformers" (local Phi-3/Qwen) or "openai"
        """
        self.use_llm = use_llm
        self.llm_backend = llm_backend
        self.ocr_engine = None
        self.llm_model = None
        self._init_ocr()
        if use_llm:
            self._init_llm()

    def _init_ocr(self):
        """Initialize PaddleOCR engine."""
        try:
            from paddleocr import PaddleOCR
            self.ocr_engine = PaddleOCR(
                use_angle_cls=True,
                lang="en",
                show_log=False,
            )
            print("[DoseReader] PaddleOCR initialized.")
        except ImportError:
            print("[DoseReader] WARNING: PaddleOCR not installed.")
            print("  Install with: pip install paddleocr paddlepaddle")

    def _init_llm(self):
        """Initialize LLM for dosage interpretation (optional)."""
        try:
            from transformers import pipeline
            self.llm_model = pipeline(
                "text-generation",
                model="microsoft/Phi-3-mini-4k-instruct",
                torch_dtype="auto",
                device_map="auto",
            )
            print("[DoseReader] LLM loaded (Phi-3-mini) for dosage interpretation.")
        except Exception as e:
            print(f"[DoseReader] WARNING: Could not load LLM: {e}")
            print("  Falling back to regex-based dosage extraction.")
            self.llm_model = None

    def extract_text(self, image: np.ndarray) -> str:
        """
        Extract text from medicine label using PaddleOCR.
        
        Args:
            image: BGR image as numpy array
            
        Returns:
            Concatenated text from all detected text regions
        """
        if self.ocr_engine is None:
            return ""

        results = self.ocr_engine.ocr(image, cls=True)
        if not results or not results[0]:
            return ""

        lines = []
        for line in results[0]:
            text = line[1][0]
            confidence = line[1][1]
            if confidence > 0.5:
                lines.append(text)

        return "\n".join(lines)

    def identify_medicine(self, raw_text: str) -> Optional[str]:
        """
        Identify medicine name using teammate's fuzzy matching.
        Fast, offline, works against 300+ medicine database.
        """
        from sorting.medicine_name_parser import find_medicine_name
        return find_medicine_name(raw_text)

    def extract_expiration(self, raw_text: str) -> Optional[str]:
        """
        Extract expiration date using teammate's regex parser.
        Handles EU/US/German date formats.
        """
        from sorting.expiration_date_parser import parse_expiration_date
        return parse_expiration_date(raw_text)

    def extract_dosage_info(self, raw_text: str) -> dict:
        """
        Extract dosage, frequency, timing from OCR text.
        Uses LLM if available, otherwise falls back to regex.
        """
        if self.use_llm and self.llm_model is not None:
            return self._extract_dosage_with_llm(raw_text)
        else:
            return self._extract_dosage_with_regex(raw_text)

    def _extract_dosage_with_llm(self, raw_text: str) -> dict:
        """Use LLM to extract dosage details from OCR text."""
        prompt = f"""Extract medication dosage information from this label text.
Respond in exactly this format:
DOSAGE: <amount, e.g., 500mg>
FREQUENCY: <how often, e.g., twice daily>
TIMING: <when to take, e.g., after meals>
WARNINGS: <any warnings or contraindications>

Label text:
{raw_text}

Extracted:"""

        try:
            output = self.llm_model(prompt, max_new_tokens=150, do_sample=False)
            response = output[0]["generated_text"][len(prompt):]
            return self._parse_llm_dosage_response(response)
        except Exception as e:
            print(f"[DoseReader] LLM error: {e}")
            return self._extract_dosage_with_regex(raw_text)

    def _parse_llm_dosage_response(self, response: str) -> dict:
        """Parse LLM response into dosage fields."""
        fields = {}
        for line in response.strip().split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                fields[key.strip().upper()] = value.strip()

        return {
            "dosage": fields.get("DOSAGE", "Unknown"),
            "frequency": fields.get("FREQUENCY", "Unknown"),
            "timing": fields.get("TIMING", "Unknown"),
            "warnings": fields.get("WARNINGS", "None"),
        }

    def _extract_dosage_with_regex(self, raw_text: str) -> dict:
        """Fallback: regex-based dosage extraction."""
        import re

        dosage_pattern = r"(\d+\s*(?:mg|ml|mcg|g|iu))"
        freq_pattern = (
            r"(\d+\s*(?:times?|x)\s*(?:daily|a day|per day)"
            r"|\b(?:once|twice|three times)\s*(?:daily|a day))"
        )
        timing_pattern = r"((?:before|after|with)\s+(?:meals?|food|breakfast|dinner|lunch))"
        warning_pattern = r"((?:do not|avoid|caution|warning)[^.]*)"

        dosage_match = re.search(dosage_pattern, raw_text, re.IGNORECASE)
        freq_match = re.search(freq_pattern, raw_text, re.IGNORECASE)
        timing_match = re.search(timing_pattern, raw_text, re.IGNORECASE)
        warning_match = re.search(warning_pattern, raw_text, re.IGNORECASE)

        return {
            "dosage": dosage_match.group(1) if dosage_match else "Unknown",
            "frequency": freq_match.group(1) if freq_match else "Unknown",
            "timing": timing_match.group(1) if timing_match else "Unknown",
            "warnings": warning_match.group(1) if warning_match else "None",
        }

    def read_medicine(self, image: np.ndarray) -> DoseInfo:
        """
        Full pipeline: image → OCR → name/expiration/dosage → structured output.
        
        This is the main entry point.
        Combines teammate's fast parsing with optional LLM interpretation.
        """
        # Step 1: OCR
        raw_text = self.extract_text(image)
        if not raw_text:
            return DoseInfo(
                medicine_name="Unknown", dosage="Unknown", frequency="Unknown",
                timing="Unknown", warnings="", expiration_date="Unknown",
                raw_text="", confidence=0.0,
            )

        # Step 2: Medicine name (teammate's fuzzy matching)
        medicine_name = self.identify_medicine(raw_text) or "Unknown"

        # Step 3: Expiration date (teammate's regex parser)
        expiration_date = self.extract_expiration(raw_text) or "Unknown"

        # Step 4: Dosage details (regex or LLM)
        dosage_info = self.extract_dosage_info(raw_text)

        # Confidence: higher if both name and expiration found
        confidence = 0.3
        if medicine_name != "Unknown":
            confidence += 0.35
        if expiration_date != "Unknown":
            confidence += 0.2
        if dosage_info["dosage"] != "Unknown":
            confidence += 0.15

        return DoseInfo(
            medicine_name=medicine_name,
            dosage=dosage_info["dosage"],
            frequency=dosage_info["frequency"],
            timing=dosage_info["timing"],
            warnings=dosage_info["warnings"],
            expiration_date=expiration_date,
            raw_text=raw_text,
            confidence=confidence,
        )


def main():
    parser = argparse.ArgumentParser(description="Medicine Dose Reader (Merged)")
    parser.add_argument("--image", type=str, required=True, help="Path to medicine label image")
    parser.add_argument("--use-llm", action="store_true", help="Use LLM for dosage interpretation")
    parser.add_argument("--backend", type=str, default="transformers",
                        choices=["transformers", "openai"])
    args = parser.parse_args()

    import cv2
    image = cv2.imread(args.image)
    if image is None:
        print(f"Could not read image: {args.image}")
        return

    reader = DoseReader(use_llm=args.use_llm, llm_backend=args.backend)
    dose_info = reader.read_medicine(image)

    print("\n" + "=" * 50)
    print("MEDICINE DOSE INFORMATION")
    print("=" * 50)
    print(f"  Medicine:    {dose_info.medicine_name}")
    print(f"  Dosage:      {dose_info.dosage}")
    print(f"  Frequency:   {dose_info.frequency}")
    print(f"  Timing:      {dose_info.timing}")
    print(f"  Warnings:    {dose_info.warnings}")
    print(f"  Expiration:  {dose_info.expiration_date}")
    print(f"  Confidence:  {dose_info.confidence:.0%}")
    print(f"\n  Raw OCR Text:\n  {dose_info.raw_text}")
    print("=" * 50)


if __name__ == "__main__":
    main()
