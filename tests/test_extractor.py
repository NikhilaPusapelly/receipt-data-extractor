"""
Unit Tests — Receipt Data Extractor
=====================================
Run with:  python -m pytest tests/test_extractor.py -v
       or: python tests/test_extractor.py
"""

import sys
import unittest
from pathlib import Path

# Allow imports from parent directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.receipt_extractor import (
    parse_receipt,
    extract_date,
    extract_items,
    extract_total,
    extract_subtotal,
    extract_tax,
    detect_currency,
    calculate_confidence,
    parse_email_receipt,
    SAMPLE_RECEIPTS,
)


# ---------------------------------------------------------------------------
# Date Extraction Tests
# ---------------------------------------------------------------------------

class TestDateExtraction(unittest.TestCase):

    def test_iso_date(self):
        self.assertEqual(extract_date("Receipt\n2024-01-08\nItem $5.00"), "2024-01-08")

    def test_us_date_slash(self):
        self.assertEqual(extract_date("Date: 04/15/2024"), "04/15/2024")

    def test_us_date_dash(self):
        self.assertEqual(extract_date("Date: 04-15-2024"), "04-15-2024")

    def test_long_date_format(self):
        result = extract_date("Order Date: March 22, 2024")
        self.assertEqual(result, "March 22, 2024")

    def test_long_date_no_comma(self):
        result = extract_date("Order Date: March 22 2024")
        self.assertIsNotNone(result)

    def test_no_date_returns_none(self):
        self.assertIsNone(extract_date("STORE\nItem A $5.00\nTotal $5.00"))


# ---------------------------------------------------------------------------
# Item Extraction Tests
# ---------------------------------------------------------------------------

class TestItemExtraction(unittest.TestCase):

    def test_whole_foods_item_count(self):
        result = parse_receipt(SAMPLE_RECEIPTS["whole_foods"])
        self.assertEqual(result["item_count"], 6)

    def test_amazon_item_count(self):
        result = parse_receipt(SAMPLE_RECEIPTS["amazon"])
        self.assertEqual(result["item_count"], 4)

    def test_starbucks_item_count(self):
        result = parse_receipt(SAMPLE_RECEIPTS["starbucks"])
        self.assertEqual(result["item_count"], 4)

    def test_caramel_macchiato_extracted(self):
        """Regression test: 'am' in SKIP_WORDS must not block 'Caramel'"""
        result = parse_receipt(SAMPLE_RECEIPTS["starbucks"])
        names = [i["name"] for i in result["items"]]
        self.assertIn("Caramel Macchiato Venti", names)

    def test_subtotal_not_extracted_as_item(self):
        result = parse_receipt(SAMPLE_RECEIPTS["whole_foods"])
        names = [i["name"].lower() for i in result["items"]]
        self.assertNotIn("subtotal", names)

    def test_tax_not_extracted_as_item(self):
        result = parse_receipt(SAMPLE_RECEIPTS["whole_foods"])
        names = [i["name"].lower() for i in result["items"]]
        self.assertFalse(any("tax" in n for n in names))

    def test_total_not_extracted_as_item(self):
        result = parse_receipt(SAMPLE_RECEIPTS["starbucks"])
        names = [i["name"].lower() for i in result["items"]]
        self.assertFalse(any("total" in n for n in names))

    def test_no_duplicate_items(self):
        result = parse_receipt(SAMPLE_RECEIPTS["whole_foods"])
        names = [i["name"] for i in result["items"]]
        self.assertEqual(len(names), len(set(names)))

    def test_item_prices_are_floats(self):
        result = parse_receipt(SAMPLE_RECEIPTS["amazon"])
        for item in result["items"]:
            self.assertIsInstance(item["price"], float)

    def test_empty_receipt_returns_no_items(self):
        result = parse_receipt("STORE NAME\nDate: 01/01/2024\nTotal: $5.00")
        self.assertEqual(result["item_count"], 0)


# ---------------------------------------------------------------------------
# Total / Subtotal / Tax Tests
# ---------------------------------------------------------------------------

class TestTotals(unittest.TestCase):

    def test_whole_foods_total_not_subtotal(self):
        """Critical: TOTAL ($32.46) must not be confused with Subtotal ($29.99)"""
        result = parse_receipt(SAMPLE_RECEIPTS["whole_foods"])
        self.assertEqual(result["total"], 32.46)
        self.assertNotEqual(result["total"], 29.99)

    def test_whole_foods_subtotal(self):
        result = parse_receipt(SAMPLE_RECEIPTS["whole_foods"])
        self.assertEqual(result["subtotal"], 29.99)

    def test_whole_foods_tax(self):
        result = parse_receipt(SAMPLE_RECEIPTS["whole_foods"])
        self.assertEqual(result["tax"], 2.47)

    def test_amazon_total(self):
        result = parse_receipt(SAMPLE_RECEIPTS["amazon"])
        self.assertEqual(result["total"], 189.90)

    def test_starbucks_total(self):
        result = parse_receipt(SAMPLE_RECEIPTS["starbucks"])
        self.assertEqual(result["total"], 21.00)

    def test_missing_total_returns_zero(self):
        result = parse_receipt("STORE\nItem A   $5.00\nDate: 2024-01-01")
        self.assertEqual(result["total"], 0.0)


# ---------------------------------------------------------------------------
# Currency Detection Tests
# ---------------------------------------------------------------------------

