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


def content_key(q: dict) -> str:
    payload = json.dumps(
        {
            "stem": q.get("stem"),
            "type": q.get("type"),
            "answer": q.get("answer"),
            "options": q.get("options") or [],
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _fullness(q: dict) -> int:
    n = 0
    for k in ("stem", "keyPoint", "answer", "options", "sourceOldId", "difficulty"):
        v = q.get(k)
        if v not in (None, "", [], 0):
            n += 1
    n += len(q.get("sources") or [])
    return n


def _same_content(a: dict, b: dict) -> bool:
    return content_key(a) == content_key(b)


def dedupe(items: list[dict]) -> tuple[list[dict], dict]:
    report = {"merged": 0, "conflicts": [], "dropped_no_uid": 0}
    by_old: dict[str, dict] = {}
    by_hash: dict[str, dict] = {}
    ordered: list[dict] = []

    def merge_into(slot: dict, incoming: dict) -> None:
        report["merged"] += 1
        prefer_incoming = _fullness(incoming) > _fullness(slot)
        slot["sources"].extend(incoming.get("sources") or [])
        if _same_content(slot, incoming) and slot.get("answer") == incoming.get("answer"):
            return
        if prefer_incoming:
            srcs = slot["sources"]
            kept_uid = slot.get("uid") or incoming.get("uid")
            slot.clear()
            slot.update(incoming)
            slot["sources"] = srcs
            slot["uid"] = kept_uid
        report["conflicts"].append(
            {
                "uid": slot.get("uid"),
                "kept": {k: slot.get(k) for k in ("answer", "keyPoint", "stem")},
                "dropped": {k: incoming.get(k) for k in ("answer", "keyPoint", "stem")},
                "reason": "answer_or_fields_differ",
            }
        )

    for item in items:
        old_id = item.get("sourceOldId")
        key_old = f"old:{old_id}" if old_id is not None else None
        h = content_key(item)
        if key_old and key_old in by_old:
            merge_into(by_old[key_old], item)
            continue
        if h in by_hash:
            merge_into(by_hash[h], item)
            if key_old:
                by_old[key_old] = by_hash[h]
            continue
        matched = None
        for prev in ordered:
            if _same_content(prev, item) and prev.get("subject") == item.get("subject"):
                matched = prev
                break
        if matched is not None:
            merge_into(matched, item)
            continue
        stored = dict(item)
        stored["sources"] = list(item.get("sources") or [])
        if key_old:
            stored["uid"] = key_old
        else:
            stored["uid"] = f"hash:{h[:16]}"
        ordered.append(stored)
        by_hash[h] = stored
        if key_old:
            by_old[key_old] = stored

    return ordered, report
