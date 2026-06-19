"""Calibration probe for the off-topic decline floor (A4).

Runs rag_search exactly as the workflow question-branch does (rewrite=True),
for on-topic vs off-topic queries across EN/MSA/Lebanese/Arabizi, and prints
the top similarity so an absolute floor can be chosen.

    docker compose exec -T api python - < scripts/probe_relevance.py
"""
import asyncio
import os
import uuid

from sqlalchemy import text

from api.core.config import get_settings
from api.infra.db import init_db, get_session_factory
import api.domain.tenant  # noqa: F401
from api.infra import embedding_client as emb
from api.services.rag_service import rag_search

TENANT_ID = "4667fd7f-944b-4ea8-bf07-657cf4b4b880"

# (label, lang, variety, query)
PROBES = [
    # ── ON-TOPIC (in KB — must stay ABOVE the floor) ────────────────────────
    ("on", "en", "en", "How much does a commercial building permit cost?"),
    ("on", "en", "en", "When is street cleaning on my street?"),
    ("on", "en", "en", "How do I pay my water bill?"),
    ("on", "en", "en", "How do I get a new water connection?"),
    ("on", "en", "en", "What are the municipality office hours?"),
    ("on", "ar", "msa", "ما هي ساعات عمل البلدية؟"),
    ("on", "ar", "msa", "كيف أحصل على رخصة عمل تجاري؟"),
    ("on", "ar", "lebanese", "شو الخدمات يلي بتقدّمها البلدية؟"),
    ("on", "ar", "lebanese", "بدي اشتراك مياه جديد"),
    ("on", "ar", "arabizi", "kif 2addem talab rokh9et bina?"),
    ("on", "ar", "arabizi", "2eemta bey collecto el nefeyet?"),
    # ── OFF-TOPIC (not in KB — should be DECLINED, i.e. below the floor) ─────
    ("off", "en", "en", "How do I renew my passport?"),
    ("off", "en", "en", "What's the weather tomorrow?"),
    ("off", "en", "en", "Can you help me book a flight to Paris?"),
    ("off", "en", "en", "What is the capital of France?"),
    ("off", "en", "en", "Who won the football match last night?"),
    ("off", "en", "en", "Write me a poem about the sea."),
    ("off", "ar", "msa", "كيف أجدد جواز سفري؟"),
    ("off", "ar", "msa", "ما هي عاصمة فرنسا؟"),
    ("off", "ar", "lebanese", "كيف فيي احجز تذكرة طيارة؟"),
    ("off", "ar", "arabizi", "kif jaded passport tabe3e?"),
]


async def main() -> None:
    settings = get_settings()
    db_url = getattr(settings, "database_url", None) or os.environ["DATABASE_URL"]
    await init_db(db_url)
    await emb.init_embedding_client()

    tenant = uuid.UUID(TENANT_ID)
    factory = get_session_factory()

    rows = []
    async with factory() as session:
        await session.execute(text(f"SET app.current_tenant = '{TENANT_ID}'"))
        for label, lang, variety, query in PROBES:
            try:
                results = await rag_search(
                    query=query, tenant_id=tenant, session=session,
                    rewrite=False, lang=lang,
                )
                top = results[0].similarity if results else 0.0
                src = results[0].source_title if results else "(none)"
            except Exception as exc:
                top, src = -1.0, f"ERROR {exc}"
            rows.append((label, variety, top, query, src))
        await session.execute(text("RESET app.current_tenant"))

    await emb.close_embedding_client()

    print(f"\n{'lbl':>3}  {'variety':<9} {'top_sim':>8}  query / top_source")
    print("-" * 88)
    for label, variety, top, query, src in rows:
        print(f"{label:>3}  {variety:<9} {top:>8.4f}  {query[:42]:<42} -> {src[:24]}")

    ons = [t for l, _, t, _, _ in rows if l == "on" and t >= 0]
    offs = [t for l, _, t, _, _ in rows if l == "off" and t >= 0]
    print("-" * 88)
    if ons:
        print(f"ON-TOPIC : min={min(ons):.4f}  max={max(ons):.4f}  n={len(ons)}")
    if offs:
        print(f"OFF-TOPIC: min={min(offs):.4f}  max={max(offs):.4f}  n={len(offs)}")
    if ons and offs:
        print(f"GAP: lowest on-topic={min(ons):.4f}  vs  highest off-topic={max(offs):.4f}")


asyncio.run(main())
