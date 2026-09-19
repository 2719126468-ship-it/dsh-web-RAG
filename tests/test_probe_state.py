"""probe_stability.py 四态判定轴的单元测试（纯函数，零网络调用）。

被测对象（都是纯函数 / 常量，可离线回放）：
    classify_state(answer, confidence, expect_reject, keywords, threshold)
    _strip_lead_refusal(answer) -> (matched, residual)
    _residual_has_substance(residual)
    MIN_REDIRECT_CHARS / CONFIDENCE_THRESHOLD

覆盖的判定口径（见 probe_stability.py 的模块 docstring）：
    闸 0   conf < 阈值                        -> SYSTEM_REFUSE
    闸 0'  命中 qa.py 模板正则                -> SYSTEM_REFUSE（阈值漂移兜底）
    闸 1   按极性分流：正样本靠 ground_truth_keywords 判 DELIVERED，
           负样本靠"无任何 legacy 拒答 marker"判 DELIVERED（幻觉交付）
    闸 2  剥首句后残句 >= MIN_REDIRECT_CHARS ? REDIRECTED : REFUSED

=== 关于导入隔离（为什么不直接 import probe_stability）===

probe_stability.py 模块头部有 `from qa import CONFIDENCE_THRESHOLD, RAGEngine`，
而 qa.py 会连环拉入 langchain_openai / langchain_core / retriever(qdrant,
sentence-transformers) / dotenv —— 本机 venv 只有 pytest，装不起也无需装。

纯函数本身不依赖这些重型依赖，只依赖 qa 的 CONFIDENCE_THRESHOLD 常量。
因此这里先尝试导入真 qa；失败才注入最小 qa 桩（仅两个符号），
从而在没有 langchain 的环境里也能**真跑**而不是 importorskip 跳过。
桩里的阈值从 qa.py 源码解析，保证与真实常量一致（有专门用例守住这点）。
"""

import importlib
import re
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / "rag-private-docs"
SRC = PROJECT / "src"


def _qa_threshold_from_source() -> float:
    """从 qa.py 源码解析真实 CONFIDENCE_THRESHOLD（不导入 qa，避免拉重型依赖）。"""
    text = (SRC / "qa.py").read_text(encoding="utf-8")
    m = re.search(r"^CONFIDENCE_THRESHOLD\s*=\s*([0-9]*\.?[0-9]+)", text, re.MULTILINE)
    assert m, "无法从 qa.py 解析出 CONFIDENCE_THRESHOLD"
    return float(m.group(1))


def _load_probe():
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))
    try:
        importlib.import_module("qa")  # 能导入就用真 qa（真阈值、真 RAGEngine）
    except ImportError:
        stub = types.ModuleType("qa")
        stub.CONFIDENCE_THRESHOLD = _qa_threshold_from_source()
        stub.RAGEngine = object
        sys.modules["qa"] = stub
    return importlib.import_module("probe_stability")


probe = _load_probe()

# 阈值上下的取点：与具体数值解耦，qa.py 改阈值时测试不需要改
BELOW = probe.CONFIDENCE_THRESHOLD - 0.01
ABOVE = probe.CONFIDENCE_THRESHOLD + 0.01

# 可被 LEAD_REFUSE_RE 剥离的拒答首句
_LEAD = "未找到相关信息。"

# 普通散答：无拒答首句，剥噪声后 17 字（>= MIN_REDIRECT_CHARS），用于测闸 0 / 闸 2
_PLAIN_ANSWER = "这是一段足够长的正常答案文本内容。"

# 残句字符表：14 个汉字，均不在 _MD_NOISE 的剥离集内，故 len 可精确控制
_ALPHABET = "甲乙丙丁戊己庚辛壬癸子丑寅卯"


def _residual(n: int) -> str:
    """构造恰好 n 个「噪声剥离后仍保留」字符的残句。"""
    return _ALPHABET[:n]


