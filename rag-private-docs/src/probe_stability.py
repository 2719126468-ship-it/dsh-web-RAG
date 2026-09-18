"""Probe: LLM 自拒稳定性测试。

对每条负样本重复 N 次，看是否一致。
正样本作为对照（应稳定回答）。
输出 JSON 到当前目录。

=== 判定口径：slot 交付四态轴（2026-09-18 起）===

本探针原先只输出 `refused` 布尔（子串匹配）。实测证明该口径无法区分三种形态：

    SYSTEM_REFUSE  qa.py confidence 闸输出（固定模板）
    REDIRECTED     未找到 X + 给出相关上下文/引用（"软拒"）
    REFUSED        裸拒答，无实质内容（"硬拒"）
    DELIVERED      真的交付了答案

注意 REDIRECTED / REFUSED 都是"未交付"，区别只在是否给了相关上下文。
判定机制是**极性感知**的，顺序如下：

    闸 0  conf < CONFIDENCE_THRESHOLD        -> SYSTEM_REFUSE（结构信号，最可靠）
    闸 0' 命中 qa.py 模板正则                 -> SYSTEM_REFUSE（防阈值漂移的第二道保险）
    闸 1  按 test_set 的 expect_reject 分流：
             正样本 -> ground_truth_keywords 命中即 DELIVERED
             负样本 -> legacy refused 为假即 DELIVERED（= 幻觉交付）
    闸 2  形态细分（只决定软拒/硬拒，不决定成败）：
             剥首句后残句非空白字符 >= MIN_REDIRECT_CHARS ? REDIRECTED : REFUSED

=== 为什么 DELIVERED 只能由金标关键词产出 ===

上一版尝试过"长度 >= 20 且（含 [n] 或命名实体/数字）"的纯形态判定，被真实数据证否：
4 条 topic_relevant 负样本（违约金/莫干山/DeepSeek 参数量/RAG 缺点）被误判为已答，
全量正确率从 legacy refused 的 14/15 退步到 11/15。根因是信号饱和，不是阈值：

    [n]      在 LLM 分支 35/35 条中全部出现 —— qa.py 的 prompt 要求引用，
             LLM 一开口就带 [n]，无论它是在答还是在拒。判别力 = 0。
    数字     与正确标签反相关：论文作者（真交付）残句里没有数字；
             违约金（真拒答）残句里塞满 0.5%/10%，而那是"延期罚则"的数字，
             被 LLM 自己明说"并非违约金条款"。数字在这里是拒答信号。
    实体     噪声：能捞到 Anonymous，也会在 DeepSeek 参数量上命中 deepseek-chat。

结论：任何表面形态正则都无法区分"首句同样写未找到、但残句交付了槽位值"与
"残句否定槽位"，这需要语义判断。因此本版把 DELIVERED 的判定权收归 test_set 的
ground_truth_keywords —— 形态正则**没有权限**翻转负样本，这是对上次翻车的结构性免疫。

已知盲区（未修）：负样本的 ground_truth_keywords 为空，因此测不出"负样本被真交付"；
若 LLM 先写"未找到"再夹带幻觉，会被记为 REDIRECTED。与 legacy 口径同一盲区，未恶化。
"""
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from qa import CONFIDENCE_THRESHOLD, RAGEngine

RUNS = 5

# legacy 口径：子串匹配。**本行逻辑一字未改**，用于与 09-16 run 逐位对比。
# 新口径已证明它在本批 15 条上是最优基线（14/15，唯一假阳性是"论文作者"）。
REFUSE_MARKERS = ["未找到", "没有找到", "资料中未", "无法回答", "not found", "No relevant", "无法从"]

# --- 四态判定用常量 ---------------------------------------------------------
# qa.py 的固定模板（含全角括号的「最高置信度 X.XX」是 SYSTEM 模板独有标记，
# LLM 自答时只会说"资料中未找到相关内容"，无括号无置信度，故两条正则天然互斥）。
SYSTEM_REFUSE_RE = re.compile(r"^\s*资料中未找到与该问题相关的内容（最高置信度\s*\d+\.\d{2}）")
EMPTY_KB_RE = re.compile(r"^\s*知识库为空")

