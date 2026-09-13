"""
Comprehensive tests for Dewey Decimal Classification (DDC),
Persian normalization, DDC validation, sorting, manual overrides,
reclassification, shelf placement, and backward compatibility.
"""

import sqlite3
import unittest

import database
from services.book_service import BookService
from services.dewey_service import (
    DeweyService,
    dewey_sort_key,
    is_valid_dewey,
    normalize_dewey_code,
    normalize_persian,
)
from services.isbn_service import clean_isbn, is_valid_isbn


class TestDeweyValidation(unittest.TestCase):
    """Test validation of Dewey Decimal Classification codes (Section 11 & 19)."""

    def test_valid_dewey_codes(self):
        valid_cases = ["510", "530", "641.5", "891.55", "005", "004.6", "900", "090", "150", "297.1"]
        for code in valid_cases:
            with self.subTest(code=code):
                self.assertTrue(is_valid_dewey(code, allow_empty=False), f"Expected {code} to be valid")

    def test_invalid_dewey_codes(self):
        invalid_cases = ["abc", "1200", "53x", "-510", "510.abc", "510.1.2", "9999", "1000", "5 10"]
        for code in invalid_cases:
            with self.subTest(code=code):
                self.assertFalse(is_valid_dewey(code, allow_empty=False), f"Expected {code} to be invalid")

    def test_empty_and_none_handling(self):
        self.assertTrue(is_valid_dewey(None, allow_empty=True))
        self.assertTrue(is_valid_dewey("", allow_empty=True))
        self.assertFalse(is_valid_dewey(None, allow_empty=False))
        self.assertFalse(is_valid_dewey("", allow_empty=False))

    def test_normalize_dewey_code(self):
        self.assertEqual(normalize_dewey_code("90"), "090")
        self.assertEqual(normalize_dewey_code("5"), "005")
        self.assertEqual(normalize_dewey_code("510"), "510")
        self.assertEqual(normalize_dewey_code("641.5"), "641.5")
        self.assertIsNone(normalize_dewey_code("invalid"))


class TestDeweyMapping(unittest.TestCase):
    """Test subject-to-DDC mapping (Section 5 & 19)."""

    def setUp(self):
        self.service = DeweyService()

    def test_standard_subject_mappings(self):
        test_cases = [
            ("mathematics", "510"),
            ("physics", "530"),
            ("psychology", "150"),
            ("history", "900"),
            ("programming", "005"),
        ]
        for subject, expected_code in test_cases:
            with self.subTest(subject=subject):
                result = self.service.classify(title="", categories=[subject])
                self.assertEqual(
                    result.dewey_code,
                    expected_code,
                    f"Expected category '{subject}' to map to {expected_code}, got {result.dewey_code}",
                )

    def test_keyword_matching_in_title(self):
        result = self.service.classify(title="Python Programming for Beginners")
        self.assertEqual(result.dewey_code, "005")
        self.assertEqual(result.dewey_source, "keyword")

        result2 = self.service.classify(title="Introduction to Quantum Mechanics")
        self.assertEqual(result2.dewey_code, "530")


class TestPersianNormalization(unittest.TestCase):
    """Test Persian character normalization and cross-lingual equivalence (Section 7 & 19)."""

    def setUp(self):
        self.service = DeweyService()

    def test_arabic_yeh_and_kaf_normalization(self):
        # ي -> ی, ك -> ک
        self.assertEqual(normalize_persian("فيزيك"), "فیزیک")
        self.assertEqual(normalize_persian("رياضيات"), "ریاضیات")

    def test_zwnj_and_spacing_normalization(self):
        # Zero-width non-joiner (\u200c)
        s1 = normalize_persian("روان‌شناسی")
        s2 = normalize_persian("روان شناسی")
        self.assertEqual(s1, s2)

    def test_persian_variants_produce_same_classification(self):
        # ریاضی, رياضيات, ریاضیات must yield the exact same classification
        variants = ["ریاضی", "رياضيات", "ریاضیات"]
        codes = []
        for v in variants:
            res = self.service.classify(title=v)
            codes.append(res.dewey_code)

        self.assertEqual(len(set(codes)), 1, f"Variants {variants} produced different codes: {codes}")
        self.assertEqual(codes[0], "510")


