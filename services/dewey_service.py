"""
Dewey Decimal Classification (DDC) Service.
Provides normalization, validation, hierarchical sorting, shelf arrangement,
and multi-step classification for books.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass
from typing import Any

from config.dewey import load_dewey_dataset

logger = logging.getLogger(__name__)


@dataclass
class DeweyResult:
    dewey_code: str | None
    dewey_class: str | None
    dewey_subject: str | None
    dewey_confidence: float
    dewey_source: str  # "api", "mapping", "keyword", "rule", "manual", "ai", "unknown"
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_persian(text: str | None) -> str:
    """
    Normalizes Persian and Arabic text:
    - Arabic Yeh (ي) to Persian Yeh (ی)
    - Arabic Kaf (ك) to Persian Kaf (ک)
    - Arabic Teh Marbuta (ة) to Heh (ه)
    - Various forms of Alef (آ, أ, إ) to regular Alef (ا)
    - Remove or normalize Zero-Width Non-Joiner (ZWNJ / \u200c) to space
    - Collapse extra whitespace and lowercase English characters.
    """
    if not text:
        return ""

    s = str(text)

    # Character normalization mappings
    char_map = {
        "\u064a": "ی",  # Arabic Yeh
        "\u0649": "ی",  # Arabic Alef Maksura
        "\u0643": "ک",  # Arabic Kaf
        "\u0629": "ه",  # Teh Marbuta
        "\u06c0": "ه",  # Heh with Yeh
        "\u0622": "ا",  # Alef with Madda
        "\u0623": "ا",  # Alef with Hamza Above
        "\u0625": "ا",  # Alef with Hamza Below
        "\u0671": "ا",  # Alef Wasla
        "\u200c": " ",  # ZWNJ to space for token splitting
        "\u00a0": " ",  # Non-breaking space
    }
    for orig, target in char_map.items():
        s = s.replace(orig, target)

    # Remove Arabic diacritics (tashkeel, tanween, sukun, etc.)
    s = re.sub(r"[\u064b-\u065f\u0670]", "", s)

    # Lowercase Latin text
    s = s.lower()

    # Collapse multiple whitespaces
    s = re.sub(r"\s+", " ", s).strip()

    return s


def is_valid_dewey(code: str | None, allow_empty: bool = True) -> bool:
    """
    Validates whether a given string is a legitimate Dewey Decimal Classification code.
    - None or empty string is valid if allow_empty is True.
    - Code must be numeric, between 000 and 999, with optional decimal fraction.
    - Malformed values (letters, multiple decimals, negative numbers, > 999) return False.
    """
    if code is None or str(code).strip() == "":
        return allow_empty

    clean = str(code).strip()
    # Match 1 to 3 digits before decimal, optional decimal point and digits after
    match = re.fullmatch(r"(\d{1,3})(?:\.(\d+))?", clean)
    if not match:
        return False

    int_part = int(match.group(1))
    if not (0 <= int_part <= 999):
        return False

    return True


def normalize_dewey_code(code: str | None) -> str | None:
    """
    Normalizes a Dewey Decimal code to standard 3-digit main class formatting.
    e.g., '90' -> '090', '5.1' -> '005.1', '510' -> '510'.
    Returns None if input is invalid or empty.
    """
    if not code or not is_valid_dewey(code, allow_empty=False):
        return None

    clean = str(code).strip()
    match = re.fullmatch(r"(\d{1,3})(?:\.(\d+))?", clean)
    if not match:
        return None

    main_num = int(match.group(1))
    main_str = f"{main_num:03d}"
    decimals = match.group(2)
    if decimals:
        return f"{main_str}.{decimals}"
    return main_str


def dewey_sort_key(code: str | None) -> tuple:
    """
    Returns a sort key tuple for proper hierarchical DDC sorting.
    Treats Dewey classification numbers numerically rather than by lexicographical string sort.
    E.g. 90, 100, 510, 519.5, 519.52, 530, 800, 900.
    None or empty values sort last.
    """
    if code is None or str(code).strip() == "":
        return (1, 999999, ())

    clean = str(code).strip()
    match = re.fullmatch(r"(\d{1,3})(?:\.(\d+))?", clean)
    if not match:
        # Invalid format placed after valid ones, before empty
        return (1, 999998, (str(clean),))

    main_num = int(match.group(1))
    decimals = match.group(2) or ""
    decimal_digits = tuple(int(d) for d in decimals if d.isdigit())
    return (0, main_num, decimal_digits)


class DeweyService:
    """
    Service responsible for Dewey Decimal Classification,
    subject resolution, shelf locating, and book classification.
    """

    def __init__(self):
        self.classes, self.subdivisions, self.subject_to_ddc = load_dewey_dataset()
        self._build_normalized_mappings()

    def _build_normalized_mappings(self):
        """Pre-normalizes subject mapping keys for fast case-insensitive & Persian lookup."""
        self.norm_subject_map: dict[str, str] = {}
        for subject, code in self.subject_to_ddc.items():
            norm_key = normalize_persian(subject)
            if norm_key:
                self.norm_subject_map[norm_key] = str(code).strip()
            # Also store without spaces for compound words
            no_space = norm_key.replace(" ", "")
            if no_space and no_space != norm_key:
                self.norm_subject_map[no_space] = str(code).strip()

    def get_class_name(self, code: str | None, lang: str = "fa") -> str | None:
        """Returns the main class name (000-900) for a given DDC code."""
        if not code or not is_valid_dewey(code, allow_empty=False):
            return None
        norm = normalize_dewey_code(code)
        if not norm:
            return None
        main_class = norm[:1] + "00"
        class_info = self.classes.get(main_class)
        if class_info:
            return class_info.get(lang, class_info.get("fa"))
        return None

    def get_subject_name(self, code: str | None, lang: str = "fa") -> str | None:
        """Returns the most specific subject name available for a DDC code."""
        if not code or not is_valid_dewey(code, allow_empty=False):
            return None
        norm = normalize_dewey_code(code)
        if not norm:
            return None

        # Try exact subdivision match first
        if norm in self.subdivisions:
            sub = self.subdivisions[norm]
            return sub.get(f"subject_{lang}", sub.get("subject_fa"))

        # Try 3-digit division
        div_code = norm.split(".")[0]
        if div_code in self.subdivisions:
            sub = self.subdivisions[div_code]
            return sub.get(f"subject_{lang}", sub.get("subject_fa"))

        # Fallback to main class
        return self.get_class_name(norm, lang=lang)

    def get_shelf_location(self, code: str | None) -> dict[str, str | None]:
        """
        Determines the physical shelf arrangement for a book by its DDC code.
        Returns main class, subdivision, and display shelf rack label.
        """
        if not code or not is_valid_dewey(code, allow_empty=False):
            return {
                "class_code": None,
                "class_name": "نامشخص",
                "division_code": None,
                "division_name": "نامشخص",
                "shelf_label": "بخش کتاب‌های فاقد رده‌بندی",
                "shelf_path": "نامشخص",
            }

        norm = normalize_dewey_code(code) or str(code).strip()
        main_code = norm[:1] + "00"
        main_name = self.get_class_name(norm, "fa") or "رده عمومی"
        div_code = norm.split(".")[0]
        div_name = self.get_subject_name(div_code, "fa") or main_name

        shelf_path = f"{main_code} ({main_name}) > {div_code} ({div_name}) > {norm}"
        shelf_label = f"قفسه {main_code} - {div_name} [{norm}]"

        return {
            "class_code": main_code,
            "class_name": main_name,
            "division_code": div_code,
            "division_name": div_name,
            "shelf_label": shelf_label,
            "shelf_path": shelf_path,
        }

    def classify(
        self,
        title: str,
        authors: list[str] | None = None,
        categories: list[str] | None = None,
        description: str | None = None,
        language: str | None = None,
        existing_dewey: str | None = None,
    ) -> DeweyResult:
        """
        Multi-step classification pipeline:
        1. Existing metadata / API DDC code
        2. Exact subject mapping from categories
        3. Title direct subject mapping
        4. Keyword classification (title & categories)
        5. Description & inference rules
        6. AI classification fallback (if available)
        7. Low confidence fallback (dewey_code = None)
        """
        title_raw = (title or "").strip()
        logger.info(f"Classifying book: '{title_raw}'")

        # --- Step 1: Existing API / Provided Dewey Code ---
        if existing_dewey and is_valid_dewey(existing_dewey, allow_empty=False):
            norm_code = normalize_dewey_code(existing_dewey) or existing_dewey.strip()
            subject = self.get_subject_name(norm_code)
            main_class = self.get_class_name(norm_code)
            logger.info(f"Book: '{title_raw}' classified via API metadata: {norm_code} ({subject})")
            return DeweyResult(
                dewey_code=norm_code,
                dewey_class=main_class,
                dewey_subject=subject,
                dewey_confidence=0.98,
                dewey_source="api",
                reason="Direct Dewey code from catalog/API metadata",
            )

        # --- Step 2: Exact Subject Mapping from Categories ---
        if categories:
            for cat in categories:
                norm_cat = normalize_persian(cat)
                if norm_cat in self.norm_subject_map:
                    code = normalize_dewey_code(self.norm_subject_map[norm_cat]) or self.norm_subject_map[norm_cat]
                    subject = self.get_subject_name(code) or cat
                    main_class = self.get_class_name(code)
                    logger.info(f"Book: '{title_raw}' classified via category mapping: {code} ({subject})")
                    return DeweyResult(
                        dewey_code=code,
                        dewey_class=main_class,
                        dewey_subject=subject,
                        dewey_confidence=0.95,
                        dewey_source="mapping",
                        reason=f"Matched category '{cat}' to DDC {code}",
                    )

        # --- Step 3: Direct Subject Mapping from Title ---
        norm_title = normalize_persian(title_raw)
        if norm_title in self.norm_subject_map:
            code = normalize_dewey_code(self.norm_subject_map[norm_title]) or self.norm_subject_map[norm_title]
            subject = self.get_subject_name(code)
            main_class = self.get_class_name(code)
            logger.info(f"Book: '{title_raw}' classified via direct title mapping: {code} ({subject})")
            return DeweyResult(
                dewey_code=code,
                dewey_class=main_class,
                dewey_subject=subject,
                dewey_confidence=0.92,
                dewey_source="mapping",
                reason="Title exactly matches subject classification",
            )

        # Also check without spaces
        norm_title_no_space = norm_title.replace(" ", "")
        if norm_title_no_space in self.norm_subject_map:
            code = (
                normalize_dewey_code(self.norm_subject_map[norm_title_no_space])
                or self.norm_subject_map[norm_title_no_space]
            )
            subject = self.get_subject_name(code)
            main_class = self.get_class_name(code)
            logger.info(f"Book: '{title_raw}' classified via title match: {code} ({subject})")
            return DeweyResult(
                dewey_code=code,
                dewey_class=main_class,
                dewey_subject=subject,
                dewey_confidence=0.90,
                dewey_source="mapping",
                reason="Title matches normalized subject",
            )

        # --- Step 4: Keyword Matching in Title and Categories ---
        # Sort subject keys by length descending to match longest specific phrases first
        sorted_subjects = sorted(self.norm_subject_map.keys(), key=len, reverse=True)

        # Check title words / phrases
        for subj_key in sorted_subjects:
            if len(subj_key) < 2:
                continue
            # Look for whole phrase or word boundary in title
            pattern = r"(?:^|\s|[«\"'\(])" + re.escape(subj_key) + r"(?:$|\s|[»\"'\)])"
            if re.search(pattern, norm_title):
                code = normalize_dewey_code(self.norm_subject_map[subj_key]) or self.norm_subject_map[subj_key]
                subject = self.get_subject_name(code)
                main_class = self.get_class_name(code)
                logger.info(f"Book: '{title_raw}' classified via title keyword '{subj_key}': {code} ({subject})")
                return DeweyResult(
                    dewey_code=code,
                    dewey_class=main_class,
                    dewey_subject=subject,
                    dewey_confidence=0.85,
                    dewey_source="keyword",
                    reason=f"Title contains strong keyword '{subj_key}'",
                )

        # Check categories for keyword match
        if categories:
            for cat in categories:
                norm_cat = normalize_persian(cat)
                for subj_key in sorted_subjects:
                    if len(subj_key) < 3:
                        continue
                    if subj_key in norm_cat:
                        code = normalize_dewey_code(self.norm_subject_map[subj_key]) or self.norm_subject_map[subj_key]
                        subject = self.get_subject_name(code)
                        main_class = self.get_class_name(code)
                        logger.info(
                            f"Book: '{title_raw}' classified via category keyword '{subj_key}': {code} ({subject})"
                        )
                        return DeweyResult(
                            dewey_code=code,
                            dewey_class=main_class,
                            dewey_subject=subject,
                            dewey_confidence=0.82,
                            dewey_source="keyword",
                            reason=f"Category contains keyword '{subj_key}'",
                        )

        # --- Step 5: Description & Inference Matching ---
        if description:
            norm_desc = normalize_persian(description)
            # Count keyword frequencies in description
            best_match: tuple[str, int] | None = None
            for subj_key in sorted_subjects:
                if len(subj_key) < 4:
                    continue
                matches = len(re.findall(re.escape(subj_key), norm_desc))
                if matches > 0 and (best_match is None or matches > best_match[1]):
                    best_match = (subj_key, matches)

            if best_match and best_match[1] >= 1:
                subj_key = best_match[0]
                code = normalize_dewey_code(self.norm_subject_map[subj_key]) or self.norm_subject_map[subj_key]
                subject = self.get_subject_name(code)
                main_class = self.get_class_name(code)
                confidence = 0.70 if best_match[1] >= 2 else 0.60
                logger.info(
                    f"Book: '{title_raw}' classified via description keyword '{subj_key}' (count={best_match[1]}): {code}"
                )
                return DeweyResult(
                    dewey_code=code,
                    dewey_class=main_class,
                    dewey_subject=subject,
                    dewey_confidence=confidence,
                    dewey_source="keyword",
                    reason=f"Description contains relevant keyword '{subj_key}' ({best_match[1]} occurrences)",
                )

        # --- Step 6: AI Fallback (if configured/available) ---
        ai_res = self._try_ai_classify(title=title_raw, authors=authors, description=description)
        if ai_res:
            return ai_res

        # --- Step 7: Low Confidence Fallback ---
        logger.warning(f"DDC classification failed for book: '{title_raw}'. Setting dewey_code to None.")
        return DeweyResult(
            dewey_code=None,
            dewey_class=None,
            dewey_subject=None,
            dewey_confidence=0.0,
            dewey_source="unknown",
            reason="No confident DDC category or keyword match found",
        )

    def _try_ai_classify(
        self,
        title: str,
        authors: list[str] | None = None,
        description: str | None = None,
    ) -> DeweyResult | None:
        """
        Optional AI fallback for classification.
        Activated only if an AI API key or service is configured in the environment or settings.
        Validates output strictly to ensure no malformed Dewey code is ever produced.
        """
        # Hook for AI classification if an API key is configured
        import os

        ai_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not ai_key:
            return None

        # If LLM API integration exists, invoke it safely here with strict JSON schema validation
        # Returns None on failure or if not configured
        return None