# =====================================================================
# 闸 0：confidence 低于阈值 -> SYSTEM_REFUSE（与 answer 内容无关）
# =====================================================================


@pytest.mark.parametrize(
    "answer",
    [
        "这是一段看起来像答案的正常文本。",
        "资料中未找到与该问题相关的内容（最高置信度 0.85）",
        "",
        None,
    ],
)
def test_gate0_low_confidence_system_refuse_regardless_of_answer(answer):
    assert probe.classify_state(answer, BELOW, False, ["任意关键词"]) == "SYSTEM_REFUSE"
    assert probe.classify_state(answer, BELOW, True, []) == "SYSTEM_REFUSE"


def test_gate0_uses_strict_inequality():
    """confidence == threshold 不算拒答（`<` 而非 `<=`）。"""
    assert probe.classify_state(_PLAIN_ANSWER, probe.CONFIDENCE_THRESHOLD, False, []) == "REDIRECTED"
    assert probe.classify_state(_PLAIN_ANSWER, probe.CONFIDENCE_THRESHOLD - 0.001, False, []) == "SYSTEM_REFUSE"


def test_custom_threshold_shifts_boundary():
    """threshold 可覆盖：同一 confidence 在两张阈值下判定不同。"""
    assert probe.classify_state(_PLAIN_ANSWER, 0.5, False, ["任意"], threshold=0.6) == "SYSTEM_REFUSE"
    assert probe.classify_state(_PLAIN_ANSWER, 0.5, False, ["任意"], threshold=0.4) == "REDIRECTED"


def test_plain_short_answer_without_lead_refusal_falls_to_refused():
    """无拒答首句、且剥噪声后不足 12 字的散答 -> REFUSED（形态细分，非交付）。"""
    assert len("这是一段正常答案文本。") == 11
    assert probe.classify_state("这是一段正常答案文本。", ABOVE, False, ["用户手册"]) == "REFUSED"


def test_default_threshold_equals_qa_constant():
    """守住导入桩的保真度：probe 用的阈值必须就是 qa.py 里的真实常量。"""
    assert probe.CONFIDENCE_THRESHOLD == _qa_threshold_from_source()


# =====================================================================
# 闸 0'：conf 过线但命中 qa.py 模板 -> SYSTEM_REFUSE（阈值漂移兜底）
# =====================================================================


@pytest.mark.parametrize(
    "answer",
    [
        "资料中未找到与该问题相关的内容（最高置信度 0.85）",
        "资料中未找到与该问题相关的内容（最高置信度0.72）\n\n[1] 相关片段",
        "知识库为空，请先将文档放入 docs/ 后重建索引。",
        "  知识库为空。",
    ],
)
def test_gate0_prime_qa_templates_system_refuse(answer):
    assert probe.classify_state(answer, ABOVE, True, []) == "SYSTEM_REFUSE"


def test_gate0_prime_template_wins_over_positive_keyword_hit():
    """模板闸在极性分流之前，正样本也不会因含金标词被误判 DELIVERED。"""
    answer = "资料中未找到与该问题相关的内容（最高置信度 0.85）"
    assert probe.classify_state(answer, ABOVE, False, ["未找到"]) == "SYSTEM_REFUSE"


def test_gate0_prime_regexes_do_not_match_llm_style_refusal():
    """LLM 自答的"资料中未找到相关内容"没有「（最高置信度 X.XX）」，两条模板正则都不得命中。"""
    answer = "资料中未找到相关内容。"
    assert not probe.SYSTEM_REFUSE_RE.match(answer)
    assert not probe.EMPTY_KB_RE.match(answer)
    # 因此它不能被记为 SYSTEM_REFUSE，只能走 LLM 分支 -> 硬拒
    assert probe.classify_state(answer, ABOVE, True, []) == "REFUSED"


# =====================================================================
# 闸 1 正样本：ground_truth_keywords 命中 -> DELIVERED
# =====================================================================