class TestCurrencyDetection(unittest.TestCase):

    def test_usd_detected(self):
        self.assertEqual(detect_currency("Total $10.00"), "USD")

    def test_inr_detected(self):
        self.assertEqual(detect_currency("Total ₹850.00"), "INR")

    def test_gbp_detected(self):
        self.assertEqual(detect_currency("Total £12.50"), "GBP")

    def test_eur_detected(self):
        self.assertEqual(detect_currency("Total €9.99"), "EUR")

    def test_unknown_currency(self):
        self.assertEqual(detect_currency("Total 10.00"), "UNKNOWN")


# ---------------------------------------------------------------------------
# Confidence Score Tests
# ---------------------------------------------------------------------------

class TestConfidenceScore(unittest.TestCase):

    def test_full_confidence(self):
        items = [{"name": "A", "price": 1.0}]
        self.assertEqual(calculate_confidence(items, 5.0, "2024-01-01"), 1.0)

    def test_no_items_reduces_confidence(self):
        self.assertEqual(calculate_confidence([], 5.0, "2024-01-01"), 0.6)

    def test_no_total_reduces_confidence(self):
        items = [{"name": "A", "price": 1.0}]
        self.assertEqual(calculate_confidence(items, None, "2024-01-01"), 0.7)

    def test_no_date_reduces_confidence(self):
        items = [{"name": "A", "price": 1.0}]
        self.assertEqual(calculate_confidence(items, 5.0, None), 0.7)

    def test_nothing_found_zero_confidence(self):
        self.assertEqual(calculate_confidence([], None, None), 0.0)

    def test_all_samples_full_confidence(self):
        for name, text in SAMPLE_RECEIPTS.items():
            result = parse_receipt(text)
            self.assertEqual(result["confidence"], 1.0, f"{name} should have 1.0 confidence")


# ---------------------------------------------------------------------------
# Store Name Tests
# ---------------------------------------------------------------------------

class TestStoreExtraction(unittest.TestCase):

    def test_whole_foods_store(self):
        result = parse_receipt(SAMPLE_RECEIPTS["whole_foods"])
        self.assertEqual(result["store"], "Whole Foods Market")

    def test_amazon_store(self):
        result = parse_receipt(SAMPLE_RECEIPTS["amazon"])
        self.assertEqual(result["store"], "Amazon")

    def test_starbucks_store(self):
        result = parse_receipt(SAMPLE_RECEIPTS["starbucks"])
        self.assertEqual(result["store"], "Starbucks")

    def test_unknown_store_fallback(self):
        result = parse_receipt("RANDOM STORE\nDate: 2024-01-01\nItem $5.00\nTotal $5.00")
        self.assertEqual(result["store"], "RANDOM STORE")


# ---------------------------------------------------------------------------
# XPath Email Parser Tests
# ---------------------------------------------------------------------------

class TestEmailParser(unittest.TestCase):

    def setUp(self):
        self.sample_html = """
        <html><body>
          <div class="store-name">Amazon</div>
          <span class="date">March 22, 2024</span>
          <table>
            <tr>
              <td class="item-name">Logitech MX Master 3</td>
              <td class="item-price">$99.99</td>
            </tr>
            <tr>
              <td class="item-name">USB-C Hub 7-Port</td>
              <td class="item-price">$34.95</td>
            </tr>
            <tr>
              <td class="order-total">$134.94</td>
            </tr>
          </table>
        </body></html>
        """

    def test_email_items_extracted(self):
        try:
            result = parse_email_receipt(self.sample_html)
            self.assertEqual(len(result["items"]), 2)
        except ImportError:
            self.skipTest("lxml not installed")

    def test_email_item_names(self):
        try:
            result = parse_email_receipt(self.sample_html)
            names = [i["name"] for i in result["items"]]
            self.assertIn("Logitech MX Master 3", names)
        except ImportError:
            self.skipTest("lxml not installed")

    def test_email_total_extracted(self):
        try:
            result = parse_email_receipt(self.sample_html)
            self.assertEqual(result["total"], 134.94)
        except ImportError:
            self.skipTest("lxml not installed")

    def test_email_source_field(self):
        try:
            result = parse_email_receipt(self.sample_html)
            self.assertEqual(result["source"], "email_html")
        except ImportError:
            self.skipTest("lxml not installed")


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

class TestIntegration(unittest.TestCase):

    def test_output_has_required_keys(self):
        required = {"store", "date", "currency", "items", "item_count",
                    "items_subtotal", "subtotal", "tax", "total", "confidence"}
        for name, text in SAMPLE_RECEIPTS.items():
            result = parse_receipt(text)
            missing = required - result.keys()
            self.assertEqual(missing, set(), f"{name} missing keys: {missing}")

    def test_items_subtotal_matches_sum(self):
        for name, text in SAMPLE_RECEIPTS.items():
            result = parse_receipt(text)
            expected = round(sum(i["price"] for i in result["items"]), 2)
            self.assertEqual(result["items_subtotal"], expected, f"{name} subtotal mismatch")

    def test_all_items_have_name_and_price(self):
        for name, text in SAMPLE_RECEIPTS.items():
            result = parse_receipt(text)
            for item in result["items"]:
                self.assertIn("name", item)
                self.assertIn("price", item)
                self.assertGreater(len(item["name"]), 0)
                self.assertGreater(item["price"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
