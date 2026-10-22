"""Print per-category and average answer_correctness from official evaluation outputs, and the mean over runs.

    python scripts/summarize_scores.py scores_novel                         # one run
    python scripts/summarize_scores.py run1/novel run2/novel run3/novel     # several runs + their mean

Each directory holds official_{fact,reason,summ,creat}.json written by Evaluation/generation_eval.py (as from
scripts/score.sh), or one official_eval_output.json[.gz] with all four question types.
"""
import gzip
import json
import statistics as st
import sys
from pathlib import Path

CATS = ["Fact Retrieval", "Complex Reasoning", "Contextual Summarize", "Creative Generation"]
FILES = {"Fact Retrieval": "fact", "Complex Reasoning": "reason", "Contextual Summarize": "summ", "Creative Generation": "creat"}


def load(d: Path) -> dict:
    res = {}
    for name in ("official_eval_output.json", "official_eval_output.json.gz"):
        p = d / name
        if p.exists():
            data = json.load(gzip.open(p, "rt") if p.suffix == ".gz" else open(p))
            res.update(data)
    for cat, s in FILES.items():
        p = d / f"official_{s}.json"
        if cat not in res and p.exists():
            res.update(json.load(open(p)))
    return res


def main() -> None:
    runs = [Path(a) for a in sys.argv[1:]] or [Path(".")]
    macros = []
    for d in runs:
        res = load(d)
        scores = {}
        line = []
        for cat in CATS:
            if cat in res:
                v = res[cat]
                scores[cat] = v["average_scores"]["answer_correctness"] * 100
                line.append(f"{cat} {scores[cat]:.2f} (n={len(v.get('detailed', []))})")
        if len(scores) == 4:
            macros.append(st.mean(scores.values()))
            line.append(f"Average {macros[-1]:.2f}")
        print(f"{d}: " + " | ".join(line))
    if len(macros) > 1:
        print(f"mean of {len(macros)} runs: {st.mean(macros):.2f} (sd {st.stdev(macros):.2f})")


if __name__ == "__main__":
    main()
