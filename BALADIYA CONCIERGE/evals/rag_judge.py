"""RAG LLM-judge: faithfulness & answer-relevancy on the golden set (A3).

RAGAS-style. For each golden triple:
  1. retrieve top-k chunks from the tenant KB (rag_service.rag_search),
  2. generate an answer grounded in those chunks (llm_client.complete_text),
  3. judge:
       faithfulness      — are the answer's claims supported by the retrieved context?
       answer_relevancy  — does the answer actually address the question?

Judge + generator use the app's Gemini→Groq fallback. While Gemini's free-tier
quota is exhausted, both run on Groq llama-3.3-70b (self-evaluation — documented
caveat in DECISIONS.md §D-RAG-002). Run in the api container:

    docker compose exec -T api python - < evals/rag_judge.py

Reports per-triple and aggregate faithfulness / answer_relevancy so non-zero
thresholds can be set in eval_thresholds.yaml (measured − buffer).
"""
import asyncio
import json
import os
import re
import uuid
from pathlib import Path

from sqlalchemy import text

from api.core.config import get_settings
from api.infra.db import init_db, get_session_factory
import api.domain.tenant  # noqa: F401
from api.infra import embedding_client as emb
from api.infra import llm_client
from api.services.rag_service import rag_search

TENANT_ID = "4667fd7f-944b-4ea8-bf07-657cf4b4b880"  # Beirut (full KB)
GOLDEN_PATH = Path(os.environ.get("GOLDEN_JSON", "/app/evals/rag_golden.json"))
TOP_K = 5

_ANSWER_SYS = (
    "You are a municipal civic assistant. Answer the resident's question using ONLY the "
    "provided context. If the context does not contain the answer, say you do not have "
    "that information. Be concise. Reply in the same language as the question."
)

_FAITHFULNESS_SYS = (
    "You are a strict evaluator of factual grounding. Given a CONTEXT and an ANSWER, decide "
    "what fraction of the factual claims in the ANSWER are directly supported by the CONTEXT. "
    "An answer that correctly says the information is unavailable is fully faithful (1.0). "
    "Hallucinated or unsupported claims lower the score. "
    'Respond ONLY with JSON: {"score": <0.0-1.0>, "reason": "<short>"}'
)

_RELEVANCY_SYS = (
    "You are a strict evaluator of answer relevancy. Given a QUESTION and an ANSWER, decide "
    "how directly and completely the ANSWER addresses the QUESTION (ignore factual accuracy). "
    "A non-answer or off-topic reply scores low; a focused, on-topic reply scores high. "
    'Respond ONLY with JSON: {"score": <0.0-1.0>, "reason": "<short>"}'
)


def _parse_score(raw: str) -> float:
    """Extract a 0..1 score from a JSON-ish judge reply; -1.0 on failure."""
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            val = float(json.loads(m.group(0)).get("score", -1.0))
            return max(0.0, min(1.0, val))
        except Exception:
            pass
    m = re.search(r'"?score"?\s*[:=]\s*([01](?:\.\d+)?)', raw)
    return max(0.0, min(1.0, float(m.group(1)))) if m else -1.0


async def generate_answer(question: str, contexts: list[str]) -> str:
    """Generate a grounded RAG answer from retrieved contexts (Gemini→Groq)."""
    ctx = "\n\n".join(contexts) if contexts else "(no relevant context found)"
    return await llm_client.complete_text(
        _ANSWER_SYS, f"Context:\n{ctx}\n\nQuestion: {question}\n\nAnswer:", max_tokens=400
    )


async def judge_faithfulness(answer: str, contexts: list[str]) -> float:
    """LLM-judge: fraction of the answer's claims supported by the contexts (0..1)."""
    ctx = "\n\n".join(contexts) if contexts else "(no context)"
    return _parse_score(await llm_client.complete_text(
        _FAITHFULNESS_SYS, f"CONTEXT:\n{ctx}\n\nANSWER:\n{answer}", max_tokens=200
    ))


async def judge_relevancy(question: str, answer: str) -> float:
    """LLM-judge: how directly the answer addresses the question (0..1)."""
    return _parse_score(await llm_client.complete_text(
        _RELEVANCY_SYS, f"QUESTION:\n{question}\n\nANSWER:\n{answer}", max_tokens=200
    ))


async def main() -> None:
    settings = get_settings()
    db_url = getattr(settings, "database_url", None) or os.environ["DATABASE_URL"]
    await init_db(db_url)
    await emb.init_embedding_client()

    data = json.loads(GOLDEN_PATH.read_text())
    triples = [t for t in data["triples"] if "source_entry" in t]  # canonical n=8 subset

    tenant = uuid.UUID(TENANT_ID)
    factory = get_session_factory()
    rows = []

    async with factory() as session:
        await session.execute(text(f"SET app.current_tenant = '{TENANT_ID}'"))
        for t in triples:
            q, lang = t["question"], t.get("lang", "en")
            results = await rag_search(query=q, tenant_id=tenant, session=session,
                                       top_k=TOP_K, rewrite=True, lang=lang)
            contexts = [r.chunk_text for r in results]
            answer = await generate_answer(q, contexts)
            faith = await judge_faithfulness(answer, contexts)
            rel = await judge_relevancy(q, answer)
            rows.append((t["id"], lang, faith, rel, q, answer))
            print(f"  {t['id']} [{lang}] faith={faith:.2f} rel={rel:.2f}  Q={q[:45]}")
        await session.execute(text("RESET app.current_tenant"))

    await emb.close_embedding_client()

    faiths = [f for _, _, f, _, _, _ in rows if f >= 0]
    rels = [r for _, _, _, r, _, _ in rows if r >= 0]
    print("\n" + "=" * 60)
    print(f"n triples judged : {len(rows)}")
    print(f"faithfulness     : mean={sum(faiths)/len(faiths):.4f}  min={min(faiths):.2f}  (valid {len(faiths)}/{len(rows)})")
    print(f"answer_relevancy : mean={sum(rels)/len(rels):.4f}  min={min(rels):.2f}  (valid {len(rels)}/{len(rows)})")


if __name__ == "__main__":
    asyncio.run(main())
