# Bodhi-GraphRAG on GraphRAG-Bench (Novel and Medical)

**Organization:** Publicis Sapient · **Product:** Bodhi · **Link:** https://www.publicissapient.com/platforms/bodhi
(a technical note on Bodhi-GraphRAG is in preparation and will be linked here)

This repository lets anyone reproduce our GraphRAG-Bench results through a public API: send the official questions
to the Bodhi-GraphRAG chat endpoint, score the answers with the official, unmodified evaluation code, and average
several runs. It also holds the answers and the full evaluation output of our own runs.

## 1. Results (public API, standard configuration)

Generation `gpt-4o-mini` at temperature 0.7, judge `gpt-4o-mini`, official evaluation code (commit `fdbab59`)
unmodified, all questions of the current official question files. Scores are `answer_correctness` (%); Average is the
mean of the four question types. Answers are sampled at temperature 0.7, so separate runs differ slightly; we report
each run and their mean.

| Novel | Fact Retrieval | Complex Reasoning | Contextual Summarize | Creative Generation | Average |
|---|---|---|---|---|---|
| Run 1 | 68.17 | 61.16 | 70.03 | 64.88 | 66.06 |
| Run 2 | 68.20 | 60.39 | 70.95 | 66.59 | 66.53 |
| **Mean** | **68.19** | **60.78** | **70.49** | **65.74** | **66.30** |

| Medical | Fact Retrieval | Complex Reasoning | Contextual Summarize | Creative Generation | Average |
|---|---|---|---|---|---|
| Run 1 | 75.86 | 75.96 | 76.23 | 74.29 | 75.58 |
| Run 2 | 76.26 | 75.53 | 76.40 | 75.48 | 75.92 |
| **Mean** | **76.06** | **75.74** | **76.32** | **74.88** | **75.75** |

