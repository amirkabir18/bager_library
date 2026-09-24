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

import database
from config.dewey import load_dewey_dataset
from services.dewey_ai_agent import DeweyAIAgent, SearchResult

logger = logging.getLogger(__name__)


@dataclass
class DeweyResult:
    dewey_code: str | None
    dewey_class: str | None
    dewey_subject: str | None
    dewey_confidence: float
    dewey_source: str  # "api", "manual", "ai", "unknown"
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
    Powered by DeweyAIAgent for autonomous AI classification.
    """

    def __init__(self, ai_agent: Any = None):
        self.classes, self.subdivisions = load_dewey_dataset()
        self.ai_agent = ai_agent

    def get_ai_agent(self) -> DeweyAIAgent | None:
        """Returns the DeweyAIAgent instance."""
        if self.ai_agent is None:
            try:
                self.ai_agent = DeweyAIAgent()
            except Exception as ex:
                logger.debug(f"Could not initialize DeweyAIAgent: {ex}")
                self.ai_agent = None
        return self.ai_agent

    def search_subject(self, query: str, limit: int = 5) -> list[SearchResult]:
        """Searches DDC using the AI Agent."""
        if not database.is_ai_features_enabled():
            return []
        agent = self.get_ai_agent()
        if agent is None:
            return []
        hit = agent.detect_ddc(topic=query)
        if hit:
            return [hit]
        return []

    def detect_subject(self, query: str, threshold: float = 0.50) -> SearchResult | None:
        """Detects the DDC code of a subject using the AI Agent."""
        if not database.is_ai_features_enabled():
            return None
        agent = self.get_ai_agent()
        if agent is None:
            return None
        hit = agent.detect_ddc(topic=query)
        if hit and hit.score >= threshold:
            return hit
        return None

    def detect_with_ai(
        self,
        title: str,
        author: str | None = None,
        description: str | None = None,
    ) -> DeweyResult | None:
        """
        Uses the OpenAI AI Agent to detect and classify DDC for a title, topic, or book.
        Validates DDC code strictly and returns a DeweyResult with source='ai'.
        """
        if not database.is_ai_features_enabled():
            return None
        agent = self.get_ai_agent()
        if agent is None:
            return None
        hit = agent.detect_ddc(topic=title, author=author, description=description)
        if hit:
            return DeweyResult(
                dewey_code=hit.code,
                dewey_class=hit.class_fa or self.get_class_name(hit.code),
                dewey_subject=hit.subject_fa or self.get_subject_name(hit.code),
                dewey_confidence=hit.score,
                dewey_source="ai",
                reason=hit.reason,
            )
        return None

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
        AI Agent classification pipeline:
        1. Existing metadata / API DDC code (if provided and valid)
        2. AI Agent classification
        3. Low confidence fallback (dewey_code = None)
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

        # --- Step 2: AI Agent Classification ---
        if database.is_ai_features_enabled():
            topic = title_raw
            if categories:
                cat_str = " | ".join([c for c in categories if c])
                if cat_str:
                    topic = f"{topic} ({cat_str})" if topic else cat_str

            author = authors[0] if authors else None
            ai_res = self.detect_with_ai(title=topic, author=author, description=description)
            if ai_res and ai_res.dewey_code:
                logger.info(
                    f"Book: '{title_raw}' classified via AI Agent: {ai_res.dewey_code} ({ai_res.dewey_subject})"
                )
                return ai_res

        # --- Step 3: Low Confidence Fallback ---
        logger.warning(f"DDC classification failed for book: '{title_raw}'. Setting dewey_code to None.")
        return DeweyResult(
            dewey_code=None,
            dewey_class=None,
            dewey_subject=None,
            dewey_confidence=0.0,
            dewey_source="unknown",
            reason="AI Agent did not return a valid DDC classification",
        )
