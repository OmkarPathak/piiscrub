"""
Validation functions for deterministic verification of matched entities.
Helps eliminate false positives.
"""
import re

def validate_credit_card(cc_string: str) -> bool:
    """Implement the Luhn algorithm to check credit card validity."""
    # Strip whitespaces and dashes first
    digits = re.sub(r'[\s-]', '', cc_string)
    if not digits.isdigit() or len(digits) < 13 or len(digits) > 16:
        return False
        
    total = 0
    reverse_digits = digits[::-1]
    
    for i, char in enumerate(reverse_digits):
        n = int(char)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
        
    return total % 10 == 0


def validate_ipv4(ip_string: str) -> bool:
    """Ensure all 4 octets of IPv4 are <= 255."""
    try:
        parts = [int(p) for p in ip_string.split('.')]
        if len(parts) != 4:
            return False
        return all(0 <= p <= 255 for p in parts)
    except ValueError:
        return False


def validate_aadhaar(aadhaar_string: str) -> bool:
    """Check length/prefix validation for IN_AADHAAR."""
    normalized = re.sub(r'\s+', '', aadhaar_string)
    if not normalized.isdigit() or len(normalized) != 12:
        return False
    # Aadhaar must not start with 0 or 1
    if normalized[0] in ('0', '1'):
        return False
    # Optionally could implement Verhoeff algorithm here, but keeping it to structural rules.
    return True
