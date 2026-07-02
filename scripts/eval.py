"""Retrieval quality + latency eval harness (docs/PLAN.md §7).

Run against whatever documents are already ingested in this deployment:

    python -m scripts.eval docs/eval_set.example.json
    python -m scripts.eval docs/eval_set.example.json --org-id org_default --with-llm

Re-run this on every change that touches chunking, embeddings, retrieval, or
the model — that's the whole point of having it instead of vibe-checking.

Eval set format (JSON list):
    [{"question": "...", "expected_source": "filename.ext"}, ...]

A question is a "hit" if expected_source appears anywhere in the chunks
retrieved for it (after hybrid search + rerank) — i.e. the final context the
LLM would have been given to answer from.

Groundedness (is every claim in the answer actually cited) isn't checked
automatically here — that's a hard NLP problem in its own right. With
--with-llm, the harness prints each generated answer next to its sources so
you can spot-check it by eye instead.
"""
import argparse
import asyncio
import json
import statistics
import sys
import time

from app.adapters.embeddings.sentence_transformers_embedder import (
    SentenceTransformerEmbedder,
)
from app.adapters.llm.ollama_llm import OllamaLLM
from app.adapters.reranker.cross_encoder_reranker import CrossEncoderReranker
from app.adapters.vectorstore.chroma_store import ChromaVectorStore
from app.services.rag import RagService


def load_eval_set(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


async def run_llm(rag: RagService, messages) -> tuple[str, float, float]:
    t0 = time.perf_counter()
    first_token_at = None
    parts = []
    async for token in rag.llm.stream_chat(messages):
        if first_token_at is None:
            first_token_at = time.perf_counter()
        parts.append(token)
    total = time.perf_counter() - t0
    ttft = (first_token_at - t0) if first_token_at else total
    return "".join(parts), ttft, total


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("eval_set", help="Path to an eval set JSON file")
    parser.add_argument("--org-id", default="org_default")
    parser.add_argument("--with-llm", action="store_true", help="Also time + print full LLM answers")
    args = parser.parse_args()

    cases = load_eval_set(args.eval_set)
    if not cases:
        print("Eval set is empty.")
        sys.exit(1)

    rag = RagService(
        SentenceTransformerEmbedder(), ChromaVectorStore(), OllamaLLM(), CrossEncoderReranker()
    )

    hits = 0
    retrieval_latencies = []
    ttfts, totals = [], []

    for case in cases:
        question, expected_source = case["question"], case["expected_source"]

        t0 = time.perf_counter()
        chunks = rag.retrieve(args.org_id, question)
        retrieval_latencies.append(time.perf_counter() - t0)

        sources = [c.source for c in chunks]
        hit = expected_source in sources
        hits += hit
        print(f"[{'HIT ' if hit else 'MISS'}] {question!r} -> retrieved {sources}")

        if args.with_llm:
            messages, citations = rag.prepare(args.org_id, question)
            answer, ttft, total = await run_llm(rag, messages)
            ttfts.append(ttft)
            totals.append(total)
            print(f"       answer: {answer}")
            print(f"       cited: {[c.source for c in citations]}")

    n = len(cases)
    print("\n--- Summary ---")
    print(f"Retrieval hit-rate: {hits}/{n} ({100 * hits / n:.0f}%)")
    print(f"Retrieval latency: avg {statistics.mean(retrieval_latencies):.2f}s, "
          f"p95 {sorted(retrieval_latencies)[int(0.95 * (n - 1))]:.2f}s")
    if args.with_llm:
        print(f"Time to first token: avg {statistics.mean(ttfts):.2f}s")
        print(f"Total answer time: avg {statistics.mean(totals):.2f}s")


if __name__ == "__main__":
    asyncio.run(main())
