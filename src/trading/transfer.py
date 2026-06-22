"""
Domain Transfer — Handle domain registrar transfers.
Manages the process of moving domains between registrars.

Flow:
1. Seller unlocks domain + provides EPP/auth code
2. Buyer initiates transfer at their registrar
3. Domain moves to buyer's account
4. Both parties confirm
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

TRANSFER_FILE = Path("data/transfers.json")


class TransferStatus(str, Enum):
    PENDING = "pending"
    UNLOCKED = "unlocked"
    EPP_PROVIDED = "epp_provided"
    TRANSFER_INITIATED = "transfer_initiated"
    TRANSFER_PENDING = "transfer_pending"  # Waiting for registrar
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TransferMethod(str, Enum):
    REGISTRAR_TO_REGISTRAR = "registrar_to_registrar"
    PUSH_TRANSFER = "push_transfer"  # Within same registrar
    CHANGE_OWNERSHIP = "change_ownership"


@dataclass
class DomainTransferRecord:
    transfer_id: str
    domain: str
    from_registrar: str
    to_registrar: str
    from_account: str
    to_account: str
    transfer_method: str = TransferMethod.REGISTRAR_TO_REGISTRAR
    status: str = TransferStatus.PENDING
    epp_code: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    unlocked_at: str = ""
    initiated_at: str = ""
    completed_at: str = ""
    transfer_proof: str = ""  # TX/receipt hash
    notes: str = ""


class DomainTransfer:
    """
    Manages domain transfers between parties.
    
    Steps:
    1. Seller unlocks domain at their registrar
    2. Seller provides EPP/authorization code
    3. Buyer initiates transfer at their registrar
    4. Registrar processes transfer (5-7 days for .com)
    5. Domain appears in buyer's account
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger("DomainTransfer")
        self.transfers: dict[str, DomainTransferRecord] = {}
        self._load_transfers()

    def _load_transfers(self) -> None:
        """Load saved transfers from disk."""
        if TRANSFER_FILE.exists():
            try:
                data = json.loads(TRANSFER_FILE.read_text())
                for tid, info in data.items():
                    self.transfers[tid] = DomainTransferRecord(**info)
                self.logger.info("Loaded %d transfers", len(self.transfers))
            except Exception as e:
                self.logger.warning("Failed to load transfers: %s", e)

    def _save_transfers(self) -> None:
        """Persist transfers to disk."""
        TRANSFER_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        for tid, transfer in self.transfers.items():
            data[tid] = {
                "transfer_id": transfer.transfer_id,
                "domain": transfer.domain,
                "from_registrar": transfer.from_registrar,
                "to_registrar": transfer.to_registrar,
                "from_account": transfer.from_account,
                "to_account": transfer.to_account,
                "transfer_method": transfer.transfer_method,
                "status": transfer.status,
                "epp_code": transfer.epp_code,
                "created_at": transfer.created_at,
                "unlocked_at": transfer.unlocked_at,
                "initiated_at": transfer.initiated_at,
                "completed_at": transfer.completed_at,
                "transfer_proof": transfer.transfer_proof,
                "notes": transfer.notes,
            }
        TRANSFER_FILE.write_text(json.dumps(data, indent=2))

    async def initiate_transfer(
        self,
        domain: str,
        from_registrar: str,
        to_registrar: str,
        from_account: str,
        to_account: str,
        transfer_method: str = TransferMethod.REGISTRAR_TO_REGISTRAR,
    ) -> DomainTransferRecord:
        """
        Create a new transfer request.
        """
        transfer_id = secrets.token_hex(8)

        record = DomainTransferRecord(
            transfer_id=transfer_id,
            domain=domain,
            from_registrar=from_registrar,
            to_registrar=to_registrar,
            from_account=from_account,
            to_account=to_account,
            transfer_method=transfer_method,
        )

        self.transfers[transfer_id] = record
        self._save_transfers()

        self.logger.info(
            "Transfer %s initiated for %s: %s -> %s",
            transfer_id[:8],
            domain,
            from_registrar,
            to_registrar,
        )

        return record

    async def set_epp_code(
        self,
        transfer_id: str,
        epp_code: str,
    ) -> bool:
        """
        Seller provides EPP/authorization code.
        """
        record = self.transfers.get(transfer_id)
        if not record:
            return False

        record.epp_code = epp_code
        record.status = TransferStatus.EPP_PROVIDED
        self._save_transfers()

        self.logger.info(
            "Transfer %s: EPP code provided for %s",
            transfer_id[:8],
            record.domain,
        )
        return True

    async def unlock_domain(self, transfer_id: str) -> bool:
        """
        Seller unlocks domain at registrar.
        """
        record = self.transfers.get(transfer_id)
        if not record:
            return False

        record.status = TransferStatus.UNLOCKED
        record.unlocked_at = datetime.now(timezone.utc).isoformat()
        self._save_transfers()

        self.logger.info(
            "Transfer %s: Domain %s unlocked",
            transfer_id[:8],
            record.domain,
        )
        return True

    async def start_transfer(self, transfer_id: str) -> dict:
        """
        Buyer initiates transfer at their registrar using EPP code.
        """
        record = self.transfers.get(transfer_id)
        if not record:
            return {"success": False, "error": "Transfer not found"}

        if record.status != TransferStatus.EPP_PROVIDED:
            return {
                "success": False,
                "error": f"Transfer in wrong state: {record.status}",
            }

        # Validate EPP code format
        if not record.epp_code or len(record.epp_code) < 6:
            return {"success": False, "error": "Invalid EPP code"}

        record.status = TransferStatus.TRANSFER_INITIATED
        record.initiated_at = datetime.now(timezone.utc).isoformat()
        self._save_transfers()

        self.logger.info(
            "Transfer %s: Transfer initiated for %s at %s",
            transfer_id[:8],
            record.domain,
            record.to_registrar,
        )

        return {
            "success": True,
            "transfer_id": transfer_id,
            "domain": record.domain,
            "estimated_completion": "5-7 business days",
            "status": "Transfer initiated — waiting for registrar processing",
        }

    async def check_transfer_status(self, transfer_id: str) -> dict:
        """
        Check current transfer status.
        In production: polls registrar API.
        """
        record = self.transfers.get(transfer_id)
        if not record:
            return {"error": "Transfer not found"}

        return {
            "transfer_id": transfer_id,
            "domain": record.domain,
            "status": record.status,
            "from_registrar": record.from_registrar,
            "to_registrar": record.to_registrar,
            "initiated_at": record.initiated_at,
            "estimated_completion": "5-7 business days",
        }

    async def complete_transfer(
        self,
        transfer_id: str,
        transfer_proof: str = "",
    ) -> bool:
        """
        Mark transfer as completed.
        Called when domain appears in buyer's account.
        """
        record = self.transfers.get(transfer_id)
        if not record:
            return False

        record.status = TransferStatus.COMPLETED
        record.completed_at = datetime.now(timezone.utc).isoformat()
        record.transfer_proof = transfer_proof
        self._save_transfers()

        self.logger.info(
            "Transfer %s: COMPLETED — %s now in %s account",
            transfer_id[:8],
            record.domain,
            record.to_registrar,
        )
        return True

    async def cancel_transfer(self, transfer_id: str, reason: str = "") -> bool:
        """Cancel a pending transfer."""
        record = self.transfers.get(transfer_id)
        if not record:
            return False

        if record.status in (TransferStatus.COMPLETED, TransferStatus.FAILED):
            return False

        record.status = TransferStatus.CANCELLED
        record.notes = f"Cancelled: {reason}"
        self._save_transfers()

        self.logger.info(
            "Transfer %s cancelled: %s", transfer_id[:8], reason
        )
        return True

    def get_transfer(self, transfer_id: str) -> Optional[DomainTransferRecord]:
        """Get transfer by ID."""
        return self.transfers.get(transfer_id)

    def list_active_transfers(self) -> list[DomainTransferRecord]:
        """List all active transfers."""
        active_states = {
            TransferStatus.PENDING,
            TransferStatus.UNLOCKED,
            TransferStatus.EPP_PROVIDED,
            TransferStatus.TRANSFER_INITIATED,
            TransferStatus.TRANSFER_PENDING,
        }
        return [t for t in self.transfers.values() if t.status in active_states]

    def get_transfer_guide(self, domain: str, registrar: str) -> dict:
        """
        Get step-by-step transfer guide for a specific registrar.
        """
        guides = {
            "godaddy": {
                "steps": [
                    "Log in to GoDaddy Domain Control Center",
                    "Select the domain to transfer",
                    "Toggle 'Domain lock' to Off",
                    "Scroll to 'Additional Settings'",
                    "Click 'Get authorization code'",
                    "Copy the EPP code",
                    "Share EPP code with buyer",
                ],
                "transfer_time": "5-7 business days",
            },
            "namecheap": {
                "steps": [
                    "Log in to Namecheap",
                    "Go to Domain List > Manage",
                    "Toggle 'Domain Lock' to OFF",
                    "Click 'Auth Code' > Get Code",
                    "Copy the EPP code",
                    "Share EPP code with buyer",
                ],
                "transfer_time": "5-7 business days",
            },
            "cloudflare": {
                "steps": [
                    "Log in to Cloudflare Dashboard",
                    "Select the domain",
                    "Go to Registrations > Overview",
                    "Click 'Unlock Domain'",
                    "Click 'Get Authorization Code'",
                    "Copy the EPP code",
                ],
                "transfer_time": "5-7 business days",
            },
            "porkbun": {
                "steps": [
                    "Log in to Porkbun",
                    "Click on the domain",
                    "Toggle 'Registrar Lock' to OFF",
                    "Click 'Get Authorization Code'",
                    "Copy the EPP code",
                ],
                "transfer_time": "5-7 business days",
            },
            "dynadot": {
                "steps": [
                    "Log in to Dynadot",
                    "Go to Domain Management",
                    "Select the domain",
                    "Set 'Transfer Lock' to Unlocked",
                    "Click 'Get Authorization Code'",
                    "Copy the EPP code",
                ],
                "transfer_time": "5-7 business days",
            },
        }

        guide = guides.get(registrar.lower(), {
            "steps": [
                f"Log in to {registrar}",
                "Find domain lock/transfer settings",
                "Unlock the domain",
                "Request authorization/EPP code",
                "Copy and share the code",
            ],
            "transfer_time": "5-7 business days",
        })

        guide["domain"] = domain
        guide["registrar"] = registrar
        return guide

    def get_status(self) -> dict:
        """Get overall transfer status."""
        active = self.list_active_transfers()
        return {
            "total_transfers": len(self.transfers),
            "active_transfers": len(active),
            "transfers": [
                {
                    "id": t.transfer_id[:8],
                    "domain": t.domain,
                    "status": t.status,
                    "from": t.from_registrar,
                    "to": t.to_registrar,
                }
                for t in active
            ],
        }
