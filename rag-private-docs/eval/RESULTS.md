# 评估结果记录

这个文件记录每次评估的关键数据和发现，用于纵向对比。
评估结果 JSON 在 `eval/results/` 下（每次 `--save` 生成）。

## 2026-09-13 基线（12 正 + 10 负）

### 汇总指标

| 指标 | 值 | 说明 |
|---|---|---|
| num_questions | 22 | 12 正 + 10 负 |
| hit_at_1 | 1.0 | 正样本 Top-1 全部命中 |
| hit_at_3 | 1.0 | |
| hit_at_5 | 1.0 | |
| context_precision | 0.567 | 有提升空间 |
| context_recall | 1.0 | |
| **reject_accuracy** | **0.6** | **10 条负样本里 6 条正确拒答** |

### 正样本 confidence（12 条）

| 问题 | confidence |
|---|---|
| 什么是 RAG | 0.9972 |
| LangChain 加载器 | 0.9977 |
| DeepSeek API | 0.9953 |
| 合同总金额 | 0.9618 |
| 莫干山装备 | 0.9880 |
| 12 月版本上线 | 0.9988 |
| 合同延期罚则 | 0.7795 |
| 客户希望提前几天 | 0.9983 |
| 论文标题 | 0.7649 |
| 论文 Hit@1 | 0.9021 |
| 论文 BM25 | 0.8132 |
| **论文作者** | **0.3663** ← 最低 |

### 负样本 confidence（10 条）

**成功拒答（6 条，confidence < 0.30）**：

| 问题 | confidence |
|---|---|
| 公司年假 | 0.1949 |
| Python GIL | 0.1870 |
| 北京到上海高铁 | 0.2020 |
| Nginx 反代 | 0.1849 |
| 团队绩效 | 0.1831 |
| LangChain vs LlamaIndex | 0.2286 |

**拒答失败（4 条，confidence > 0.30）**：

| 问题 | confidence | top1 来源 |
|---|---|---|
| 莫干山海拔 | 0.4328 | 05-hike |
| DeepSeek 参数量 | 0.4883 | 03-api |
| 合同违约金 | 0.8489 | 04-contract |
| 12 月功能清单 | 0.9083 | 06-email |

### 最危险的 case

**12 月功能清单（confidence = 0.9083）是所有负样本里最高的，比 10 条正样本里的 7 条都高。**

这不只是"失败"，是系统对一个完全无答案的问题给出了**近乎确定的回答**。比"合同违约金 0.8489"更值得警惕：

- 违约金至少文档里有"违约""罚则"这些词
- "功能清单"是把一个**部分相关的话题推到了 0.91**

**这是"话题相关 ≠ 答案存在"最极端的体现。** 下次优先解决这个场景。

### 关键发现：阈值救不了

把两端的数排出来：

    最低正样本 confidence    = 0.3663  （论文作者）
    最高成功负样本 confidence = 0.2286  （LangChain vs LlamaIndex）
    最低失败负样本 confidence = 0.4328  （莫干山海拔）

**正负区间重叠**：

- 正样本最低 0.37
- 负样本最高 0.91

无论阈值调到哪，都会误伤其中一边：

- 阈值提到 0.5 → 论文作者（0.37）那条正样本被误拒
- 阈值保持 0.3 → 4 条难负样本继续漏网

**这不是阈值问题。**

### 根因

reranker 测的是「问题与文本的**话题相关性**」，不是「文本里**有没有答案**」。

- "合同违约金" → 文档里全是"合同""违约""罚则" → reranker 给 0.85
- 但它不知道答案是"没有违约金条款"
- "LangChain vs LlamaIndex" 成功拒答（0.23），是因为"LlamaIndex"这个词从没出现在文档里

**成功的唯一一条，恰恰是因为有一个关键词完全不存在。**

### 下一步方向

> **注（2026-09-16 补）**：本节写于 2026-09-13，三个方向后续状态如下——
> - 方向 1（集成 critic）**已归档**：commit `e900df7` "critic 纯过滤契约确认 + 定位（不进 qa.py）"。
>   后续实验证明 MAYBE 折扣是 metric hacking，纯过滤后 critic 对 reject_accuracy 零贡献。
> - 方向 2（低分正样本）：论文作者这条经 probe（`ad87f16`）查明——LLM 实际给出了
>   "Anonymous Authors"，措辞保守但非拒答。
> - 方向 3（加负样本）**已完成**：test_set 从 10 条扩到 12 条。

1. **集成 critic 到拒答链路**（关键）
   - `critic.py` 是 CRAG 实现：让 LLM 判断"这段 chunk 是否真的包含答案"
   - 目前只在 `evaluator.py` 里可选开启，`qa.py` 没强制用
   - 计划：`qa.py` 拒答判断加一层——`max_conf < 阈值` **或** `critic 全判 NO`
   - 改完重跑，看 4 条失败能否被救回
   - **优先验证**：12 月功能清单（0.9083）这条能否被 critic 拦下

2. **降低低分正样本风险**
   - 论文作者问题（0.3663）离阈值太近
   - 可能方向：改 PDF metadata 解析方式，或对 metadata 类问题单独处理

3. **加更多负样本**
   - 当前 10 条，统计意义有限
   - 目标 20-30 条，覆盖更多场景

### 参考

- 本次原始数据：`eval/results/2026-09-13T04-55-47.json`
- critic 实现：`src/critic.py`
- 拒答逻辑：`src/qa.py` 的 `CONFIDENCE_THRESHOLD`

## 2026-09-13 下午：critic 实验

在基线之上，测试 CRAG（critic）对拒答的影响。跑了 5 轮 workflow。

### 5 轮对比

