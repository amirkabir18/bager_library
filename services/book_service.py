"""
Book Service for Bager Library Management.
Coordinates ISBN metadata retrieval, Dewey Decimal classification,
book registration, updates, and reclassification.
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from database import _resolve_connection
from services.dewey_service import DeweyResult, DeweyService, dewey_sort_key, is_valid_dewey
from services.isbn_service import ISBNService, clean_isbn

logger = logging.getLogger(__name__)


class BookService:
    """
    High-level business service for book operations, DDC classification,
    and ISBN metadata synchronization.
    """

    def __init__(
        self,
        dewey_service: DeweyService | None = None,
        isbn_service: ISBNService | None = None,
    ):
        self.dewey_service = dewey_service or DeweyService()
        self.isbn_service = isbn_service or ISBNService()

    def lookup_isbn_and_classify(self, raw_isbn: str) -> dict[str, Any]:
        """
        Given an ISBN, fetches book details from external catalogs and runs
        the Dewey classification pipeline.
        Returns a structured dictionary with book info and DDC classification.
        """
        cleaned_isbn = clean_isbn(raw_isbn)
        metadata = self.isbn_service.fetch_metadata(cleaned_isbn) if cleaned_isbn else None

        title = metadata.title if metadata and metadata.title else ""
        authors = metadata.authors if metadata and metadata.authors else []
        categories = metadata.categories if metadata and metadata.categories else []
        description = metadata.description if metadata and metadata.description else None
        existing_dewey = metadata.dewey_decimal_class if metadata else None
        author_str = ", ".join(authors) if authors else ""

        dewey_res: DeweyResult
        if title or existing_dewey or categories:
            dewey_res = self.dewey_service.classify(
                title=title,
                authors=authors,
                categories=categories,
                description=description,
                existing_dewey=existing_dewey,
            )
        else:
            dewey_res = DeweyResult(
                dewey_code=None,
                dewey_class=None,
                dewey_subject=None,
                dewey_confidence=0.0,
                dewey_source="unknown",
                reason="No title or metadata available for classification",
            )

        return {
            "isbn": cleaned_isbn,
            "title": title,
            "author": author_str,
            "dewey_code": dewey_res.dewey_code,
            "dewey_class": dewey_res.dewey_class,
            "dewey_subject": dewey_res.dewey_subject,
            "dewey_confidence": dewey_res.dewey_confidence,
            "dewey_source": dewey_res.dewey_source,
            "dewey": {
                "code": dewey_res.dewey_code,
                "class": dewey_res.dewey_class,
                "subject": dewey_res.dewey_subject,
                "confidence": dewey_res.dewey_confidence,
                "source": dewey_res.dewey_source,
                "reason": dewey_res.reason,
            },
        }

    def register_book(
        self,
        title: str,
        author: str | None = None,
        isbn: str | None = None,
        dewey_code: str | None = None,
        dewey_subject: str | None = None,
        dewey_class: str | None = None,
        dewey_source: str | None = None,
        auto_classify: bool = True,
        conn_or_path: sqlite3.Connection | str | None = None,
    ) -> dict[str, Any]:
        """
        Registers a new book in the database.
        - If dewey_code is manually provided, source is marked as 'manual'.
        - If dewey_code is not provided and auto_classify is True, classifies automatically.
        - If DDC classification yields no result, registers book with dewey_code=None without error.
        """
        conn, should_close = _resolve_connection(conn_or_path)
        try:
            cur = conn.cursor()
            cleaned_title = (title or "").strip()
            cleaned_author = (author or "").strip() if author else None
            cleaned_isbn = clean_isbn(isbn) if isbn else None

            final_code = dewey_code.strip() if dewey_code and str(dewey_code).strip() else None
            final_subject = dewey_subject.strip() if dewey_subject and str(dewey_subject).strip() else None
            final_class = dewey_class.strip() if dewey_class and str(dewey_class).strip() else None
            final_source = dewey_source or ("manual" if final_code else "unknown")
            final_confidence = 1.0 if final_source == "manual" else 0.0

            if not final_code and auto_classify and cleaned_title:
                # Classify based on title and author
                classification = self.dewey_service.classify(
                    title=cleaned_title,
                    authors=[cleaned_author] if cleaned_author else None,
                )
                if classification.dewey_code:
                    final_code = classification.dewey_code
                    final_subject = classification.dewey_subject
                    final_class = classification.dewey_class
                    final_source = classification.dewey_source
                    final_confidence = classification.dewey_confidence

            if final_code and not final_subject:
                final_subject = self.dewey_service.get_subject_name(final_code)
            if final_code and not final_class:
                final_class = self.dewey_service.get_class_name(final_code)

            # Insert into books table
            cur.execute(
                """
                INSERT INTO books (
                    title, author, isbn,
                    dewey_code, dewey_class, dewey_subject, dewey_confidence, dewey_source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cleaned_title,
                    cleaned_author,
                    cleaned_isbn,
                    final_code,
                    final_class,
                    final_subject,
                    final_confidence,
                    final_source,
                ),
            )
            inserted_id = cur.lastrowid
            conn.commit()

            return {
                "id": inserted_id,
                "title": cleaned_title,
                "author": cleaned_author,
                "isbn": cleaned_isbn,
                "dewey_code": final_code,
                "dewey_class": final_class,
                "dewey_subject": final_subject,
                "dewey_confidence": final_confidence,
                "dewey_source": final_source,
            }
        finally:
            if should_close:
                conn.close()

    def update_book_dewey(
        self,
        book_id: int,
        dewey_code: str | None,
        dewey_subject: str | None = None,
        dewey_source: str = "manual",
        conn_or_path: sqlite3.Connection | str | None = None,
    ) -> bool:
        """
        Manually updates Dewey classification for a book.
        Sets dewey_source to 'manual' to prevent automatic reclassification overwrite.
        """
        conn, should_close = _resolve_connection(conn_or_path)
        try:
            cur = conn.cursor()
            code = dewey_code.strip() if dewey_code and str(dewey_code).strip() else None
            if code and not is_valid_dewey(code):
                raise ValueError(f"Invalid Dewey code: {code}")

            subject = (
                dewey_subject.strip()
                if dewey_subject and str(dewey_subject).strip()
                else (self.dewey_service.get_subject_name(code) if code else None)
            )
            cls_name = self.dewey_service.get_class_name(code) if code else None
            confidence = 1.0 if code else 0.0

            cur.execute(
                """
                UPDATE books SET
                    dewey_code = ?,
                    dewey_class = ?,
                    dewey_subject = ?,
                    dewey_confidence = ?,
                    dewey_source = ?
                WHERE id = ?
                """,
                (code, cls_name, subject, confidence, dewey_source, book_id),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            if should_close:
                conn.close()

    def reclassify_book(
        self,
        book_id: int,
        force: bool = False,
        conn_or_path: sqlite3.Connection | str | None = None,
    ) -> DeweyResult | None:
        """
        Reclassifies an existing book.
        - If dewey_source is 'manual' and force is False, skips reclassification.
        - Updates the database record with the new classification.
        """
        conn, should_close = _resolve_connection(conn_or_path)
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, title, author, isbn, dewey_source FROM books WHERE id = ?", (book_id,))
            row = cur.fetchone()
            if not row:
                return None

            _id, title, author, isbn, source = row
            if source == "manual" and not force:
                logger.info(f"Skipping reclassification for book ID {book_id}: dewey_source is 'manual'")
                return None

            classification = self.dewey_service.classify(
                title=title or "",
                authors=[author] if author else None,
            )

            # Update book record
            code = classification.dewey_code
            cls_name = classification.dewey_class
            subj = classification.dewey_subject
            conf = classification.dewey_confidence
            src = classification.dewey_source

            cur.execute(
                """
                UPDATE books SET
                    dewey_code = ?,
                    dewey_class = ?,
                    dewey_subject = ?,
                    dewey_confidence = ?,
                    dewey_source = ?
                WHERE id = ?
                """,
                (code, cls_name, subj, conf, src, book_id),
            )
            conn.commit()
            return classification
        finally:
            if should_close:
                conn.close()

    def reclassify_all_books(
        self,
        force: bool = False,
        conn_or_path: sqlite3.Connection | str | None = None,
    ) -> dict[str, int]:
        """
        Reclassifies all books in the database.
        Skips books where dewey_source == 'manual' unless force is True.
        Returns a summary report of operations.
        """
        conn, should_close = _resolve_connection(conn_or_path)
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, title, author, isbn, dewey_source FROM books")
            books = cur.fetchall()

            total = len(books)
            updated = 0
            skipped_manual = 0
            unclassified = 0

            for b in books:
                book_id, title, author, isbn, source = b
                if source == "manual" and not force:
                    skipped_manual += 1
                    continue

                res = self.dewey_service.classify(
                    title=title or "",
                    authors=[author] if author else None,
                )
                code = res.dewey_code
                cls_name = res.dewey_class
                subj = res.dewey_subject
                conf = res.dewey_confidence
                src = res.dewey_source

                cur.execute(
                    """
                    UPDATE books SET
                        dewey_code = ?,
                        dewey_class = ?,
                        dewey_subject = ?,
                        dewey_confidence = ?,
                        dewey_source = ?
                    WHERE id = ?
                    """,
                    (code, cls_name, subj, conf, src, book_id),
                )
                if code:
                    updated += 1
                else:
                    unclassified += 1

            conn.commit()
            return {
                "total": total,
                "updated": updated,
                "skipped_manual": skipped_manual,
                "unclassified": unclassified,
            }
        finally:
            if should_close:
                conn.close()

    def get_book(
        self,
        book_id: int,
        conn_or_path: sqlite3.Connection | str | None = None,
    ) -> dict[str, Any] | None:
        """Retrieves complete information for a single book including Dewey metadata."""
        conn, should_close = _resolve_connection(conn_or_path)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, title, author, isbn,
                       dewey_code, dewey_class, dewey_subject, dewey_confidence, dewey_source
                FROM books WHERE id = ?
                """,
                (book_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "title": row[1],
                "author": row[2],
                "isbn": row[3],
                "dewey_code": row[4],
                "dewey_class": row[5],
                "dewey_subject": row[6],
                "dewey_confidence": row[7],
                "dewey_source": row[8],
            }
        finally:
            if should_close:
                conn.close()

    def list_books(
        self,
        sort_by: str = "id",
        sort_dir: str = "ASC",
        conn_or_path: sqlite3.Connection | str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Lists books with optional Dewey hierarchical sorting.
        """
        conn, should_close = _resolve_connection(conn_or_path)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, title, author, isbn,
                       dewey_code, dewey_class, dewey_subject, dewey_confidence, dewey_source
                FROM books
                """
            )
            rows = cur.fetchall()
            books = []
            for row in rows:
                books.append(
                    {
                        "id": row[0],
                        "title": row[1],
                        "author": row[2],
                        "isbn": row[3],
                        "dewey_code": row[4],
                        "dewey_class": row[5],
                        "dewey_subject": row[6],
                        "dewey_confidence": row[7],
                        "dewey_source": row[8],
                    }
                )

            # Python-level hierarchical Dewey sorting if requested
            if sort_by in ("dewey", "dewey_code"):
                reverse = sort_dir.upper() == "DESC"
                books.sort(key=lambda b: dewey_sort_key(b["dewey_code"]), reverse=reverse)
            elif sort_by == "title":
                books.sort(key=lambda b: b["title"] or "", reverse=(sort_dir.upper() == "DESC"))
            elif sort_by == "author":
                books.sort(key=lambda b: b["author"] or "", reverse=(sort_dir.upper() == "DESC"))
            elif sort_by == "id":
                books.sort(key=lambda b: b["id"], reverse=(sort_dir.upper() == "DESC"))

            return books
        finally:
            if should_close:
                conn.close()
