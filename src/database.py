from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)

_DOMAINS_TABLE = """
CREATE TABLE IF NOT EXISTS domains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain_name TEXT UNIQUE NOT NULL,
    price REAL,
    auction_end_date TEXT,
    registrar TEXT,
    tld TEXT,
    source TEXT,
    dr INTEGER,
    referring_domains INTEGER,
    domain_age INTEGER,
    category TEXT,
    final_score REAL,
    opportunity_grade TEXT,
    trust_score REAL,
    seo_score REAL,
    commercial_score REAL,
    cleanliness_score REAL,
    reason TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""

_PURCHASES_TABLE = """
CREATE TABLE IF NOT EXISTS purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain_name TEXT NOT NULL,
    purchase_price REAL NOT NULL,
    purchase_date TEXT NOT NULL,
    sale_price REAL,
    sale_date TEXT,
    holding_days INTEGER,
    roi REAL,
    notes TEXT
)
"""

_SCRAPE_LOGS_TABLE = """
CREATE TABLE IF NOT EXISTS scrape_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    domains_found INTEGER DEFAULT 0,
    status TEXT NOT NULL,
    message TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def _connect(self) -> aiosqlite.Connection:
        if self._conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = await aiosqlite.connect(str(self.db_path))
            self._conn.row_factory = aiosqlite.Row
        return self._conn

    async def init_db(self) -> None:
        conn = await self._connect()
        for ddl in (_DOMAINS_TABLE, _PURCHASES_TABLE, _SCRAPE_LOGS_TABLE):
            await conn.execute(ddl)
        await conn.commit()
        logger.info("Database initialised at %s", self.db_path)

    # ------------------------------------------------------------------
    # Domain helpers
    # ------------------------------------------------------------------

    async def save_domain(self, domain: dict[str, Any]) -> None:
        conn = await self._connect()
        sql = """INSERT OR REPLACE INTO domains
            (domain_name, price, auction_end_date, registrar, tld, source,
             dr, referring_domains, domain_age, category, final_score,
             opportunity_grade, trust_score, seo_score, commercial_score,
             cleanliness_score, reason)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""
        await conn.execute(sql, _domain_values(domain))
        await conn.commit()

    async def save_domains_batch(self, domains: list[dict[str, Any]]) -> None:
        conn = await self._connect()
        sql = """INSERT OR REPLACE INTO domains
            (domain_name, price, auction_end_date, registrar, tld, source,
             dr, referring_domains, domain_age, category, final_score,
             opportunity_grade, trust_score, seo_score, commercial_score,
             cleanliness_score, reason)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""
        await conn.executemany(sql, [_domain_values(d) for d in domains])
        await conn.commit()
        logger.info("Saved %d domains in batch", len(domains))

    async def get_today_domains(self) -> list[dict[str, Any]]:
        conn = await self._connect()
        today = date.today().isoformat()
        cursor = await conn.execute(
            "SELECT * FROM domains WHERE date(created_at) = ? ORDER BY final_score DESC",
            (today,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_top_domains(self, limit: int = 20) -> list[dict[str, Any]]:
        conn = await self._connect()
        cursor = await conn.execute(
            "SELECT * FROM domains ORDER BY final_score DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Purchase helpers
    # ------------------------------------------------------------------

    async def save_purchase(self, purchase: dict[str, Any]) -> None:
        conn = await self._connect()
        sql = """INSERT INTO purchases
            (domain_name, purchase_price, purchase_date,
             sale_price, sale_date, holding_days, roi, notes)
            VALUES (?,?,?,?,?,?,?,?)"""
        await conn.execute(
            sql,
            (
                purchase["domain_name"],
                purchase["purchase_price"],
                purchase.get("purchase_date", date.today().isoformat()),
                purchase.get("sale_price"),
                purchase.get("sale_date"),
                purchase.get("holding_days"),
                purchase.get("roi"),
                purchase.get("notes"),
            ),
        )
        await conn.commit()

    async def get_all_purchases(self) -> list[dict[str, Any]]:
        conn = await self._connect()
        cursor = await conn.execute("SELECT * FROM purchases ORDER BY purchase_date DESC")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Scrape logging
    # ------------------------------------------------------------------

    async def log_scrape(
        self,
        source: str,
        count: int,
        status: str,
        message: str = "",
    ) -> None:
        conn = await self._connect()
        await conn.execute(
            "INSERT INTO scrape_logs (source, domains_found, status, message) VALUES (?,?,?,?)",
            (source, count, status, message),
        )
        await conn.commit()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
            logger.debug("Database connection closed")


def _domain_values(d: dict[str, Any]) -> tuple[Any, ...]:
    return (
        d.get("domain_name"),
        d.get("price"),
        d.get("auction_end_date"),
        d.get("registrar"),
        d.get("tld"),
        d.get("source"),
        d.get("dr"),
        d.get("referring_domains"),
        d.get("domain_age"),
        d.get("category"),
        d.get("final_score"),
        d.get("opportunity_grade"),
        d.get("trust_score"),
        d.get("seo_score"),
        d.get("commercial_score"),
        d.get("cleanliness_score"),
        d.get("reason"),
    )
