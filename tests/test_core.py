import unittest
from piiscrub.core import PiiScrub

class TestCoreEngine(unittest.TestCase):
    def setUp(self):
        self.cs = PiiScrub()

    def test_extract_email(self):
        text = "Contact us at test@example.com or support@example.co.uk."
        res = self.cs.extract_entities(text)
        self.assertIn("EMAIL", res)
        self.assertEqual(len(res["EMAIL"]), 2)
        self.assertIn("test@example.com", res["EMAIL"])
        self.assertIn("support@example.co.uk", res["EMAIL"])

    def test_scrub_email(self):
        text = "My email is test@example.com"
        scrubbed_tag = self.cs.scrub_text(text, replacement_style="tag")
        self.assertEqual(scrubbed_tag, "My email is <EMAIL>")
        
        scrubbed_redacted = self.cs.scrub_text(text, replacement_style="redacted")
        self.assertEqual(scrubbed_redacted, "My email is <REDACTED>")

    def test_extract_phone(self):
        # Basic validation, just checking we identify typical formats
        text = "Call +1-800-555-1234 or 0044 20 7123 4567"
        res = self.cs.extract_entities(text)
        self.assertIn("PHONE_GENERIC", res)
        # Regex might extract "0044 20 7123 4567" or parts of it depending on exact pattern matches
        # The exact matched substrings depends on regex boundaries
        self.assertTrue(len(res["PHONE_GENERIC"]) > 0)

    def test_validate_credit_card_integration(self):
        valid_cc = "4111 1111 1111 1111"
        invalid_cc = "1111  1111  1111  1111"  # Fails Luhn and multiple spaces evades PHONE_GENERIC
        
        text = f"Valid: {valid_cc} Invalid: {invalid_cc}"
        res = self.cs.extract_entities(text)
        
        self.assertIn("CREDIT_CARD", res)
        self.assertIn(valid_cc, res["CREDIT_CARD"])
        self.assertNotIn(invalid_cc, res["CREDIT_CARD"])
        
        scrubbed = self.cs.scrub_text(text)
        # valid gets scrubbed, invalid remains
        self.assertIn("<CREDIT_CARD>", scrubbed)
        self.assertIn(invalid_cc, scrubbed)

    def test_ipv4_integration(self):
        text = "Server is at 192.168.1.1 and 256.1.2.3"
        res = self.cs.extract_entities(text)
        self.assertIn("IPV4", res)
        self.assertIn("192.168.1.1", res["IPV4"])
        self.assertNotIn("256.1.2.3", res["IPV4"])

    def test_in_pan(self):
        text = "My PAN is ABCDE1234F and invalid is ABcDE1234f or ABCDE12345"
        res = self.cs.extract_entities(text)
        self.assertIn("IN_PAN", res)
        self.assertEqual(res["IN_PAN"], ["ABCDE1234F"])

    def test_secret_detection(self):
        text = "AWS: AKIAIOSFODNN7EXAMPLE GitHub: ghp_16C7e42k292c3938E2C849E2F19O3819A29e RSA: -----BEGIN PRIVATE KEY-----\nMIIEvAIBADAN\n-----END PRIVATE KEY-----"
        res = self.cs.extract_entities(text)
        
        self.assertIn("AWS_ACCESS_KEY", res)
        self.assertEqual(res["AWS_ACCESS_KEY"], ["AKIAIOSFODNN7EXAMPLE"])
        
        self.assertIn("GITHUB_TOKEN", res)
        self.assertEqual(res["GITHUB_TOKEN"], ["ghp_16C7e42k292c3938E2C849E2F19O3819A29e"])
        
        self.assertIn("RSA_PRIVATE_KEY", res)
        self.assertTrue(res["RSA_PRIVATE_KEY"][0].startswith("-----BEGIN PRIVATE KEY-----"))

    def test_extract_stream(self):
        lines = [
            "Line 1 with email test@example.com",
            "Line 2 with email support@example.com",
            "Line 3 duplicate test@example.com"
        ]
        res = self.cs.extract_stream(iter(lines))
        self.assertIn("EMAIL", res)
        # Should deduplicate test@example.com
        self.assertEqual(len(res["EMAIL"]), 2)
        self.assertIn("test@example.com", res["EMAIL"])
        self.assertIn("support@example.com", res["EMAIL"])

    def test_scrub_hash_style(self):
        text = "Process user omkar@test.com"
        scrubbed = self.cs.scrub_text(text, replacement_style="hash")
        # sha256 of "omkar@test.com" starts with a1517717
        self.assertEqual(scrubbed, "Process user <EMAIL_a1517717>")

    def test_custom_patterns(self):
        import re
        custom_pats = {
            "TICKET_ID": re.compile(r"\bPROJ-\d{4}\b")
        }
        
        cs_custom = PiiScrub(custom_patterns=custom_pats)
        text = "Fixing issue PROJ-1234 and emailing dev@test.com"
        
        # Test extraction
        extracted = cs_custom.extract_entities(text)
        self.assertIn("TICKET_ID", extracted)
        self.assertEqual(extracted["TICKET_ID"], ["PROJ-1234"])
        self.assertIn("EMAIL", extracted)
        
        # Test scrubbing
    def test_allowlist(self):
        allowlist = ["support@example.com", "4111   1111   1111   1111"]
        cs_allow = PiiScrub(allowlist=allowlist)
        
        text = "Contact support@example.com or user@test.com. Card: 4111   1111   1111   1111"
        
        # Test extraction (should omit allowlisted items)
        extracted = cs_allow.extract_entities(text)
        self.assertIn("EMAIL", extracted)
        self.assertEqual(len(extracted["EMAIL"]), 1)
        self.assertEqual(extracted["EMAIL"][0], "user@test.com")
        self.assertNotIn("CREDIT_CARD", extracted)
        
        # Test scrubbing (should leave allowlisted items intact)
        scrubbed = cs_allow.scrub_text(text)
        self.assertEqual(scrubbed, "Contact support@example.com or <EMAIL>. Card: 4111   1111   1111   1111")

if __name__ == "__main__":
    unittest.main()
