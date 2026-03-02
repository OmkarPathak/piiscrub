import unittest
from cleanslate.validators import validate_credit_card, validate_ipv4, validate_aadhaar

class TestValidators(unittest.TestCase):
    def test_validate_credit_card_valid(self):
        # Visa example (a valid Luhn string)
        self.assertTrue(validate_credit_card("4111 1111 1111 1111"))
        self.assertTrue(validate_credit_card("4111-1111-1111-1111"))
        
    def test_validate_credit_card_invalid_luhn(self):
        # Same sequence but failed luhn because of last digit swapped
        self.assertFalse(validate_credit_card("4111 1111 1111 1112"))
        
    def test_validate_credit_card_invalid_length(self):
        self.assertFalse(validate_credit_card("400"))
        # 17 digits
        self.assertFalse(validate_credit_card("12345678901234567"))
        
    def test_validate_ipv4_valid(self):
        self.assertTrue(validate_ipv4("192.168.1.1"))
        self.assertTrue(validate_ipv4("255.255.255.255"))
        self.assertTrue(validate_ipv4("0.0.0.0"))
        
    def test_validate_ipv4_invalid(self):
        self.assertFalse(validate_ipv4("256.1.1.1"))
        self.assertFalse(validate_ipv4("192.168.1.256"))
        self.assertFalse(validate_ipv4("192.168.1"))
        self.assertFalse(validate_ipv4("192.168.1.1.1"))
        self.assertFalse(validate_ipv4("abc.def.ghi.jkl"))
        
    def test_validate_aadhaar_valid(self):
        # Random valid Aadhaar formatting (does not start with 0 or 1, 12 digits total)
        self.assertTrue(validate_aadhaar("2345 6789 0123"))
        self.assertTrue(validate_aadhaar("999999999999"))
        
    def test_validate_aadhaar_invalid_start(self):
        # Starts with 0
        self.assertFalse(validate_aadhaar("0123 4567 8901"))
        # Starts with 1
        self.assertFalse(validate_aadhaar("1234 5678 9012"))
        
    def test_validate_aadhaar_invalid_length(self):
        # 11 digits
        self.assertFalse(validate_aadhaar("2345 6789 012"))
        # 13 digits
        self.assertFalse(validate_aadhaar("2345 6789 0123 4"))

if __name__ == "__main__":
    unittest.main()
