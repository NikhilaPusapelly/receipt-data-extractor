"""
Receipt Data Extractor — Numerator-style Config-Driven Architecture
====================================================================
Parses receipt text (from raw text, OCR images, or HTML emails) into
structured JSON using per-retailer regex configurations.

Usage:
    python receipt_extractor.py                        # run sample receipts
    python receipt_extractor.py my_receipt.txt         # parse text file
    python receipt_extractor.py receipt.jpg            # parse image (OCR)
    python receipt_extractor.py email.html             # parse HTML email
"""

import re
import json
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Regex Patterns (fallback / global defaults)
# ---------------------------------------------------------------------------

DATE_PATTERNS = [
    r'\b\d{4}-\d{2}-\d{2}\b',
    r'\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4}\b',
    r'\b(?:January|February|March|April|May|June|July|August|'
    r'September|October|November|December)\s+\d{1,2},?\s+\d{4}\b',
]

ITEM_PATTERN = re.compile(
    r'([A-Za-z][A-Za-z0-9 \-\'\.#&\/]+?)\s*\$([\d]+\.\d{2})'
)

TOTAL_PATTERN    = re.compile(r'(?<!sub)\btotal[:\s]+\$?([\d,]+\.\d{2})', re.IGNORECASE)
SUBTOTAL_PATTERN = re.compile(r'subtotal[:\s]+\$?([\d,]+\.\d{2})', re.IGNORECASE)
TAX_PATTERN      = re.compile(r'tax(?:\s*\([\d.]+%\))?[:\s]+\$?([\d,]+\.\d{2})', re.IGNORECASE)
TIME_PATTERN     = re.compile(r'\d{1,2}:\d{2}\s*(?:AM|PM)', re.IGNORECASE)

SKIP_WORDS = {
    "subtotal", "tax", "total", "order", "shipping", "card",
    "visa", "mastercard", "thank", "amex", "cash", "change", "pm"
}


# ---------------------------------------------------------------------------
# Config Loader
# ---------------------------------------------------------------------------

def load_config(store_hint: str) -> dict:
    """
    Load a retailer-specific config JSON from /configs folder.
    Falls back to default global patterns if no config found.
    """
    config_dir = Path(__file__).parent / "configs"
    slug = store_hint.lower().replace(" ", "_").replace("'", "")

    for config_file in config_dir.glob("*.json"):
        cfg = json.loads(config_file.read_text(encoding="utf-8"))
        for keyword in cfg.get("keywords", []):
            if keyword.lower() in slug or keyword.lower() in store_hint.lower():
                return cfg

    return {}  # empty = use global defaults


def get_pattern(config: dict, key: str, default_pattern):
    """Return compiled regex from config, or fall back to default."""
    raw = config.get(key)
    if raw:
        return re.compile(raw, re.IGNORECASE)
    return default_pattern


# ---------------------------------------------------------------------------
# Extraction Functions
# ---------------------------------------------------------------------------

def extract_date(text: str) -> str | None:
    for pattern in DATE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0).strip()
    return None


def extract_store(text: str, config: dict) -> str:
    if config.get("store_name"):
        return config["store_name"]
    text_upper = text.upper()
    if "WHOLE FOODS" in text_upper:
        return "Whole Foods Market"
    elif "AMAZON" in text_upper:
        return "Amazon"
    elif "STARBUCKS" in text_upper:
        return "Starbucks"
    for line in text.strip().split("\n"):
        line = line.strip()
        if line:
            return line[:60]
    return "Unknown Store"


def extract_items(text: str, config: dict) -> list[dict]:
    items = []
    seen = set()

    skip = set(config.get("skip_words", [])) | SKIP_WORDS
    item_pat = get_pattern(config, "item_pattern", ITEM_PATTERN)

    cleaned = TIME_PATTERN.sub("", text)

    for name, price_str in item_pat.findall(cleaned):
        name = re.sub(r'\s+', ' ', name).strip()
        name_lower = name.lower()

        # Whole-word skip check — avoids "am" hitting "Caramel"
        if any(re.search(r'\b' + re.escape(w) + r'\b', name_lower) for w in skip):
            continue

        try:
            price = float(price_str)
        except ValueError:
            continue

        if not (0.01 <= price <= 9999.99):
            continue

        key = name_lower
        if key not in seen and len(name) > 2:
            seen.add(key)
            items.append({"name": name, "price": price})

    return items


