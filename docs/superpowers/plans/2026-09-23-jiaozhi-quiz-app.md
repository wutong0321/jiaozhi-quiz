# 教资刷题 App（题库流水线 + 移动端刷题）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从多份 exercise JSON 生成唯一总题库 `bank.js`，并做出可离线使用的移动端刷题 App（顺序 / 随机 / 错题本 / 模考）。

**Architecture:** 离线 Python 流水线解析 `raw/` 练习卷 → 归一化 → 按 `questionIdOld` 优先再内容哈希去重 → 产出 `bank.js` + `dedupe_report.json`；单页 `index.html` 只读 `bank.js`，用 `localStorage` 存进度与错题。

**Tech Stack:** Python 3（`$MIMO_PYTHON`，仅标准库 `json`/`hashlib`/`unittest`）、原生 HTML/CSS/JS（无框架、无 CDN）。

**Spec:** `docs/superpowers/specs/2026-09-23-jiaozhi-quiz-app-design.md`

## Global Constraints

- 交付根目录：`C:\Users\pc\XiaomiMiMoProjects\教资考试`（下文相对路径均相对此根）
- 无答案解析；多选**全对才算对**（漏选、错选均错）；判断答案内部统一为 `["TRUE"]` / `["FALSE"]`
- 去重：先相同 `questionIdOld`，再内容哈希；冲突取非空字段更多者，仍平则保留先入库者；双方写入 `dedupe_report.json`
- 科目：`edu` / `psy` / `law`；文件名前缀优先于 `subjectId`/`exerciseName`
- `bank.js` 格式：`window.BANK = [ ... ];`，条目字段见 Spec §5，**脚本生成，禁止手改**
- App 单文件优先 `index.html`（CSS/JS 内联），约 390px 宽度可刷、无横向滚动
- 模考默认 40 单 + 20 多 + 20 判，可随机 N；默认限时 100 分钟；**交卷后才显示答案**
- 错题做对默认保留；设置项可开「做对自动移出」（默认关）
- 测试：Python 用 `$env:MIMO_PYTHON -m unittest`；App 无测试框架，用浏览器手工断言步骤
- 提交信息用 Conventional Commits（`feat:` / `test:` / `chore:`）；仓库若无 `.git` 则先 `git init`
- **Phase B（Task 6–12）仅在三科题库采集完成、`bank.js` 冻结之后开始**（与 Spec §12 一致）；Phase A 可立即用 fixture 与已到 raw 做

## Review Focus

| 风险 / 输入 | 期望行为 | 钉住测试 |
|-------------|----------|----------|
| `questions`/`answers`/`options` 为**双重字符串化** JSON | 解析成功，选项为对象数组 | Task 1 `test_parse_nested_json_strings` |
| 判断题 `options` 为 `[]`，答案为 `TRUE`/`FALSE` | 归一为 `type=judge`，`answer=["TRUE"\|"FALSE"]`，选项保持 `[]` | Task 2 `test_normalize_judge_question` |
| 多题共享 `questionIdOld` 或同题干不同卷 | 合并为一条且 `sources` 增长 | Task 3 `test_dedupe_by_old_id_merges_sources` |
| 同内容键但答案不一致 | 取更全者，report 有 conflict 记录，不丢双份进 BANK | Task 3 `test_conflict_keeps_fuller_and_reports` |
| 组卷时某题型不足 40/20/20 | 该题型全取，其余随机补齐并提示实际题量 | Task 11 `test_assemble_paper_fills_when_short`（逻辑函数）+ 手工 |
| `localStorage` 损坏 / `bank.js` 缺失 | 不白屏：空库提示或重置进度 toast | Task 6 `test_boot_handles_missing_bank`（手工）+ Task 12 |
| 多选漏选 | 判错 | Task 8 `test_multiple_partial_wrong`（纯函数） |

---

## File Structure

| 路径 | 职责 |
|------|------|
| `raw/*.json` | 用户投喂的原始 exercise 包 |
| `raw/_backup/` | 同名覆盖备份 |
| `raw/fixtures/sample_exercise.json` | 测试用最小练习卷（不计入正式题库） |
| `scripts/build_bank.py` | 解析、归一、去重、出库 CLI；函数可被 unittest 导入 |
| `tests/test_build_bank.py` | 流水线单测 |
| `bank.js` | 生成物：`window.BANK` |
| `dedupe_report.json` | 生成物：合并/丢弃/冲突 |
| `index.html` | 移动端 App 兛模式 |
| `docs/superpowers/specs/2026-09-23-jiaozhi-quiz-app-design.md` | Spec |
| `docs/superpowers/plans/2026-09-23-jiaozhi-quiz-app.md` | 本计划 |

**模块边界（`build_bank.py` 内函数，供后续任务复用）：**

- `load_exercise(path: str) -> dict` — 读文件并解嵌套 JSON 字符串
- `join_answers(exercise: dict) -> list[dict]` — 产出半原始题列表（含 answer）
- `normalize_question(raw: dict, subject: str, exercise_meta: dict) -> dict | None` — Spec §5 条目或 None（丢弃）
- `content_key(q: dict) -> str` — 内容哈希
- `dedupe(items: list[dict]) -> tuple[list[dict], dict]` — (BANK 列表, report)
- `emit_bank_js(items: list[dict], path: str) -> None`
- `emit_report(report: dict, path: str) -> None`
- `build(raw_dir: str, bank_path: str, report_path: str) -> dict` — CLI 主流程，返回统计

**App 内纯函数（挂 `window` 或 IIFE，便于手工/后续抽测）：**

- `scoreAnswer(type, userAnswer[], keyAnswer[]) -> boolean` — 多选全对才算对
- `assemblePaper(bank, opts) -> question[]` — 默认 40/20/20 或随机 N

---

### Task 1: Git 初始化、fixture 与 exercise 解析

**Files:**
- Create: `raw/fixtures/sample_exercise.json`
- Create: `scripts/build_bank.py`
- Create: `tests/test_build_bank.py`

**Interfaces:**
- Consumes: 无
- Produces: `load_exercise(path: str) -> dict`；`join_answers(exercise: dict) -> list[dict]`（每项含 `questionDesc`/`questionId`/`questionIdOld`/`questionType`/`options`(已解析 list)/`answer`(原始 str)/`keyPoint`/`difficultyLevel`/`importanceLevel`/`subjectId`）

- [ ] **Step 1: 初始化 git 与目录**

```powershell
cd "C:\Users\pc\XiaomiMiMoProjects\教资考试"
git init
New-Item -ItemType Directory -Force -Path raw/fixtures, raw/_backup, scripts, tests | Out-Null
```

- [ ] **Step 2: 写入最小 fixture（2 单选 + 1 判断，含嵌套字符串化）**

写入 `raw/fixtures/sample_exercise.json`：

