import unittest
import os
import shutil
import tempfile
from piiscrub.cli import main
from unittest.mock import patch
import sys

class TestBatchProcessing(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.input_dir = os.path.join(self.test_dir, "input")
        self.output_dir = os.path.join(self.test_dir, "output")
        os.makedirs(self.input_dir)
        
        # Create some sample files
        with open(os.path.join(self.input_dir, "file1.txt"), "w") as f:
            f.write("My email is test1@example.com")
        
        self.sub_dir = os.path.join(self.input_dir, "sub")
        os.makedirs(self.sub_dir)
        with open(os.path.join(self.sub_dir, "file2.txt"), "w") as f:
            f.write("My email is test2@example.com")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_batch_scrub_shallow(self):
        test_args = ["piiscrub", "scrub", "--dir", self.input_dir, "--output", self.output_dir]
        with patch.object(sys, 'argv', test_args):
            main()
        
        # Verify file1.txt is scrubbed
        out_file1 = os.path.join(self.output_dir, "file1.txt")
        self.assertTrue(os.path.exists(out_file1))
        with open(out_file1, "r") as f:
            content = f.read()
            self.assertEqual(content, "My email is <EMAIL>")
            
        # Verify file2.txt is NOT scrubbed (not recursive)
        out_file2 = os.path.join(self.output_dir, "sub", "file2.txt")
        self.assertFalse(os.path.exists(out_file2))

    def test_batch_scrub_recursive(self):
        test_args = ["piiscrub", "scrub", "--dir", self.input_dir, "--output", self.output_dir, "--recursive"]
        with patch.object(sys, 'argv', test_args):
            main()
        
        # Verify file1.txt is scrubbed
        out_file1 = os.path.join(self.output_dir, "file1.txt")
        self.assertTrue(os.path.exists(out_file1))
        with open(out_file1, "r") as f:
            self.assertEqual(f.read(), "My email is <EMAIL>")
            
        # Verify file2.txt is scrubbed (recursive)
        out_file2 = os.path.join(self.output_dir, "sub", "file2.txt")
        self.assertTrue(os.path.exists(out_file2))
        with open(out_file2, "r") as f:
            self.assertEqual(f.read(), "My email is <EMAIL>")

    def test_batch_extract_recursive(self):
        # We need to capture stdout for this
        from io import StringIO
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            test_args = ["piiscrub", "extract", "--dir", self.input_dir, "--recursive"]
            with patch.object(sys, 'argv', test_args):
                main()
                output = mock_stdout.getvalue()
                self.assertIn("test1@example.com", output)
                self.assertIn("test2@example.com", output)

if __name__ == "__main__":
    unittest.main()
