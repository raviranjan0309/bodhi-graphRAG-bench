#!/usr/bin/env bash
# Score an answers file with the official, unmodified GraphRAG-Bench evaluation script.
#
#   export LLM_API_KEY=<OpenAI key>          # the official script reads the judge key from LLM_API_KEY
#   scripts/score.sh <path to GraphRAG-Benchmark checkout> answers_novel.json scores_novel
#
# The four question types are split into separate files and scored in parallel; each part is the official
# script run as-is: --mode API --model gpt-4o-mini --embedding_model BAAI/bge-large-en-v1.5 --detailed_output.
# Optional: JUDGE_BASE_URL (default https://api.openai.com/v1).
set -euo pipefail
REPO=$(cd "$1" && pwd); ANSWERS=$(cd "$(dirname "$2")" && pwd)/$(basename "$2"); OUT=$(mkdir -p "$3" && cd "$3" && pwd)
: "${LLM_API_KEY:?set LLM_API_KEY (judge key)}"
BASE=${JUDGE_BASE_URL:-https://api.openai.com/v1}
python3 - "$ANSWERS" "$OUT" <<'PY'
import gzip, json, sys
p, out = sys.argv[1], sys.argv[2]
f = gzip.open(p, "rt") if p.endswith(".gz") else open(p)
content = f.read().strip()
rows = json.loads(content) if content.startswith("[") else [json.loads(line) for line in content.splitlines() if line.strip()]
names = {"Fact Retrieval": "fact", "Complex Reasoning": "reason", "Contextual Summarize": "summ", "Creative Generation": "creat"}
for qt, s in names.items():
    part = [r for r in rows if r["question_type"] == qt]
    json.dump(part, open(f"{out}/answers_{s}.json", "w")); print(f"{qt}: {len(part)} answers")
PY
cd "$REPO"
for s in fact reason summ creat; do
  python3 -m Evaluation.generation_eval --mode API --model gpt-4o-mini --base_url "$BASE" \
    --embedding_model BAAI/bge-large-en-v1.5 --data_file "$OUT/answers_$s.json" \
    --output_file "$OUT/official_$s.json" --detailed_output > "$OUT/official_$s.log" 2>&1 &
done
wait
python3 "$(dirname "$0")/summarize_scores.py" "$OUT" 2>/dev/null || python3 "$OLDPWD/$(dirname "$0")/summarize_scores.py" "$OUT"
