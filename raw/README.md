# raw 投喂约定

- 文件名：`edu_*.json` / `psy_*.json` / `law_*.json`
- 内容：完整 exercise 顶层 JSON（含字符串化的 questions/answers）
- 同名覆盖前请改名或接受备份到 `_backup/`
- 三科齐了之后执行：
  `& $env:MIMO_PYTHON scripts/build_bank.py --raw raw --bank bank.js --report dedupe_report.json`
- `raw/fixtures/` 仅测试用，不会进入题库
- 以 `_` 开头的文件会被流水线跳过