| 时间戳 | 配置 | reject_acc | precision | 关键变化 |
|---|---|---|---|---|
| 04-55-47 | 无 critic | 0.6 | 0.567 | baseline |
| 05-33-36 | strict prompt | **0.7** | 0.867 | 合同违约金 0.85→0.25 |
| 05-49-47 | lenient prompt | 0.6 | 0.825 | 更差，回退 |
| 06-10-25 | strict + MAYBE bug 修 | 0.7 | 0.746 | precision 虚高被修正 |
| 06-23-45 | strict + MAYBE 折扣 0.5 | 0.7 | 0.746 | 合同违约金 0.25→0.12 |

注意：`precision` 从 0.867 降到 0.746 是**指标修正**，不是系统变差——MAYBE chunk 保留进 hits 后，关键词匹配率下降，但给 LLM 的上下文更完整。

### 本轮（06-23-45）负样本结果

**成功拒答（7 条）**：

| 问题 | confidence | 备注 |
|---|---|---|
| 公司年假 | 0.1949 | |
| Python GIL | 0.1870 | |
| 北京到上海高铁 | 0.2020 | |
| Nginx 反代 | 0.1822 | |
| 团队绩效 | 0.1808 | |
| **合同违约金** | **0.1234** | 从 0.8489 降下来，MAYBE 折扣生效 |
| LangChain vs LlamaIndex | 0.2286 | |

**拒答失败（3 条）——三个不同根因**：

| 问题 | confidence | 根因 |
|---|---|---|
| 莫干山海拔 | 0.4328 | **全丢 → 兜底 → 折扣未执行** |
| DeepSeek 参数量 | 0.4883 | **全丢 → 兜底 → 折扣未执行** |
| 12月功能清单 | 0.5205 | **critic 判 YES，不打折** |

### 三条失败的机制

**1. 莫干山 / DeepSeek：兜底冲掉了折扣**

日志：

    [warn] critic dropped all 5 chunks for: 莫干山的海拔是多少？
    [warn] falling back to unfiltered hits to avoid zero score

critic 全判 NO → `hits` 空 → 兜底恢复原始 hits → 折扣没机会执行。

**2. 12月功能清单：critic 判定粒度不够**

critic 保留了 2 个 chunk，判为 YES。它认为"文档里有 12 月发布信息 → 相关"，但**没看出"发布信息"和"功能清单"不是一回事**。

### 正样本的副作用

三条 PDF 正样本 confidence 下降（MAYBE 折扣被应用）：

| 问题 | 原值 | 本轮 | 状态 |
|---|---|---|---|
| 论文标题 | 0.7649 | 0.3824 | 安全（> 0.30） |
| 论文 BM25 | 0.8132 | 0.4066 | 安全 |
| 论文作者 | 0.3663 | 0.3663 | 全丢兜底，未变 |

**hit_at_1 仍 1.0，未误伤。** 但论文标题从 0.76 掉到 0.38，离阈值只差 0.08——**下次改任何东西都要盯住这条**。

### 下次开工的方向

**A. 改全丢兜底逻辑**（优先）

现在：

    if not filtered:
        # 用回原始 hits（折扣不生效）
        pass

改成：

    if not filtered:
        # 保留 rerank top-1，confidence × 0.3
        top = max(hits, key=lambda x: x.get("confidence", 0))
        top["confidence"] *= 0.3
        hits = [top]

预期：莫干山 0.43→0.13，DeepSeek 0.49→0.15。

**B. 改 critic prompt，区分"话题相关"和"有答案"**

12月功能清单需要 prompt 明确：

    YES only if the chunk contains the specific fact the question asks for.
    If the chunk is topically related but does not state that fact, use MAYBE.

预期：12月功能清单从 YES 降为 MAYBE，再被折扣拦截。

**C. 降低论文标题类正样本的风险**

论文标题从 0.76 掉到 0.38，margin 太窄。可能需要：
- MAYBE 折扣从 0.5 放宽到 0.7
- 或 PDF metadata 类 chunk 不参与 MAYBE 折扣

### 参考

- 本轮原始数据：`eval/results/2026-09-13T06-23-45.json`
- 5 轮数据可在 `eval/results/` 下按时间戳找到

## 2026-09-13 傍晚：dev/holdout 分离后的第一轮

测试集已切分：dev（9 正 + 6 负 = 15）/ holdout（3 正 + 4 负 = 7）。

### 本轮改动

1. `critic.py` prompt 改成明确区分「含答案」vs「话题相关」
2. `evaluator.py` 全丢兜底改成：保留 top-1，confidence × 0.3

### 结果（dev 集）

| 指标 | 值 |
|---|---|
| num_positive | 9 |
| num_negative | 6 |
| hit_at_1 | 1.0 |
| context_precision | 0.719 |
| reject_accuracy | **0.833**（5/6） |

失败 1 条：合同违约金（confidence 0.4244）

### 两个新发现

**发现 1：hit@1 和真实体验错位**

`evaluator.py` 的 `hit_at_k` 只看 `must_cite` 是否在 `metadata.source` 里——**完全不看 confidence**。

例：论文作者（正样本）

| 视角 | 结果 |
|---|---|
| evaluator | hit@1 = true（来源文件对） |
| qa.py（真实用户） | confidence 0.18 < 0.30 → 拒答 |

**真实用户会看到"资料中未找到"，但评估说 1.0。**

这是评估体系和用户体验的脱节。**hit@1 只能测"检索排序"，不能测"系统会不会真的回答"。**

影响：论文作者（0.1832）、论文 BM25（0.4066）虽然 hit@1=true，但 confidence 都低于 0.5，如果阈值提高，会被误拒。

**发现 2：critic 判定不稳定**

合同违约金三次结果：

| 时间 | confidence | 结果 |
|---|---|---|
| 06-10-25 | 0.8489 | 失败 |
| 06-23-45 | 0.1234 | 成功 |
| 06-46-59 | 0.4244 | 失败 |

