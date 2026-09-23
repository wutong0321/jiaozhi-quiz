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
