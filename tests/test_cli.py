import unittest
import json
import os
import tempfile
from piiscrub.cli import load_config, main
from unittest.mock import patch
import sys
from io import StringIO

class TestCLI(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.test_dir.name, "piiscrub.json")

    def tearDown(self):
        self.test_dir.cleanup()

    def test_load_config_valid(self):
        config_data = {"style": "hash", "entities": ["EMAIL"]}
        with open(self.config_path, "w") as f:
            json.dump(config_data, f)
        
        config = load_config(self.config_path)
        self.assertEqual(config["style"], "hash")
        self.assertEqual(config["entities"], ["EMAIL"])

    def test_load_config_invalid(self):
        with open(self.config_path, "w") as f:
            f.write("invalid json")
        
        # Should return empty dict and not crash
        config = load_config(self.config_path)
        self.assertEqual(config, {})

    def test_load_config_missing(self):
        config = load_config("non_existent.json")
        self.assertEqual(config, {})

    @patch('sys.stdout', new_callable=StringIO)
    def test_cli_scrub_text_style_override(self, mock_stdout):
        # Test that CLI flag overrides config style
        config_data = {"style": "hash"}
        with open("piiscrub.json", "w") as f:
            json.dump(config_data, f)
        
        try:
            test_args = ["piiscrub", "scrub", "--text", "test@example.com", "--style", "tag"]
            with patch.object(sys, 'argv', test_args):
                main()
                output = mock_stdout.getvalue().strip()
                self.assertEqual(output, "<EMAIL>")
        finally:
            if os.path.exists("piiscrub.json"):
                os.remove("piiscrub.json")

    @patch('sys.stdout', new_callable=StringIO)
    def test_cli_scrub_text_config_style(self, mock_stdout):
        # Test that config style is used if CLI flag is missing
        config_data = {"style": "redacted"}
        with open("piiscrub.json", "w") as f:
            json.dump(config_data, f)
        
        try:
            test_args = ["piiscrub", "scrub", "--text", "test@example.com"]
            with patch.object(sys, 'argv', test_args):
                main()
                output = mock_stdout.getvalue().strip()
                self.assertEqual(output, "<REDACTED>")
        finally:
            if os.path.exists("piiscrub.json"):
                os.remove("piiscrub.json")

    @patch('sys.stdout', new_callable=StringIO)
    def test_cli_custom_pattern_from_config(self, mock_stdout):
        config_data = {
            "custom_patterns": {
                "TEST_ID": "TID-\\d{3}"
            }
        }
        with open("piiscrub.json", "w") as f:
            json.dump(config_data, f)
            
        try:
            test_args = ["piiscrub", "scrub", "--text", "My id is TID-123"]
            with patch.object(sys, 'argv', test_args):
                main()
                output = mock_stdout.getvalue().strip()
                self.assertEqual(output, "My id is <TEST_ID>")
        finally:
            if os.path.exists("piiscrub.json"):
                os.remove("piiscrub.json")

if __name__ == "__main__":
    unittest.main()