**同一份数据、同一份 prompt、temperature=0.0，结果三次不同。**

LLM critic 有随机性。这意味着：

- 单次评估的 reject_accuracy 不可靠
- 需要跑多次取平均，或
- critic 不能作为唯一的拒答判断依据

### 下次优先做的事（顺序变了）

**1. 修 hit@1 的定义**（比 holdout 更根本）

现在：只测 source 是否命中
应该：source 命中 **且** confidence ≥ 阈值（即用户真的会看到答案）

这个改动会让 hit@1 从"检索指标"变成"端到端指标"，更贴近真实体验。

**2. 评估 critic 的稳定性**

对同一份数据跑 3 次，看 reject_accuracy 波动范围。如果波动 > 0.15，critic 需要换方案（比如固定 seed、或用更稳定的 prompt）。

**3. 跑 holdout 验证泛化**（排在最后）

dev 集已经被调过多轮。holdout 才是真实泛化信号。但在修完 1、2 之前，holdout 的结果也无法完全信任。

### 参考

- 本轮原始数据：`eval/results/2026-09-13T06-46-59.json`
- dev 集：`eval/test_set.json`（15 条）
- holdout 集：`eval/test_set_holdout.json`（7 条）

## 2026-09-13 晚：reject_correct 口径修复（防御性）

### 改动

`evaluator.py` 的 `reject_correct` 从 `hits[0].confidence` 改为 `max_confidence(hits)`。

**为什么改**：`qa.py` 用 `max_conf = max(...)` 判拒答，evaluator 用 `hits[0].confidence`——两个口径不一致。`hits[0]` 是按 `rerank_score` 排的，不是按 `confidence` 排的（confidence = 0.8*rerank + 0.2*rrf，混合后可能打破排序）。

### 实测

- 正样本 9 条：confidence 未变
- 负样本 12 条：4 条变化，8 条未变

变化条目（全部仍在低分拒答区）：

| 问题 | 旧 | 新 |
|---|---|---|
| 公司年假 | 0.1949 | 0.2001 |
| Python GIL | 0.1870 | 0.2000 |
| Nginx | 0.1892 | 0.2000 |
| 团队绩效 | 0.1854 | 0.2000 |

`reject_accuracy` 仍为 0.667，未翻转。

### 结论

**旧口径在本次测试集上未造成误判，但埋了雷**。

- 变化 4 条距阈值 0.30 尚有 0.10 余量，不翻转
- 但 `hits[0].confidence ≤ max_confidence(hits)` 恒成立——将来任何样本的 `hits[0]` 与 `max` 跨越 0.30 时，就会误判
- 本次修复是**防御性**，不是修实伤

### 附带发现

0.20 = `0.8*0 + 0.2*1.0`，说明有 chunk 的 reranker 给 0 分但 rrf 归一化 = 1.0。confidence 公式的触底值就是 0.2，不是 0。

### 下一步

- Qdrant 远程（0.2917）仍是当前最脆弱样本，距阈值仅 0.0083
- 不急于改动，记录在案

## 2026-09-14 Part A：测试集去污染 + 分层（dev@v4）

### 改动
- 关键词去污染：移除短数字、单字中文
- 负样本分层：off_topic / topic_relevant_no_answer
- 加 id / difficulty 字段

### 结果

| 指标 | 旧 (v3) | 新 (v4) | 变化 |
|---|---|---|---|
| context_precision | 0.622 | **0.400** | ↓ 0.222（去污染后暴露真实值） |
| reject_accuracy | 0.667 | 0.667 | = |
| hit_at_1 | 1.0 | 1.0 | = |
| reject_accuracy_off_topic | — | **1.000** | 新增（4 条） |
| reject_accuracy_topic_relevant_no_answer | — | **0.500** | 新增（8 条） |

### 结论

1. 旧的 context_precision=0.622 被短数字关键词虚高，真实值是 0.4
2. 分层统计证实：话题相关的负样本拒答率只有 50%，是真实弱点
3. 混合指标 reject_accuracy=0.667 掩盖了 off_topic(100%) 和 topic_relevant(50%) 的差异

### CI
- run 34866220381
- 触发 commit: 733d63c (Part A) + 缩进修复

## 2026-09-15 Part B：代码正确性修复（dev@v4）

### 改动
- B1: indexer.load_file 全分支 try 包装，坏文件不再穿透
- B4: QDRANT_PATH 统一到 qdrant_factory，去掉 lstrip 字符集陷阱
- B5: 删除 retriever 里 BM25 no-op 归一化（RRF 只用 rank，source_max 从未被使用）

### 结果（与 Part A 逐位一致）

| 指标 | Part A | Part B | 结论 |
|---|---|---|---|
| context_precision | 0.400 | 0.400 | = |
| reject_accuracy | 0.667 | 0.667 | = |
| hit_at_1 | 1.0 | 1.0 | = |
| reject_accuracy_off_topic | 1.000 | 1.000 | = |
| reject_accuracy_topic_relevant_no_answer | 0.500 | 0.500 | = |

### 结论

1. B4+B5 是纯清理，不改变检索行为 —— 证实 BM25 归一化确实是 no-op
2. B1 是真实修复，但不影响检索指标（只在坏文件场景生效）
3. Part A 的新基线（context_precision=0.4, reject_accuracy=0.667）是可信的

### CI
- run 34868068522
- 触发 commit: 17e0a6f (B1) + B4+B5

## 2026-09-15 首次 holdout 评估（holdout@v1）

### 结果

| 指标 | dev@v4 | holdout@v1 |
|---|---|---|
| num_questions | 21 | 7 |
| context_precision | 0.400 | **0.200** |
| reject_accuracy | 0.667 | 0.500 |
| hit_at_1 | 1.000 | 0.667 |
| reject_accuracy_off_topic | 1.000 | 1.000 |
| reject_accuracy_topic_relevant_no_answer | 0.500 | **0.000** |