def extract_total(text: str, config: dict) -> float | None:
    pat = get_pattern(config, "total_pattern", TOTAL_PATTERN)
    match = pat.search(text)
    return float(match.group(1).replace(',', '')) if match else None


def extract_subtotal(text: str) -> float | None:
    match = SUBTOTAL_PATTERN.search(text)
    return float(match.group(1).replace(',', '')) if match else None


def extract_tax(text: str) -> float | None:
    match = TAX_PATTERN.search(text)
    return float(match.group(1).replace(',', '')) if match else None


def detect_currency(text: str) -> str:
    if '$' in text:  return "USD"
    if '₹' in text:  return "INR"
    if '£' in text:  return "GBP"
    if '€' in text:  return "EUR"
    return "UNKNOWN"


def calculate_confidence(items: list, total: float, date: str) -> float:
    score = 0.0
    if items:  score += 0.4
    if total:  score += 0.3
    if date:   score += 0.3
    return round(score, 2)


# ---------------------------------------------------------------------------
# OCR Pipeline
# ---------------------------------------------------------------------------

def ocr_image_to_text(image_path: str) -> str:
    """
    Convert a receipt image to text using Tesseract OCR.
    Applies grayscale + threshold preprocessing to improve accuracy.
    Requires: pip install pytesseract pillow
    """
    try:
        import pytesseract
        from PIL import Image, ImageFilter, ImageEnhance

        img = Image.open(image_path).convert('L')         # grayscale
        img = ImageEnhance.Contrast(img).enhance(2.0)     # boost contrast
        img = img.filter(ImageFilter.SHARPEN)             # sharpen edges
        text = pytesseract.image_to_string(img)
        return text
    except ImportError:
        raise ImportError(
            "OCR requires pytesseract and pillow.\n"
            "Install with: pip install pytesseract pillow\n"
            "Also install Tesseract: https://github.com/tesseract-ocr/tesseract"
        )


# ---------------------------------------------------------------------------
# XPath Email Receipt Parser
# ---------------------------------------------------------------------------

def parse_email_receipt(html: str) -> dict:
    """
    Extract receipt data from HTML email receipts using XPath.
    Handles common e-commerce email structures (Amazon, etc.)
    Requires: pip install lxml
    """
    try:
        from lxml import etree

        parser = etree.HTMLParser()
        tree = etree.fromstring(html.encode("utf-8"), parser)

        def xpath_first(expressions: list) -> str | None:
            for expr in expressions:
                results = tree.xpath(expr)
                if results:
                    val = results[0]
                    return val.strip() if isinstance(val, str) else None
            return None

        def xpath_all(expressions: list) -> list:
            for expr in expressions:
                results = tree.xpath(expr)
                if results:
                    return [r.strip() for r in results if r.strip()]
            return []

        # Try multiple XPath strategies for item names
        item_names = xpath_all([
            '//td[contains(@class,"item-name")]/text()',
            '//span[contains(@class,"product-name")]/text()',
            '//td[contains(@class,"description")]/text()',
            '//div[contains(@class,"item-title")]/text()',
        ])

        # Try multiple XPath strategies for prices
        item_prices = xpath_all([
            '//td[contains(@class,"item-price")]/text()',
            '//span[contains(@class,"price")]/text()',
            '//td[contains(@class,"amount")]/text()',
        ])

        # Parse prices — strip $ signs
        parsed_prices = []
        for p in item_prices:
            try:
                parsed_prices.append(float(re.sub(r'[^\d.]', '', p)))
            except ValueError:
                continue

        items = [
            {"name": n, "price": p}
            for n, p in zip(item_names, parsed_prices)
        ]

        # Extract total — iterate all matches, skip label text, take first numeric value
        total = None
        for expr in [
            '//td[contains(@class,"order-total")]/text()',
            '//span[contains(@class,"total-price")]/text()',
            '//td[contains(@class,"grand-total")]/text()',
        ]:
            for val in tree.xpath(expr):
                cleaned = re.sub(r'[^\d.]', '', val.strip())
                if cleaned:
                    try:
                        total = float(cleaned)
                        break
                    except ValueError:
                        continue
            if total:
                break

        # Extract date
        date_str = xpath_first([
            '//td[contains(@class,"order-date")]/text()',
            '//span[contains(@class,"date")]/text()',
            '//*[contains(text(),"Order Date")]/following-sibling::*/text()',
        ])

        # Extract store name
        store = xpath_first([
            '//div[contains(@class,"store-name")]/text()',
            '//h1/text()',
            '//title/text()',
        ]) or "Unknown Store"

        date = extract_date(date_str) if date_str else None

        return {
            "source":     "email_html",
            "store":      store,
            "date":       date,
            "currency":   "USD",
            "items":      items,
            "item_count": len(items),
            "items_subtotal": round(sum(i["price"] for i in items), 2),
            "total":      total or 0.0,
            "confidence": calculate_confidence(items, total, date),
        }

    except ImportError:
        raise ImportError(
            "XPath parsing requires lxml.\n"
            "Install with: pip install lxml"
        )


