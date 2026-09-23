import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

FIXTURE = os.path.join(ROOT, "raw", "fixtures", "sample_exercise.json")


class TestParse(unittest.TestCase):
    def test_parse_nested_json_strings(self):
        from build_bank import join_answers, load_exercise

        ex = load_exercise(FIXTURE)
        rows = join_answers(ex)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["questionId"], 1)
        self.assertEqual(rows[0]["options"][0]["id"], "A")
        self.assertEqual(rows[0]["answer"], "A")
        self.assertEqual(rows[2]["options"], [])
        self.assertEqual(rows[2]["answer"], "TRUE")


if __name__ == "__main__":
    unittest.main()