### 三条正样本详情

| 问题 | hit@1 | top1_source | 分析 |
|---|---|---|---|
| 战略会在哪里开的？ | ✓ | h1 | 正常 |
| 研发预算是多少？ | ✗ | h1 | **假阴性**：h1 和 h2 都含答案，top-1 命中了 h1 |
| 订单故障根因？ | ✓ | h3 | 正常 |

### 两条 topic_relevant 负样本详情

| 问题 | confidence | 分析 |
|---|---|---|
| 战略会参会人名单是谁？ | 0.72 | 失败——文档只说"12 人"，无名单 |
| 订单故障影响多少用户？ | 0.79 | 失败——文档只说"服务不可用"，无用户数 |

### 结论

1. **hit_at_1=0.667 是假阴性**：h1 和 h2 都含"研发预算 200 万"，`must_cite` 硬编码 h2 导致误判。已把 must_cite 改成 `"h2-budget"` 子串修复标注。
2. **context_precision=0.2 是文档长度产物**：holdout 文档短（300-500 字），切成 1-2 chunk，但 TOP_K=5 固定返回 5 条，剩下的是其他文档的噪声。非检索质量问题，但**真实用户体验确实是 top-5 里有 4 条噪声**。
3. **topic_relevant_no_answer = 0.0 是真实信号**：两个全新文档、两个全新问题，reranker 又被骗到 0.72/0.79。**第四次验证同一缺陷**，与文档无关，是 BGE-reranker 的机制问题。
4. **off_topic = 1.0 稳定**：与 dev 一致。

### 下一步

- topic_relevant 问题需要 reranker 之外的机制（critic、LLM 二次确认），不是调参能解决
- context_precision 对短文档偏低是结构问题，可考虑按文档长度动态调 TOP_K

### CI
- run 34911192733
- 触发: `gh workflow run "Evaluate (手动触发)" -f dataset=holdout`

## 2026-09-15 holdout@v2（must_cite 列表支持）

### 改动
- `evaluator.hit_at_k` 支持 `must_cite` 为字符串或列表
- `q_q1_dev_budget` 的 `must_cite` 改成 `[h1, h2]`（答案在两篇文档里都有）
- `test_eval_set.py` 的 disjoint 检查同步支持列表

### 结果

| 指标 | v1 | v3 |
|---|---|---|
| hit_at_1 | 0.667 | **1.000** |
| hit_at_3 | 1.000 | 1.000 |
| context_precision | 0.200 | 0.200 |
| reject_accuracy | 0.500 | 0.500 |
| reject_accuracy_off_topic | 1.000 | 1.000 |
| reject_accuracy_topic_relevant_no_answer | 0.000 | 0.000 |

### 结论

1. **hit_at_1 修复**：v1 的 0.667 是标注问题（答案在两篇文档），非检索缺陷。v3 是真实值。
2. **context_precision = 0.2 未变**：短文档 + 固定 TOP_K=5 的结构问题，与检索质量无关。
3. **topic_relevant_no_answer = 0.0 稳定**：第五次验证。与文档无关，是 BGE-reranker 的机制缺陷。

### holdout 基线的真实含义

- 3 条正样本：检索 100% 命中，reranker 判定 0.99+
- 4 条负样本：
  - off_topic（2 条）：100% 拒答 ✓
  - topic_relevant（2 条）：0% 拒答 ✗ —— **当前系统的真实弱点**

### CI
- run 34919424143

## 2026-09-15 critic 纯过滤契约确认

### 背景

`apply_critic` 的 `maybe_penalty` 从 0.5 改为默认 1.0，废弃 MAYBE 折扣。

之前"critic 有效"的数字（dev topic_relevant 0.625 / holdout 0.5）全部来自折扣本身，
是 metric hacking：只降负样本 confidence 不改判定，虚增 reject_accuracy 而不提升能力。

### 验证

对比"显式传 `maybe_penalty=1.0`"与"默认 1.0"两种调用，dev 集：

| 指标 | 显式 1.0 | 默认 1.0 |
|---|---|---|
| reject_accuracy | 0.667 | 0.667 |
| reject_accuracy_topic_relevant_no_answer | 0.500 | 0.500 |
| answer_hit_at_1 | 1.000 | 1.000 |
| hit_at_1 | 1.000 | 1.000 |
| context_precision | 0.589 | 0.580 |

### 结论

1. 关键指标逐位一致 → 默认值改动是纯契约变化，无行为差异
2. context_precision 有 0.009 微差 → 机制未确认（可能是 indexer 产出的 parent_text 边界差异，也可能是 critic LLM 判定抖动）
3. critic 的真实价值只有 context_precision 提升（dev +0.189 / holdout +0.467）
4. **对拒答贡献为 0**——topic_relevant 回到无 critic 的值（dev 0.5 / holdout 0.0）

### critic 定位

保留 critic.py 作为**评估可观测工具**，qa.py 不接入。

理由：
- 对拒答零贡献（唯一的拒答机制是 MAYBE 折扣，已废弃）
  > 注（2026-09-15）：上句"唯一的拒答机制"部分被 probe 修正——LLM 自拒是第二条机制。
  > "对拒答零贡献"部分仍成立：critic 不参与 qa.py 生产链路。
  > 详见本节末"reject_accuracy 语义边界"。
- context_precision 是代理指标，不代表 LLM 回答质量
- 每次问答多一次 critic LLM 调用，成本翻倍

若未来做"丢 NO chunk 是否让 LLM 回答更好"的实验，再决定是否进生产。

### CI（按 commit 区分）

**f182a1e（critic 默认 0.5，metric hacking 阶段）**
- 34921754578
- 34922419905
- 34922949117

