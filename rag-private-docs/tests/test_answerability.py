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
