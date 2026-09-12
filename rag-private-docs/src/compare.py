"""Compare two evaluation result JSON files.

Usage:
  python compare.py eval/results/2026-09-13T10-30-00.json eval/results/2026-09-13T14-20-00.json
  python compare.py --latest    # 比较最近两次
"""
import json
import sys
from pathlib import Path
from typing import Dict, Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "eval" / "results"


def load(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_latest_two():
    if not RESULTS_DIR.exists():
        return None, None
    files = sorted(RESULTS_DIR.glob("*.json"))
    if len(files) < 2:
        return None, None
    return str(files[-2]), str(files[-1])


def compare(a: Dict, b: Dict) -> Dict[str, Dict[str, Any]]:
    sa = a.get("summary", {})
    sb = b.get("summary", {})
    keys = sorted(set(sa) | set(sb))
    out = {}
    for k in keys:
        va = sa.get(k)
        vb = sb.get(k)
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            diff = round(vb - va, 4)
            out[k] = {"before": va, "after": vb, "diff": diff, "improved": diff > 0}
        else:
            out[k] = {"before": va, "after": vb, "diff": None, "improved": None}
    return out


def print_report(a: Dict, b: Dict, path_a: str, path_b: str):
    print("=" * 70)
    print("评估对比报告")
    print("=" * 70)
    print(f"  之前: {path_a}")
    print(f"  之后: {path_b}")
    print(f"  时间: {a.get('timestamp', '?')}  →  {b.get('timestamp', '?')}")
    print()
    print(f"  {'指标':<25s} {'之前':>10s} {'之后':>10s} {'变化':>10s}")
    print("-" * 70)
    result = compare(a, b)
    for k, v in result.items():
        if v["diff"] is None:
            continue
        diff = v["diff"]
        if diff > 0:
            arrow = "↑"
        elif diff < 0:
            arrow = "↓"
        else:
            arrow = "="
        print(f"  {k:<25s} {v['before']:>10.4f} {v['after']:>10.4f} {arrow} {abs(diff):>7.4f}")
    print()


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--latest":
        pa, pb = load_latest_two()
        if pa is None:
            print("结果目录里少于两个文件，无法对比")
            sys.exit(1)
    elif len(sys.argv) == 3:
        pa, pb = sys.argv[1], sys.argv[2]
    else:
        print(__doc__)
        sys.exit(1)

    a = load(pa)
    b = load(pb)
    print_report(a, b, pa, pb)


if __name__ == "__main__":
    main()
