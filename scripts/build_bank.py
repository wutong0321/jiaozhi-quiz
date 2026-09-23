"""Build unique question bank from raw exercise JSON files."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
from typing import Any


def _loads(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return [] if s == "" or s == "[]" else {}
        return json.loads(s)
    return value


def load_exercise(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["questions"] = _loads(data.get("questions") or "[]")
    data["answers"] = _loads(data.get("answers") or "[]")
    return data


def join_answers(exercise: dict) -> list[dict]:
    ans_map = {}
    for a in exercise.get("answers") or []:
        key = str(a.get("questionId"))
        ans_map[key] = a.get("answer")
    rows = []
    for q in exercise.get("questions") or []:
        qid = str(q.get("questionId"))
        options = _loads(q.get("options") or "[]")
        row = dict(q)
        row["options"] = options if isinstance(options, list) else []
        row["answer"] = ans_map.get(qid)
        rows.append(row)
    return rows


TYPE_MAP = {1: "single", 2: "multiple", 3: "judge"}


def _ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _parse_answer(qtype: str, answer: Any) -> list[str] | None:
    if answer is None:
        return None
    if qtype == "judge":
        a = str(answer).strip().upper()
        if a in ("TRUE", "FALSE"):
            return [a]
        return None
    if isinstance(answer, list):
        parts = [str(x).strip().upper() for x in answer if str(x).strip()]
    else:
        parts = [p.strip().upper() for p in str(answer).split(",") if p.strip()]
    if not parts:
        return None
    if qtype == "single" and len(parts) != 1:
        return None
    return sorted(parts)


def normalize_question(raw: dict, subject: str, exercise_meta: dict) -> dict | None:
    stem = _ws(raw.get("questionDesc") or "")
    if not stem:
        return None
    qtype = TYPE_MAP.get(int(raw.get("questionType") or 0))
    if not qtype:
        return None
    options_raw = raw.get("options") or []
    if not isinstance(options_raw, list):
        return None
    options = []
    for opt in options_raw:
        if not isinstance(opt, dict) or "id" not in opt:
            return None
        options.append({"id": str(opt["id"]), "value": _ws(str(opt.get("value") or ""))})
    options = sorted(options, key=lambda o: o["id"])
    if qtype != "judge" and not options:
        return None
    answer = _parse_answer(qtype, raw.get("answer"))
    if answer is None:
        return None
    old_id = raw.get("questionIdOld")
    old_id = int(old_id) if old_id is not None else None
    uid = f"old:{old_id}" if old_id is not None else None
    return {
        "uid": uid,
        "sourceOldId": old_id,
        "subject": subject,
        "type": qtype,
        "stem": stem,
        "options": options,
        "answer": answer,
        "keyPoint": _ws(raw.get("keyPoint") or ""),
        "difficulty": int(raw.get("difficultyLevel") or 1),
        "importance": int(raw.get("importanceLevel") or 1),
        "sources": [
            {
                "exerciseId": exercise_meta.get("exerciseId"),
                "exerciseName": exercise_meta.get("exerciseName"),
                "questionId": raw.get("questionId"),
            }
        ],
    }