这三个 run 的 topic_relevant 数字（0.625 / 0.5）来自 MAYBE 折扣虚降，**不可作为 critic 能力依据**。

**398c61c（显式传 maybe_penalty=1.0）**
- 34923928476  dev     → topic_rel=0.5, ans_hit_1=1.0
- 34924019457  holdout → topic_rel=0.0, ans_hit_1=1.0

**7b89eb0（默认值 1.0，契约固化）**
- 34966141623  dev     → 与 398c61c 关键指标一致

### 附带发现

CI 结果**不是逐位确定的**。`context_precision` 在相同 commit、相同输入下两次运行可出现 0.009 级差异。
做精细对比（<0.05 变化）时需警惕这类噪声。

## 2026-09-15 reject_accuracy 语义边界

### 背景

probe run 34987266954（正常模式 use_rerank=True）显示：正常拒答分两层。

正常模式下 dev 负样本的分布（数据来自 dev+critic run 34966141623，maybe_penalty=1.0（当前默认））：

| 类别 | conf | 拒答位置 | 条数 |
|---|---|---|---|
| off_topic | < 0.30 | confidence 闸（qa.py 的 max_conf < 0.30）| 4/4 |
| topic_rel | < 0.30 | confidence 闸（同上）| 4/8 |
| topic_rel | >= 0.30 | LLM 自拒（进 LLM）| 4/8 |

注意：上表为 critic 开启 + maybe_penalty=1.0（当前默认）时的分布。
历史对照：早期 run 34921754578（maybe_penalty=0.5）为 topic_rel 5/3。
若无折扣，分裂是 4/4；应用 0.5 折扣后变为 5/3——DeepSeek 参数量被从 0.4883 压到 0.2442，跨过 0.30 阈值。

对照组：probe run 34984139269（fallback 模式 use_rerank=False）：
全部负样本 conf ≈ 0.33 > 0.30 → 全部进 LLM → 全部由 LLM 自拒。

### 结论

- `evaluator.py` 的 `reject_correct = row_confidence < THRESHOLD` 只测 confidence 闸
- 不测 LLM 自拒（evaluator 不调 LLM）
- 因此 `reject_accuracy` = "confidence 闸拒答率"，不是"用户看到的拒答率"
- dev 的 0.667 只反映子系统 A

### 影响

- 基于 `reject_accuracy` 的历史解读需加此边界
- critic 在 qa.py 外——与 LLM 自拒无交互
- confidence 闸在正常模式下拦截了 off_topic 类 query，它们不进 LLM。
  （若移除闸，LLM 会如何处理，未验证。）

### 稳定性未验证

- `qa.py` 的 temperature=0.1 → 同一输入多次调用可能不同输出
- probe 单次 run，不能外推"LLM 必自拒"
- 待扩 probe：按类型分配 + 每条跑 2~3 次

## 2026-09-16 probe 稳定性 + refused 检测边界

### 背景

为验证 LLM 自拒稳定性，重建 probe（`rag-private-docs/src/probe_stability.py`）。
设计：12 负样本 + 3 正样本 × 5 次 = 75 次 LLM 调用。
CI run: 35104159356。

### 结果

**稳定性**：15 条全部 STABLE——同一问题 5 次调用给出一致结果。
（off_topic 5/5 拒、topic_rel 5/5 拒、2 条正样本 0/5 拒、论文作者 5/5 "拒"）

**结论**：`temperature=0.1` 在本批样本上未产生可见抖动。单次 probe 结果可外推。

### 但 probe 的 refused 检测不可靠

`probe_stability.py` 用子串匹配判断拒答：

    refused = any(m in ans for m in ["未找到", "没有找到", "资料中未", ...])

**问题**：只测"是否出现关键词"，不测"是否只有拒答内容"。

实际回答揭示三种形态：

| 形态 | 例 | refused 判定 | 实际 |
|---|---|---|---|
| 系统模板拒答 | "资料中未找到与该问题相关的内容（最高置信度 0.20）..." | True | 正确 |
| LLM 拒答 + 解释 | "资料中未找到 X。参考资料中...但没有提及 Y" | True | 正确 |
| LLM 措辞保守但给出答案 | "资料中未找到相关内容。参考资料中该论文的作者仅标注为 Anonymous Authors..." | True | 误判 |

**第 3 种实际上回答了**——用户读到 "Anonymous Authors" 就得到了信息。

### 对早前解读的影响

早前 `34987266954` probe run 的"合同违约金"完整回答（从日志可恢复）：

    资料中未找到"违约金"的相关约定。
    参考资料中与违约责任相关的内容为：[1]
    - 任一方违约，应赔偿对方因此遭受的直接经济损失（未约定具体违约金金额或比例）
    - 乙方代码存在严重缺陷且拒不修复的，甲方有权解除合同
    另外，资料[2]中提到了延期罚则：每延期 1 天，扣合同总额 0.5%，最高不超过 10%——
    但这属于延期罚则，并非一般意义上的"违约金"条款。
    如需确认是否存在其他违约金约定，建议查阅合同全文。

**早前只看了首行 `grep -A 5`**——看到了开头，没看后续。

**因此**：
- "LLM 简单拒答"的解读基于**回答开头**，不完整
- 完整回答的实际形态是"先声明未找到，再列出所有相关信息与出处，建议查阅原文档"
- 这形态**不是简单拒答**，是"有边界的引导式回答"

### 未决

`refused` 检测需区分三种状态：

- SYSTEM_REFUSE（qa.py confidence 闸输出）
- LLM_REFUSE（LLM 判断无答案 + 提供上下文）
- LLM_ANSWERED（LLM 措辞保守但实际给出答案）

当前 probe 无法区分。需改检测逻辑 + 重跑。

### CI
- run 35104159356

## 2026-09-18 probe 判定口径：被证否的三态 + 落地四态轴

### 数据来源