```json
{
  "exerciseId": 1,
  "exerciseUuid": "fixture-uuid",
  "exerciseName": "高等教育学-练习FIX",
  "courseId": 66,
  "questionAmount": 3,
  "singleAmount": 2,
  "multipleAmount": 0,
  "judgeAmount": 1,
  "canExamTime": 100,
  "questions": "[{\"questionDesc\":\"美国哈佛学院创建于（　）年。\",\"questionId\":1,\"questionIdOld\":27183,\"questionType\":1,\"subjectId\":64,\"keyPoint\":\"美国大学\",\"difficultyLevel\":1,\"importanceLevel\":1,\"options\":\"[{\\\"id\\\":\\\"A\\\",\\\"value\\\":\\\"1636\\\"},{\\\"id\\\":\\\"B\\\",\\\"value\\\":\\\"1646\\\"}]\"},{\"questionDesc\":\"下面说法正确的是（）。\",\"questionId\":2,\"questionIdOld\":27374,\"questionType\":1,\"subjectId\":64,\"keyPoint\":\"专业学科\",\"difficultyLevel\":1,\"importanceLevel\":1,\"options\":\"[{\\\"id\\\":\\\"A\\\",\\\"value\\\":\\\"错项\\\"},{\\\"id\\\":\\\"B\\\",\\\"value\\\":\\\"对项\\\"}]\"},{\"questionDesc\":\"政治制约着高等教育体制。\",\"questionId\":3,\"questionIdOld\":27707,\"questionType\":3,\"subjectId\":64,\"keyPoint\":\"政治\",\"difficultyLevel\":1,\"importanceLevel\":1,\"options\":\"[]\"}]",
  "answers": "[{\"questionId\":\"1\",\"answer\":\"A\"},{\"questionId\":\"2\",\"answer\":\"B\"},{\"questionId\":\"3\",\"answer\":\"TRUE\"}]"
}
```

- [ ] **Step 3: 写失败测试**

写入 `tests/test_build_bank.py`：

```python
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
```

- [ ] **Step 4: 跑测试确认失败**

```powershell
$env:MIMO_PYTHON -m unittest tests.test_build_bank -v
```

期望：FAIL / ImportError（`load_exercise` 未定义）

- [ ] **Step 5: 实现 `load_exercise` 与 `join_answers`**

写入 `scripts/build_bank.py`：

```python
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
```

- [ ] **Step 6: 跑测试确认通过**

```powershell
$env:MIMO_PYTHON -m unittest tests.test_build_bank -v
```

期望：PASS（`test_parse_nested_json_strings`）

- [ ] **Step 7: Commit**

```powershell
git add scripts/build_bank.py tests/test_build_bank.py raw/fixtures/sample_exercise.json
git commit -m "feat: parse nested exercise JSON and join answers"
```

---

### Task 2: 归一化题目模型

**Files:**
- Modify: `scripts/build_bank.py`
- Modify: `tests/test_build_bank.py`

**Interfaces:**
- Consumes: `join_answers` 的半原始行
- Produces: `normalize_question(raw: dict, subject: str, exercise_meta: dict) -> dict | None`，返回 Spec §5 形状：`uid, sourceOldId, subject, type, stem, options, answer[], keyPoint, difficulty, importance, sources[]`

- [ ] **Step 1: 追加失败测试**

在 `tests/test_build_bank.py` 增加：

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
$env:MIMO_PYTHON -m unittest tests.test_build_bank -v
```

期望：`test_normalize_*` FAIL（`normalize_question` 未定义）

- [ ] **Step 3: 实现 `normalize_question` 与题型映射**

在 `scripts/build_bank.py` 追加：

```python
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
```

- [ ] **Step 4: 跑测试确认通过**

```powershell
$env:MIMO_PYTHON -m unittest tests.test_build_bank -v
```

期望：Task 1–2 测试 PASS

- [ ] **Step 5: Commit**

```powershell
git add scripts/build_bank.py tests/test_build_bank.py
git commit -m "feat: normalize questions to bank entry model"
```

---

### Task 3: 去重（oldId 优先，再内容，冲突记 report）

**Files:**
- Modify: `scripts/build_bank.py`
- Modify: `tests/test_build_bank.py`

**Interfaces:**
- Consumes: `normalize_question` 输出列表
- Produces: `content_key(q: dict) -> str`；`dedupe(items: list[dict]) -> tuple[list[dict], dict]`  
  report 结构：`{"merged": int, "conflicts": [{"uid": str, "kept": dict, "dropped": dict, "reason": str}], "dropped_no_uid": int}`

- [ ] **Step 1: 追加失败测试**

```python
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
        other = dict(base)
        other = {**base, "sources": [{"exerciseId": 2, "exerciseName": "e2", "questionId": 9}]}
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
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
$env:MIMO_PYTHON -m unittest tests.test_build_bank -v
```

期望：`test_dedupe_*` / `test_conflict_*` FAIL

- [ ] **Step 3: 实现 `content_key` 与 `dedupe`**

```python
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
    by_hash: dict[str, dict] = []
    by_hash = {}
    ordered: list[dict] = []

    def merge_into(slot: dict, incoming: dict) -> None:
        report["merged"] += 1
        slot["sources"].extend(incoming.get("sources") or [])
        if _same_content(slot, incoming) and slot.get("answer") == incoming.get("answer"):
            return
        if _fullness(incoming) > _fullness(slot):
            srcs = slot["sources"]
            slot.clear()
            slot.update(incoming)
            slot["sources"] = srcs
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
        # content-only match against prior items without old-id collision
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
            report["dropped_no_uid"] += 0  # counted as hash-uid, not dropped
        ordered.append(stored)
        by_hash[h] = stored
        if key_old:
            by_old[key_old] = stored

    return ordered, report
```

- [ ] **Step 4: 跑测试确认通过**

```powershell
$env:MIMO_PYTHON -m unittest tests.test_build_bank -v
```

期望：全部 PASS

- [ ] **Step 5: Commit**

```powershell
git add scripts/build_bank.py tests/test_build_bank.py
git commit -m "feat: dedupe bank by old id then content hash"
```

---

### Task 4: 出库 `bank.js` / `dedupe_report.json` 与 CLI

**Files:**
- Modify: `scripts/build_bank.py`
- Modify: `tests/test_build_bank.py`

**Interfaces:**
- Consumes: `dedupe`, `normalize_question`, `load_exercise`, `join_answers`
- Produces: `infer_subject(path: str, exercise: dict) -> str`；`build(raw_dir, bank_path, report_path) -> dict` 统计；`emit_bank_js` / `emit_report`；CLI `python scripts/build_bank.py --raw raw --bank bank.js --report dedupe_report.json`

- [ ] **Step 1: 追加失败测试**

```python
    def test_infer_subject_from_filename(self):
        from build_bank import infer_subject

        self.assertEqual(infer_subject("edu_练习01.json", {}), "edu")
        self.assertEqual(infer_subject("psy_练习02.json", {}), "psy")
        self.assertEqual(infer_subject("law_练习03.json", {}), "law")
        self.assertEqual(
            infer_subject("x.json", {"exerciseName": "高等教育心理学-练习01"}), "psy"
        )

    def test_build_end_to_end_on_fixture_dir(self):
        import tempfile
        from build_bank import build

        with tempfile.TemporaryDirectory() as td:
            raw_dir = os.path.join(td, "raw")
            os.makedirs(raw_dir)
            shutil_copy = FIXTURE
            import shutil as _sh

            _sh.copy(shutil_copy, os.path.join(raw_dir, "edu_练习FIX.json"))
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
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
$env:MIMO_PYTHON -m unittest tests.test_build_bank -v
```

期望：`infer_subject` / `build` FAIL

- [ ] **Step 3: 实现 infer_subject、emit、build、CLI**

在 `scripts/build_bank.py` 追加（文件末尾）：

```python
SUBJECT_PREFIX = {"edu": "edu", "psy": "psy", "law": "law"}


