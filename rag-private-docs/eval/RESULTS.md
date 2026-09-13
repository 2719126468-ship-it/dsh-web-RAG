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