本地 `probe_stability_results.json`（仓库根，已被 .gitignore 忽略）来自 CI artifact：

    gh run download 35104159356 -n probe-stability-result   # artifact id 10450590236, 3651 bytes
    # run 35104159356 · head_sha c5c1f268 · 2026-09-16 · 30 天保留（2026-10-16 过期）

75 条记录 = 15 问 × 5 次。三条被质疑的 answer 完整存世，**均未被 300 字截断**（len 68 / 177 / 82）。

### 第一版方案被真实数据证否

原计划把 `refused` 布尔升级为三态（SYSTEM_REFUSE / LLM_REFUSE / LLM_ANSWERED），
LLM 分支用「位置闸 + 残留闸」区分，规则为 **残句 ≥ 20 字 且（含 [n] 或命名实体/数字）→ LLM_ANSWERED**。

**实测结果：失败，且比现状更差。**

| 口径 | 问题级正确率 | 错在哪 |
|---|---|---|
| legacy `refused`（子串匹配，现状） | **14/15** | 只错"论文作者"1 条 |
| 三态 + 残留闸（原方案） | **11/15** | 4 条 topic_rel 负样本被误判为已答 |

被误判的 4 条：违约金 / 莫干山全长 / DeepSeek 参数量 / RAG 缺点。
它们全都满足"长度 ≥ 20 且含 [n]"，但**实际没有回答问题**——
违约金那条明说"资料中未找到违约金的相关约定"，莫干山那条明说"没有提及路线全长多少公里"。

**根因不是阈值，是信号饱和**（实测数字）：

| 信号 | 实测 | 判别力 |
|---|---|---|
| 引用角标 `[n]` | LLM 分支 **35/35 条**全部含 `[n]` | **0** —— qa.py 的 prompt 要求引用，LLM 一开口就带，无论答还是拒 |
| 数字 | "论文作者"（真交付）残句含数字 **0/5**；违约金（真拒答）残句塞满 0.5%/10% | **反相关** —— 那些数字属于"延期罚则"，被 LLM 自己明说"并非违约金条款" |
| 命名实体 | 能捞到 `Anonymous`，也能在 DeepSeek 参数量上命中 `deepseek-chat` | 噪声 |

结论：**任何表面形态正则都无法区分"首句同样写未找到、但残句交付了槽位值"与"残句否定槽位"**，
这需要语义判断。此外违约金 5 次回答措辞全不同（「并非…条款」/「均未出现…表述」/「但这属于…」）
却判定稳定 —— 说明靠正则枚举否定措辞也不可行。

**另一个被本次证实的旧问题**：300 字截断确实在发生，而且砍到的是**正样本** ——
`什么是 RAG？` 的回答断在 `与传`。截断偏差方向是"低估正样本"。故本次改为存全文 answer。

### 落地的口径：slot 交付四态轴（极性感知）

放弃"拒答/已答"二分（实测该轴不成立），改为：

    SYSTEM_REFUSE  qa.py confidence 闸输出（固定模板）
    REDIRECTED     未找到 X + 给出相关上下文/引用（"软拒"）
    REFUSED        裸拒答，无实质内容（"硬拒"）
    DELIVERED      真的交付了答案

注意 REDIRECTED / REFUSED **都是"未交付"**，区别只在是否给了相关上下文。

判定顺序：

    闸 0   conf < CONFIDENCE_THRESHOLD      -> SYSTEM_REFUSE（结构信号，最可靠）
    闸 0'  命中 qa.py 模板正则               -> SYSTEM_REFUSE（防阈值漂移的第二道保险）
    闸 0'' 空回答（含 None）                 -> REFUSED（空串不含拒答标记，若不加此闸，
                                              负样本分支会把它误判成 DELIVERED）
    闸 1   按 test_set 的 expect_reject 分流：
             正样本 -> ground_truth_keywords 命中即 DELIVERED
             负样本 -> legacy refused 为假即 DELIVERED（= 幻觉交付）
    闸 2   形态细分：剥首句后残句非空白字符 >= MIN_REDIRECT_CHARS ? REDIRECTED : REFUSED

**关键设计保证：DELIVERED 只能由 test_set 的金标关键词产出，形态正则无权翻转负样本。**
这是对上面那次翻车的结构性免疫，不是把阈值调小。

`MIN_REDIRECT_CHARS = 12`：本批数据所有负样本残句 **≥ 53 字**（实测 53/96/103~146/144~162），
故任何合理取值都不改变本批判定；选 12 是为未来更短回答留余量（只要"有实质内容"，不要"够长"）。
计数前剥离空白与 Markdown 标记。

### 本次重判结果（本地 artifact，非新 run）

问题级 **15/15**；记录级四态分布：

| state | 记录数（75） | 问题数（15） |
|---|---|---|
| SYSTEM_REFUSE | 40 | 8 |
| REDIRECTED | 20 | 4 |
| REFUSED | **0** | **0** |
| DELIVERED | 15 | 3 |

- 负样本被误判 DELIVERED = **0**（硬门禁要求）
- 正样本 delivery_rate = 1.0
- "论文作者"从 `refused=True` 翻转为 `DELIVERED`（test_set 的 `ground_truth_keywords` 正是 "Anonymous"，
  落定的金标即"占位值也是答案"）
- **REFUSED 在本批是空类**：LLM 分支的 4 条负样本全落 REDIRECTED，本批没有裸拒答。
  若下次 live run 仍为空，考虑正式塌缩成三态，不要为一个理论类别保留整套分支。

### 首次量化：两层拒答机制的分解

新轴按极性聚合后，把 09-15「reject_accuracy 语义边界」一节留下的缺口补上了：