def test_positive_keyword_hit_delivered():
    answer = "该论文的作者署名为 Anonymous Authors。[1]"
    assert probe.classify_state(answer, ABOVE, False, ["Anonymous"]) == "DELIVERED"


def test_positive_keyword_hit_is_case_insensitive():
    answer = "该论文的作者署名为 Anonymous Authors。[1]"
    assert probe.classify_state(answer, ABOVE, False, ["anonymous"]) == "DELIVERED"


def test_positive_keyword_miss_with_substantial_residual_redirected():
    answer = "未找到关于具体功能清单的说明。参考资料中提到 12 月版本发布过若干改进。[1]"
    assert probe.classify_state(answer, ABOVE, False, ["用户手册"]) == "REDIRECTED"


@pytest.mark.parametrize(
    "answer",
    ["未找到相关信息。", "未找到相关信息。\n", "  未找到相关信息。  "],
)
def test_positive_keyword_miss_with_empty_residual_refused(answer):
    assert probe.classify_state(answer, ABOVE, False, ["用户手册"]) == "REFUSED"


def test_positive_keywords_none_treated_as_empty():
    answer = "参考资料中提到过相近的章节内容。[1]"
    assert probe.classify_state(answer, ABOVE, False, None) == "REDIRECTED"


def test_positive_empty_keyword_string_does_not_deliver():
    """空串关键词不得命中（否则空串 `in` 任意文本恒真）。"""
    answer = "参考资料中提到过相近的章节内容。[1]"
    assert probe.classify_state(answer, ABOVE, False, [""]) == "REDIRECTED"


# =====================================================================
# 闸 1 负样本
# =====================================================================


def test_negative_without_marker_delivered():
    """负样本无任何 legacy 拒答 marker -> 幻觉交付。"""
    answer = "该论文的作者是 Zhang Wei 与 Li Na。"
    assert probe.classify_state(answer, ABOVE, True, []) == "DELIVERED"


def test_negative_with_marker_and_substantial_residual_redirected():
    answer = "未找到该条款。参考资料中相近的内容涉及延期罚则。[1]"
    assert probe.classify_state(answer, ABOVE, True, []) == "REDIRECTED"


def test_negative_keywords_are_ignored_for_delivery():
    """负样本不看 keywords：即使关键词命中，无拒答 marker 仍是 DELIVERED。"""
    answer = "该论文的作者署名为 Anonymous Authors。[1]"
    assert probe.classify_state(answer, ABOVE, True, ["Anonymous"]) == "DELIVERED"


def test_state_is_polarity_aware_same_text_two_polarities():
    """state 不携带极性：同一段文本，正样本算未交付、负样本算幻觉交付。"""
    answer = "参考资料中提到过相近的章节内容。[1]"
    assert probe.classify_state(answer, ABOVE, False, ["用户手册"]) == "REDIRECTED"
    assert probe.classify_state(answer, ABOVE, True, []) == "DELIVERED"


# =====================================================================
# 边界：空回答 / None
# =====================================================================


@pytest.mark.parametrize("answer", ["", None, "   \n\t  "])
def test_empty_or_whitespace_answer_refused(answer):
    """空回答既非模板拒答也不是交付；必须显式 REFUSED 而非落入 DELIVERED。"""
    assert probe.classify_state(answer, ABOVE, True, []) == "REFUSED"
    assert probe.classify_state(answer, ABOVE, False, ["任意关键词"]) == "REFUSED"


# =====================================================================
# 边界：marker 出现在文本中段（非首句）不得被当作拒答首句
# =====================================================================

_MID_TEXT = "文档第 3 节提到了该功能，但资料中未找到具体清单。"


def test_mid_text_marker_is_not_stripped_as_lead_refusal():
    matched, residual = probe._strip_lead_refusal(_MID_TEXT)
    assert matched is False
    assert residual == _MID_TEXT


def test_mid_text_marker_negative_sample_redirected_not_refused():
    """中段 marker 未能剥离 -> 残句 = 全文 -> 有实质内容 -> REDIRECTED（而非 REFUSED）。"""
    assert probe.classify_state(_MID_TEXT, ABOVE, True, []) == "REDIRECTED"


