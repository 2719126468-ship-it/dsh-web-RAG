"""测试集格式与内容规范。零外部依赖。"""
import json
import re
from pathlib import Path
import pytest

REPO = Path(__file__).resolve().parent.parent
EVAL = REPO / "rag-private-docs" / "eval"


@pytest.fixture
def test_set():
    return json.loads((EVAL / "test_set.json").read_text(encoding="utf-8"))


def test_all_questions_have_id(test_set):
    for q in test_set:
        assert "id" in q and q["id"], f"缺少 id: {q.get('question')}"


def test_negative_type_valid(test_set):
    valid = {None, "off_topic", "topic_relevant_no_answer"}
    for q in test_set:
        assert q.get("negative_type") in valid, f"{q['id']} negative_type 非法: {q.get('negative_type')}"


def test_no_short_numeric_keywords(test_set):
    for q in test_set:
        for kw in q["ground_truth_keywords"]:
            if re.fullmatch(r"\d+", kw):
                assert len(kw) >= 4, f"关键词 '{kw}' 太短 ({q['id']})"


def test_no_single_cjk_keywords(test_set):
    for q in test_set:
        for kw in q["ground_truth_keywords"]:
            if re.fullmatch(r"[\u4e00-\u9fff]", kw):
                pytest.fail(f"单字中文关键词 '{kw}' ({q['id']})")


def test_expect_reject_has_empty_keywords(test_set):
    for q in test_set:
        if q.get("expect_reject"):
            assert q["ground_truth_keywords"] == [], f"负样本不应有关键词 ({q['id']})"


def test_holdout_docs_disjoint_from_dev():
    dev = json.loads((EVAL / "test_set.json").read_text(encoding="utf-8"))
    hold = json.loads((EVAL / "test_set_holdout.json").read_text(encoding="utf-8"))
    dev_docs = {q["must_cite"] for q in dev if not q.get("expect_reject")}
    hold_docs = {q["must_cite"] for q in hold if not q.get("expect_reject")}
    overlap = dev_docs & hold_docs
    assert not overlap, f"holdout 和 dev 共享文档: {overlap}"


def test_negative_type_counts(test_set):
    """确认分层数量符合预期（4 off_topic + 8 topic_relevant）。"""
    from collections import Counter
    neg = [q for q in test_set if q.get("expect_reject")]
    counts = Counter(q["negative_type"] for q in neg)
    assert counts.get("off_topic") == 4, f"off_topic 数量不对: {counts}"
    assert counts.get("topic_relevant_no_answer") == 8, f"topic_relevant 数量不对: {counts}"
