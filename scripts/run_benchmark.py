"""Answer GraphRAG-Bench questions with the public Bodhi-GraphRAG API.

Sends every question to the chat endpoint as its own new conversation (no history), with the benchmark's standard
generation settings (gpt-4o-mini, temperature 0.7), and writes a JSON list that the official evaluation script
(`Evaluation/generation_eval.py`) reads directly: id, question, question_type, ground_truth, generated_answer, context.

Usage:
    export BODHI_API_TOKEN=<token>            # sent as "Authorization: Bearer <token>"
    python scripts/run_benchmark.py --subset novel   --questions Datasets/Questions/novel_questions.json   --output answers_novel.json
    python scripts/run_benchmark.py --subset medical --questions Datasets/Questions/medical_questions.json --output answers_medical.json

Progress is checkpointed to <output>.partial.json every few answers; re-running the same command resumes from it.
Requires Python 3.9+ and httpx (`pip install httpx`).
"""
import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

import httpx

BASE_URL = "https://bodhi-ecg-api.ks.psbodhi.ai"
WORKSPACE_ID = "894cafb0-5360-49df-8949-53a63ab9ad02"
GRAPHS = {"novel": "bodhi_ecg_894cafb0_novel_bench_1910", "medical": "bodhi_ecg_894cafb0_medical_bench_1910"}


def request_body(question: str, graph_name: str) -> dict:
    """The exact request used for the reported results."""
    return {
        "message": question,
        "conversation_id": "",          # empty = a new conversation for every question (no history)
        "session_id": "",
        "graph_name": graph_name,
        "graph_db_type": "falkordb",
        "algorithm": "bodhi",
        "query_type": "hybrid_search",
        "answer_style": "concise",
        "model": "gpt-4o-mini",
        "llm_provider": "openai",
        "max_cypher_retries": 3,
        "debug": False,
        "settings": {
            "temperature": 0.7,
            "max_tokens": 2048,
            "stream": False,
            "include_context": True,
            "include_cypher": True,
            "max_context_items": 0,
            "context_token_budget": 0,
            "cypher_limit": 50,
            "post_retrieval": {
                "enabled": True,
                "dedup": True,
                "near_dedup": {"enabled": True, "threshold": 0.92},
                "rerank": {"enabled": True, "top_k": 20, "batch_size": 8},
                "community_boost": {"enabled": True, "limit": 3},
            },
        },
    }


async def ask(client: httpx.AsyncClient, url: str, headers: dict, q: dict, graph: str, retries: int = 4) -> dict:
    record = {"id": q["id"], "source": q.get("source", ""), "question": q["question"], "question_type": q["question_type"],
              "ground_truth": q["answer"], "generated_answer": "", "context": [], "http_status": None, "error": None}
    for attempt in range(1, retries + 1):
        t0 = time.perf_counter()
        try:
            r = await client.post(url, headers=headers, json=request_body(q["question"], graph), timeout=500.0)
            record["http_status"] = r.status_code
            if 400 <= r.status_code < 500:
                record["error"] = f"HTTP {r.status_code}: {r.text[:300]}"
                return record                      # auth / payload problem: retrying will not help
            r.raise_for_status()
            p = r.json()
            record.update(generated_answer=(p.get("content") or "").strip(),
                          context=[str(c.get("content", "")) if isinstance(c, dict) else str(c) for c in (p.get("context") or [])],
                          cypher_query=p.get("cypher_query"), latency_seconds=round(time.perf_counter() - t0, 2), error=None)
            return record
        except Exception as exc:  # noqa: BLE001 - network errors and 5xx are retried
            record["error"] = f"{type(exc).__name__}: {exc}"[:300]
            await asyncio.sleep(3 * attempt)
    return record


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--subset", required=True, choices=sorted(GRAPHS))
    ap.add_argument("--questions", required=True, help="official novel_questions.json / medical_questions.json")
    ap.add_argument("--output", required=True)
    ap.add_argument("--concurrency", type=int, default=10, help="parallel requests (10 is what the reported runs used)")
    ap.add_argument("--base_url", default=BASE_URL)
    ap.add_argument("--workspace_id", default=WORKSPACE_ID)
    ap.add_argument("--graph_name", default=None, help="defaults to the benchmark graph of --subset")
    ap.add_argument("--limit", type=int, default=0, help="answer only the first N questions (for a quick test)")
    a = ap.parse_args()

    # Load from .env if present
    if "BODHI_API_TOKEN" not in os.environ:
        for p in (Path(".env"), Path(__file__).resolve().parent.parent / ".env"):
            if p.exists():
                for line in p.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip())
                break

    token = os.environ.get("BODHI_API_TOKEN")
    if not token:
        sys.exit("Set BODHI_API_TOKEN in your environment or in a .env file (BODHI_API_TOKEN=<token>).")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "accept": "application/json"}

    url = f"{a.base_url.rstrip('/')}/api/v1/workspaces/{a.workspace_id}/chat"
    graph = a.graph_name or GRAPHS[a.subset]

    questions = json.loads(Path(a.questions).read_text(encoding="utf-8"))
    if a.limit:
        questions = questions[: a.limit]
    out, ckpt = Path(a.output), Path(a.output + ".partial.json")
    done = {r["id"]: r for r in json.loads(ckpt.read_text())} if ckpt.exists() else {}
    done = {k: v for k, v in done.items() if v.get("generated_answer")}   # failed ones are asked again
    todo = [q for q in questions if q["id"] not in done]
    print(f"{a.subset}: {len(questions)} questions, {len(done)} already answered, {len(todo)} to ask (concurrency {a.concurrency})")

    sem = asyncio.Semaphore(a.concurrency)
    async with httpx.AsyncClient() as client:
        async def one(q):
            async with sem:
                return await ask(client, url, headers, q, graph)
        n = 0
        for fut in asyncio.as_completed([one(q) for q in todo]):
            rec = await fut
            done[rec["id"]] = rec
            n += 1
            if n % 10 == 0 or n == len(todo):
                ckpt.write_text(json.dumps(list(done.values()), ensure_ascii=False))
                print(f"  {n}/{len(todo)}", flush=True)

    ordered = [done[q["id"]] for q in questions if q["id"] in done]
    failed = [r["id"] for r in ordered if not r.get("generated_answer")]
    out.write_text(json.dumps(ordered, ensure_ascii=False, indent=1))
    print(f"wrote {len(ordered)} answers to {out}; failed (re-run the same command to retry): {len(failed)}")
    if not failed:
        ckpt.unlink(missing_ok=True)


if __name__ == "__main__":
    asyncio.run(main())
