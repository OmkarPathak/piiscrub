# PiiScrub

A blazing-fast, lightweight Python library and CLI tool designed to scrub Personally Identifiable Information (PII) from datasets for LLM training and RAG pipelines.

## Features

- **Maximum Speed & Zero Dependencies:** Relies exclusively on Python's standard library. No `pandas`, `spaCy`, or other heavy external packages.
- **Deterministic Validation:** Raw regex matches for high-risk entities (like credit cards and IPs) pass algorithmic checksums (e.g., Luhn algorithm, octet range checks) before being flagged to eliminate false positives.
- **Pre-compiled Regex:** All regular expressions are compiled at the module level using `re.compile()` for O(1) setup time during execution.
- **Large Dataset Streaming:** Features `scrub_stream` and `extract_stream` to process massive datasets chunk-by-chunk without hitting Out-Of-Memory limit.
- **Multi-Core Parallel Processing:** Leverage multiple CPU cores to scrub large files at blazing speed using `--parallel`.
- **Pre-Bundled Compliance Profiles:** Quickly target specific standards like `hipaa`, `pci-dss`, or `gdpr` using the `--profile` flag.
- **Compliance Auditing & Metric Reports:** Generate detailed JSON reports with statistics on redacted entities and execution time using `--report`.
- **High-Value Secret Detection:** Added parsing to locate critical assets like AWS Access Keys, GitHub Tokens, and RSA Private Keys out of the box.
- **Deterministic Hashing:** Replace PII with deterministic SHA-256 hashes instead of generic tags to track uniqueness without leaking data.
- **Synthetic Data Generation:** Replace real PII with realistic "fake" data using the `faker` library (beta).
- **Configuration File Support:** Manage complex settings via `piiscrub.json` instead of long CLI commands.
- **Custom Pattern Injection:** Dynamically inject your own regex patterns and validators directly into the engine without modifying the core library.
- **Allowlist Support:** Explicitly bypass scrubbing for public figures, system emails, or company identifiers to prevent false positives.

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
piiscrub extract --text "My email is test@example.com"
piiscrub extract --file text.txt
```

### Scrub PII
```bash
piiscrub scrub --text "My email is test@example.com"
piiscrub scrub --file text.txt

# Use deterministic hashing instead of standard tags
piiscrub scrub --text "My email is test@example.com" --style hash
# Output: My email is <EMAIL_a1517717>

# Bypass scrubbing for specific public strings
piiscrub scrub --text "Contact support@example.com or user@example.com" --allowlist support@example.com
# Output: Contact support@example.com or <EMAIL>

# Inject Custom Pattern from the CLI
piiscrub scrub --text "This is employee EMP-99881 and email a@b.com" --custom-pattern EMP_ID "\bEMP-\d{5}\b" --entities EMP_ID EMAIL
# Output: This is employee <EMP_ID> and email <EMAIL>

# Synthetic Data Generation
piiscrub scrub --text "Contact me at omkar@example.com" --style synthetic
# Output: Contact me at victoria12@gmail.com
```

### Advanced Features

#### 1. Configuration File (`piiscrub.json`)
You can define a `piiscrub.json` file in your working directory to simplify your commands:

```json
{
    "style": "hash",
    "entities": ["EMAIL", "PHONE_GENERIC"],
    "allowlist": ["support@mycompany.com"],
    "custom_patterns": {
        "ORDER_ID": "ORD-\\d{5}"
    }
}
```

Now just run:
```bash
piiscrub scrub --file data.txt
```

#### 2. Parallel Processing
For large files, use multi-core processing:

```bash
piiscrub scrub --file large_dataset.txt --parallel --output cleaned.txt
```
> [!TIP]
> Parallel mode automatically handles file I/O efficiently and defaults to using all available CPU cores.

#### 3. Pre-Bundled Compliance Profiles
Quickly target common privacy standards without remembering every entity name:

```bash
# Scrub only PCI-DSS related data (Credit Cards)
piiscrub scrub --file transactions.txt --profile pci-dss

# Scrub HIPAA related data (SSN, Phone, Email, IP)
piiscrub scrub --file medical_records.txt --profile hipaa
```

Available profiles: `pci-dss`, `hipaa`, `gdpr`, `strict`.

#### 4. Compliance Auditing & Metric Reports
Data compliance teams can generate a statistical summary of the scrubbing process as proof of redaction:

```bash
piiscrub scrub --file sensitive_data.txt --report audit.json
```

**Sample `audit.json` output:**
```json
{
    "command": "scrub",
    "total_lines_processed": 5000,
    "execution_time_seconds": 1.25,
    "entities_redacted": {
        "EMAIL": 142,
        "CREDIT_CARD": 12,
        "PHONE_GENERIC": 5
    },
    "style": "tag"
}
```

#### 5. Structured Data Support (JSON & CSV)
Target specific fields in structured files to preserve the format while scrubbing PII.

```bash
# Scrub only specific keys in a JSON file
piiscrub scrub --file data.json --json-key email secret

# Scrub only specific columns in a CSV file
piiscrub scrub --file data.csv --csv-column phone email
```

### Stream Processing
For extremely large files (e.g. LLM corpus data logs):
```bash
piiscrub scrub --file huge_dataset.jsonl --stream > scrubbed.jsonl
piiscrub extract --file huge_dataset.jsonl --stream > entities.json
```

## Library Usage

```python
from piiscrub.core import PiiScrub
import re

# Initialize with custom generic entities or pattern injection!
custom_patterns = {
    "INTERNAL_ID": re.compile(r"\bEMP-\d{5}\b")
}
cs = PiiScrub(
    entities=["EMAIL", "CREDIT_CARD", "INTERNAL_ID"], 
    custom_patterns=custom_patterns,
    allowlist=["public@example.com"]
)

code = "Contact test@example.com for info on EMP-12345."

# Extract entities
extracted = cs.extract_entities(code)
print(extracted)
# {'EMAIL': ['test@example.com'], 'INTERNAL_ID': ['EMP-12345']}

# Scrub entities using hashing
scrubbed_code = cs.scrub_text(code, replacement_style="hash")
print(scrubbed_code)
# Contact <EMAIL_a1517717> for info on <INTERNAL_ID_b5fb38c3>.
```