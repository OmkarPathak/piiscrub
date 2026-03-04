"""
Pre-bundled compliance profiles for PiiScrub.
"""

COMPLIANCE_PROFILES = {
    "pci-dss": [
        "CREDIT_CARD"
    ],
    "hipaa": [
        "US_SSN",
        "EMAIL",
        "PHONE_GENERIC",
        "IPV4",
        "IPV6"
    ],
    "gdpr": [
        "EMAIL",
        "PHONE_GENERIC",
        "IPV4",
        "IPV6",
        "IN_AADHAAR",
        "IN_PAN"
    ],
    "strict": None # Will be handled as 'all entities' in the core engine
}
