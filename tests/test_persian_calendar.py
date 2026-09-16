"""
Unit tests for the global Jalali (Persian) Calendar component and utilities.
"""

from __future__ import annotations

import datetime
import unittest

import jdatetime

from persian_calendar import (
    PERSIAN_MONTHS,
    PERSIAN_WEEKDAYS_FULL,
    PERSIAN_WEEKDAYS_SHORT,
    add_days_jalali,
    format_jalali_date,
    format_jalali_date_long,
    get_days_in_jalali_month,
    get_jalali_first_weekday,
    get_today_jalali,
    gregorian_to_jalali,
    gregorian_to_jalali_str,
    is_leap_jalali_year,
    is_valid_jalali_date,
    jalali_to_gregorian,
    jalali_to_gregorian_str,
    parse_jalali_date,
    to_ascii_digits,
    to_persian_digits,
)


class TestPersianCalendarUtilities(unittest.TestCase):
    """Test suite for Jalali date calculations, formatting, parsing, and conversions."""

    def test_constants(self):
        self.assertEqual(len(PERSIAN_MONTHS), 12)
        self.assertEqual(PERSIAN_MONTHS[0], "فروردین")
        self.assertEqual(PERSIAN_MONTHS[11], "اسفند")
        self.assertEqual(len(PERSIAN_WEEKDAYS_SHORT), 7)
        self.assertEqual(len(PERSIAN_WEEKDAYS_FULL), 7)
        self.assertEqual(PERSIAN_WEEKDAYS_FULL[0], "شنبه")
        self.assertEqual(PERSIAN_WEEKDAYS_FULL[6], "جمعه")

    def test_digit_normalization(self):
        self.assertEqual(to_ascii_digits("۱۴۰۳/۰۶/۲۵"), "1403/06/25")
        self.assertEqual(to_ascii_digits("٠١٢٣٤٥٦٧٨٩"), "0123456789")
        self.assertEqual(to_ascii_digits(""), "")
        self.assertEqual(to_ascii_digits(None), "")

        self.assertEqual(to_persian_digits("1403-06-25"), "۱۴۰۳-۰۶-۲۵")
        self.assertEqual(to_persian_digits(15), "۱۵")

    def test_leap_year_detection(self):
        # 1399 and 1403 are leap years in the Persian calendar
        self.assertTrue(is_leap_jalali_year(1399))
        self.assertTrue(is_leap_jalali_year(1403))
        # 1400, 1401, 1402, 1404 are not leap years
        self.assertFalse(is_leap_jalali_year(1400))
        self.assertFalse(is_leap_jalali_year(1401))
        self.assertFalse(is_leap_jalali_year(1402))
        self.assertFalse(is_leap_jalali_year(1404))

    def test_days_in_jalali_month(self):
        # Months 1 to 6 have 31 days
        for m in range(1, 7):
            self.assertEqual(get_days_in_jalali_month(1403, m), 31)

        # Months 7 to 11 have 30 days
        for m in range(7, 12):
            self.assertEqual(get_days_in_jalali_month(1403, m), 30)

        # Month 12 (Esfand) in leap year has 30 days
        self.assertEqual(get_days_in_jalali_month(1403, 12), 30)
        # Month 12 (Esfand) in non-leap year has 29 days
        self.assertEqual(get_days_in_jalali_month(1404, 12), 29)

    def test_get_jalali_first_weekday(self):
        # 1403-01-01 was Wednesday (weekday index 4 where Sat=0, Sun=1, Mon=2, Tue=3, Wed=4, Thu=5, Fri=6)
        self.assertEqual(get_jalali_first_weekday(1403, 1), 4)
        # 1403-01-04 was Saturday (weekday index 0)
        d_sat = jdatetime.date(1403, 1, 4)
        self.assertEqual(d_sat.weekday(), 0)

    def test_format_jalali_date(self):
        j_date = jdatetime.date(1403, 6, 5)
        self.assertEqual(format_jalali_date(j_date), "1403-06-05")

        g_date = datetime.date(2024, 9, 15)
        self.assertEqual(format_jalali_date(g_date), "1403-06-25")

    def test_format_jalali_date_long(self):
        j_date = jdatetime.date(1403, 6, 25)
        formatted_long = format_jalali_date_long(j_date)
        self.assertIn("شهریور", formatted_long)
        self.assertIn("۱۴۰۳", formatted_long)
        self.assertTrue("یک‌شنبه" in formatted_long or "یکشنبه" in formatted_long)

    def test_parse_jalali_date(self):
        # Standard format
        d1 = parse_jalali_date("1403-06-25")
        self.assertIsNotNone(d1)
        self.assertEqual(d1.year, 1403)
        self.assertEqual(d1.month, 6)
        self.assertEqual(d1.day, 25)

        # Slash separator
        d2 = parse_jalali_date("1403/06/25")
        self.assertEqual(d2, d1)

        # Dot separator
        d3 = parse_jalali_date("1403.06.25")
        self.assertEqual(d3, d1)

        # Persian digits
        d4 = parse_jalali_date("۱۴۰۳-۰۶-۲۵")
        self.assertEqual(d4, d1)

        # Direct jdatetime.date object
        d5 = parse_jalali_date(d1)
        self.assertEqual(d5, d1)

        # datetime.date object
        g_d = datetime.date(2024, 9, 15)
        d6 = parse_jalali_date(g_d)
        self.assertEqual(d6, d1)

        # Invalid inputs
        self.assertIsNone(parse_jalali_date(None))
        self.assertIsNone(parse_jalali_date(""))
        self.assertIsNone(parse_jalali_date("not-a-date"))
        self.assertIsNone(parse_jalali_date("1403-13-01"))  # month > 12
        self.assertIsNone(parse_jalali_date("1403-01-32"))  # day > 31
        self.assertIsNone(parse_jalali_date("1404-12-30"))  # non-leap year Esfand 30

    def test_is_valid_jalali_date(self):
        self.assertTrue(is_valid_jalali_date("1403-06-25"))
        self.assertTrue(is_valid_jalali_date("1403/12/30"))  # 1403 is leap
        self.assertFalse(is_valid_jalali_date("1404/12/30"))  # 1404 is not leap
        self.assertFalse(is_valid_jalali_date("invalid"))

    def test_conversions_between_jalali_and_gregorian(self):
        # 1403-06-25 is 2024-09-15
        g_date = jalali_to_gregorian("1403-06-25")
        self.assertEqual(g_date, datetime.date(2024, 9, 15))
        self.assertEqual(jalali_to_gregorian_str("1403-06-25"), "2024-09-15")

        j_date = gregorian_to_jalali("2024-09-15")
        self.assertEqual(j_date, jdatetime.date(1403, 6, 25))
        self.assertEqual(gregorian_to_jalali_str("2024-09-15"), "1403-06-25")

        # Invalid strings return None
        self.assertIsNone(jalali_to_gregorian("invalid-date"))
        self.assertIsNone(jalali_to_gregorian_str("invalid-date"))
        self.assertIsNone(gregorian_to_jalali("invalid-date"))
        self.assertIsNone(gregorian_to_jalali_str("invalid-date"))

    def test_date_arithmetic(self):
        base = jdatetime.date(1403, 6, 25)
        added = add_days_jalali(base, 10)
        self.assertEqual(added, jdatetime.date(1403, 7, 4))
        subtracted = add_days_jalali(base, -5)
        self.assertEqual(subtracted, jdatetime.date(1403, 6, 20))


