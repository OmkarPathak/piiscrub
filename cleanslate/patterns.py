"""
Pre-compiled regular expressions for PII extraction.
"""
import re

_RAW_PATTERNS = {
    "CREDIT_CARD": r"\b(?:\d[ -]*?){13,16}\b",
    "US_SSN": r"\b\d{3}[- ]?\d{2}[- ]?\d{4}\b",
    "IN_AADHAAR": r"\b[2-9]{1}\d{3}\s?\d{4}\s?\d{4}\b",
    "IN_PAN": r"\b[A-Z]{5}\d{4}[A-Z]{1}\b",
    "IPV6": r"\b(?:[A-Fa-f0-9]{1,4}:){7}[A-Fa-f0-9]{1,4}\b",
    "IPV4": r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b",
    "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    "AWS_ACCESS_KEY": r"\b(?:AKIA|ASIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}\b",
    "GITHUB_TOKEN": r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36}\b",
    "RSA_PRIVATE_KEY": r"-----BEGIN (?:\w+ )?PRIVATE KEY-----[a-zA-Z0-9\+/\s=\n]+-----END (?:\w+ )?PRIVATE KEY-----",
    "PHONE_GENERIC": r"(?:(?:\+|00)\d{1,3}[\s-]?)?(?:\(?\d{2,4}\)?[\s-]?)?\d{3,4}[\s-]?\d{3,4}[\s-]?\d{2,4}\b",
}

# Pre-compile for O(1) matching time
COMPILED_PATTERNS = {
    name: re.compile(pattern)
    for name, pattern in _RAW_PATTERNS.items()
}
