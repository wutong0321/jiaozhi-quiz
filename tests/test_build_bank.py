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

    def test_dedupe_by_old_id_merges_sources(self):
        from build_bank import dedupe

        a = {
            "uid": "old:1",
            "sourceOldId": 1,
            "subject": "edu",
            "type": "single",
            "stem": "题干一",
            "options": [{"id": "A", "value": "1"}, {"id": "B", "value": "2"}],
            "answer": ["A"],
            "keyPoint": "k1",
            "difficulty": 1,
            "importance": 1,
            "sources": [{"exerciseId": 1, "exerciseName": "e1", "questionId": 1}],
        }
        b = {
            "uid": "old:1",
            "sourceOldId": 1,
            "subject": "edu",
            "type": "single",
            "stem": "题干一",
            "options": [{"id": "A", "value": "1"}, {"id": "B", "value": "2"}],
            "answer": ["A"],
            "keyPoint": "k1",
            "difficulty": 1,
            "importance": 1,
            "sources": [{"exerciseId": 2, "exerciseName": "e2", "questionId": 5}],
        }
        bank, report = dedupe([a, b])
        self.assertEqual(len(bank), 1)
        self.assertEqual(len(bank[0]["sources"]), 2)
        self.assertEqual(report["merged"], 1)

    def test_dedupe_by_content_when_no_old_id(self):
        from build_bank import content_key, dedupe

        base = {
            "uid": None,
            "sourceOldId": None,
            "subject": "edu",
            "type": "judge",
            "stem": "对错题干",
            "options": [],
            "answer": ["TRUE"],
            "keyPoint": "k",
            "difficulty": 1,
            "importance": 1,
            "sources": [{"exerciseId": 1, "exerciseName": "e1", "questionId": 1}],
        }
        other = {
            **base,
            "sources": [{"exerciseId": 2, "exerciseName": "e2", "questionId": 9}],
        }
        self.assertEqual(content_key(base), content_key(other))
        bank, report = dedupe([base, other])
        self.assertEqual(len(bank), 1)
        self.assertEqual(report["merged"], 1)

    def test_conflict_keeps_fuller_and_reports(self):
        from build_bank import dedupe

        thin = {
            "uid": "old:2",
            "sourceOldId": 2,
            "subject": "edu",
            "type": "single",
            "stem": "冲突题",
            "options": [{"id": "A", "value": "1"}],
            "answer": ["A"],
            "keyPoint": "",
            "difficulty": 1,
            "importance": 1,
            "sources": [{"exerciseId": 1, "exerciseName": "e1", "questionId": 1}],
        }
        full = {
            "uid": "old:2",
            "sourceOldId": 2,
            "subject": "edu",
            "type": "single",
            "stem": "冲突题",
            "options": [{"id": "A", "value": "1"}],
            "answer": ["B"],
            "keyPoint": "有知识点",
            "difficulty": 2,
            "importance": 1,
            "sources": [{"exerciseId": 2, "exerciseName": "e2", "questionId": 2}],
        }
        bank, report = dedupe([thin, full])
        self.assertEqual(len(bank), 1)
        self.assertEqual(bank[0]["answer"], ["B"])
        self.assertEqual(bank[0]["keyPoint"], "有知识点")
        self.assertEqual(len(report["conflicts"]), 1)
        self.assertEqual(report["conflicts"][0]["reason"], "answer_or_fields_differ")

    def test_infer_subject_from_filename(self):
        from build_bank import infer_subject

        self.assertEqual(infer_subject("edu_练习01.json", {}), "edu")
        self.assertEqual(infer_subject("psy_练习02.json", {}), "psy")
        self.assertEqual(infer_subject("law_练习03.json", {}), "law")
        self.assertEqual(
            infer_subject("x.json", {"exerciseName": "高等教育心理学-练习01"}), "psy"
        )

    def test_build_end_to_end_on_fixture_dir(self):
        import shutil as _sh
        import tempfile
        from build_bank import build

        with tempfile.TemporaryDirectory() as td:
            raw_dir = os.path.join(td, "raw")
            os.makedirs(raw_dir)
            _sh.copy(FIXTURE, os.path.join(raw_dir, "edu_练习FIX.json"))
            bank_path = os.path.join(td, "bank.js")
            report_path = os.path.join(td, "dedupe_report.json")
            stats = build(raw_dir, bank_path, report_path)
            self.assertEqual(stats["bank_size"], 3)
            with open(bank_path, "r", encoding="utf-8") as f:
                text = f.read()
            self.assertIn("window.BANK", text)
            self.assertIn("old:27183", text)
            with open(report_path, "r", encoding="utf-8") as f:
                rep = json.load(f)
            self.assertIn("merged", rep)


if __name__ == "__main__":
    unittest.main()