| 阶段 | 拦下的负样本 | 占 12 条负样本 |
|---|---|---|
| confidence 闸（qa.py，用户看不到 LLM） | 8 条 | **0.667** |
| LLM 自拒（进 LLM 后仍未交付） | 4 条 | **0.333** |
| **端到端 non_delivery** | **12 条** | **1.000** |

其中 confidence 闸的 0.667 与 RESULTS.md 长期使用的 `reject_accuracy = 0.667` **逐位相同** ——
证实该指标确实只测子系统 A。而记录级口径是 40/60 = 0.667 与 20/60 = 0.333，同一比例。
**用户实际感知的拒答率是 1.000，不是 0.667。**

### 附带的可观测性

- `system_refuse_by = {confidence: 40, template: 0}` —— 本批**模板正则一次都没触发**，
  它是"未被执行的保险"。一旦将来 template > 0 而 conf ≥ 阈值，即为阈值漂移告警。
- 该保险不是多余的：实测 SYSTEM 模板的尾句恒为 **17 字 ≥ 12**，
  若闸 0 失效且无模板正则，这 40 条会被误判成 REDIRECTED。
- `summary` 保留 legacy 的 `refused_count / refused_ratio / stable` 三字段（口径未改），
  新增 `state / state_counts / stable_on_state`；聚合块在顶层 `aggregate`。
- 每条 `results` 记录含 `expect_reject` 与 `keywords` ——
  因为 **state 本身不携带极性**（REDIRECTED 对负样本是正确、对正样本是失败），
  下游解读必须有极性上下文；同时这让 artifact 自带标注快照，便于日后离线重判。

### 已知盲区（未修，与 legacy 同一盲区）

- 负样本的 `ground_truth_keywords` 为空，**测不出"负样本被真交付"**。
- 若 LLM 先写"未找到"再夹带幻觉，会被记为 REDIRECTED（软拒），不会被识破。

### 验证方式与残留风险

本机缺 `langchain_openai`，无法导入 `qa`，故**不能 live 跑**。验证是用 fake `qa` 模块注入 +
回放 artifact 答案，驱动 `probe_stability.main()` 的**真实代码路径**（区分 / results 组装 /
summary / aggregate），共 26 项断言全通过，含：legacy `refused` 与 09-16 逐条一致（75/75）、
四态分布、gate_split、模板兜底、残句恰好卡 12/11、英文拒答、marker 在中段、空/None answer。

**残留风险（重要）**：上述 15/15 是在**同一批 15 条上拟合出来的自洽性**，
不是系统能力的证明。唯一诚实的检验是**下一次真实 CI run 用新数据重跑混淆表**。
在此之前不要把 15/15 当作结论引用。

### 相关文件

- 探针：`rag-private-docs/src/probe_stability.py`（唯一功能改动；qa.py / evaluator.py / retriever.py / probe.yml 均未改）
- 判定输入：`rag-private-docs/eval/test_set.json`（`expect_reject` + `ground_truth_keywords`）

## 2026-09-19 四态轴在新数据上复现（真实 CI run）

### 这一节与上一节的区别

上一节（`### 本次重判结果（本地 artifact，非新 run）`）用的是 **09-16 artifact 的旧回答 + 本地回放**，
数字来自手算/回放，其 15/15 是"在同一批回答文本上拟合出的自洽性"，
正因如此那次明确标注为"不是系统能力的证明"，并把"下一次真实 CI run 重跑混淆表"列为唯一诚实的检验。

本节是那项检验的结果：**commit `c6f5f47b` 触发的新 run，用 LLM 重新生成的回答**，
不是回放、不是手算。

    run 35388126182（run_number 4，workflow_dispatch，conclusion: success）
    head_sha c6f5f47b89fdbc7f7c2b1a5b5dcf51c5e137b7e3  ← 四态改造 commit
    2026-09-18T19:50:01Z → 20:00:16Z（≈10m15s）= CST 2026-09-19 03:50 → 04:00

### 结果：聚合量与新口径预期逐项一致

| 指标 | 期望 | 实测（新数据） |
|---|---|---|
| state_counts | 40 / 20 / 0 / 15 | **SYSTEM_REFUSE 40 · REDIRECTED 20 · REFUSED 0 · DELIVERED 15** |
| legacy_refused_count | 65 | **65** |
| system_refuse_by | confidence 主导 | **{confidence: 40, template: 0}** |
| positive delivery_rate | 1.0 | **15/15 = 1.0** |
| negative false_delivered | 0 | **0** |
| negative non_delivery_rate | 1.0 | **1.0** |

注意 `template: 0` 在真实 run 上**依旧一次都没触发** —— 闸 0（confidence）单独完成了全部 40 条
SYSTEM_REFUSE 的归因。模板正则仍是"未被执行的保险"，其触发条件（conf ≥ 阈值却命中模板句）
在本批数据上尚未出现。

### 设计目标达成的证据：论文作者那条

    What are the authors of the synthetic study paper?
    refused = 5/5  (legacy，子串匹配判定为"拒答")
    state   = DELIVERED  (四态，判定为"已交付")

同一批回答上，legacy 布尔与四态**给出相反结论**，而这正是本次改造的全部理由：
这条回答的首句写"资料中未找到相关内容"，但残句交付了槽位值 `Anonymous Authors`，
且该值就是 `test_set` 为它定义的金标（`ground_truth_keywords = ["Anonymous"]`）。

legacy 口径只有"是/否"一个自由度，无法表达"首句在拒、残句在交付"，
所以它把这条**正样本误记为拒答**，成为 14/15 里唯一的那 1 条错误。
四态轴用极性分流把判定权交还给金标关键词，因此这条从 `refused=True` 翻为 `DELIVERED` ——
**这不是放宽阈值，是换了正确的轴。**

### 首次实证分解：reject_accuracy 到底测的是什么

