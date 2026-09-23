# 教资考试刷题 App — 设计 Spec

日期：2026-09-23  
状态：待用户审阅书面 spec  
路径：Architectural（已完：需求澄清、方案比较、分节设计对话确认）

## 1. 意图与成功标准

做一个高校教师资格类考试的**移动端刷题 App**（Web 单页，可在手机模拟器中使用）。用户从做题系统爬取多份「练习卷」JSON，全部到齐后清洗去重，得到**唯一总题库**，再据此做 App。

成功标准：

- 三科题库合并去重后可刷
- 支持顺序刷题、随机抽题、错题本、模拟考试
- 判分正确（多选全对才算对），无答案解析
- 离线可用；进度与错题本地持久化
- 约 390px 宽度下可正常刷题

## 2. 范围

**做：**

- `raw/` 原始 exercise JSON 归档
- `scripts/build_bank.py` 解析 / 合并 / 去重 / 出库
- `bank.js` 唯一总题库（脚本生成）
- `index.html` 移动端刷题 App（四模式）
- `dedupe_report.json` 去重与冲突日志

**不做：**

- 答案解析 / 详解
- 收藏 / 标记
- 账号、云同步、后端 API
- 原生安装包

## 3. 总体架构与数据流

```text
raw/*.json  →  scripts/build_bank.py  →  bank.js
                      ↓
              dedupe_report.json
                      ↓
              index.html（读 bank.js，四模式刷题）
```

交付文件布局（工作目录根）：

| 路径 | 职责 |
|------|------|
| `raw/` | 用户投喂的原始练习卷 JSON；命名 `edu_*.json` / `psy_*.json` / `law_*.json` |
| `raw/_backup/` | 同名覆盖前的备份 |
| `scripts/build_bank.py` | 唯一流水线入口 |
| `bank.js` | `window.BANK = [...]`，勿手改 |
| `dedupe_report.json` | 合并、丢弃、冲突记录 |
| `index.html` | App 入口（CSS/JS 内联或同目录） |

## 4. 源数据 Schema（已知）

顶层 exercise 包装字段（节选）：

- `exerciseId`, `exerciseUuid`, `exerciseName`, `courseId`
- `questions`: **字符串化 JSON 数组**
- `answers`: **字符串化** `[{questionId, answer}]`，`questionId` 为卷内序号
- `questionAmount`, `singleAmount`, `multipleAmount`, `judgeAmount`, `canExamTime`

单题（`questions` 内层）：

| 字段 | 含义 |
|------|------|
| `questionDesc` | 题干 |
| `questionId` | **卷内**序号，不作去重键 |
| `questionIdOld` | 全库旧 ID，去重首选 |
| `questionType` | `1` 单选 / `2` 多选 / `3` 判断 |
| `options` | 字符串化 `[{id, value}]`；判断题为 `[]` |
| `keyPoint` | 知识点 |
| `difficultyLevel` / `importanceLevel` | 难度 / 重要度 |
| `subjectId` | 科目线索之一 |

答案形态：

- 单选：`"A"`
- 多选：`"A,B,C,D,E"`
- 判断：`"TRUE"` / `"FALSE"`

样例卷：`高等教育学(…)-练习01`，`subjectId=64`，80 题 = 40 单 + 20 多 + 20 判。  
**无解析字段**（已确认产品只判对错）。

## 5. 归一化题目模型（BANK 条目）

```js
{
  uid: string,                 // 优先 sourceOldId，否则 content hash
  sourceOldId: number|null,
  subject: "edu"|"psy"|"law",
  type: "single"|"multiple"|"judge",
  stem: string,
  options: [{ id: "A", value: "..." }],
  answer: string[],            // 单选 ["A"]；多选 ["A","B"]；判断 ["TRUE"]|["FALSE"]
  keyPoint: string,
  difficulty: number,
  importance: number,
  sources: [{ exerciseId, exerciseName, questionId }]
}
```

科目映射：

| subject | 名称 | 文件名前缀 |
|---------|------|------------|
| `edu` | 高等教育学 | `edu_` |
| `psy` | 高等教育心理学 | `psy_` |
| `law` | 高校教师职业道德修养和高等教育法规 | `law_` |

优先级：文件名前缀 → `subjectId`/`exerciseName` 规则表 → 标记 `unknown` 并入 report。

## 6. 去重规则（已确认：先 ID，再内容）

1. 相同 `questionIdOld` → 合并，`sources` 追加  
2. 否则内容键相同则合并：`hash(stem + 规范化 options + answer + type)`  
3. 同键字段冲突（如答案不一致）→ 按「更全」比较：非空字段数多者优先；仍平则保留先入库者。冲突双方均记入 `dedupe_report.json`  
4. 卷内 `questionId` 仅写入 `sources`