class TestDeweySorting(unittest.TestCase):
    """Test proper hierarchical and numeric DDC sorting (Section 12 & 19)."""

    def test_numerical_sorting_order(self):
        # Must sort as 90, 100, 510, 530, 800, 900
        # (ASCII string sort would incorrectly place '100' before '90')
        raw_list = ["900", "530", "100", "90", "800", "510"]
        sorted_list = sorted(raw_list, key=dewey_sort_key)
        expected = ["90", "100", "510", "530", "800", "900"]
        self.assertEqual(sorted_list, expected)

    def test_decimal_subclass_sorting(self):
        raw_list = ["520", "519.52", "510", "519.5", "519.12"]
        sorted_list = sorted(raw_list, key=dewey_sort_key)
        expected = ["510", "519.12", "519.5", "519.52", "520"]
        self.assertEqual(sorted_list, expected)

    def test_none_and_empty_sort_last(self):
        raw_list = [None, "510", "", "100"]
        sorted_list = sorted(raw_list, key=dewey_sort_key)
        self.assertEqual(sorted_list[0], "100")
        self.assertEqual(sorted_list[1], "510")
        self.assertIn(sorted_list[2], (None, ""))
        self.assertIn(sorted_list[3], (None, ""))


class TestShelfLocation(unittest.TestCase):
    """Test shelf and physical arrangement resolution (Section 13)."""

    def setUp(self):
        self.service = DeweyService()

    def test_shelf_assignment_science_and_math(self):
        loc510 = self.service.get_shelf_location("510")
        self.assertEqual(loc510["class_code"], "500")
        self.assertEqual(loc510["division_code"], "510")
        self.assertIn("ریاضیات", loc510["division_name"])

        loc530 = self.service.get_shelf_location("530")
        self.assertEqual(loc530["class_code"], "500")
        self.assertEqual(loc530["division_code"], "530")
        self.assertIn("فیزیک", loc530["division_name"])


class TestManualOverrideAndReclassification(unittest.TestCase):
    """Test manual override protection and reclassification (Section 16, 17, 18)."""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        database.init_database(self.conn)
        self.book_service = BookService()

    def tearDown(self):
        self.conn.close()

    def test_manual_override_persists_and_blocks_auto_overwrite(self):
        # 1. Register a book with manual Dewey code
        registered = self.book_service.register_book(
            title="فیزیک هالیدی",
            author="هالیدی",
            dewey_code="530",
            dewey_source="manual",
            conn_or_path=self.conn,
        )
        book_id = registered["id"]

        # 2. Verify registered details
        book = self.book_service.get_book(book_id, conn_or_path=self.conn)
        self.assertEqual(book["dewey_source"], "manual")
        self.assertEqual(book["dewey_code"], "530")

        # 3. Manually override code to 500 (general science)
        self.book_service.update_book_dewey(
            book_id=book_id,
            dewey_code="500",
            dewey_subject="علوم عمومی",
            dewey_source="manual",
            conn_or_path=self.conn,
        )
        book_updated = self.book_service.get_book(book_id, conn_or_path=self.conn)
        self.assertEqual(book_updated["dewey_code"], "500")
        self.assertEqual(book_updated["dewey_source"], "manual")

        # 4. Attempt reclassification without force: should NOT overwrite manual source
        res = self.book_service.reclassify_book(book_id=book_id, force=False, conn_or_path=self.conn)
        self.assertIsNone(res, "reclassify_book without force must return None for manual source")

        book_after = self.book_service.get_book(book_id, conn_or_path=self.conn)
        self.assertEqual(book_after["dewey_code"], "500", "Manual code was unexpectedly modified!")
        self.assertEqual(book_after["dewey_source"], "manual")

        # 5. Forced reclassification overrides
        res_forced = self.book_service.reclassify_book(book_id=book_id, force=True, conn_or_path=self.conn)
        self.assertIsNotNone(res_forced)
        self.assertEqual(res_forced.dewey_code, "530")

        book_forced = self.book_service.get_book(book_id, conn_or_path=self.conn)
        self.assertEqual(book_forced["dewey_code"], "530")

    def test_reclassify_all_books_respects_manual(self):
        # Book 1: Auto classified (mapping)
        self.book_service.register_book(
            title="ریاضیات عمومی",
            auto_classify=True,
            conn_or_path=self.conn,
        )
        # Book 2: Manual override
        self.book_service.register_book(
            title="فیزیک مدرن",
            dewey_code="530",
            dewey_source="manual",
            conn_or_path=self.conn,
        )
        # Book 3: Unclassified old book (NULL)
        cur = self.conn.cursor()
        cur.execute("INSERT INTO books (title, author) VALUES ('کتاب با عنوان نامفهوم xyz123', 'نویسنده')")
        self.conn.commit()

        # Run reclassify_all_books
        report = self.book_service.reclassify_all_books(force=False, conn_or_path=self.conn)
        self.assertEqual(report["total"], 3)
        self.assertEqual(report["skipped_manual"], 1)
        self.assertEqual(report["updated"], 1)  # Book 1 reclassified to 510
        self.assertEqual(report["unclassified"], 1)  # Book 3 unclassifiable


