"""
Escrow Manager — On-chain escrow for safe domain trading.
Uses USDC on Base chain. No bank account needed.

Flow:
1. Buyer deposits USDC to escrow contract
2. Seller transfers domain
3. Buyer confirms receipt
4. Escrow releases funds to seller

Disputes are handled by an AI arbiter.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import json

logger = logging.getLogger(__name__)

ESCROW_FILE = Path("data/escrows.json")


class EscrowStatus(str, Enum):
    CREATED = "created"
    DEPOSITED = "deposited"
    DOMAIN_TRANSFERRED = "domain_transferred"
    CONFIRMED = "confirmed"
    DISPUTED = "disputed"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


@dataclass
class EscrowDeal:
    escrow_id: str
    domain: str
    buyer_address: str
    seller_address: str
    amount_usdc: float
    chain: str = "base"
    status: str = EscrowStatus.CREATED
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    deposited_at: str = ""
    transferred_at: str = ""
    confirmed_at: str = ""
    resolved_at: str = ""
    arbiter_notes: str = ""
    domain_transfer_proof: str = ""  # TX hash of domain transfer
    payment_proof: str = ""  # TX hash of USDC transfer


class EscrowManager:
    """
    Manages escrow transactions for domain trades.
    
    In production, this calls the @arbitova MCP server or
    a custom escrow smart contract on Base chain.
    
    For now, simulates escrow with local state.
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger("EscrowManager")
        self.deals: dict[str, EscrowDeal] = {}
        self._load_deals()

    def _load_deals(self) -> None:
        """Load saved deals from disk."""
        if ESCROW_FILE.exists():
            try:
                data = json.loads(ESCROW_FILE.read_text())
                for eid, info in data.items():
                    self.deals[eid] = EscrowDeal(**info)
                self.logger.info("Loaded %d escrow deals", len(self.deals))
            except Exception as e:
                self.logger.warning("Failed to load escrows: %s", e)

    def _save_deals(self) -> None:
        """Persist deals to disk."""
        ESCROW_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        for eid, deal in self.deals.items():
            data[eid] = {
                "escrow_id": deal.escrow_id,
                "domain": deal.domain,
                "buyer_address": deal.buyer_address,
                "seller_address": deal.seller_address,
                "amount_usdc": deal.amount_usdc,
                "chain": deal.chain,
                "status": deal.status,
                "created_at": deal.created_at,
                "deposited_at": deal.deposited_at,
                "transferred_at": deal.transferred_at,
                "confirmed_at": deal.confirmed_at,
                "resolved_at": deal.resolved_at,
                "arbiter_notes": deal.arbiter_notes,
                "domain_transfer_proof": deal.domain_transfer_proof,
                "payment_proof": deal.payment_proof,
            }
        ESCROW_FILE.write_text(json.dumps(data, indent=2))

    async def create_escrow(
        self,
        domain: str,
        buyer_address: str,
        seller_address: str,
        amount_usdc: float,
        chain: str = "base",
    ) -> EscrowDeal:
        """
        Create a new escrow deal.
        Returns the deal with deposit instructions for the buyer.
        """
        escrow_id = secrets.token_hex(8)

        deal = EscrowDeal(
            escrow_id=escrow_id,
            domain=domain,
            buyer_address=buyer_address,
            seller_address=seller_address,
            amount_usdc=amount_usdc,
            chain=chain,
        )

        self.deals[escrow_id] = deal
        self._save_deals()

        self.logger.info(
            "Created escrow %s for %s: %s USDC (buyer=%s, seller=%s)",
            escrow_id[:8],
            domain,
            amount_usdc,
            buyer_address[:10] + "...",
            seller_address[:10] + "...",
        )

        return deal

    async def confirm_deposit(
        self,
        escrow_id: str,
        payment_proof: str = "",
    ) -> bool:
        """
        Confirm buyer has deposited USDC to escrow.
        In production, this checks on-chain balance.
        """
        deal = self.deals.get(escrow_id)
        if not deal:
            self.logger.error("Escrow %s not found", escrow_id)
            return False

        if deal.status != EscrowStatus.CREATED:
            self.logger.warning(
                "Escrow %s in wrong state: %s", escrow_id, deal.status
            )
            return False

        deal.status = EscrowStatus.DEPOSITED
        deal.deposited_at = datetime.now(timezone.utc).isoformat()
        deal.payment_proof = payment_proof
        self._save_deals()

        self.logger.info(
            "Escrow %s deposit confirmed. Seller can now transfer domain.",
            escrow_id[:8],
        )
        return True

    async def confirm_domain_transfer(
        self,
        escrow_id: str,
        domain_transfer_proof: str = "",
    ) -> bool:
        """
        Seller confirms they've transferred the domain.
        """
        deal = self.deals.get(escrow_id)
        if not deal:
            return False

        if deal.status != EscrowStatus.DEPOSITED:
            self.logger.warning(
                "Escrow %s not in deposited state: %s", escrow_id, deal.status
            )
            return False

        deal.status = EscrowStatus.DOMAIN_TRANSFERRED
        deal.transferred_at = datetime.now(timezone.utc).isoformat()
        deal.domain_transfer_proof = domain_transfer_proof
        self._save_deals()

        self.logger.info(
            "Escrow %s: Domain transfer confirmed. Awaiting buyer confirmation.",
            escrow_id[:8],
        )
        return True

    async def confirm_receipt(self, escrow_id: str) -> dict:
        """
        Buyer confirms they received the domain.
        This releases funds to the seller.
        """
        deal = self.deals.get(escrow_id)
        if not deal:
            return {"success": False, "error": "Escrow not found"}

        if deal.status != EscrowStatus.DOMAIN_TRANSFERRED:
            return {"success": False, "error": "Domain not yet transferred"}

        deal.status = EscrowStatus.CONFIRMED
        deal.confirmed_at = datetime.now(timezone.utc).isoformat()
        self._save_deals()

        # In production: call smart contract to release funds
        release_result = await self._release_funds(deal)

        self.logger.info(
            "Escrow %s: Funds released to seller (%s USDC)",
            escrow_id[:8],
            deal.amount_usdc,
        )

        return {
            "success": True,
            "escrow_id": escrow_id,
            "amount_released": deal.amount_usdc,
            "seller_address": deal.seller_address,
            "release_tx": release_result.get("tx_hash", ""),
        }

    async def dispute(
        self,
        escrow_id: str,
        reason: str,
        raised_by: str,
    ) -> dict:
        """
        Raise a dispute. AI arbiter will resolve.
        """
        deal = self.deals.get(escrow_id)
        if not deal:
            return {"success": False, "error": "Escrow not found"}

        deal.status = EscrowStatus.DISPUTED
        deal.arbiter_notes = f"Dispute by {raised_by}: {reason}"
        self._save_deals()

        self.logger.warning(
            "Escrow %s: Dispute raised by %s — %s",
            escrow_id[:8],
            raised_by,
            reason,
        )

        # In production: call @arbitova MCP for AI arbitration
        resolution = await self._resolve_dispute(deal, reason, raised_by)

        return {
            "success": True,
            "escrow_id": escrow_id,
            "resolution": resolution,
        }

    async def cancel_escrow(self, escrow_id: str, reason: str = "") -> bool:
        """
        Cancel escrow and refund buyer.
        """
        deal = self.deals.get(escrow_id)
        if not deal:
            return False

        if deal.status not in (EscrowStatus.CREATED, EscrowStatus.DEPOSITED):
            self.logger.warning(
                "Cannot cancel escrow %s in state %s", escrow_id, deal.status
            )
            return False

        deal.status = EscrowStatus.CANCELLED
        deal.arbiter_notes = f"Cancelled: {reason}"
        self._save_deals()

        # In production: refund buyer's USDC
        if deal.status == EscrowStatus.DEPOSITED:
            await self._refund_buyer(deal)

        self.logger.info("Escrow %s cancelled: %s", escrow_id[:8], reason)
        return True

    async def check_timeout(self, escrow_id: str) -> bool:
        """
        Check if escrow has timed out (72 hours default).
        Auto-refund if timed out.
        """
        deal = self.deals.get(escrow_id)
        if not deal:
            return False

        if deal.status not in (
            EscrowStatus.DEPOSITED,
            EscrowStatus.DOMAIN_TRANSFERRED,
        ):
            return False

        created = datetime.fromisoformat(deal.created_at)
        now = datetime.now(timezone.utc)
        hours_elapsed = (now - created).total_seconds() / 3600

        if hours_elapsed > 72:
            deal.status = EscrowStatus.TIMED_OUT
            deal.arbiter_notes = f"Timed out after {hours_elapsed:.1f} hours"
            self._save_deals()

            # Refund buyer
            if deal.status == EscrowStatus.DEPOSITED:
                await self._refund_buyer(deal)

            self.logger.warning(
                "Escrow %s timed out after %.1f hours", escrow_id[:8], hours_elapsed
            )
            return True

        return False

    async def _release_funds(self, deal: EscrowDeal) -> dict:
        """
        Release funds from escrow to seller.
        In production: calls smart contract on Base chain.
        """
        # Simulated TX hash
        tx_hash = f"0x{secrets.token_hex(32)}"
        self.logger.info(
            "Released %s USDC to %s (tx: %s)",
            deal.amount_usdc,
            deal.seller_address[:10] + "...",
            tx_hash[:10] + "...",
        )
        return {"tx_hash": tx_hash, "amount": deal.amount_usdc}

    async def _refund_buyer(self, deal: EscrowDeal) -> dict:
        """Refund USDC to buyer."""
        tx_hash = f"0x{secrets.token_hex(32)}"
        self.logger.info(
            "Refunded %s USDC to %s (tx: %s)",
            deal.amount_usdc,
            deal.buyer_address[:10] + "...",
            tx_hash[:10] + "...",
        )
        return {"tx_hash": tx_hash, "amount": deal.amount_usdc}

    async def _resolve_dispute(
        self,
        deal: EscrowDeal,
        reason: str,
        raised_by: str,
    ) -> str:
        """
        AI arbitration for disputes.
        In production: calls @arbitova MCP server.
        """
        # Simple heuristic for now
        if "domain not received" in reason.lower():
            return "REFUND_BUYER"
        elif "domain is different" in reason.lower():
            return "REFUND_BUYER"
        elif "buyer didn't pay" in reason.lower():
            return "RELEASE_TO_SELLER"
        else:
            return "ESCALATE_TO_HUMAN"

    def get_deal(self, escrow_id: str) -> Optional[EscrowDeal]:
        """Get escrow deal by ID."""
        return self.deals.get(escrow_id)

    def list_active_deals(self) -> list[EscrowDeal]:
        """List all active (non-terminal) deals."""
        active_states = {
            EscrowStatus.CREATED,
            EscrowStatus.DEPOSITED,
            EscrowStatus.DOMAIN_TRANSFERRED,
        }
        return [d for d in self.deals.values() if d.status in active_states]

    def get_status(self) -> dict:
        """Get overall escrow status."""
        active = self.list_active_deals()
        return {
            "total_deals": len(self.deals),
            "active_deals": len(active),
            "total_escrowed_usdc": sum(d.amount_usdc for d in active),
            "deals": [
                {
                    "id": d.escrow_id[:8],
                    "domain": d.domain,
                    "amount": d.amount_usdc,
                    "status": d.status,
                }
                for d in active
            ],
        }