class TestPersianCalendarUI(unittest.TestCase):
    """Test suite for Persian Calendar UI components."""

    @classmethod
    def setUpClass(cls):
        # Create headless / withdraw Tk root
        import customtkinter as ctk

        cls.root = ctk.CTk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    def test_jalali_date_entry_widget(self):
        from persian_calendar import JalaliDateEntry

        entry_frame = JalaliDateEntry(self.root, initial_date="1403-06-25")
        self.assertEqual(entry_frame.get(), "1403-06-25")
        self.assertEqual(entry_frame.get_date(), jdatetime.date(1403, 6, 25))

        entry_frame.set("1403-07-10")
        self.assertEqual(entry_frame.get(), "1403-07-10")
        self.assertEqual(entry_frame.get_date(), jdatetime.date(1403, 7, 10))

        entry_frame.set_date(jdatetime.date(1403, 8, 1))
        self.assertEqual(entry_frame.get(), "1403-08-01")

        entry_frame.destroy()

    def test_create_date_picker_button(self):
        import customtkinter as ctk

        from persian_calendar import create_date_picker_button

        ent = ctk.CTkEntry(self.root)
        btn = create_date_picker_button(self.root, entry_widget=ent)
        self.assertIsNotNone(btn)
        btn.destroy()
        ent.destroy()

    def test_dialog_lifecycle(self):
        from persian_calendar import JalaliDatePickerDialog

        dialog = JalaliDatePickerDialog(self.root, initial_date="1403-06-25")
        self.assertEqual(dialog.selected_date, jdatetime.date(1403, 6, 25))
        self.assertEqual(dialog.view_year, 1403)
        self.assertEqual(dialog.view_month, 6)

        # Test selecting a new date
        new_d = jdatetime.date(1403, 6, 20)
        dialog._on_day_clicked(new_d)
        self.assertEqual(dialog.selected_date, new_d)

        # Test jump to today
        dialog._jump_to_today()
        self.assertEqual(dialog.selected_date, get_today_jalali())

        # Test confirm
        dialog._confirm_selection()
        self.assertEqual(dialog.result, format_jalali_date(get_today_jalali()))


if __name__ == "__main__":
    unittest.main()