# ---------------------------------------------------------------------------
# Main Parser
# ---------------------------------------------------------------------------

def parse_receipt(text: str, config: dict = None) -> dict:
    if config is None:
        config = load_config(text[:200])  # sniff store from first 200 chars

    items    = extract_items(text, config)
    total    = extract_total(text, config)
    date     = extract_date(text)

    if not items:
        print("[WARNING] No items detected — check receipt formatting")

    return {
        "store":          extract_store(text, config),
        "date":           date,
        "currency":       detect_currency(text),
        "items":          items,
        "item_count":     len(items),
        "items_subtotal": round(sum(i["price"] for i in items), 2),
        "subtotal":       extract_subtotal(text) or 0.0,
        "tax":            extract_tax(text) or 0.0,
        "total":          total or 0.0,
        "confidence":     calculate_confidence(items, total, date),
    }


# ---------------------------------------------------------------------------
# Sample Receipts
# ---------------------------------------------------------------------------

SAMPLE_RECEIPTS = {
    "whole_foods": """WHOLE FOODS MARKET
123 Main Street, Austin TX
Date: 04/15/2024  Time: 14:32

Organic Bananas         $1.29
Almond Milk 64oz        $4.99
Greek Yogurt 32oz       $6.49
Free Range Eggs 12ct    $5.79
Sourdough Bread         $3.99
Sparkling Water 6pk     $7.49

Subtotal:              $29.99
Tax (8.25%):            $2.47
TOTAL:                 $32.46
""",
    "amazon": """AMAZON ORDER RECEIPT
Order #: 112-3456789-0123456
Order Date: March 22, 2024

Logitech MX Master 3      $99.99
USB-C Hub 7-Port          $34.95
Cable Management Kit      $12.49
Wireless Charging Pad     $27.99

Subtotal:                $175.42
Shipping:                  $0.00
Tax:                      $14.48
ORDER TOTAL:             $189.90
""",
    "starbucks": """STARBUCKS #12345
789 Coffee Lane
2024-01-08  09:15 AM

Caramel Macchiato Venti   $6.75
Blueberry Scone            $3.45
Cold Brew Grande           $5.25
Cheese Danish              $3.95

Subtotal:                 $19.40
Tax:                       $1.60
Total:                    $21.00
""",
}


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        if not path.exists():
            print(f"[ERROR] File not found: {path}")
            sys.exit(1)

        suffix = path.suffix.lower()

        if suffix in (".jpg", ".jpeg", ".png", ".tiff", ".bmp"):
            print(f"[OCR] Processing image: {path.name}")
            text = ocr_image_to_text(str(path))
            print("[OCR] Extracted text:")
            print(text[:500])
            result = parse_receipt(text)

        elif suffix in (".html", ".htm"):
            print(f"[XPath] Processing HTML email: {path.name}")
            html = path.read_text(encoding="utf-8")
            result = parse_email_receipt(html)

        else:
            text = path.read_text(encoding="utf-8")
            result = parse_receipt(text)

        print(json.dumps(result, indent=2))

    else:
        print("Running on sample receipts...\n")
        results = {}
        for name, text in SAMPLE_RECEIPTS.items():
            print(f"--- Parsing: {name} ---")
            results[name] = parse_receipt(text)

        output = json.dumps(results, indent=2)
        print("\n" + output)

        out_path = Path("receipts_output.json")
        out_path.write_text(output, encoding="utf-8")
        print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
