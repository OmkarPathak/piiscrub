# CleanSlate

A blazing-fast, lightweight Python library and CLI tool designed to scrub Personally Identifiable Information (PII) from datasets for LLM training and RAG pipelines.

## Features

- **Maximum Speed & Zero Dependencies:** Relies exclusively on Python's standard library. No `pandas`, `spaCy`, or other heavy external packages.
- **Deterministic Validation:** Raw regex matches for high-risk entities (like credit cards and IPs) pass algorithmic checksums (e.g., Luhn algorithm, octet range checks) before being flagged to eliminate false positives.
- **Pre-compiled Regex:** All regular expressions are compiled at the module level using `re.compile()` for O(1) setup time during execution.
- **Large Dataset Streaming (V2):** Features `scrub_stream` and `extract_stream` to process massive datasets chunk-by-chunk without hitting Out-Of-Memory limit.
- **High-Value Secret Detection (V2):** Added parsing to locate critical assets like AWS Access Keys, GitHub Tokens, and RSA Private Keys out of the box.

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
- **Secrets & Credentials (V2):**
  - `AWS_ACCESS_KEY`
  - `GITHUB_TOKEN`
  - `RSA_PRIVATE_KEY`

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

### Stream Processing
For extremely large files (e.g. LLM corpus data logs):
```bash
cleanslate scrub --file huge_dataset.jsonl --stream > scrubbed.jsonl
cleanslate extract --file huge_dataset.jsonl --stream > entities.json
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