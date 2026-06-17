from __future__ import annotations

from typing import Any

import aiosqlite

from src.config import settings

_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        settings.database_path.parent.mkdir(parents=True, exist_ok=True)
        _db = await aiosqlite.connect(str(settings.database_path))
        _db.row_factory = aiosqlite.Row
    return _db


async def get_dashboard_stats() -> dict[str, Any]:
    db = await get_db()

    cursor = await db.execute("SELECT COUNT(*) FROM domains")
    total = (await cursor.fetchone())[0]

    cursor = await db.execute(
        "SELECT COUNT(*) FROM domains WHERE date(created_at) = date('now')"
    )
    today = (await cursor.fetchone())[0]

    cursor = await db.execute("SELECT AVG(final_score) FROM domains")
    avg_score = (await cursor.fetchone())[0] or 0.0

    cursor = await db.execute("SELECT AVG(COALESCE(broker_score, 0)) FROM domains")
    avg_broker = (await cursor.fetchone())[0] or 0.0

    cursor = await db.execute(
        "SELECT domain_name, final_score FROM domains ORDER BY final_score DESC LIMIT 1"
    )
    top = await cursor.fetchone()
    top_domain = {"name": top["domain_name"], "score": top["final_score"]} if top else None

    cursor = await db.execute(
        "SELECT opportunity_grade AS grade, COUNT(*) AS cnt FROM domains WHERE opportunity_grade IS NOT NULL GROUP BY opportunity_grade"
    )
    by_grade = {r["grade"]: r["cnt"] for r in await cursor.fetchall()}

    cursor = await db.execute(
        "SELECT source, COUNT(*) AS cnt FROM domains WHERE source IS NOT NULL GROUP BY source"
    )
    by_source = {r["source"]: r["cnt"] for r in await cursor.fetchall()}

    return {
        "total_domains": total,
        "domains_today": today,
        "avg_final_score": round(avg_score, 2),
        "avg_broker_score": round(avg_broker, 2),
        "top_domain": top_domain,
        "domains_by_grade": by_grade,
        "domains_by_source": by_source,
    }


