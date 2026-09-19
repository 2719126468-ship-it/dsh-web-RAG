"""README 用例数与实际 pytest 收集数的一致性守卫。

背景
----
README 的「能力速览」表里有一行硬编码用例数：

    | 测试 | pytest，96 个用例（本地 94 passed, 2 skipped；CI 3.11 / 3.12 各 92 passed, 4 skipped）|

这行历史上已连续失真两轮（48 → 55 → 96）—— 每次新增测试文件都可能忘记同步。
本测试把这种「静默失真」变成「CI 硬报红」。

口径（与 eval/RESULTS.md 的约定一致）
------------------------------------
N 取 **pytest 收集数（collected）**，即 passed + skipped，
不是 passed 数、也不是 CI 侧某个特定数字。

为什么是收集数而不是 passed 数：
    本地有 .env / DEEPSEEK_API_KEY，CI 没有，
    因此 `test_env_file_exists` 与 `test_api_key_format` 在 CI 会由 passed 变 skipped
    （CI: 4 skipped vs 本地: 2 skipped）。
    passed/skipped 的**拆分**随环境变化，但**收集数**在本地与 CI 两侧一致 ——
    所以只有收集数可跨环境校验。

为什么只校验总数，不校验括号里的拆分：
    括号里的 `94 passed, 2 skipped` 是环境相关的（见上），无法在同一断言里跨环境成立。
    本测试只守住「总数」这一条两侧一致的契约。

设计要点
--------
* 用 `--collect-only`：**只收集、不执行**，因此不会递归调用本测试自身（安全）。
* 解析失败 / 子进程非零退出 / README 里找不到数字模式 —— 一律 `pytest.fail` 硬报错，
  不做 `pytest.skip` 静默放过（与项目「不静默降级」的哲学一致）。
* 零第三方依赖：只用标准库 + pytest，不导入 qa / retriever 等重型模块。

已知前提（若本测试意外报「收集数异常低」，先查这个）
----------------------------------------------------
`tests/test_config_fields.py` / `test_memory.py` / `test_webhook.py` 用的是
**模块级** `pytest.importorskip("dotenv")`：若环境里没装 `python-dotenv`，
这三个模块会在**收集阶段**整体跳过，收集数会骤降（例如 96 → 56）。
CI（.github/workflows/test.yml）会安装 `python-dotenv`，故 CI 侧安全；
本地若缺该依赖，请先 `pip install python-dotenv` 再跑，否则报错反映的是环境问题而非 README 漂移。
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"

# README 里声明的用例数，形如「pytest，96 个用例」/「pytest, 96 个用例」
README_COUNT_RE = re.compile(r"pytest[，,]\s*(\d+)\s*个用例")

# pytest 收集阶段的汇总行，形如「96 tests collected in 0.06s」/「1 test collected」
COLLECTED_RE = re.compile(r"(\d+)\s+tests?\s+collected")


def _readme_declared_count() -> int:
    """从 README 解析出声明的用例数；解析不到即硬失败。"""
    text = README.read_text(encoding="utf-8")
    m = README_COUNT_RE.search(text)
    if not m:
        pytest.fail(
            "README.md 中未找到用例数声明（期望形如「pytest，N 个用例」）。"
            "若已改为不含数字的表述，请同步删除本测试（见 eval/RESULTS.md 的决策记录）。"
        )
    return int(m.group(1))


def _actual_collected_count() -> int:
    """跑一次 `pytest --collect-only`，解析真实收集数。"""
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    m = COLLECTED_RE.search(output)
    if proc.returncode != 0 or not m:
        tail = output.strip().splitlines()[-15:]
        pytest.fail(
            "无法从 `pytest --collect-only` 的输出解析收集数"
            f"（returncode={proc.returncode}）。输出尾部：\n" + "\n".join(tail)
        )
    return int(m.group(1))


def test_readme_test_count_matches_actual_collection():
    declared = _readme_declared_count()
    actual = _actual_collected_count()
    assert declared == actual, (
        f"README.md 声明的用例数（{declared}）与实际 pytest 收集数（{actual}）不一致。\n"
        f"请把 README「能力速览」里的用例数改为 {actual}（本地 {actual - 2} passed, 2 skipped）。"
    )