def infer_subject(path: str, exercise: dict) -> str:
    name = os.path.basename(path).lower()
    for p, subj in SUBJECT_PREFIX.items():
        if name.startswith(p + "_") or name.startswith(p + "-"):
            return subj
    hay = f"{exercise.get('exerciseName') or ''} {exercise.get('courseId') or ''}"
    if "心理" in hay or "psy" in hay.lower():
        return "psy"
    if "法规" in hay or "道德" in hay or "law" in hay.lower():
        return "law"
    if "教育学" in hay or "高教" in hay:
        return "edu"
    return "unknown"


def emit_bank_js(items: list[dict], path: str) -> None:
    payload = json.dumps(items, ensure_ascii=False, separators=(",", ":"))
    with open(path, "w", encoding="utf-8") as f:
        f.write("window.BANK = ")
        f.write(payload)
        f.write(";\n")


def emit_report(report: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


def _score_fullness_sort_key(q: dict) -> tuple:
    return (-_fullness(q), q.get("uid") or "")


def build(raw_dir: str, bank_path: str, report_path: str) -> dict:
    items: list[dict] = []
    files_stats = []
    report_extra = {"files": []}
    for name in sorted(os.listdir(raw_dir)):
        if not name.lower().endswith(".json"):
            continue
        if name.startswith("_") or name == "fixtures":
            continue
        path = os.path.join(raw_dir, name)
        if not os.path.isfile(path):
            continue
        try:
            ex = load_exercise(path)
        except Exception as e:
            report_extra["files"].append({"file": name, "error": str(e)})
            continue
        subject = infer_subject(name, ex)
        meta = {"exerciseId": ex.get("exerciseId"), "exerciseName": ex.get("exerciseName")}
        rows = join_answers(ex)
        kept = 0
        for row in rows:
            q = normalize_question(row, subject, meta)
            if q is None:
                continue
            items.append(q)
            kept += 1
        files_stats.append({"file": name, "subject": subject, "rows": len(rows), "kept": kept})

    bank, report = dedupe(items)
    report["files"] = files_stats
    report["by_subject"] = {}
    for q in bank:
        report["by_subject"][q["subject"]] = report["by_subject"].get(q["subject"], 0) + 1
    emit_bank_js(bank, bank_path)
    emit_report(report, report_path)
    return {
        "files": len(files_stats),
        "parsed": len(items),
        "bank_size": len(bank),
        "merged": report.get("merged", 0),
        "conflicts": len(report.get("conflicts") or []),
        "by_subject": report["by_subject"],
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Build unique bank.js from raw exercises")
    p.add_argument("--raw", default="raw")
    p.add_argument("--bank", default="bank.js")
    p.add_argument("--report", default="dedupe_report.json")
    args = p.parse_args(argv)
    # skip fixtures dir: build() only reads files in raw_dir, fixtures is a subdir
    stats = build(args.raw, args.bank, args.report)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

说明：`raw/fixtures/` 是子目录，`build` 只扫 `raw/` 下的 `.json` 文件，不会误收 fixture。

- [ ] **Step 4: 跑全部测试**

```powershell
$env:MIMO_PYTHON -m unittest tests.test_build_bank -v
```

期望：全部 PASS

- [ ] **Step 5: 对 fixture 跑一次 CLI 冒烟**

```powershell
Copy-Item raw/fixtures/sample_exercise.json raw/_smoke_edu_fix.json
$env:MIMO_PYTHON scripts/build_bank.py --raw raw --bank bank.js --report dedupe_report.json
Remove-Item raw/_smoke_edu_fix.json
```

期望：stdout 含 `"bank_size": 3`；生成 `bank.js`、`dedupe_report.json`。冒烟文件名以 `_smoke` 开头会被跳过则改用 `edu_smoke_fix.json` 并在跑后删除。

- [ ] **Step 6: Commit**

```powershell
git add scripts/build_bank.py tests/test_build_bank.py
git commit -m "feat: emit bank.js and dedupe report via CLI"
```

---

### Task 5: 真实 raw 接入约定与出库验收（Phase A 收口）

**Files:**
- Create: `raw/README.md`（命名约定，短文即可）
- Modify: `tests/test_build_bank.py`（可选：bank 契约测试）
- Generate: `bank.js`, `dedupe_report.json`（有真实 raw 时）

**Interfaces:**
- Consumes: Task 4 的 `build`
- Produces: 冻结的 `bank.js` 契约（`window.BANK` 数组；字段同 Spec §5）

- [ ] **Step 1: 写 `raw/README.md`**

```markdown
# raw 投喂约定

- 文件名：`edu_*.json` / `psy_*.json` / `law_*.json`
- 内容：完整 exercise 顶层 JSON（含字符串化的 questions/answers）
- 同名覆盖前请改名或接受备份到 `_backup/`
- 三科齐了之后执行：
  `$env:MIMO_PYTHON scripts/build_bank.py --raw raw --bank bank.js --report dedupe_report.json`
- `raw/fixtures/` 仅测试用，不会进入题库
```

- [ ] **Step 2: 追加 bank 契约测试**

```python
    def test_bank_entry_fields(self):
        from build_bank import load_exercise, join_answers, normalize_question

        ex = load_exercise(FIXTURE)
        meta = {"exerciseId": ex["exerciseId"], "exerciseName": ex["exerciseName"]}
        q = normalize_question(join_answers(ex)[0], "edu", meta)
        for field in (
            "uid",
            "sourceOldId",
            "subject",
            "type",
            "stem",
            "options",
            "answer",
            "keyPoint",
            "difficulty",
            "importance",
            "sources",
        ):
            self.assertIn(field, q)
```

- [ ] **Step 3: 跑测试**

```powershell
$env:MIMO_PYTHON -m unittest tests.test_build_bank -v
```

期望：PASS

- [ ] **Step 4: （题库齐了再做）生成正式 bank 并人工扫 report**

```powershell
$env:MIMO_PYTHON scripts/build_bank.py --raw raw --bank bank.js --report dedupe_report.json
```

检查：`dedupe_report.json` 中 conflicts 无大量未解释堆积；`by_subject` 三科计数符合预期。若有缺口，回到投喂，不要改手 `bank.js`。

- [ ] **Step 5: Commit**

```powershell
git add raw/README.md tests/test_build_bank.py bank.js dedupe_report.json
git commit -m "chore: freeze bank contract and ingest notes"
```

**Gate:** Phase B（App）在本 Step 4 通过且用户确认「题库齐了」之后才开始。

---

### Task 6: App 壳、Tab 导航与题库加载

**Files:**
- Create: `index.html`

**Interfaces:**
- Consumes: `bank.js` 的 `window.BANK`
- Produces: `scoreAnswer(type, user, key)`；`loadState()/saveState()`（localStorage key `jiaozhi_v1`）；路由函数 `showTab(name)`

- [ ] **Step 1: 写 `index.html` 壳（含空库/坏库保护）**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
<title>教资刷题</title>
<style>
  :root {
    --bg: #f4f1ea;
    --ink: #1c2430;
    --muted: #5c6675;
    --accent: #0f6b4c;
    --accent-ink: #f4f1ea;
    --danger: #b33a3a;
    --ok: #1f7a4c;
    --card: #ffffff;
    --line: #d9d2c5;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
    background: var(--bg);
    color: var(--ink);
    min-height: 100vh;
    padding-bottom: 72px;
  }
  header {
    padding: 14px 16px 8px;
    border-bottom: 1px solid var(--line);
    background: var(--card);
    position: sticky;
    top: 0;
    z-index: 5;
  }
  header h1 { font-size: 17px; margin: 0; font-weight: 600; }
  main { padding: 12px 16px 24px; max-width: 480px; margin: 0 auto; }
  nav {
    position: fixed; left: 0; right: 0; bottom: 0;
    display: grid; grid-template-columns: repeat(4, 1fr);
    background: var(--card); border-top: 1px solid var(--line);
  }
  nav button {
    border: 0; background: transparent; padding: 10px 0 12px;
    font-size: 12px; color: var(--muted); cursor: pointer;
  }
  nav button.active { color: var(--accent); font-weight: 600; }
  .card {
    background: var(--card); border: 1px solid var(--line);
    border-radius: 12px; padding: 14px; margin-bottom: 12px;
  }
  .muted { color: var(--muted); font-size: 13px; }
  .btn {
    display: inline-block; border: 0; border-radius: 10px;
    background: var(--accent); color: var(--accent-ink);
    padding: 10px 14px; font-size: 14px; cursor: pointer;
  }
  .btn.ghost { background: transparent; color: var(--ink); border: 1px solid var(--line); }
  .btn.danger { background: var(--danger); }
  .row { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
  .opt {
    display: block; width: 100%; text-align: left;
    border: 1px solid var(--line); border-radius: 10px;
    background: var(--card); padding: 12px; margin-bottom: 8px;
    font-size: 15px; cursor: pointer;
  }
  .opt.selected { border-color: var(--accent); }
  .opt.correct { border-color: var(--ok); background: #e8f6ee; }
  .opt.wrong { border-color: var(--danger); background: #f8ecec; }
  .badge {
    display: inline-block; font-size: 11px; padding: 2px 8px;
    border-radius: 999px; background: var(--bg); color: var(--muted);
    border: 1px solid var(--line); margin-right: 6px;
  }
  h2 { font-size: 15px; margin: 0 0 8px; }
  .stem { font-size: 16px; line-height: 1.55; margin: 8px 0 12px; }
  .hidden { display: none !important; }
</style>
</head>
<body>
<header>
  <h1>教资刷题</h1>
  <div class="muted" id="bankMeta">加载题库…</div>
</header>
<main id="main"></main>
<nav id="tabbar">
  <button data-tab="practice" class="active">刷题</button>
  <button data-tab="wrong">错题</button>
  <button data-tab="exam">模考</button>
  <button data-tab="me">我的</button>
</nav>
<script src="bank.js"></script>
<script>
(function () {
  const STATE_KEY = "jiaozhi_v1";
  const TYPE_LABEL = { single: "单选", multiple: "多选", judge: "判断" };

  function bankReady() {
    return Array.isArray(window.BANK) && window.BANK.length > 0;
  }

  function loadState() {
    try {
      const raw = localStorage.getItem(STATE_KEY);
      if (!raw) return { wrong: [], progress: {}, exams: [], settings: { autoRemoveWrong: false } };
      const s = JSON.parse(raw);
      return {
        wrong: Array.isArray(s.wrong) ? s.wrong : [],
        progress: s.progress || {},
        exams: Array.isArray(s.exams) ? s.exams.slice(0, 20) : [],
        settings: { autoRemoveWrong: !!((s.settings || {}).autoRemoveWrong) },
      };
    } catch (e) {
      return { wrong: [], progress: {}, exams: [], settings: { autoRemoveWrong: false } };
    }
  }

  function saveState(state) {
    try {
      localStorage.setItem(STATE_KEY, JSON.stringify(state));
    } catch (e) {
      alert("进度保存失败，已尝试继续");
    }
  }

  function scoreAnswer(type, userAnswer, keyAnswer) {
    const u = (userAnswer || []).slice().sort().join(",");
    const k = (keyAnswer || []).slice().sort().join(",");
    return u === k && u.length > 0;
  }

  function showTab(name) {
    document.querySelectorAll("#tabbar button").forEach((b) => {
      b.classList.toggle("active", b.dataset.tab === name);
    });
    render(name);
  }

  function render(tab) {
    const main = document.getElementById("main");
    const meta = document.getElementById("bankMeta");
    if (!bankReady()) {
      meta.textContent = "题库未就绪";
      main.innerHTML = '<div class="card"><h2>题库未就绪</h2><p class="muted">请先生成 bank.js 再使用刷题功能。</p></div>';
      return;
    }
    meta.textContent = "题库 " + window.BANK.length + " 题";
    main.innerHTML = '<div class="card"><p class="muted">加载中…</p></div>';
    if (tab === "practice") renderPractice(main);
    else if (tab === "wrong") renderWrong(main);
    else if (tab === "exam") renderExam(main);
    else renderMe(main);
  }

  // 占位：后续 Task 实现
  function renderPractice(main) {
    main.innerHTML = '<div class="card"><h2>刷题</h2><p class="muted">Task 7/8/9 实现</p></div>';
  }
  function renderWrong(main) {
    main.innerHTML = '<div class="card"><h2>错题</h2><p class="muted">Task 10 实现</p></div>';
  }
  function renderExam(main) {
    main.innerHTML = '<div class="card"><h2>模考</h2><p class="muted">Task 11 实现</p></div>';
  }
  function renderMe(main) {
    main.innerHTML = '<div class="card"><h2>我的</h2><p class="muted">Task 12 实现</p></div>';
  }

  document.getElementById("tabbar").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-tab]");
    if (btn) showTab(btn.dataset.tab);
  });

  window.JZ = { scoreAnswer, loadState, saveState, showTab, bankReady, TYPE_LABEL };
  showTab("practice");
})();
</script>
</body>
</html>
```

- [ ] **Step 2: 手工验证空库与有库两条路径**

- 临时改名 `bank.js` 为 `bank.js.bak`，打开 `index.html`：显示「题库未就绪」，不白屏  
- 恢复 `bank.js`（用 Task 4 生成的），显示题库计数  
- 窗口宽 390px：无横向滚动  

- [ ] **Step 3: Commit**

```powershell
git add index.html
git commit -m "feat: app shell with tabs and bank boot guard"
```

---

### Task 7: 顺序刷题 — 单选 / 判断即点即判

**Files:**
- Modify: `index.html`（替换 `renderPractice` 及练习状态）

**Interfaces:**
- Consumes: `JZ.scoreAnswer`, `JZ.loadState/saveState`, `window.BANK`
- Produces: `renderPractice` 可选科目→顺序列表；答错写入 `state.wrong`（uid 去重）

- [ ] **Step 1: 实现顺序练习（单选/判断先通）**

将 `renderPractice` 与相关逻辑替换为（保留壳里其它函数）：

```javascript
  const subjName = { edu: "高等教育学", psy: "高等教育心理学", law: "职业道德与法规", unknown: "其他" };

  function filterBySubject(subject) {
    return window.BANK.filter((q) => q.subject === subject);
  }

  function renderPractice(main) {
    const state = JZ.loadState();
    if (!practiceSession) {
      const cards = ["edu", "psy", "law"].map((s) => {
        const n = filterBySubject(s).length;
        return (
          '<div class="card"><h2>' + subjName[s] + '</h2><p class="muted">' + n + ' 题</p>' +
          '<div class="row"><button class="btn" data-go="seq" data-subject="' + s + '">顺序刷题</button>' +
          '<button class="btn ghost" data-go="rand" data-subject="' + s + '">随机抽题</button></div></div>'
        );
      }).join("");
      main.innerHTML = cards + '<div class="card"><p class="muted">随机也可跨科：在「随机抽题」里选全部。</p></div>';
      main.querySelectorAll("[data-go]").forEach((b) => {
        b.addEventListener("click", () => {
          if (b.dataset.go === "seq") startSeq(b.dataset.subject);
          else startRand(b.dataset.subject);
        });
      });
      return;
    }
    drawQuestion(main, state);
  }

  let practiceSession = null;
  // startRand 在 Task 9 定义；此处先给出桩避免未定义
  function startRand(subject) {
    startSession(pickRandom(filterBySubject(subject === "all" ? null : subject) || window.BANK, 20), subject, "随机");
  }
  function startSeq(subject) {
    startSession(filterBySubject(subject), subject, "顺序");
  }
  function startSession(list, subject, modeLabel) {
    if (!list.length) {
      alert("该科暂无题");
      return;
    }
    practiceSession = { list: list.slice(), idx: 0, subject, modeLabel, selected: [], locked: false };
    JZ.showTab("practice");
  }

  function drawQuestion(main, state) {
    const s = practiceSession;
    const q = s.list[s.idx];
    if (!q) {
      practiceSession = null;
      renderPractice(main);
      return;
    }
    const typeLabel = JZ.TYPE_LABEL[q.type] || q.type;
    let html =
      '<div class="card">' +
      '<div><span class="badge">' + typeLabel + '</span><span class="badge">' + (s.modeLabel) + ' ' + (s.idx + 1) + '/' + s.list.length + '</span></div>' +
      '<div class="stem">' + escapeHtml(q.stem) + '</div><div id="opts"></div>' +
      '<div class="row" id="actions"></div></div>';
    main.innerHTML = html;
    const opts = document.getElementById("opts");
    const actions = document.getElementById("actions");
    if (q.type === "judge") {
      renderOptions(opts, q, [{ id: "TRUE", value: "正确" }, { id: "FALSE", value: "错误" }]);
    } else {
      renderOptions(opts, q, q.options);
    }
    if (q.type === "multiple") {
      actions.innerHTML = '<button class="btn" id="submitBtn">提交</button>';
      document.getElementById("submitBtn").addEventListener("click", () => lockAnswer(main, state, true));
    } else {
      // 即点即判：选中后立即 lock
    }
  }

  function renderOptions(container, q, options) {
    container.innerHTML = options
      .map(
        (o) =>
          '<button type="button" class="opt" data-id="' + o.id + '">' +
          o.id + ". " + escapeHtml(o.value) + "</button>"
      )
      .join("");
    container.querySelectorAll(".opt").forEach((btn) => {
      btn.addEventListener("click", () => onPick(btn, q));
    });
  }

  function onPick(btn, q) {
    if (!practiceSession || practiceSession.locked) return;
    const id = btn.dataset.id;
    if (q.type === "multiple") {
      btn.classList.toggle("selected");
    } else {
      document.querySelectorAll("#opts .opt").forEach((b) => b.classList.remove("selected"));
      btn.classList.add("selected");
      practiceSession.selected = [id];
      lockAnswer(document.getElementById("main"), JZ.loadState(), false);
    }
  }

  function currentSelected() {
    return Array.from(document.querySelectorAll("#opts .opt.selected")).map((b) => b.dataset.id);
  }

  function lockAnswer(main, state, isMultiple) {
    const s = practiceSession;
    if (!s || s.locked) return;
    const q = s.list[s.idx];
    const selected = isMultiple ? currentSelected() : s.selected;
    if (!selected.length) return;
    s.selected = selected;
    s.locked = true;
    const ok = JZ.scoreAnswer(q.type, selected, q.answer);
    document.querySelectorAll("#opts .opt").forEach((b) => {
      const id = b.dataset.id;
      const should = q.answer.indexOf(id) >= 0;
      if (should) b.classList.add("correct");
      else if (b.classList.contains("selected")) b.classList.add("wrong");
      b.disabled = true;
    });
    if (!ok) addWrong(state, q);
    else if (state.settings.autoRemoveWrong) removeWrong(state, q.uid);
    JZ.saveState(state);
    const actions = document.getElementById("actions");
    actions.innerHTML =
      '<span class="muted">' + (ok ? "答对" : "答错，正确答案 " + q.answer.join("")) + '</span>' +
      '<button class="btn" id="nextBtn">下一题</button>';
    document.getElementById("nextBtn").addEventListener("click", () => {
      s.idx += 1;
      s.selected = [];
      s.locked = false;
      JZ.showTab("practice");
    });
  }

  function addWrong(state, q) {
    if (state.wrong.indexOf(q.uid) < 0) state.wrong.push(q.uid);
  }
  function removeWrong(state, uid) {
    state.wrong = state.wrong.filter((x) => x !== uid);
  }

  function pickRandom(list, n) {
    const arr = list.slice();
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      const t = arr[i]; arr[i] = arr[j]; arr[j] = t;
    }
    return arr.slice(0, Math.max(0, n));
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
```

- [ ] **Step 2: 手工断言 — 单选 / 判断**

- 顺序进入 `edu`（或 fixture 科目）  
- 单选点正确项 → 绿、「答对」；点错误项 → 红 + 标出正确项、「答错」  
- 判断点「正确/错误」同上  
- 答错后刷新页面 → 「错题」里能见到该题（Task 10 完成前可在 `localStorage` 的 `jiaozhi_v1.wrong` 看到 uid）  

- [ ] **Step 3: Commit**

```powershell
git add index.html
git commit -m "feat: sequential practice for single and judge"
```

---

### Task 8: 多选提交制与全对判分

**Files:**
- Modify: `index.html`（`scoreAnswer` 已有；补多选 UI 流程测试说明）

**Interfaces:**
- Consumes: Task 7 的 `lockAnswer` / `onPick`
- Produces: 多选「可改选 → 提交 → 判」；`scoreAnswer("multiple", ["A"], ["A","B"]) === false`

- [ ] **Step 1: 确认纯函数（可贴到 DevTools）**

```javascript
console.assert(JZ.scoreAnswer("multiple", ["A", "B"], ["A", "B"]) === true);
console.assert(JZ.scoreAnswer("multiple", ["A"], ["A", "B"]) === false);
console.assert(JZ.scoreAnswer("multiple", ["A", "C"], ["A", "B"]) === false);
console.assert(JZ.scoreAnswer("single", ["A"], ["A"]) === true);
console.assert(JZ.scoreAnswer("judge", ["TRUE"], ["TRUE"]) === true);
```

期望：无 assertion failed

- [ ] **Step 2: 手工断言 — 多选**

- 多选题可反复点选切换  
- 未点「提交」不判对错  
- 只选部分正确项 → 提交 → **答错**  
- 多选了含错项 → 答错  
- 全选正确 → 答对  

- [ ] **Step 3: Commit**

```powershell
git add index.html
git commit -m "feat: multiple-choice submit and all-or-nothing scoring"
```

---

### Task 9: 随机抽题（题量 / 题型过滤 / 跨科）

**Files:**
- Modify: `index.html`（`startRand` 面板）

**Interfaces:**
- Consumes: `pickRandom`, `startSession`
- Produces: 随机配置 UI：科目=具体科或「全部」、N∈{10,20,50,自定义}、题型过滤

- [ ] **Step 1: 实现随机配置面板**

替换 `startRand`：

```javascript
  function startRand(subject) {
    const main = document.getElementById("main");
    const base = subject === "all" ? window.BANK.slice() : filterBySubject(subject);
    main.innerHTML =
      '<div class="card"><h2>随机抽题</h2>' +
      '<p class="muted">科目：' + (subject === "all" ? "全部" : subjName[subject]) + ' · 池内 ' + base.length + ' 题</p>' +
      '<label>题量 <select id="randN"><option>10</option><option selected>20</option><option>50</option><option value="custom">自定义</option></select></label> ' +
      '<input id="randCustom" class="hidden" type="number" min="1" placeholder="N" style="width:72px" />' +
      '<div class="row"><label><input type="checkbox" data-type="single" checked /> 单选</label>' +
      '<label><input type="checkbox" data-type="multiple" checked /> 多选</label>' +
      '<label><input type="checkbox" data-type="judge" checked /> 判断</label></div>' +
      '<div class="row"><button class="btn" id="randGo">开始</button>' +
      '<button class="btn ghost" id="randBack">返回</button></div></div>';
    const nSel = document.getElementById("randN");
    const nCustom = document.getElementById("randCustom");
    nSel.addEventListener("change", () => nCustom.classList.toggle("hidden", nSel.value !== "custom"));
    document.getElementById("randBack").addEventListener("click", () => {
      practiceSession = null;
      JZ.showTab("practice");
    });
    document.getElementById("randGo").addEventListener("click", () => {
      const types = Array.from(main.querySelectorAll("input[data-type]:checked")).map((x) => x.dataset.type);
      let n = nSel.value === "custom" ? parseInt(nCustom.value || "0", 10) : parseInt(nSel.value, 10);
      const pool = base.filter((q) => types.indexOf(q.type) >= 0);
      if (!n || n < 1) n = Math.min(20, pool.length);
      startSession(pickRandom(pool, n), subject, "随机");
    });
  }
```

在科目入口行增加「全部」按钮：在 `renderPractice` 无 session 时追加：

```javascript
      // 在 cards 之后
      // 已在 Task 7 HTML 中说明跨科；补一个入口：
```

将 `renderPractice` 里科目卡下方的提示卡片替换为：

```javascript
      main.innerHTML =
        cards +
        '<div class="card"><div class="row">' +
        '<button class="btn ghost" data-go="rand" data-subject="all">全部科目随机</button></div></div>';
```

（注意保留 Task 7 里对 `data-go` 的绑定。）

- [ ] **Step 2: 手工断言**

- 选科 → 随机 10 题 → 作答流程与顺序模式一致  
- 只勾「判断」→ 出题全为判断  
- 「全部科目随机」→ 可能混科，题干可见  
- 自定义 N=3 → 共 3 题  

- [ ] **Step 3: Commit**

```powershell
git add index.html
git commit -m "feat: random practice with size and type filters"
```

---

### Task 10: 错题本（列表 / 重刷 / 手动移出）

**Files:**
- Modify: `index.html`（`renderWrong`）

**Interfaces:**
- Consumes: `state.wrong`（uid 数组）、`startSession`
- Produces: 错题列表、按科筛选、「重刷」「移出」；uid 找不到题时自动清理

- [ ] **Step 1: 实现 `renderWrong`**

```javascript
  function renderWrong(main) {
    const state = JZ.loadState();
    const all = state.wrong
      .map((uid) => window.BANK.find((q) => q.uid === uid))
      .filter(Boolean);
    const missing = state.wrong.length - all.length;
    if (missing > 0) {
      state.wrong = all.map((q) => q.uid);
      JZ.saveState(state);
    }
    let filter = "all";
    function draw() {
      const list = filter === "all" ? all : all.filter((q) => q.subject === filter);
      main.innerHTML =
        '<div class="card"><h2>错题本</h2><p class="muted">' + all.length + " 题" +
        (missing ? "（已清理 " + missing + " 条失效）" : "") + '</p>' +
        '<div class="row">' +
        '<button class="btn ghost" data-f="all">全部</button>' +
        '<button class="btn ghost" data-f="edu">高教</button>' +
        '<button class="btn ghost" data-f="psy">心理</button>' +
        '<button class="btn ghost" data-f="law">道德法规</button>' +
        '<button class="btn" id="reWrong">重刷 ' + list.length + ' 题</button></div></div>' +
        list.map((q, i) =>
          '<div class="card"><div><span class="badge">' + (JZ.TYPE_LABEL[q.type] || "") + '</span>' +
          '<span class="badge">' + (subjName[q.subject] || q.subject) + '</span></div>' +
          '<div class="stem">' + escapeHtml(q.stem) + '</div>' +
          '<div class="row"><button class="btn ghost" data-off="' + i + '">移出</button></div></div>'
        ).join("");
      main.querySelectorAll("[data-f]").forEach((b) =>
        b.addEventListener("click", () => { filter = b.dataset.f; draw(); })
      );
      main.querySelectorAll("[data-off]").forEach((b) =>
        b.addEventListener("click", () => {
          const q = list[parseInt(b.dataset.off, 10)];
          removeWrong(state, q.uid);
          JZ.saveState(state);
          renderWrong(main);
        })
      );
      const re = document.getElementById("reWrong");
      if (re) re.addEventListener("click", () => {
        if (!list.length) return;
        startSession(list.slice(), filter, "错题重刷");
      });
    }
    draw();
  }
```

- [ ] **Step 2: 手工断言**

- 答错 2 题 → 错题本 2 条  
- 「移出」后减少  
- 「重刷」进入会话，再答对且未开自动移出 → 仍保留  
- 设置打开自动移出后答对 → 自动消失（与 Task 12 联调）  

- [ ] **Step 3: Commit**

```powershell
git add index.html
git commit -m "feat: wrong-answer book with retry and remove"
```

---

### Task 11: 模拟考试（组卷 / 计时 / 交卷判分）

**Files:**
- Modify: `index.html`（`renderExam` + `assemblePaper`）

**Interfaces:**
- Consumes: `scoreAnswer`, `window.BANK`
- Produces: `assemblePaper(bank, opts) -> questions[]`；`opts = { mode: "classic"|"randomN", n, types, subject }`  
  classic：尽量 40 single + 20 multiple + 20 judge；不足则该题型全取，缺额从其它已选题型随机补  
  计时默认 100 分钟；交卷后展示答案；历史 `state.exams` 最多 20 条

- [ ] **Step 1: 实现 `assemblePaper` 与模考流程**

在 IIFE 内增加：

```javascript
  function assemblePaper(bank, opts) {
    const types = opts.types && opts.types.length ? opts.types : ["single", "multiple", "judge"];
    const pool = bank.filter((q) => types.indexOf(q.type) >= 0 && (!opts.subject || opts.subject === "all" || q.subject === opts.subject));
    if (opts.mode === "randomN") {
      return pickRandom(pool, opts.n || 20);
    }
    const quota = { single: 40, multiple: 20, judge: 20 };
    const picked = [];
    const used = new Set();
    const lack = [];
    ["single", "multiple", "judge"].forEach((t) => {
      if (types.indexOf(t) < 0) return;
      const seg = pickRandom(pool.filter((q) => q.type === t && !used.has(q.uid)), quota[t]);
      seg.forEach((q) => { used.add(q.uid); picked.push(q); });
      if (seg.length < quota[t]) lack.push(t + "不足" + quota[t]);
    });
    const totalWant = 80;
    if (picked.length < totalWant) {
      const rest = pickRandom(pool.filter((q) => !used.has(q.uid)), totalWant - picked.length);
      rest.forEach((q) => { used.add(q.uid); picked.push(q); });
    }
    picked.lackHint = lack.length ? lack.join("；") : "";
    return picked;
  }

  let examSession = null;

  function renderExam(main) {
    const state = JZ.loadState();
    if (!examSession) {
      main.innerHTML =
        '<div class="card"><h2>模拟考试</h2>' +
        '<p class="muted">默认 40 单选 + 20 多选 + 20 判断；多选全对才算对；交卷后显示答案。</p>' +
        '<div class="row"><label>模式 <select id="exMode"><option value="classic">标准 80 题</option><option value="randomN">随机 N 题</option></select></label></div>' +
        '<div class="row"><label>N <input id="exN" type="number" value="20" min="1" style="width:72px" disabled /></label>' +
        '<label>限时（分） <select id="exMin"><option>30</option><option>60</option><option>90</option><option selected>100</option><option>120</option><option value="0">不限时</option></select></label></div>' +
        '<div class="row"><label><input type="checkbox" data-type="single" checked /> 单</label>' +
        '<label><input type="checkbox" data-type="multiple" checked /> 多</label>' +
        '<label><input type="checkbox" data-type="judge" checked /> 判</label></div>' +
        '<div class="row"><button class="btn" id="exGo">开始考试</button></div></div>' +
        '<div class="card"><h2>最近成绩</h2>' +
        (state.exams.length
          ? state.exams.map((e) => '<p class="muted">' + e.at + " · " + e.right + "/" + e.total + " · " + e.modeLabel + "</p>").join("")
          : '<p class="muted">暂无记录</p>') +
        "</div>";
      const mode = document.getElementById("exMode");
      const nInput = document.getElementById("exN");
      mode.addEventListener("change", () => {
        nInput.disabled = mode.value !== "randomN";
      });
      document.getElementById("exGo").addEventListener("click", () => {
        const types = Array.from(main.querySelectorAll("input[data-type]:checked")).map((x) => x.dataset.type);
        const opts = {
          mode: mode.value,
          n: parseInt(nInput.value || "20", 10),
          types,
          subject: "all",
        };
        const list = assemblePaper(window.BANK, opts);
        if (!list.length) {
          alert("题量不足，无法组卷");
          return;
        }
        const minutes = parseInt(document.getElementById("exMin").value, 10);
        examSession = {
          list,
          idx: 0,
          answers: {},
          deadline: minutes > 0 ? Date.now() + minutes * 60000 : null,
          modeLabel: opts.mode === "classic" ? "标准卷" : "随机" + opts.n,
          lackHint: list.lackHint || "",
          submitted: false,
        };
        if (examSession.lackHint) alert("题型不足已自动补齐：" + examSession.lackHint);
        drawExam(main);
      });
      return;
    }
    drawExam(main);
  }

  function drawExam(main) {
    const s = examSession;
    if (!s || s.submitted) return drawExamResult(main);
    const q = s.list[s.idx];
    const left = s.deadline ? Math.max(0, Math.floor((s.deadline - Date.now()) / 1000)) : null;
    const timeTxt = left == null ? "不限时" : "剩余 " + Math.floor(left / 60) + ":" + String(left % 60).padStart(2, "0");
    main.innerHTML =
      '<div class="card"><div><span class="badge">' + (JZ.TYPE_LABEL[q.type] || "") + '</span>' +
      '<span class="badge">' + (s.idx + 1) + "/" + s.list.length + '</span><span class="badge" id="exClock">' + timeTxt + '</span></div>' +
      '<div class="stem">' + escapeHtml(q.stem) + '</div><div id="opts"></div>' +
      '<div class="row"><button class="btn ghost" id="exPrev">上一题</button>' +
      '<button class="btn ghost" id="exNext">下一题</button>' +
      '<button class="btn" id="exSubmit">交卷</button></div></div>';
    const opts = document.getElementById("opts");
    const choices = q.type === "judge" ? [{ id: "TRUE", value: "正确" }, { id: "FALSE", value: "错误" }] : q.options;
    const saved = s.answers[q.uid] || [];
    opts.innerHTML = choices
      .map((o) => {
        const sel = saved.indexOf(o.id) >= 0 ? " selected" : "";
        return '<button type="button" class="opt' + sel + '" data-id="' + o.id + '">' + o.id + ". " + escapeHtml(o.value) + "</button>";
      })
      .join("");
    opts.querySelectorAll(".opt").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.dataset.id;
        let cur = (s.answers[q.uid] || []).slice();
        if (q.type === "multiple") {
          const i = cur.indexOf(id);
          if (i >= 0) cur.splice(i, 1);
          else cur.push(id);
          btn.classList.toggle("selected");
        } else {
          cur = [id];
          opts.querySelectorAll(".opt").forEach((b) => b.classList.remove("selected"));
          btn.classList.add("selected");
        }
        s.answers[q.uid] = cur;
      });
    });
    document.getElementById("exPrev").addEventListener("click", () => {
      if (s.idx > 0) s.idx -= 1;
      drawExam(main);
    });
    document.getElementById("exNext").addEventListener("click", () => {
      if (s.idx < s.list.length - 1) s.idx += 1;
      drawExam(main);
    });
    document.getElementById("exSubmit").addEventListener("click", () => submitExam(main, false));
    if (s.deadline) {
      clearInterval(examSession.timer);
      s.timer = setInterval(() => {
        if (!examSession || examSession.submitted) return;
        if (Date.now() >= s.deadline) {
          clearInterval(s.timer);
          submitExam(document.getElementById("main"), true);
        } else {
          const el = document.getElementById("exClock");
          if (el) {
            const sec = Math.max(0, Math.floor((s.deadline - Date.now()) / 1000));
            el.textContent = "剩余 " + Math.floor(sec / 60) + ":" + String(sec % 60).padStart(2, "0");
          }
        }
      }, 1000);
    }
  }

  function submitExam(main, auto) {
    const s = examSession;
    if (!s || s.submitted) return;
    s.submitted = true;
    if (s.timer) clearInterval(s.timer);
    let right = 0;
    s.list.forEach((q) => {
      const ok = JZ.scoreAnswer(q.type, s.answers[q.uid] || [], q.answer);
      if (ok) right += 1;
    });
    const state = JZ.loadState();
    state.exams.unshift({
      at: new Date().toISOString().slice(0, 16).replace("T", " "),
      right,
      total: s.list.length,
      modeLabel: s.modeLabel + (auto ? "（自动交卷）" : ""),
    });
    state.exams = state.exams.slice(0, 20);
    JZ.saveState(state);
    drawExamResult(main, right, auto);
  }

  function drawExamResult(main, rightArg, auto) {
    const s = examSession;
    if (!s) return renderExam(main);
    let right = rightArg;
    if (right == null) {
      right = s.list.reduce((n, q) => n + (JZ.scoreAnswer(q.type, s.answers[q.uid] || [], q.answer) ? 1 : 0), 0);
    }
    main.innerHTML =
      '<div class="card"><h2>考试结果' + (auto ? "（到时自动交卷）" : "") + '</h2>' +
      '<p class="stem">' + right + " / " + s.list.length + '</p>' +
      '<div class="row"><button class="btn" id="exDone">返回</button>' +
      '<button class="btn ghost" id="exToWrong">错题入本</button></div></div>' +
      s.list.map((q) => {
        const ok = JZ.scoreAnswer(q.type, s.answers[q.uid] || [], q.answer);
        const you = (s.answers[q.uid] || []).join("") || "—";
        return (
          '<div class="card"><div><span class="badge">' + (ok ? "对" : "错") + '</span>' +
          '<span class="badge">' + (JZ.TYPE_LABEL[q.type] || "") + '</span></div>' +
          '<div class="stem">' + escapeHtml(q.stem) + '</div>' +
          '<p class="muted">你的答案 ' + escapeHtml(you) + ' · 正确 ' + escapeHtml(q.answer.join("")) + '</p></div>'
        );
      }).join("");
    document.getElementById("exDone").addEventListener("click", () => {
      examSession = null;
      renderExam(main);
    });
    document.getElementById("exToWrong").addEventListener("click", () => {
      const state = JZ.loadState();
      s.list.forEach((q) => {
        if (!JZ.scoreAnswer(q.type, s.answers[q.uid] || [], q.answer)) addWrong(state, q);
      });
      JZ.saveState(state);
      alert("错题已入本");
    });
  }