# 位置闸：只认定"出现在开头"的拒答首句。marker 出现在文本中段（例如合法答案里
# 夹一句"但这属于延期罚则"）不会被当作拒答首句剥掉。
LEAD_REFUSE_RE = re.compile(
    r"^\s*(资料中未找到[^。]*。|未找到[^。]*。|没有找到[^。]*。"
    r"|无法回答[^。]*。|无法从[^。]*。|not found[^.]*\.)",
    re.I,
)

# 残句长度阈值。本批数据所有残句 >= 40 字（实测 topic_rel 为 53~162，
# SYSTEM 模板尾句为 17），故任何合理取值都不改变本批判定结果；
# 选 12 是为未来更短的回答留余量（只需要"有实质内容"而非"够长"）。
# 计数前会剥离空白与 Markdown 标记，避免 **加粗** / 列表符号污染长度。
MIN_REDIRECT_CHARS = 12

_MD_NOISE = re.compile(r"[*_`#>\[\]()\-•·\s]+")

# 四态枚举顺序（用于输出与预置零值；顺序即"从最硬的拒答到真正的交付"）
STATE_NAMES = ("SYSTEM_REFUSE", "REDIRECTED", "REFUSED", "DELIVERED")

# 正样本对照（与旧版一致）
POSITIVE_SAMPLES = [
    "什么是 RAG？",
    "软件开发合同的总金额是多少？",
    "What are the authors of the synthetic study paper?",
]


def _strip_lead_refusal(answer: str):
    """剥离开头的拒答首句。返回 (是否命中, 残句)。未命中则残句 = 原文。"""
    m = LEAD_REFUSE_RE.match(answer or "")
    if not m:
        return False, (answer or "")
    return True, (answer or "")[m.end():]


def _residual_has_substance(residual: str) -> bool:
    """残句剥掉空白与 Markdown 标记后，非空白字符数是否达到阈值。"""
    return len(_MD_NOISE.sub("", residual or "")) >= MIN_REDIRECT_CHARS


def classify_state(
    answer: str,
    confidence: float,
    expect_reject: bool,
    keywords,
    threshold: float = CONFIDENCE_THRESHOLD,
) -> str:
    """把一次回答判为四态之一：SYSTEM_REFUSE / REDIRECTED / REFUSED / DELIVERED。

    纯函数、无副作用，可对历史 artifact 离线回放（重判不依赖任何网络调用）。

    注意 state 本身**不携带极性**：REDIRECTED 对负样本是正确行为，对正样本是失败。
    因此每条 results 都同时写入 expect_reject 与 keywords，供下游解读。
    """
    ans = answer or ""

    # 闸 0：结构化信号，最可靠，不依赖文本形态
    if confidence < threshold:
        return "SYSTEM_REFUSE"
    # 闸 0'：模板兜底。实测本批 8 条模板拒答的残句长度为 17 字（>= MIN_REDIRECT_CHARS），
    # 若闸 0 因阈值漂移失效且无此行，它们会被误判成 REDIRECTED。此正则即为此而设。
    if EMPTY_KB_RE.match(ans) or SYSTEM_REFUSE_RE.match(ans):
        return "SYSTEM_REFUSE"
    # 空回答（含 None）：既非模板拒答，也不是交付。必须显式判 REFUSED，否则
    # 负样本分支的 "没有任何拒答标记" 会把空串当成 DELIVERED ——
    # 空串的正确含义是"什么都没给"，不是"给了答案"。
    if not ans.strip():
        return "REFUSED"

    # 闸 1：按极性分流。DELIVERED 只能由金标关键词（正样本）或"无任何拒答标记"（负样本）产出。
    if not expect_reject:
        low = ans.lower()
        if any(k and k.lower() in low for k in (keywords or [])):
            return "DELIVERED"
    else:
        if not any(m in ans for m in REFUSE_MARKERS):
            return "DELIVERED"

    # 闸 2：形态细分，只区分软拒与硬拒，不翻转成败
    _matched, residual = _strip_lead_refusal(ans)
    return "REDIRECTED" if _residual_has_substance(residual) else "REFUSED"


