# CleanSlate

A blazing-fast, lightweight Python library and CLI tool designed to scrub Personally Identifiable Information (PII) from datasets for LLM training and RAG pipelines.

## Features

- **Maximum Speed & Zero Dependencies:** Relies exclusively on Python's standard library. No `pandas`, `spaCy`, or other heavy external packages.
- **Deterministic Validation:** Raw regex matches for high-risk entities (like credit cards and IPs) pass algorithmic checksums (e.g., Luhn algorithm, octet range checks) before being flagged to eliminate false positives.
- **Pre-compiled Regex:** All regular expressions are compiled at the module level using `re.compile()` for O(1) setup time during execution.

## Supported Entities

- **Global:**
  - `EMAIL`
  - `PHONE_GENERIC` (international)
  - `CREDIT_CARD` (13-16 digits with Luhn algorithm validation)
  - `IPV4` (validation ensuring all octets <= 255)
  - `IPV6`
- **US Specific:**
  - `US_SSN`
- **India Specific:**
  - `IN_AADHAAR` (12 digits, cannot start with 0 or 1)
  - `IN_PAN` (5 uppercase letters, 4 digits, 1 uppercase letter)

## Installation

```bash
pip install .
```

## CLI Usage

### Extract PII
```bash
cleanslate extract --text "My email is test@example.com"
cleanslate extract --file text.txt
```

### Scrub PII
```bash
cleanslate scrub --text "My email is test@example.com"
cleanslate scrub --file text.txt
```

## Library Usage

```python
from cleanslate.core import CleanSlate

# Initialize with specific entities
cs = CleanSlate(entities=["EMAIL", "CREDIT_CARD"])

code = "Contact test@example.com for info."

# Extract entities
extracted = cs.extract_entities(code)
print(extracted)

# Scrub entities
scrubbed_code = cs.scrub_text(code, replacement_style="tag")
print(scrubbed_code)
```