```

- [ ] **Step 2: 纯函数断言（DevTools / 临时 script）**

```javascript
const fake = [];
for (let i = 0; i < 50; i++) fake.push({ uid: "s" + i, type: "single", subject: "edu" });
for (let i = 0; i < 5; i++) fake.push({ uid: "m" + i, type: "multiple", subject: "edu" });
for (let i = 0; i < 10; i++) fake.push({ uid: "j" + i, type: "judge", subject: "edu" });
const paper = assemblePaper(fake, { mode: "classic", types: ["single", "multiple", "judge"] });
console.assert(paper.length === 65); // 50+5+10 全取后不足 80
console.assert(paper.filter((q) => q.type === "single").length === 50);
```

期望：无 assertion failed；UI 在题量不足时弹出提示。

- [ ] **Step 3: 手工断言 — 模考主路径**

- 标准卷开始 → 可翻页改答案 → 交卷 → 见得分与**答案**  
- 到时不交 → 自动交卷  
- 「错题入本」→ 错题本增加  
- 历史最多 20 条（连续考 21 次可抽查）  

- [ ] **Step 4: Commit**

```powershell
git add index.html
git commit -m "feat: mock exam assembly, timer, and scored report"
```

---

### Task 12: 我的 / 设置 / 持久化加固 + 总验收

**Files:**
- Modify: `index.html`（`renderMe`、坏 localStorage 重置提示）

**Interfaces:**
- Consumes: `loadState/saveState`
- Produces: 统计、清空进度、`autoRemoveWrong` 开关

- [ ] **Step 1: 实现 `renderMe`**

```javascript
  function renderMe(main) {
    const state = JZ.loadState();
    const total = window.BANK.length;
    main.innerHTML =
      '<div class="card"><h2>我的</h2>' +
      '<p class="muted">题库 ' + total + " 题 · 错题 " + state.wrong.length + " · 模考记录 " + state.exams.length + '</p>' +
      '<p class="muted">多选计分：全对才算对（固定）</p>' +
      '<label><input type="checkbox" id="autoOff" ' + (state.settings.autoRemoveWrong ? "checked" : "") + ' /> 错题做对后自动移出</label>' +
      '<div class="row"><button class="btn danger" id="clearAll">清空进度与错题</button></div></div>';
    document.getElementById("autoOff").addEventListener("change", (e) => {
      state.settings.autoRemoveWrong = e.target.checked;
      JZ.saveState(state);
    });
    document.getElementById("clearAll").addEventListener("click", () => {
      if (!confirm("确认清空错题与进度？")) return;
      const s = { wrong: [], progress: {}, exams: [], settings: state.settings };
      JZ.saveState(s);
      renderMe(main);
    });
  }
