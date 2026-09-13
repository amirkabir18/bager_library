"""
ISBN service for validation, normalization, and external metadata retrieval.
Queries Open Library and Google Books API with offline fallbacks.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any

from auth import normalize_digits

logger = logging.getLogger(__name__)


@dataclass
class BookMetadata:
    isbn: str
    title: str | None = None
    authors: list[str] | None = None
    categories: list[str] | None = None
    description: str | None = None
    publisher: str | None = None
    publish_date: str | None = None
    dewey_decimal_class: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def clean_isbn(raw_isbn: str | None) -> str:
    """
    Cleans raw ISBN by converting Persian/Arabic digits, removing hyphens and spaces,
    and making checksum characters uppercase.
    """
    if not raw_isbn:
        return ""
    norm = normalize_digits(str(raw_isbn))
    # Keep only digits and 'X' or 'x'
    cleaned = re.sub(r"[^\dX]", "", norm.upper())
    return cleaned


def is_valid_isbn(raw_isbn: str | None) -> bool:
    """
    Validates an ISBN-10 or ISBN-13 code using standard checksum algorithms.
    """
    isbn = clean_isbn(raw_isbn)
    if len(isbn) == 10:
        # Validate ISBN-10
        total = 0
        for i in range(9):
            if not isbn[i].isdigit():
                return False
            total += int(isbn[i]) * (10 - i)
        check = 10 if isbn[9] == "X" else (int(isbn[9]) if isbn[9].isdigit() else -1)
        if check == -1:
            return False
        total += check
        return total % 11 == 0
    elif len(isbn) == 13:
        # Validate ISBN-13
        if not isbn.isdigit():
            return False
        total = 0
        for i in range(12):
            factor = 1 if i % 2 == 0 else 3
            total += int(isbn[i]) * factor
        calc_check = (10 - (total % 10)) % 10
        return calc_check == int(isbn[12])
    return False


class ISBNService:
    """
    Service for looking up book metadata via public APIs (Open Library, Google Books).
    """

    def __init__(self, timeout: float = 4.0):
        self.timeout = timeout

    def fetch_metadata(self, raw_isbn: str) -> BookMetadata | None:
        """
        Fetches metadata for a given ISBN from Open Library and Google Books.
        Gracefully returns partial data or None if offline/unreachable.
        """
        isbn = clean_isbn(raw_isbn)
        if not isbn:
            return None

        # 1. Try Open Library
        meta = self._fetch_from_open_library(isbn)
        if meta and meta.title:
            return meta

        # 2. Fallback to Google Books
        meta = self._fetch_from_google_books(isbn)
        if meta and meta.title:
            return meta

        return BookMetadata(isbn=isbn)

    def _fetch_from_open_library(self, isbn: str) -> BookMetadata | None:
        """Query Open Library Books API."""
        try:
            url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
            req = urllib.request.Request(url, headers={"User-Agent": "BagerLibraryApp/1.0"})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            key = f"ISBN:{isbn}"
            if key not in data:
                return None

            b_data = data[key]
            title = b_data.get("title")
            authors = [a.get("name") for a in b_data.get("authors", []) if a.get("name")]

            # Subjects / Categories
            subjects = [s.get("name") for s in b_data.get("subjects", []) if s.get("name")]

            # Classifications (DDC)
            classifications = b_data.get("classifications", {})
            dewey_list = classifications.get("dewey_decimal_class", [])
            dewey_code = dewey_list[0] if dewey_list else None

            # Publishers
            publishers = [p.get("name") for p in b_data.get("publishers", []) if p.get("name")]
            publisher = publishers[0] if publishers else None

            publish_date = b_data.get("publish_date")
            description = None
            if "notes" in b_data:
                description = b_data.get("notes")

            return BookMetadata(
                isbn=isbn,
                title=title,
                authors=authors,
                categories=subjects,
                description=description,
                publisher=publisher,
                publish_date=publish_date,
                dewey_decimal_class=dewey_code,
            )
        except Exception as e:
            logger.debug(f"Open Library lookup failed for ISBN {isbn}: {e}")
            return None

    def _fetch_from_google_books(self, isbn: str) -> BookMetadata | None:
        """Query Google Books Volume API."""
        try:
            url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
            req = urllib.request.Request(url, headers={"User-Agent": "BagerLibraryApp/1.0"})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            items = data.get("items", [])
            if not items:
                return None

            vol = items[0].get("volumeInfo", {})
            title = vol.get("title")
            authors = vol.get("authors", [])
            categories = vol.get("categories", [])
            description = vol.get("description")
            publisher = vol.get("publisher")
            publish_date = vol.get("publishedDate")

            return BookMetadata(
                isbn=isbn,
                title=title,
                authors=authors,
                categories=categories,
                description=description,
                publisher=publisher,
                publish_date=publish_date,
                dewey_decimal_class=None,
            )
        except Exception as e:
            logger.debug(f"Google Books lookup failed for ISBN {isbn}: {e}")
            return None