规范化：去首尾空白、压缩连续空白；选项按 `id` 排序后再哈希。

## 7. 流水线步骤与异常

`build_bank.py`：

1. 读 `raw/*.json`；`questions`/`answers`/`options` 为字符串则 `json.loads`
2. 用 `answers` 按卷内 `questionId` 挂答案
3. 映射 `subject`
4. 规范化并按 §6 去重
5. 写出 `bank.js`、`dedupe_report.json`；打印三科数量、合并数、冲突数

| 异常 | 行为 |
|------|------|
| 某题缺答案 | 丢弃该题，记 report |
| 题干空 / options 非法 | 丢弃，记 report |
| 同 uid 答案冲突 | 取更全者，双记 report |
| 同名 raw 文件 | 覆盖前备份到 `raw/_backup/` |
| 某科 0 题 | 允许出库，App 显示「该科暂无题」 |

## 8. App 信息架构

底部 Tab：**刷题 · 错题 · 模考 · 我的**

### 8.1 刷题

- 选科目 → **顺序** 或 **随机**
- 顺序：该科总题库按稳定顺序；顶栏显示 `12/80` 与题型徽章
- 随机：科目（或全部）+ 题量 N（10/20/50/自定义）+ 可选题型过滤
- **单选 / 判断**：点选即判，绿/红并标出正确项，「下一题」
- **多选**：可改选，点「提交」才判；**全对才算对**（漏选、错选均错）
- 无解析
- 答错自动按 `uid` 进错题本；做对**默认仍保留**，可在错题本手动移出

### 8.2 错题本

- 按科目筛选列表；重刷错题；手动移出

### 8.3 模考

- **默认组卷**：单 40 + 多 20 + 判 20；某题型存量不足则该题型全取，其余名额随机补齐
- **随机 N 题**：自定义数量；可限时 / 不限时
- 默认限时 **100 分钟**。源卷字段 `canExamTime` 若存在且可解释为分钟则优先取整到 5 分钟粒度；无法解释或缺失时用 100。用户可在组卷时改（30/60/90/100/120/不限时）
- 交卷前可回头修改；到时自动交卷
- **交卷后才显示正确答案**
- 计分：正确率；多选全对才算对
- 成绩页：得分率、对错列表、错题一键入本

### 8.4 我的

- 正确率、已刷题数、题库规模
- 清空进度
- 设置：错题「做对后自动移出」开关（**默认关**=保留）；多选计分固定「全对才算对」，仅展示说明
- 关于

### 8.5 持久化（`localStorage`）

- 错题 `uid` 集合
- 各科目顺序刷题进度
- 模考历史（最多保留最近 20 次）
- 设置项

损坏时：重置进度并提示，不白屏。

## 9. App 错误处理

| 情况 | 行为 |
|------|------|
| `bank.js` 未加载或空库 | 首页「题库未就绪」，禁用进入刷题 |
| `localStorage` 异常 | 重置并 toast |
| 组卷题量不足 | 降级为实际可组题量并提示 |
| 某科 0 题 | 该科入口提示「该科暂无题」 |

## 10. 验收清单

1. 三科顺序刷题、随机抽题、错题本、模考四条路径可走通  
2. 单选 / 多选（全对才算对）/ 判断 判分正确  
3. 错题入库、重刷、手动移出可用  
4. 模考默认 40/20/20 + 随机 N；限时自动交卷；交卷后才见答案  
5. 刷新后进度与错题仍在  
6. 约 390px 宽度无横向滚动；`dedupe_report` 无大量未解释冲突  

## 11. 测试策略

- 流水线：对样例 exercise 断言可解析、字段归一、去重可预期（轻量脚本或手工核对 report 统计）
- App：按 §10 手工验收（无强制测试框架）
- 视觉：手机模拟器宽度走查

## 12. 数据投喂约定（并行采集）

- 边爬边丢：贴 JSON 或放入 `raw/`
- 命名：`edu_练习01.json` 等
- 收到即归档并回执题数
- **三科齐了**之后跑 `build_bank.py`，出唯一总题库，**再开始写 App**

## 13. 已确认决策

| 决策点 | 结论 |
|--------|------|
| 解析 | 无，只判对错 |
| 功能 | 顺序 + 随机 + 错题本 + 模考；不做收藏 |
| 去重 | 先 `questionIdOld` 再内容；冲突取更全并记日志 |
| 模考 | 默认 40/20/20，可改随机 N |
| 多选计分 | 全对才算对 |
| 错题做对 | 默认保留，手动移出 |
| 技术路线 | 方案 A：离线流水线 + `bank.js` + 单页 App |