```

在 `loadState` 的 catch 分支增加：

```javascript
    } catch (e) {
      try { localStorage.removeItem(STATE_KEY); } catch (e2) {}
      return { wrong: [], progress: {}, exams: [], settings: { autoRemoveWrong: false } };
    }
```

- [ ] **Step 2: 走 Spec §10 验收清单（手工）**

1. 三科顺序 + 随机 + 错题 + 模考四条路径  
2. 单 / 多全对 / 判 判分  
3. 错题入库、重刷、移出  
4. 模考默认 80 与随机 N；限时自动交卷；交卷后见答案  
5. 刷新后错题与成绩仍在  
6. 390px 无横向滚动；`dedupe_report.json` 抽查无大量未解释冲突  

- [ ] **Step 3: Commit**

```powershell
git add index.html
git commit -m "feat: profile stats and settings with storage reset guard"
```

---

## Phase 切换备忘

| 阶段 | 任务 | 何时做 |
|------|------|--------|
| A 题库流水线 | 1–5 | 立刻；Step 5 出正式 bank 需三科 raw 齐 |
| B 刷题 App | 6–12 | **题库齐并生成 bank.js 之后** |

投喂：`raw/edu_*.json` / `psy_*.json` / `law_*.json`，或直接贴 exercise JSON 由执行者落盘。

## Self-Review 记录

1. **Spec coverage:** §3 架构→Task 1–5；§4–6 模型与去重→Task 1–3；§7 异常→Task 2/3/4 测试；§8 四模式→Task 6–11；§8.4 我的→Task 12；§9 错误处理→Task 6/11/12；§10 验收→Task 12 Step 2；§11 测试→各任务；§12 投喂→Task 5 + Phase 表。无缺口。  
2. **Placeholder scan:** 无 TBD；Task 7 对 `startRand` 先桩后 Task 9 替换，两处均给了代码。  
3. **Type consistency:** `scoreAnswer(type, user[], key[]) -> boolean`；`assemblePaper(bank, opts)`；`state = {wrong[], progress, exams[], settings.autoRemoveWrong}`；`uid` 字符串一致。  
4. **Review Focus:** 表中 7 条均钉到具体测试步骤；组卷不足、坏 storage 另有手工步骤覆盖。
