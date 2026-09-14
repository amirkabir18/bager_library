"""
Dewey Decimal Classification (DDC) configuration and data loader.
Separates dataset and classification settings from core business logic.
"""

import json
import logging
import os
import sys

logger = logging.getLogger(__name__)

# Minimum confidence threshold for setting dewey_code
MIN_CONFIDENCE_THRESHOLD = 0.50

# Default fallbacks if external JSON data cannot be found
DEFAULT_CLASSES: dict[str, dict[str, str]] = {
    "000": {"fa": "کلیات، علوم رایانه و اطلاعات", "en": "Computer science, information & general works"},
    "100": {"fa": "فلسفه و روان‌شناسی", "en": "Philosophy & psychology"},
    "200": {"fa": "دین و الهیات", "en": "Religion"},
    "300": {"fa": "علوم اجتماعی", "en": "Social sciences"},
    "400": {"fa": "زبان و زبان‌شناسی", "en": "Language"},
    "500": {"fa": "علوم محض و طبیعی", "en": "Science"},
    "600": {"fa": "فناوری و علوم کاربردی", "en": "Technology"},
    "700": {"fa": "هنر و سرگرمی", "en": "Arts & recreation"},
    "800": {"fa": "ادبیات", "en": "Literature"},
    "900": {"fa": "تاریخ و جغرافیا", "en": "History & geography"},
}

DEFAULT_SUBDIVISIONS: dict[str, dict[str, str]] = {
    "004": {
        "class": "000",
        "subject_fa": "علوم کامپیوتر و پردازش داده",
        "subject_en": "Computer science & data processing",
    },
    "005": {"class": "000", "subject_fa": "برنامه‌نویسی و نرم‌افزار", "subject_en": "Computer programming & software"},
    "100": {"class": "100", "subject_fa": "فلسفه", "subject_en": "Philosophy"},
    "150": {"class": "100", "subject_fa": "روان‌شناسی", "subject_en": "Psychology"},
    "200": {"class": "200", "subject_fa": "دین", "subject_en": "Religion"},
    "297": {"class": "200", "subject_fa": "اسلام و علوم قرآنی", "subject_en": "Islam"},
    "300": {"class": "300", "subject_fa": "علوم اجتماعی", "subject_en": "Social sciences"},
    "400": {"class": "400", "subject_fa": "زبان", "subject_en": "Language"},
    "500": {"class": "500", "subject_fa": "علوم طبیعی و ریاضی", "subject_en": "Science"},
    "510": {"class": "500", "subject_fa": "ریاضیات", "subject_en": "Mathematics"},
    "519.5": {"class": "500", "subject_fa": "آمار ریاضی", "subject_en": "Mathematical statistics"},
    "520": {"class": "500", "subject_fa": "نجوم و کیهان‌شناسی", "subject_en": "Astronomy"},
    "530": {"class": "500", "subject_fa": "فیزیک", "subject_en": "Physics"},
    "540": {"class": "500", "subject_fa": "شیمی", "subject_en": "Chemistry"},
    "550": {"class": "500", "subject_fa": "علوم زمین و زمین‌شناسی", "subject_en": "Earth sciences"},
    "560": {"class": "500", "subject_fa": "دیرین‌شناسی", "subject_en": "Paleontology"},
    "570": {"class": "500", "subject_fa": "زیست‌شناسی", "subject_en": "Biology"},
    "580": {"class": "500", "subject_fa": "گیاه‌شناسی", "subject_en": "Botany"},
    "590": {"class": "500", "subject_fa": "جانورشناسی", "subject_en": "Zoology"},
    "600": {"class": "600", "subject_fa": "فناوری و علوم کاربردی", "subject_en": "Technology"},
    "610": {"class": "600", "subject_fa": "پزشکی و سلامت", "subject_en": "Medicine & health"},
    "620": {"class": "600", "subject_fa": "مهندسی", "subject_en": "Engineering"},
    "641.5": {"class": "600", "subject_fa": "آشپزی", "subject_en": "Cooking"},
    "700": {"class": "700", "subject_fa": "هنر", "subject_en": "The Arts"},
    "780": {"class": "700", "subject_fa": "موسیقی", "subject_en": "Music"},
    "800": {"class": "800", "subject_fa": "ادبیات", "subject_en": "Literature"},
    "891.55": {"class": "800", "subject_fa": "ادبیات فارسی", "subject_en": "Persian literature"},
    "900": {"class": "900", "subject_fa": "تاریخ و جغرافیا", "subject_en": "History & geography"},
    "955": {"class": "900", "subject_fa": "تاریخ ایران", "subject_en": "History of Iran"},
}

DEFAULT_SUBJECT_TO_DDC: dict[str, str] = {
    "mathematics": "510",
    "math": "510",
    "physics": "530",
    "chemistry": "540",
    "biology": "570",
    "computer science": "004",
    "programming": "005",
    "psychology": "150",
    "philosophy": "100",
    "history": "900",
}


def get_data_file_path() -> str:
    """Resolve absolute path to dewey_data.json supporting PyInstaller frozen bundles."""
    base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    candidate = os.path.join(base_dir, "data", "dewey_data.json")
    if os.path.exists(candidate):
        return candidate
    local_dir = os.path.dirname(os.path.abspath(__file__))
    candidate2 = os.path.join(local_dir, "..", "data", "dewey_data.json")
    if os.path.exists(candidate2):
        return os.path.abspath(candidate2)
    return candidate


def load_dewey_dataset() -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]], dict[str, str]]:
    """
    Loads classes, subdivisions, and subject mappings from JSON dataset file.
    Falls back to built-in defaults if the file cannot be loaded.
    """
    classes = dict(DEFAULT_CLASSES)
    subdivisions = dict(DEFAULT_SUBDIVISIONS)
    subject_map = dict(DEFAULT_SUBJECT_TO_DDC)

    path = get_data_file_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "classes" in data and isinstance(data["classes"], dict):
                    classes.update(data["classes"])
                if "subdivisions" in data and isinstance(data["subdivisions"], dict):
                    subdivisions.update(data["subdivisions"])
                if "subject_to_ddc" in data and isinstance(data["subject_to_ddc"], dict):
                    subject_map.update(data["subject_to_ddc"])
        except Exception as e:
            logger.warning(f"Could not load dewey dataset from {path}: {e}")

    return classes, subdivisions, subject_map
