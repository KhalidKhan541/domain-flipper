"""
Wallet Manager — Create and manage crypto wallets for domain trading.
No bank account needed. Supports Coinbase Wallet, Phantom (Solana), MetaMask.
"""

from __future__ import annotations

import logging
import os
import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

WALLET_FILE = Path("data/wallets.json")


@dataclass
class WalletInfo:
    wallet_id: str
    wallet_type: str  # "coinbase" | "phantom" | "metamask"
    chain: str  # "base" | "ethereum" | "solana"
    address: str
    balance_usdc: float = 0.0
    balance_native: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    is_primary: bool = False
    notes: str = ""


class WalletManager:
    """
    Manages crypto wallets for receiving domain sale payments.
    
    Flow:
    1. Create/load wallet
    2. Receive USDC from buyer via escrow
    3. Pay seller from escrow
    4. Cash out via P2P exchange
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger("WalletManager")
        self.wallets: dict[str, WalletInfo] = {}
        self._load_wallets()

    def _load_wallets(self) -> None:
        """Load saved wallets from disk."""
        if WALLET_FILE.exists():
            try:
                data = json.loads(WALLET_FILE.read_text())
                for wid, info in data.items():
                    self.wallets[wid] = WalletInfo(**info)
                self.logger.info("Loaded %d wallets", len(self.wallets))
            except Exception as e:
                self.logger.warning("Failed to load wallets: %s", e)

    def _save_wallets(self) -> None:
        """Persist wallets to disk."""
        WALLET_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        for wid, wallet in self.wallets.items():
            data[wid] = {
                "wallet_id": wallet.wallet_id,
                "wallet_type": wallet.wallet_type,
                "chain": wallet.chain,
                "address": wallet.address,
                "balance_usdc": wallet.balance_usdc,
                "balance_native": wallet.balance_native,
                "created_at": wallet.created_at,
                "is_primary": wallet.is_primary,
                "notes": wallet.notes,
            }
        WALLET_FILE.write_text(json.dumps(data, indent=2))
        self.logger.info("Saved %d wallets", len(self.wallets))

    def create_wallet(
        self,
        wallet_type: str = "coinbase",
        chain: str = "base",
        notes: str = "",
    ) -> WalletInfo:
        """
        Create a new wallet.
        
        In production, this would call Coinbase/Phantom SDK.
        For now, generates a placeholder address.
        """
        import hashlib
        import secrets

        # Generate deterministic wallet ID
        seed = secrets.token_hex(16)
        wallet_id = hashlib.sha256(seed.encode()).hexdigest()[:12]

        # Placeholder address (real implementation uses wallet SDK)
        prefix = "0x" if chain != "solana" else ""
        address = f"{prefix}{secrets.token_hex(20)}" if chain != "solana" else secrets.token_hex(32)

        wallet = WalletInfo(
            wallet_id=wallet_id,
            wallet_type=wallet_type,
            chain=chain,
            address=address,
            notes=notes,
            is_primary=len(self.wallets) == 0,
        )

        self.wallets[wallet_id] = wallet
        self._save_wallets()

        self.logger.info(
            "Created %s wallet on %s: %s",
            wallet_type,
            chain,
            address[:10] + "...",
        )
        return wallet

    def get_primary_wallet(self) -> Optional[WalletInfo]:
        """Get the primary wallet for receiving payments."""
        for wallet in self.wallets.values():
            if wallet.is_primary:
                return wallet
        return None

    def get_wallet(self, wallet_id: str) -> Optional[WalletInfo]:
        """Get wallet by ID."""
        return self.wallets.get(wallet_id)

    def list_wallets(self) -> list[WalletInfo]:
        """List all wallets."""
        return list(self.wallets.values())

    def set_primary(self, wallet_id: str) -> bool:
        """Set a wallet as primary."""
        if wallet_id not in self.wallets:
            return False
        for w in self.wallets.values():
            w.is_primary = False
        self.wallets[wallet_id].is_primary = True
        self._save_wallets()
        return True

    def update_balance(self, wallet_id: str, usdc: float, native: float) -> bool:
        """Update wallet balance (called after transactions)."""
        if wallet_id not in self.wallets:
            return False
        self.wallets[wallet_id].balance_usdc = usdc
        self.wallets[wallet_id].balance_native = native
        self._save_wallets()
        return True

    def get_receive_address(self, wallet_id: str) -> Optional[str]:
        """Get the public address for receiving payments."""
        wallet = self.wallets.get(wallet_id)
        return wallet.address if wallet else None

    def generate_payment_request(
        self,
        amount_usdc: float,
        memo: str = "",
    ) -> dict:
        """
        Generate a payment request for a buyer.
        Returns address + amount for the buyer to send to.
        """
        wallet = self.get_primary_wallet()
        if not wallet:
            wallet = self.create_wallet()

        return {
            "wallet_id": wallet.wallet_id,
            "chain": wallet.chain,
            "address": wallet.address,
            "amount_usdc": amount_usdc,
            "memo": memo,
            "expires_in": "30 minutes",
            "instructions": (
                f"Send exactly {amount_usdc} USDC to:\n"
                f"Address: {wallet.address}\n"
                f"Network: {wallet.chain}\n"
                f"Token: USDC\n"
                f"Memo: {memo}"
            ),
        }

    def get_status(self) -> dict:
        """Get overall wallet status."""
        primary = self.get_primary_wallet()
        total_usdc = sum(w.balance_usdc for w in self.wallets.values())
        return {
            "wallet_count": len(self.wallets),
            "primary_wallet": primary.wallet_id if primary else None,
            "primary_address": primary.address if primary else None,
            "total_usdc": total_usdc,
            "wallets": [
                {
                    "id": w.wallet_id,
                    "type": w.wallet_type,
                    "chain": w.chain,
                    "balance_usdc": w.balance_usdc,
                }
                for w in self.wallets.values()
            ],
        }
