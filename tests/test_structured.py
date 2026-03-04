import unittest
import json
import csv
import io
from piiscrub.core import PiiScrub

class TestStructuredData(unittest.TestCase):
    def setUp(self):
        self.ps = PiiScrub()

    def test_scrub_json_recursive(self):
        data = {
            "name": "Omkar Pathak",
            "contact": {
                "email": "omkarpathak27@gmail.com",
                "phone": "+91-9876543210"
            },
            "history": [
                "Purchased item with card 4111 1111 1111 1111",
                {"comment": "Reply to user@example.com"}
            ]
        }
        
        # Scrub only specific keys
        scrubbed = self.ps.scrub_json(data, keys_to_scrub=["email", "comment"])
        
        # 'email' should be scrubbed
        self.assertEqual(scrubbed["contact"]["email"], "<EMAIL>")
        # 'comment' should be scrubbed (inside list)
        self.assertEqual(scrubbed["history"][1]["comment"], "Reply to <EMAIL>")
        # 'phone' should NOT be scrubbed because it wasn't in keys_to_scrub
        self.assertEqual(scrubbed["contact"]["phone"], "+91-9876543210")
        # 'history' string should NOT be scrubbed for the same reason
        self.assertIn("4111 1111 1111 1111", scrubbed["history"][0])

    def test_scrub_json_all(self):
        data = {
            "comment": "My email is test@example.com",
            "info": ["Phone: +91-9876543210"]
        }
        # Scrub all string values
        scrubbed = self.ps.scrub_json(data)
        self.assertEqual(scrubbed["comment"], "My email is <EMAIL>")
        self.assertEqual(scrubbed["info"][0], "Phone: <PHONE_GENERIC>")

    def test_scrub_csv(self):
        csv_data = "name,email,comment\nOmkar,omkar@example.com,hello\nJohn,john@test.com,Contact me at +1-202-555-0123"
        f_in = io.StringIO(csv_data)
        
        # Scrub only 'email' and 'comment' columns
        scrubbed_gen = self.ps.scrub_csv(f_in, columns_to_scrub=["email", "comment"])
        scrubbed_rows = list(scrubbed_gen)
        
        # Check header
        self.assertEqual(scrubbed_rows[0].strip(), "name,email,comment")
        
        # Check first data row
        row1 = scrubbed_rows[1].strip()
        self.assertIn("Omkar", row1)
        self.assertIn("<EMAIL>", row1)
        self.assertNotIn("omkar@example.com", row1)
        
        # Check second data row
        row2 = scrubbed_rows[2].strip()
        self.assertIn("John", row2)
        self.assertIn("<EMAIL>", row2)
        self.assertIn("<PHONE_GENERIC>", row2)
        self.assertNotIn("john@test.com", row2)

if __name__ == "__main__":
    unittest.main()
