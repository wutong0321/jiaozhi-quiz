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

    def test_normalize_single_and_judge(self):
        from build_bank import join_answers, load_exercise, normalize_question

        ex = load_exercise(FIXTURE)
        rows = join_answers(ex)
        meta = {
            "exerciseId": ex["exerciseId"],
            "exerciseName": ex["exerciseName"],
        }
        single = normalize_question(rows[0], "edu", meta)
        self.assertEqual(single["type"], "single")
        self.assertEqual(single["answer"], ["A"])
        self.assertEqual(single["sourceOldId"], 27183)
        self.assertEqual(single["uid"], "old:27183")
        self.assertEqual(single["sources"][0]["questionId"], 1)

        judge = normalize_question(rows[2], "edu", meta)
        self.assertEqual(judge["type"], "judge")
        self.assertEqual(judge["answer"], ["TRUE"])
        self.assertEqual(judge["options"], [])

    def test_normalize_judge_false_and_drop_missing_answer(self):
        from build_bank import normalize_question

        raw_false = {
            "questionDesc": "错的判断",
            "questionId": 9,
            "questionIdOld": 99,
            "questionType": 3,
            "options": [],
            "answer": "FALSE",
            "keyPoint": "k",
            "difficultyLevel": 2,
            "importanceLevel": 1,
        }
        q = normalize_question(raw_false, "psy", {"exerciseId": 2, "exerciseName": "e"})
        self.assertEqual(q["answer"], ["FALSE"])
        self.assertEqual(q["difficulty"], 2)

        raw_missing = {
            "questionDesc": "无答案",
            "questionId": 10,
            "questionIdOld": 100,
            "questionType": 1,
            "options": [{"id": "A", "value": "x"}],
            "answer": None,
        }
        self.assertIsNone(normalize_question(raw_missing, "edu", {"exerciseId": 3, "exerciseName": "e"}))

        raw_blank = {
            "questionDesc": "   ",
            "questionId": 11,
            "questionIdOld": 101,
            "questionType": 1,
            "options": [{"id": "A", "value": "x"}],
            "answer": "A",
        }
        self.assertIsNone(normalize_question(raw_blank, "edu", {"exerciseId": 3, "exerciseName": "e"}))


if __name__ == "__main__":
    unittest.main()
