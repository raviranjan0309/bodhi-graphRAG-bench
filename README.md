# Bodhi-GraphRAG on GraphRAG-Bench (Novel and Medical)

**Organization:** `Publicis Sapient` · **Product:** `Bodhi` · **Link:** `https://www.publicissapient.com/platforms/bodhi`

## System description

`Bodhi-GraphRAG` is a hybrid GraphRAG system over a document knowledge graph. Each corpus is indexed into a property graph
of text chunks, entities, typed relationships and community summaries, with vector and full-text indexes. For each
question, an LLM router picks one of four answer paths (lookup, multi-hop, aggregation, ambiguous). Four retrieval
legs run in parallel and are fused with Reciprocal Rank Fusion: an LLM-generated graph (Cypher) query, vector search
over chunks and entities, vector search over relationships, and a BM25-style full-text search. The fused results are
deduplicated and reranked with a cross-encoder to 20 context items, with related community summaries attached. The
answer is generated with the path's prompt and then passed through a short editing step that removes content the
question did not ask for.

## Results

Standard configuration: generation `gpt-4o-mini` at temperature 0.7, judge `gpt-4o-mini`, official evaluation code
unmodified. Scores are `answer_correctness` (%); Average is the mean of the four categories.

| Subset | Fact Retrieval | Complex Reasoning | Contextual Summarize | Creative Generation | Average | Evaluated |
|---|---|---|---|---|---|---|
| Novel | 63.14 | 60.05 | 68.86 | 63.36 | **63.85** | 2,007 / 2,010 |
| Medical | 70.84 | 74.65 | 75.79 | 72.89 | **73.54** | 2,060 / 2,062 |

These include one retry of the questions the judge dropped, with the same code and settings. The first official pass
alone gave Novel 63.90 (2,003 evaluated) and Medical 73.57 (2,059 evaluated).

Evaluated per category. Novel: Fact 969/971, Reasoning 610/610, Summarize 361/362, Creative 67/67.
Medical: Fact 1,098/1,098, Reasoning 508/509, Summarize 289/289, Creative 165/166.

Other metrics:

| Subset | Fact ROUGE | Reasoning ROUGE | Summarize coverage | Creative coverage | Creative faithfulness |
|---|---|---|---|---|---|
| Novel | 49.06 | 34.94 | 39.98 | 36.37 | 32.20 |
| Medical | 50.18 | 35.36 | 47.94 | 46.35 | 41.31 |

**Not evaluated (judge output failed validation on the first pass and on the retry):**

| Question id | Category | Error |
|---|---|---|
| Novel-e9c535e5 | Fact Retrieval | pydantic `ValidationError` for `ClassificationWithReason` |
| Novel-a116a662 | Fact Retrieval | pydantic `ValidationError` for `ClassificationWithReason` |
| Novel-b08051d8 | Contextual Summarize | 2 validation errors for `ClassificationWithReason` |
| Medical-6ac9b753 | Complex Reasoning | 2 validation errors for `ClassificationWithReason` |
| Medical-bf68d23e | Creative Generation | 9 validation errors for `ClassificationWithReason` |

Our answers to these questions are included in the answers files.

## Configuration

**Generation and retrieval**

| Item | Value |
|---|---|
| Answer generation | `gpt-4o-mini`, temperature 0.7, max_tokens 2048 |
| Cypher generation / query classification | OpenAI `gpt-4o-mini` |
| Retrieval embedding model | OpenAI `text-embedding-3-small` (1536 dimensions) |
| Reranker | cross-encoder `ms-marco-MiniLM-L6-v2`, final context of 20 items |
| Retrieval legs | vector, relationship-vector and full-text: 10 candidates each (vector and relationship-vector 25 for lookup / multi-hop questions); Cypher: 20 rows (50 for lookup / multi-hop) |
| Fusion and filtering | Reciprocal Rank Fusion; vector similarity floor 0.18; near-duplicate removal at 0.92 similarity; up to 3 community summaries |
| Context | 20 items per question, about 12K tokens; no conversation history; questions sent verbatim |
| Indexing | chunks of up to 512 tokens (minimum 256, overlap 64) |

**Evaluation**

| Item | Value |
|---|---|
| Code | `GraphRAG-Bench/GraphRAG-Benchmark` commit `fdbab59`, `Evaluation/generation_eval.py`, unmodified |
| Command | `--mode API --model gpt-4o-mini --embedding_model BAAI/bge-large-en-v1.5 --detailed_output` |
| Judge | `gpt-4o-mini` via an internal LiteLLM gateway that routes to OpenAI `gpt-4o-mini`; official prompts and parameters unchanged |
| Questions | current official `novel_questions.json` (2,010) and `medical_questions.json` (2,062), unmodified; all answered |
| Evaluated counts | Novel 2,007 / 2,010, Medical 2,060 / 2,062 |

## Files

| File | Contents |
|---|---|
| `graphrag_bench_submission/novel/answers.jsonl`, `graphrag_bench_submission/medical/answers.jsonl` | One line per question: `id`, `source`, `question_type`, `question`, `generated_answer`, `ground_truth`, `retrieved_contexts` |
| `graphrag_bench_submission/novel/official_eval_output.json`, `graphrag_bench_submission/medical/official_eval_output.json` | Full detailed output of the official evaluation script (first pass) |
| `graphrag_bench_submission/novel/official_eval_output_retry.json`, `graphrag_bench_submission/medical/official_eval_output_retry.json` | Output of the retry of dropped questions |

