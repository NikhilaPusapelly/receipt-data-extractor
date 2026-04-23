# Receipt Data Extractor

A Python-based receipt parsing engine that extracts structured data from
raw receipt text, OCR-scanned images, and HTML email receipts using
regular expressions and XPath.

Built to mirror real-world data extraction pipelines used in market
research and consumer analytics platforms.

---

## Features

- **Regex-based text parsing** — extracts items, prices, dates, totals
- **Config-driven architecture** — per-retailer JSON configs (scalable to thousands)
- **OCR pipeline** — parse receipt images using Tesseract
- **XPath email parser** — extract data from HTML receipt emails
- **Confidence scoring** — rates extraction quality (0.0 to 1.0)
- **Currency detection** — USD, INR, GBP, EUR
- **Unit tested** — 30+ tests covering all extraction functions

---

## Project Structure

```
receipt-extractor/
├── receipt_extractor.py        # core parser
├── tests/
│   └── test_extractor.py       # unit test suite (30+ tests)
├── configs/
│   ├── whole_foods.json        # retailer-specific regex config
│   ├── amazon.json
│   └── starbucks.json
├── samples/
│   └── amazon_email.html       # sample HTML email receipt
└── README.md
```

---

## Installation

```bash
# Core (no dependencies)
python receipt_extractor.py

# For OCR (image parsing)
pip install pytesseract pillow
# Also install Tesseract: https://github.com/tesseract-ocr/tesseract

# For XPath (HTML email parsing)
pip install lxml

# For running tests
pip install pytest
```

---

## Usage

```bash
# Run all sample receipts
python receipt_extractor.py

# Parse a text receipt
python receipt_extractor.py my_receipt.txt

# Parse a receipt image (requires pytesseract)
python receipt_extractor.py receipt.jpg

# Parse an HTML email receipt (requires lxml)
python receipt_extractor.py email.html
```

---

## Running Tests

```bash
# Run all tests with verbose output
python -m pytest tests/test_extractor.py -v

# Run a specific test class
python -m pytest tests/test_extractor.py::TestTotals -v
```

---

## Config-Driven Architecture

Each retailer has its own JSON config in `/configs`. This allows patterns
to be tuned per store without touching core logic — the same approach
used in large-scale receipt parsing platforms.

```json
{
  "store_name": "Whole Foods Market",
  "keywords": ["whole foods"],
  "item_pattern": "([A-Za-z][A-Za-z0-9 ]+?)\\s*\\$([\\d]+\\.\\d{2})",
  "total_pattern": "(?<!sub)\\btotal[:\\s]+\\$?([\\d,]+\\.\\d{2})",
  "skip_words": ["subtotal", "tax", "total"],
  "date_format": "US"
}
```

To add a new retailer, just drop a new `.json` file into `/configs`.

---

## Sample Output

```json
{
  "store": "Whole Foods Market",
  "date": "04/15/2024",
  "currency": "USD",
  "items": [
    { "name": "Organic Bananas", "price": 1.29 },
    { "name": "Almond Milk 64oz", "price": 4.99 }
  ],
  "item_count": 6,
  "items_subtotal": 30.04,
  "subtotal": 29.99,
  "tax": 2.47,
  "total": 32.46,
  "confidence": 1.0
}
```

---

## Technologies

- Python 3.10+
- `re` — regular expressions
- `lxml` — XPath parsing for HTML emails
- `pytesseract` + `Pillow` — OCR for receipt images
- `unittest` / `pytest` — test-driven development
- JSON — config format and output format