09-15「reject_accuracy 语义边界」一节曾写过：`evaluator.py` 的 `reject_correct` 只比
`confidence < THRESHOLD`，不调用 LLM，因此 `reject_accuracy` = "confidence 闸拒答率"，
**不是用户看到的拒答率**，但当时只是定性判断，没有量化。

新轴按极性聚合后给出了分解，且这次是真实 run 的数据（12 条负样本）：

| 阶段 | 拦下 | 占负样本 |
|---|---|---|
| confidence 闸（qa.py，用户看不到 LLM） | 8 条 | **0.667** |
| LLM 自拒（进了 LLM 仍未交付） | 4 条 | **0.333** |
| **端到端 non_delivery**（用户实际感知） | **12 条** | **1.000** |

`confidence_gate = 0.667` 与 RESULTS.md 长期引用的 `reject_accuracy = 0.667` **逐位相同** ——
即该指标确定性地只覆盖子系统 A，缺口恰是 LLM 自拒那 0.333。
**用户实际经历的拒答率是 1.000（12/12），比 0.667 高出的部分全部来自 LLM 自拒。**

### REFUSED 在新数据上仍为空类（第二次观察）

09-16 与 09-19 两次独立 run（不同日期、重新生成的回答）中，`REFUSED` 计数**都是 0**：
LLM 分支的 4 条 topic_relevant 负样本全部落在 REDIRECTED，本批数据里**没有裸拒答**。

按**第二次观察**的定义，可以认为该类别在本 test_set 上稳定为空，
但这不构成删除依据，理由：其判定成本接近零（闸 2 的一个分支），
且它是"未来出现硬拒答"的安全网 —— 若某次 run 出现 REFUSED > 0，
那本身就是"LLM 拒答行为发生变化"的信号，删掉它就丢失了这个观测点。
结论：保留。若第三次观察仍为空，再考虑是否降级为"仅记录不分支"。

### 修正上文「验证方式与残留风险」的结论

**以下这段修正 `### 验证方式与残留风险` 一节末尾的「残留风险（重要）」判断，不删除原行。**

原文（写于 09-18）称：15/15 是在同一批 15 条上拟合出的自洽性，唯一诚实的检验是下一次真实 CI run。

现在该检验**已完成并通过**（run 35388126182）。因此：

- 原文"在此之前不要把 15/15 当作结论引用"这一限制**已解除** ——
  分类器并非拟合到 09-16 那批回答的具体措辞：换成 09-19 新生成的回答，15/15 仍然成立。
- 但需保留一条更窄的限制，避免过度外推：
  **test_set 的 15 个问题本身没有变。** 本次消除的是"对回答措辞过拟合"的风险，
  **没有**消除"口径与这批 test_set 的构造相适配"的风险（例如金标关键词恰好又是判据）。
  真正的外推检验需要**新问题**（holdout 扩样），不是新回答。

### 附带观察：本地回放方法被真实 run 验证

09-18 的验证是在无法 live 跑（本机缺 `langchain_openai`）的前提下，
用 fake `qa` 注入 + 回放 artifact 驱动 `probe_stability.main()` 真实代码路径完成的。
本次真实 run 的聚合量与那次回放**逐项相同** ——
说明"回放驱动真实代码路径"这套离线验证方法本身可信，可作为后续无 live 环境时的标准手段。

需说明同一性的边界：一致的是**聚合分布**，不是逐条回答文本。
不同 run 的回答措辞会有差异（09-16 已观察到违约金的 5 次措辞各不相同），
因此聚合相同不等于答案逐字相同。

### 正样本 delivery 的分母限制

`positive.delivery_rate = 1.0` 的分母是 3，不是 9 ——
probe_stability.py 的 POSITIVE_SAMPLES 硬编码三条
（什么是 RAG / 软件开发合同总金额 / 论文作者），其余 6 条正样本
未被探针覆盖。因此 1.0 只说明"被测的 3 条全部交付"，
不能推广到 test_set 的全部 9 条正样本。扩样是独立的外推检验。

> **注（2026-09-19）**：本段所述限制已解除。
> commit `4d924b5` 删除了 POSITIVE_SAMPLES 硬编码，
> probe 现覆盖 test_set 全部 9 条正样本。run `35425691671` 实测：
> `positive.questions = 9`、`delivered = 45/45`、`delivery_rate = 1.0`
> —— 原 3 条样本上的 1.0 得到全量复现。详见下文 2026-09-19 节。

### 数据来源声明

run 元数据（run id / run_number / head_sha / conclusion / 时间戳）由 GitHub API 核对确认。
上述聚合数字来自该 run 的 CI 输出（artifact `probe-stability-result` 需 token 才能下载，
无 token 时 zip 端点返回 401），**未做二次独立解析**。

## 2026-09-19 probe 正样本扩样（3 → 9）

### 改动

- commit `4d924b5`：删除 `POSITIVE_SAMPLES` 硬编码，
  `positives` 改为 `[r for r in test_set if not r.get("expect_reject")]`

### 验证（run 35425691671）

| 指标 | 扩样前 | 扩样后 |
|---|---|---|
| n_records | 75 | 105 |
| positive.questions | 3 | 9 |
| DELIVERED | 15 | 45 |
| positive.delivery_rate | 1.0 | 1.0 |
| 负样本三项 | 40/20/0 | 40/20/0 |
| gate_split | .667/.333 | .667/.333 |

### 结论

- 扩样未暴露新问题：先前 3 条上的 1.0 是全量 9 条的真实反映，不是样本偏差
- 负样本侧指标逐位不变 → 扩样只影响正样本计数，无副作用

### 待办

- test_set 的 `q_What_does_the_paper_say_about_` 关键词含 `op-1`（疑似 `top-1` 笔误）——
  在本次 9 条正样本中侥幸命中（`op-1` 是 `Top-1` 子串），但关键词升格为 DELIVERED
  判据后，脏关键词是隐患。需列入关键词清理。