def test_mid_text_marker_positive_sample_keyword_hit_delivered():
    answer = "该论文由 Anonymous Authors 撰写，虽然资料中未找到完整作者列表。[1]"
    assert probe.classify_state(answer, ABOVE, False, ["Anonymous"]) == "DELIVERED"


# =====================================================================
# _strip_lead_refusal 精确行为
# =====================================================================


def test_strip_lead_refusal_returns_exact_residual():
    matched, residual = probe._strip_lead_refusal("未找到相关信息。后续有内容。")
    assert matched is True
    assert residual == "后续有内容。"


def test_strip_lead_refusal_no_match_returns_original():
    text = "这是一段正常答案。"
    matched, residual = probe._strip_lead_refusal(text)
    assert matched is False
    assert residual == text


def test_strip_lead_refusal_none_is_safe():
    matched, residual = probe._strip_lead_refusal(None)
    assert matched is False
    assert residual == ""


# =====================================================================
# 边界：MIN_REDIRECT_CHARS 的 11 / 12 分界
# =====================================================================


def test_min_redirect_chars_contract_is_12():
    assert probe.MIN_REDIRECT_CHARS == 12


def test_residual_boundary_11_vs_12():
    # 先自证夹具干净：噪声剥离后的长度确实就是 11 / 12
    assert len(probe._MD_NOISE.sub("", _residual(11))) == 11
    assert len(probe._MD_NOISE.sub("", _residual(12))) == 12
    assert probe._residual_has_substance(_residual(11)) is False
    assert probe._residual_has_substance(_residual(12)) is True

    # 端到端：同一拒答首句，残句 11 字 -> REFUSED；12 字 -> REDIRECTED
    assert probe.classify_state(_LEAD + _residual(11), ABOVE, True, []) == "REFUSED"
    assert probe.classify_state(_LEAD + _residual(12), ABOVE, True, []) == "REDIRECTED"


def test_markdown_markup_is_stripped_before_counting():
    """**加粗** / 空白 / 列表符号不参与字数统计：11 个汉字配这些噪声仍是 11 字。"""
    noisy = "**" + _residual(11) + "**\n- "
    assert len(probe._MD_NOISE.sub("", noisy)) == 11
    assert probe._residual_has_substance(noisy) is False
    assert probe.classify_state(_LEAD + noisy, ABOVE, True, []) == "REFUSED"


def test_markdown_digits_are_not_stripped():
    """实测行为：_MD_NOISE 剥离 *[]()- 与空白，但**数字保留**。

    故 `[1]` 角标里那个 "1" 会算进长度：11 个汉字 + `[1]` = 12 字 -> 恰好过线。
    这是真实现状（非预期），在此显式固定，避免以后误以为角标被整体忽略。
    """
    noisy = "**" + _residual(11) + "** [1]"
    assert len(probe._MD_NOISE.sub("", noisy)) == 12
    assert probe._residual_has_substance(noisy) is True
    assert probe.classify_state(_LEAD + noisy, ABOVE, True, []) == "REDIRECTED"


# =====================================================================
# 常量一致性
# =====================================================================


def test_state_names_cover_all_four_states():
    assert probe.STATE_NAMES == ("SYSTEM_REFUSE", "REDIRECTED", "REFUSED", "DELIVERED")


def test_classify_state_never_returns_unknown_state():
    """穷举若干输入形态，输出必须落在四态枚举内。"""
    cases = [
        ("", BELOW, False, []),
        ("正常答案", ABOVE, False, []),
        ("未找到相关信息。", ABOVE, True, []),
        ("该论文作者是 Anonymous Authors。", ABOVE, False, ["Anonymous"]),
    ]
    for answer, conf, expect_reject, keywords in cases:
        assert probe.classify_state(answer, conf, expect_reject, keywords) in probe.STATE_NAMES