Evaluated counts (questions the judge scored; the others failed the judge's output validation, see section 6):
Novel run 1 2,006 / 2,010, run 2 2,008 / 2,010; Medical run 1 2,058 / 2,062, run 2 2,061 / 2,062. Every question was
answered (HTTP 200) in both runs. Per-type counts and the other metrics (ROUGE, coverage, faithfulness) are in each
run's `summary.json`. A third run is in progress and will be added.

## 2. Public API

| Item | Value |
|---|---|
| Base URL | `https://bodhi-ecg-api.ks.psbodhi.ai` |
| Endpoint | `POST /api/v1/workspaces/{workspace_id}/chat` |
| Authentication | `Authorization: Bearer <token>` (token sent to you separately) |
| Workspace id | `894cafb0-5360-49df-8949-53a63ab9ad02` |
| Graph, Novel | `bodhi_ecg_894cafb0_novel_bench_1910` |
| Graph, Medical | `bodhi_ecg_894cafb0_medical_bench_1910` |
| Generation model | `gpt-4o-mini`, temperature 0.7 (set in the request) |
| Recommended load | up to 10 parallel requests per subset; one full subset takes about 1.5 h |

Each request is one question in a new conversation (empty `conversation_id`), so no history is carried between
questions. Example:

```bash
curl -s -X POST "https://bodhi-ecg-api.ks.psbodhi.ai/api/v1/workspaces/894cafb0-5360-49df-8949-53a63ab9ad02/chat" \
  -H "Authorization: Bearer $BODHI_API_TOKEN" -H "Content-Type: application/json" \
  -d '{
    "message": "What is the most common type of skin cancer?",
    "conversation_id": "", "session_id": "",
    "graph_name": "bodhi_ecg_894cafb0_medical_bench_1910", "graph_db_type": "falkordb", "algorithm": "bodhi",
    "query_type": "hybrid_search", "answer_style": "concise",
    "model": "gpt-4o-mini", "llm_provider": "openai", "max_cypher_retries": 3, "debug": false,
    "settings": {
      "temperature": 0.7, "max_tokens": 2048, "stream": false,
      "include_context": true, "include_cypher": true,
      "max_context_items": 0, "context_token_budget": 0, "cypher_limit": 50,
      "post_retrieval": {"enabled": true, "dedup": true, "near_dedup": {"enabled": true, "threshold": 0.92},
                         "rerank": {"enabled": true, "top_k": 20, "batch_size": 8},
                         "community_boost": {"enabled": true, "limit": 3}}
    }
  }'
```

Response (fields used for the benchmark):

| Field | Meaning |
|---|---|
| `content` | the answer text (scored as `generated_answer`) |
| `context` | list of `{source, content, relevance_score}`: the retrieved context the answer was generated from |
| `cypher_query` | the graph query generated for the question |
| `query_type`, `response_time_ms`, `llm_tokens_used`, `embedding_tokens_used` | request metadata |

## 3. Reproducing the results

### Setup

1. **Install dependencies:**
   ```bash
   pip install httpx
   ```
2. **Set your access token:**  
   Create a `.env` file in the root of this repo and paste the token provided to you:
   ```env
   BODHI_API_TOKEN=<token_provided_separately>
   ```
   *(Alternatively, run `export BODHI_API_TOKEN=<token>` in your terminal).*

3. **Locate the official questions:**  
   Point to your checkout of [GraphRAG-Bench/GraphRAG-Benchmark](https://github.com/GraphRAG-Bench/GraphRAG-Benchmark):
   `PATH_TO_BENCH=<path_to_GraphRAG-Benchmark_repo>` (questions are in `$PATH_TO_BENCH/Datasets/Questions/`).

---

### Command 1: Quick Test (1 question)

Test API connectivity and output generation on a single question:

* **Novel (1 question):**
  ```bash
  python scripts/run_benchmark.py \
    --subset novel \
    --questions $PATH_TO_BENCH/Datasets/Questions/novel_questions.json \
    --output test_answers_novel.json \
    --limit 1
  ```

* **Medical (1 question):**
  ```bash
  python scripts/run_benchmark.py \
    --subset medical \
    --questions $PATH_TO_BENCH/Datasets/Questions/medical_questions.json \
    --output test_answers_medical.json \
    --limit 1
  ```

---

### Command 2: Full Benchmark Run (Concurrency 10)

Run the complete question sets against the deployed Bodhi-GraphRAG public API. Progress is checkpointed to `<output>.partial.json` continuously; re-running the command automatically resumes:

* **Novel (Full set — 2,010 questions):**
  ```bash
  python scripts/run_benchmark.py \
    --subset novel \
    --questions $PATH_TO_BENCH/Datasets/Questions/novel_questions.json \
    --output answers_novel.json \
    --concurrency 10
  ```

* **Medical (Full set — 2,062 questions):**
  ```bash
  python scripts/run_benchmark.py \
    --subset medical \
    --questions $PATH_TO_BENCH/Datasets/Questions/medical_questions.json \
    --output answers_medical.json \
    --concurrency 10
  ```

---

### Scoring with Official Benchmark Evaluator

The output files (`answers_novel.json` / `answers_medical.json`) are structured as JSON lists matching the exact schema expected by the official evaluation script (`id`, `question`, `question_type`, `ground_truth`, `generated_answer`, `context`).

In your `GraphRAG-Benchmark` checkout, run your official evaluator with your judge key:

```bash
export LLM_API_KEY=<your_openai_or_judge_key>

# Novel scoring
python -m Evaluation.generation_eval \
  --mode API \
  --model gpt-4o-mini \
  --embedding_model BAAI/bge-large-en-v1.5 \
  --data_file <path_to_answers>/answers_novel.json \
  --output_file scores_novel.json \
  --detailed_output

# Medical scoring
python -m Evaluation.generation_eval \
  --mode API \
  --model gpt-4o-mini \
  --embedding_model BAAI/bge-large-en-v1.5 \
  --data_file <path_to_answers>/answers_medical.json \
  --output_file scores_medical.json \
  --detailed_output
```

*(Optional parallel scoring)*: You can also use `scripts/score.sh $PATH_TO_BENCH answers_novel.json scores_novel` to score the 4 categories in parallel.

To average multiple runs:
```bash
python scripts/summarize_scores.py run1/scores_novel run2/scores_novel
```

## 4. System description

Bodhi-GraphRAG is the GraphRAG engine of the Bodhi platform. It builds a knowledge graph from structured data,
data warehouses (through a federated connector) and unstructured documents, and answers natural-language questions
over it. For documents, the graph holds text chunks, entities, typed relationships and LLM-written community
summaries, with vector and full-text indexes.

**Retrieval (hybrid search, the default for documents).** Four legs run per question and are fused with Reciprocal
Rank Fusion: an LLM-generated graph (Cypher) query, vector search over chunks and entities, vector search over
relationships, and BM25 full-text search over chunk text. The fused list is deduplicated and reranked with a
cross-encoder to 20 items.

## 5. Configuration of the reported runs

| Item | Value |
|---|---|
| Answer generation | `gpt-4o-mini`, temperature 0.7, max_tokens 2048 |
| Retrieval embedding model | OpenAI `text-embedding-3-small` (1536 dimensions) |
| Reranker | cross-encoder `cross-encoder/ms-marco-MiniLM-L6-v2` |
| Retrieval legs | vector and relationship-vector: 25 candidates each, Cypher: 50 rows (10 / 10 / 20 for questions worded as broad overviews or creative tasks); BM25 full text: 10 |
| Fusion and context | RRF; near-duplicate removal at 0.92 similarity; rerank to 20 items |
| Evaluation | `Evaluation/generation_eval.py` at commit `fdbab59`, unmodified; `--mode API --model gpt-4o-mini --embedding_model BAAI/bge-large-en-v1.5 --detailed_output`; judge `gpt-4o-mini` through an internal LiteLLM gateway that routes to OpenAI `gpt-4o-mini` |
| Load | 10 parallel requests per subset |

## 6. Notes

- **Judge output parsing.** In `calculate_factuality`, the judge's reply is parsed with `json.loads`. `gpt-4o-mini`
  sometimes starts its reply with `Output:` (following the few-shot format); the parse fails and the answer scores 0
  for factuality without an error. Other replies fail the `ClassificationWithReason` validation and the question is
  dropped from the average. Our scores come from the unmodified code and include both effects.
- **Run-to-run variation.** With sampling at temperature 0.7, the Average of a full run may vary.
- **Load.** Above about 10 parallel requests per subset, a small share of requests may return with part of the
  retrieval missing; we recommend 10.

## 7. Files

| Path | Contents |
|---|---|
| `scripts/run_benchmark.py` | client for the public API; writes answers in the official evaluation input format |
| `scripts/score.sh` | runs the official evaluation script (unmodified) on an answers file |
| `scripts/summarize_scores.py` | per-type and Average scores of one or more runs, and their mean |
| `graphrag_bench_submission/run{1,2}/{novel,medical}/answers.jsonl.gz` | our answers, one line per question: `id`, `source`, `question_type`, `question`, `generated_answer`, `ground_truth`, `retrieved_contexts` (gzipped to adhere to GitHub's 100MB limit) |
| `graphrag_bench_submission/run{1,2}/{novel,medical}/official_eval_output.json.gz` | full detailed output of the official evaluation script (gzipped) |
| `graphrag_bench_submission/run{1,2}/{novel,medical}/summary.json` | per-type scores, other metrics, evaluated counts |

> **Note on `.gz` files:** Because the full logs with detailed multi-hop retrieved contexts across 2,000+ questions exceed GitHub's 100 MB file limit (~123 MB raw), they are compressed using standard gzip (`.gz`, ~28–35 MB). Scripts (`summarize_scores.py`, `score.sh`) read `.gz` transparently. To decompress them locally to plain text at any time, run:  
> `gzip -dk graphrag_bench_submission/*/*/*.gz`
