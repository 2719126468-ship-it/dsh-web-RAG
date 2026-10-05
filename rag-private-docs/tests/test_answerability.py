"""Unit tests for grounded answerability verification."""

from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

from answerability import AnswerabilityChecker


def test_answerable_requires_verbatim_evidence():
    context = "[1] contract.md\n总金额为 480,000 元。"
    parsed = {"verdict": "ANSWERABLE", "evidence": "480,000 元"}
    assert AnswerabilityChecker._validate_answerable(parsed, context)


def test_answerable_rejects_paraphrased_evidence():
    context = "[1] contract.md\n总金额为 480,000 元。"
    parsed = {"verdict": "ANSWERABLE", "evidence": "合同金额是48万元"}
    assert not AnswerabilityChecker._validate_answerable(parsed, context)


def test_unanswerable_never_passes():
    context = "[1] contract.md\n合同延期每天罚款 0.5%。"
    parsed = {"verdict": "UNANSWERABLE", "evidence": ""}
    assert not AnswerabilityChecker._validate_answerable(parsed, context)


def test_parse_json_response():
    parsed = AnswerabilityChecker._parse_response(
        '{"verdict":"ANSWERABLE","evidence":"总金额为 480,000 元。"}'
    )
    assert parsed == {
        "verdict": "ANSWERABLE",
        "evidence": "总金额为 480,000 元。",
    }



def test_context_deduplicates_parent_chunks():
    hits = [
        {
            "content": "child one",
            "metadata": {
                "source": "notes.md",
                "parent_id": "p1",
                "parent_text": "完整父文档内容",
            },
        },
        {
            "content": "child two",
            "metadata": {
                "source": "notes.md",
                "parent_id": "p1",
                "parent_text": "完整父文档内容",
            },
        },
        {
            "content": "独立内容",
            "metadata": {"source": "other.md"},
        },
    ]

    context = AnswerabilityChecker._context_text(hits)

    assert context.count("完整父文档内容") == 1
    assert "child one" not in context
    assert "child two" not in context
    assert "独立内容" in context


def test_context_prefers_parent_text_for_verification():
    hits = [
        {
            "content": "child: answer fragment",
            "metadata": {
                "source": "notes.md",
                "parent_id": "p1",
                "parent_text": "parent contains the complete answer",
            },
        }
    ]

    context = AnswerabilityChecker._context_text(hits)

    assert "parent contains the complete answer" in context
    assert "child: answer fragment" not in context


def test_enabled_gate_is_strict_in_qa_source():
    qa_source = (
        Path(__file__).resolve().parent.parent / "src" / "qa.py"
    ).read_text(encoding="utf-8")

    assert (
        'if self.answerability.enabled and answerability["status"] != "ANSWERABLE":'
        in qa_source
    )
    assert '"answerability": answerability' in qa_source