class TestBackwardCompatibility(unittest.TestCase):
    """Test backward compatibility with old database and without DDC (Section 20)."""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        database.init_database(self.conn)
        self.book_service = BookService()

    def tearDown(self):
        self.conn.close()

    def test_book_registration_without_ddc_succeeds(self):
        # A book that cannot be classified should register successfully with dewey_code=None
        res = self.book_service.register_book(
            title="یادداشت‌های روزانه ناشناس ۱۲۳",
            author="نامشخص",
            isbn="9780000000000",
            auto_classify=True,
            conn_or_path=self.conn,
        )
        self.assertIsNotNone(res["id"])
        self.assertIsNone(res["dewey_code"])

        book = self.book_service.get_book(res["id"], conn_or_path=self.conn)
        self.assertIsNotNone(book)
        self.assertEqual(book["title"], "یادداشت‌های روزانه ناشناس ۱۲۳")
        self.assertIsNone(book["dewey_code"])

    def test_legacy_due_column_migrated_and_removed(self):
        # 1. New DB should not have 'due' column
        cur = self.conn.cursor()
        cur.execute('PRAGMA table_info("books")')
        cols = {row[1] for row in cur.fetchall()}
        self.assertNotIn("due", cols)
        self.assertIn("dewey_code", cols)

        # 2. Test migration on a pre-existing DB with legacy 'due' column
        test_conn = sqlite3.connect(":memory:")
        t_cur = test_conn.cursor()
        t_cur.execute("CREATE TABLE books (id INTEGER PRIMARY KEY, title TEXT, author TEXT, isbn TEXT, due TEXT)")
        t_cur.execute("INSERT INTO books (title, author, due) VALUES ('کتاب ریاضی', 'نویسنده', '510')")
        test_conn.commit()

        # Run database initialization/migration
        database.init_database(test_conn)

        t_cur.execute('PRAGMA table_info("books")')
        migrated_cols = {row[1] for row in t_cur.fetchall()}
        self.assertNotIn("due", migrated_cols)
        self.assertIn("dewey_code", migrated_cols)

        t_cur.execute("SELECT title, dewey_code FROM books WHERE id = 1")
        row = t_cur.fetchone()
        self.assertEqual(row[0], "کتاب ریاضی")
        self.assertEqual(row[1], "510")
        test_conn.close()


class TestISBNService(unittest.TestCase):
    """Test ISBN cleaning and validation."""

    def test_clean_isbn(self):
        self.assertEqual(clean_isbn("978-0-306-40615-7"), "9780306406157")
        self.assertEqual(clean_isbn("۰-۳۰۶-۴۰۶۱۵-۷"), "0306406157")

    def test_isbn_validation(self):
        # Valid ISBN-10
        self.assertTrue(is_valid_isbn("0-306-40615-2"))
        # Valid ISBN-13
        self.assertTrue(is_valid_isbn("978-0-306-40615-7"))
        # Invalid ISBN
        self.assertFalse(is_valid_isbn("978-0-306-40615-9"))
        self.assertFalse(is_valid_isbn("123"))
