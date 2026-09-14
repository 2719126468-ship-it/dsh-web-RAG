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
