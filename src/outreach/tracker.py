from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import aiosqlite

from src.utils import setup_logger

OUTREACH_TABLE = """
CREATE TABLE IF NOT EXISTS outreach (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain_name TEXT NOT NULL,
    lead_type TEXT NOT NULL,
    company TEXT,
    contact_name TEXT,
    contact_title TEXT,
    contact_email TEXT,
    contact_linkedin TEXT,
    template_subject TEXT,
    template_body TEXT,
    status TEXT DEFAULT 'pending',
    message_sent TEXT,
    reply_received TEXT,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""

COMMISSION_TABLE = """
CREATE TABLE IF NOT EXISTS commission_agreements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain_name TEXT NOT NULL,
    buyer_name TEXT,
    buyer_company TEXT,
    seller_name TEXT,
    seller_company TEXT,
    commission_amount REAL,
    commission_rate REAL,
    estimated_value REAL,
    agreement_path TEXT,
    status TEXT DEFAULT 'draft',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""


class OutreachTracker:
    """Track all buyer/seller outreach for domain brokering."""

    def __init__(self, db_path: str = "data/domains.db") -> None:
        self.logger = setup_logger("OutreachTracker")
        self.db_path = Path(db_path)
        self._conn: aiosqlite.Connection | None = None

    async def _connect(self) -> aiosqlite.Connection:
        if self._conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = await aiosqlite.connect(str(self.db_path))
            self._conn.row_factory = aiosqlite.Row
        return self._conn

    async def init_db(self) -> None:
        conn = await self._connect()
        for ddl in (OUTREACH_TABLE, COMMISSION_TABLE):
            await conn.execute(ddl)
        await conn.commit()
        self.logger.info("Outreach tables initialised")

    async def add_lead(
        self,
        domain_name: str,
        lead_type: str,
        company: str,
        contact_name: str = "",
        contact_title: str = "",
        contact_email: str = "",
        contact_linkedin: str = "",
        template_subject: str = "",
        template_body: str = "",
    ) -> int:
        conn = await self._connect()
        cursor = await conn.execute(
            """INSERT INTO outreach
                (domain_name, lead_type, company, contact_name, contact_title,
                 contact_email, contact_linkedin, template_subject, template_body)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                domain_name, lead_type, company, contact_name, contact_title,
                contact_email, contact_linkedin, template_subject, template_body,
            ),
        )
        await conn.commit()
        assert cursor.lastrowid is not None
        return cursor.lastrowid

    async def update_status(
        self,
        lead_id: int,
        status: str,
        message_sent: Optional[str] = None,
        reply_received: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> None:
        conn = await self._connect()
        now = datetime.now(timezone.utc).isoformat()
        await conn.execute(
            """UPDATE outreach
                SET status = ?,
                    message_sent = COALESCE(?, message_sent),
                    reply_received = COALESCE(?, reply_received),
                    notes = COALESCE(?, notes),
                    updated_at = ?
              WHERE id = ?""",
            (status, message_sent, reply_received, notes, now, lead_id),
        )
        await conn.commit()

    async def get_pending(self) -> list[dict[str, Any]]:
        conn = await self._connect()
        cursor = await conn.execute(
            "SELECT * FROM outreach WHERE status IN ('pending', 'sent') ORDER BY created_at DESC",
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_by_domain(self, domain_name: str) -> list[dict[str, Any]]:
        conn = await self._connect()
        cursor = await conn.execute(
            "SELECT * FROM outreach WHERE domain_name = ? ORDER BY created_at DESC",
            (domain_name,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_all(self) -> list[dict[str, Any]]:
        conn = await self._connect()
        cursor = await conn.execute("SELECT * FROM outreach ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def save_agreement(
        self,
        domain_name: str,
        buyer_name: str,
        buyer_company: str,
        seller_name: str,
        seller_company: str,
        commission_amount: float,
        commission_rate: float,
        estimated_value: float,
        agreement_path: str,
    ) -> int:
        conn = await self._connect()
        cursor = await conn.execute(
            """INSERT INTO commission_agreements
                (domain_name, buyer_name, buyer_company, seller_name, seller_company,
                 commission_amount, commission_rate, estimated_value, agreement_path)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                domain_name, buyer_name, buyer_company, seller_name, seller_company,
                commission_amount, commission_rate, estimated_value, agreement_path,
            ),
        )
        await conn.commit()
        assert cursor.lastrowid is not None
        return cursor.lastrowid

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
            self.logger.debug("OutreachTracker connection closed")