def main():
    test_set_path = Path(__file__).resolve().parent.parent / "eval" / "test_set.json"
    test_set = json.loads(test_set_path.read_text(encoding="utf-8"))

    # 每条 probe 携带 expect_reject 与 ground_truth_keywords：
    # state 不携带极性，下游必须有这两个字段才能正确解读 REDIRECTED / DELIVERED。
    negatives = [
        (r["question"], r.get("negative_type", "negative"), True,
         list(r.get("ground_truth_keywords") or []))
        for r in test_set if r.get("expect_reject")
    ]
    positives = [
        (r["question"], "positive", False, list(r.get("ground_truth_keywords") or []))
        for r in test_set
        if not r.get("expect_reject") and r["question"] in POSITIVE_SAMPLES
    ]

    probes = negatives + positives
    print(f"=== probe stability: {len(probes)} questions x {RUNS} runs = {len(probes) * RUNS} calls ===")

    engine = RAGEngine(use_rerank=True)

    results = []
    for i, (q, typ, expect_reject, keywords) in enumerate(probes, 1):
        print(f"\n--- [{i}/{len(probes)}] [{typ}] {q}")
        for run in range(1, RUNS + 1):
            try:
                r = engine.query(q)
                ans = r["answer"]
                conf = r["confidence"]
                # legacy 口径（子串匹配），保持与 09-16 run 逐位可比
                refused = any(m in ans for m in REFUSE_MARKERS)
                # 新口径：四态
                state = classify_state(ans, conf, expect_reject, keywords)
                preview = ans[:120].replace("\n", " ")
                print(f"  run {run}/{RUNS}: refused={refused} state={state} conf={conf:.4f} | {preview}")
                results.append({
                    "question": q,
                    "type": typ,
                    "run": run,
                    "refused": refused,
                    "state": state,
                    "confidence": round(conf, 4),
                    "expect_reject": expect_reject,
                    "keywords": keywords,
                    # 存完整回答（旧版截断到 300 字，已证实会砍到正样本：
                    # "什么是 RAG？" 断在"与传"，导致离线重判只能覆盖短回答）
                    "answer": ans,
                })
            except Exception as e:
                print(f"  run {run}/{RUNS}: ERROR {e}")
                results.append({
                    "question": q,
                    "type": typ,
                    "run": run,
                    "expect_reject": expect_reject,
                    "keywords": keywords,
                    "error": str(e),
                })
            time.sleep(1)

    by_q = defaultdict(list)
    for r in results:
        if "refused" in r:
            by_q[(r["question"], r["type"])].append(r)

    summary = {}
    for (q, typ), rows in by_q.items():
        refused_list = [r["refused"] for r in rows]
        state_list = [r["state"] for r in rows]
        n = len(refused_list)
        n_refused = sum(refused_list)
        state_counts = defaultdict(int)
        for s in state_list:
            state_counts[s] += 1
        summary[q] = {
            # --- legacy 三字段：口径未改，与 09-16 run 逐位可比 ---
            "type": typ,
            "runs": n,
            "refused_count": n_refused,
            "refused_ratio": round(n_refused / n, 2) if n else 0.0,
            "stable": len(set(refused_list)) == 1,
            # --- 新口径 ---
            "state": state_list[0] if len(set(state_list)) == 1 else "MIXED",
            "state_counts": dict(state_counts),
            "stable_on_state": len(set(state_list)) == 1,
        }

    # 极性聚合：state 不携带极性，聚合必须按 expect_reject 分组才可解读。
    # 这里首次把"两层拒答机制"的分解量化出来（见 RESULTS.md 的语义边界一节）：
    # confidence 闸拒答率 + LLM 自拒率 = 端到端 non_delivery。
    # 两个键都预置为 0：本批数据 template 一次都没触发（40 条全被 conf 闸拦下），
    # 若省略零值键，下游就只能靠 .get() 猜。保留显式 0 才能让"template > 0"
    # 成为一个可被直接观测的阈值漂移告警。
    sys_refuse_by = defaultdict(int, {"confidence": 0, "template": 0})
    agg = {
        "n_records": 0,
        # 四态全部预置为 0：本批 REFUSED 为空类，而"某态为空"本身就是结论
        # （空类不可见 = 无法区分"没发生"与"没统计"）。
        "state_counts": defaultdict(int, {s: 0 for s in STATE_NAMES}),
        "legacy_refused_count": 0,
        "system_refuse_by": sys_refuse_by,
        "positive": {"questions": 0, "records": 0, "delivered": 0},
        "negative": {"questions": 0, "records": 0, "false_delivered": 0,
                     "blocked_by_confidence_gate": 0, "blocked_by_llm_self_refuse": 0},
    }
    for r in results:
        if "state" not in r:
            continue
        agg["n_records"] += 1
        agg["state_counts"][r["state"]] += 1
        agg["legacy_refused_count"] += 1 if r["refused"] else 0
        if r["state"] == "SYSTEM_REFUSE":
            # 归因：confidence 优先（模板只在阈值漂移时才会成为唯一触发者）
            reason = "confidence" if r["confidence"] < CONFIDENCE_THRESHOLD else "template"
            sys_refuse_by[reason] += 1
        bucket = agg["negative"] if r["expect_reject"] else agg["positive"]
        bucket["records"] += 1
        if not r["expect_reject"]:
            bucket["delivered"] += 1 if r["state"] == "DELIVERED" else 0
        else:
            if r["state"] == "DELIVERED":
                bucket["false_delivered"] += 1
            elif r["state"] == "SYSTEM_REFUSE":
                bucket["blocked_by_confidence_gate"] += 1
            else:
                bucket["blocked_by_llm_self_refuse"] += 1
    # 问题级极性计数（用 summary 更直观）
    for s in summary.values():
        if s["type"] == "positive":
            agg["positive"]["questions"] += 1
        else:
            agg["negative"]["questions"] += 1

    n_pos = agg["positive"]["records"]
    n_neg = agg["negative"]["records"]
    agg["positive"]["delivery_rate"] = round(agg["positive"]["delivered"] / n_pos, 3) if n_pos else 0.0
    agg["negative"]["non_delivery"] = n_neg - agg["negative"]["false_delivered"]
    agg["negative"]["non_delivery_rate"] = (
        round((n_neg - agg["negative"]["false_delivered"]) / n_neg, 3) if n_neg else 0.0
    )
    if n_neg:
        agg["negative"]["gate_split"] = {
            "confidence_gate": round(agg["negative"]["blocked_by_confidence_gate"] / n_neg, 3),
            "llm_self_refuse": round(agg["negative"]["blocked_by_llm_self_refuse"] / n_neg, 3),
        }
    agg["state_counts"] = dict(agg["state_counts"])
    agg["system_refuse_by"] = dict(sys_refuse_by)

    out = Path("probe_stability_results.json")
    out.write_text(
        json.dumps(
            {"results": results, "summary": summary, "aggregate": agg},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\n=== 写入 {out} ===")
    print("\n=== 稳定性汇总 ===")
    for q, s in summary.items():
        marker = "STABLE" if s["stable"] else "UNSTABLE"
        smarker = "STABLE" if s["stable_on_state"] else "UNSTABLE"
        print(
            f"  [{s['type']:30s}] [{marker:8s}] {s['refused_count']}/{s['runs']} refused"
            f" | state={s['state']:14s} [{smarker:8s}] | {q[:40]}"
        )


if __name__ == "__main__":
    main()