async def get_domains(
    limit: int = 50,
    offset: int = 0,
    sort_by: str = "final_score",
    order: str = "DESC",
    grade_filter: str | None = None,
    source_filter: str | None = None,
) -> list[dict[str, Any]]:
    db = await get_db()

    safe_sort = {"domain_name", "final_score", "price", "dr", "created_at", "opportunity_grade", "source", "broker_score", "estimated_value", "commission_amount", "buyer_lead_count", "marketplace_listings", "broker_grade"}
    if sort_by not in safe_sort:
        sort_by = "final_score"
    order_dir = "ASC" if order.upper() == "ASC" else "DESC"

    clauses: list[str] = []
    params: list[Any] = []

    if grade_filter:
        clauses.append("opportunity_grade = ?")
        params.append(grade_filter)
    if source_filter:
        clauses.append("source = ?")
        params.append(source_filter)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    sql = (
        "SELECT domain_name, final_score, price, dr, created_at, opportunity_grade, source, "
        "registrar, auction_end_date, tld, "
        "COALESCE(broker_score, 0) as broker_score, "
        "COALESCE(estimated_value, 0) as estimated_value, "
        "COALESCE(commission_amount, 0) as commission_amount, "
        "COALESCE(buyer_lead_count, 0) as buyer_lead_count, "
        "COALESCE(marketplace_listings, '[]') as marketplace_listings, "
        "COALESCE(broker_grade, '') as broker_grade "
        f"FROM domains {where} ORDER BY {sort_by} {order_dir} LIMIT ? OFFSET ?"
    )
    params.extend([limit, offset])

    cursor = await db.execute(sql, params)
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_domain_detail(domain_name: str) -> dict[str, Any] | None:
    db = await get_db()
    cursor = await db.execute(
        "SELECT domain_name, final_score, price, dr, created_at, opportunity_grade, source, "
        "registrar, auction_end_date, tld, "
        "COALESCE(broker_score, 0) as broker_score, "
        "COALESCE(estimated_value, 0) as estimated_value, "
        "COALESCE(commission_amount, 0) as commission_amount, "
        "COALESCE(buyer_lead_count, 0) as buyer_lead_count, "
        "COALESCE(marketplace_listings, '[]') as marketplace_listings, "
        "COALESCE(broker_grade, '') as broker_grade "
        "FROM domains WHERE domain_name = ?", (domain_name,)
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    domain = dict(row)
    cursor = await db.execute(
        "SELECT * FROM outreach WHERE domain_name = ? ORDER BY created_at DESC",
        (domain_name,),
    )
    domain["leads"] = [dict(r) for r in await cursor.fetchall()]
    return domain


async def get_today_domains() -> list[dict[str, Any]]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT domain_name, final_score, price, dr, created_at, opportunity_grade, source, "
        "registrar, auction_end_date, tld, "
        "COALESCE(broker_score, 0) as broker_score, "
        "COALESCE(estimated_value, 0) as estimated_value, "
        "COALESCE(commission_amount, 0) as commission_amount, "
        "COALESCE(buyer_lead_count, 0) as buyer_lead_count, "
        "COALESCE(marketplace_listings, '[]') as marketplace_listings, "
        "COALESCE(broker_grade, '') as broker_grade "
        "FROM domains WHERE date(created_at) = date('now') ORDER BY final_score DESC"
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_top_domains(limit: int = 20) -> list[dict[str, Any]]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT domain_name, final_score, price, dr, created_at, opportunity_grade, source, "
        "registrar, auction_end_date, tld, "
        "COALESCE(broker_score, 0) as broker_score, "
        "COALESCE(estimated_value, 0) as estimated_value, "
        "COALESCE(commission_amount, 0) as commission_amount, "
        "COALESCE(buyer_lead_count, 0) as buyer_lead_count, "
        "COALESCE(marketplace_listings, '[]') as marketplace_listings, "
        "COALESCE(broker_grade, '') as broker_grade "
        "FROM domains ORDER BY final_score DESC LIMIT ?", (limit,)
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_leads(
    status: str | None = None,
    lead_type: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    db = await get_db()
    clauses: list[str] = []
    params: list[Any] = []

    if status:
        clauses.append("status = ?")
        params.append(status)
    if lead_type:
        clauses.append("lead_type = ?")
        params.append(lead_type)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    sql = f"SELECT * FROM outreach {where} ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    cursor = await db.execute(sql, params)
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_lead(lead_id: int) -> dict[str, Any] | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM outreach WHERE id = ?", (lead_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def update_lead_status(
    lead_id: int, status: str, notes: str | None = None
) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE outreach SET status = ?, notes = COALESCE(?, notes), updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (status, notes, lead_id),
    )
    await db.commit()


async def get_leads_by_domain(domain_name: str) -> list[dict[str, Any]]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM outreach WHERE domain_name = ? ORDER BY created_at DESC",
        (domain_name,),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_deals() -> list[dict[str, Any]]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM commission_agreements ORDER BY created_at DESC"
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_all_purchases() -> list[dict[str, Any]]:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM purchases ORDER BY purchase_date DESC")
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_recent_runs(limit: int = 10) -> list[dict[str, Any]]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM scrape_logs ORDER BY created_at DESC LIMIT ?", (limit,)
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def search_domains(query: str, limit: int = 20) -> list[dict[str, Any]]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT domain_name, final_score, price, dr, created_at, opportunity_grade, source, "
        "registrar, auction_end_date, tld, "
        "COALESCE(broker_score, 0) as broker_score, "
        "COALESCE(estimated_value, 0) as estimated_value, "
        "COALESCE(commission_amount, 0) as commission_amount, "
        "COALESCE(buyer_lead_count, 0) as buyer_lead_count, "
        "COALESCE(marketplace_listings, '[]') as marketplace_listings, "
        "COALESCE(broker_grade, '') as broker_grade "
        "FROM domains WHERE domain_name LIKE ? ORDER BY final_score DESC LIMIT ?",
        (f"%{query}%", limit),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]
