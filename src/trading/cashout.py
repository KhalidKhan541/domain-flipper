"""
Cashout Manager — Convert USDC to local currency via P2P exchanges.
No bank account needed. Works with Binance P2P, Paxful, LocalBitcoins.

Flow:
1. Connect P2P exchange account
2. Create sell order for USDC
3. Buyer sends local currency (bank transfer, UPI, etc.)
4. Release USDC to buyer
5. Receive local currency
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import json

logger = logging.getLogger(__name__)

CASHOUT_FILE = Path("data/cashouts.json")


class CashoutMethod(str, Enum):
    BINANCE_P2P = "binance_p2p"
    PAXFUL = "paxful"
    LOCALBITCOINS = "localbitcoins"
    REMITLY = "remitly"
    WISE = "wise"
    MANUAL = "manual"


class CashoutStatus(str, Enum):
    PENDING = "pending"
    ORDER_CREATED = "order_created"
    BUYER_FOUND = "buyer_found"
    PAYMENT_RECEIVED = "payment_received"
    USDC_RELEASED = "usdc_released"
    COMPLETED = "completed"
    DISPUTED = "disputed"
    CANCELLED = "cancelled"


@dataclass
class CashoutOrder:
    order_id: str
    amount_usdc: float
    method: str
    currency: str = "USD"
    rate: float = 0.0  # Exchange rate
    amount_fiat: float = 0.0
    status: str = CashoutStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    buyer_name: str = ""
    payment_method: str = ""  # "bank_transfer" | "upi" | "paypal" | etc.
    payment_proof: str = ""
    completed_at: str = ""
    notes: str = ""


class CashoutManager:
    """
    Manages converting USDC to local currency.
    
    Options:
    1. Binance P2P — sell USDC, receive via bank/UPI
    2. Paxful — trade USDC for gift cards or cash
    3. Direct P2P — find buyers on Telegram/Discord
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger("CashoutManager")
        self.orders: dict[str, CashoutOrder] = {}
        self._load_orders()

    def _load_orders(self) -> None:
        """Load saved orders from disk."""
        if CASHOUT_FILE.exists():
            try:
                data = json.loads(CASHOUT_FILE.read_text())
                for oid, info in data.items():
                    self.orders[oid] = CashoutOrder(**info)
                self.logger.info("Loaded %d cashout orders", len(self.orders))
            except Exception as e:
                self.logger.warning("Failed to load cashouts: %s", e)

    def _save_orders(self) -> None:
        """Persist orders to disk."""
        CASHOUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        for oid, order in self.orders.items():
            data[oid] = {
                "order_id": order.order_id,
                "amount_usdc": order.amount_usdc,
                "method": order.method,
                "currency": order.currency,
                "rate": order.rate,
                "amount_fiat": order.amount_fiat,
                "status": order.status,
                "created_at": order.created_at,
                "buyer_name": order.buyer_name,
                "payment_method": order.payment_method,
                "payment_proof": order.payment_proof,
                "completed_at": order.completed_at,
                "notes": order.notes,
            }
        CASHOUT_FILE.write_text(json.dumps(data, indent=2))

    async def create_cashout_order(
        self,
        amount_usdc: float,
        method: str = CashoutMethod.BINANCE_P2P,
        currency: str = "USD",
        payment_method: str = "bank_transfer",
    ) -> CashoutOrder:
        """
        Create a cashout order.
        """
        import secrets
        order_id = secrets.token_hex(8)

        order = CashoutOrder(
            order_id=order_id,
            amount_usdc=amount_usdc,
            method=method,
            currency=currency,
            payment_method=payment_method,
        )

        self.orders[order_id] = order
        self._save_orders()

        self.logger.info(
            "Cashout order %s created: %s USDC via %s",
            order_id[:8],
            amount_usdc,
            method,
        )

        return order

    async def get_p2p_rate(
        self,
        method: str,
        currency: str = "USD",
    ) -> dict:
        """
        Get current P2P exchange rate.
        In production: calls exchange API.
        """
        # Simulated rates
        rates = {
            "USD": 1.0,
            "EUR": 0.92,
            "GBP": 0.79,
            "INR": 83.5,
            "NGN": 1550.0,
            "PHP": 56.0,
            "BRL": 5.0,
        }

        rate = rates.get(currency, 1.0)
        # P2P usually has 0.5-2% spread
        spread = 0.01  # 1% spread
        buy_rate = rate * (1 + spread)
        sell_rate = rate * (1 - spread)

        return {
            "currency": currency,
            "mid_rate": rate,
            "buy_rate": buy_rate,
            "sell_rate": sell_rate,
            "spread": f"{spread * 100}%",
            "method": method,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    async def find_p2p_buyers(
        self,
        amount_usdc: float,
        currency: str = "USD",
    ) -> list[dict]:
        """
        Find available P2P buyers.
        In production: calls Binance/Paxful API.
        """
        # Simulated buyers
        return [
            {
                "buyer_id": "buyer_001",
                "name": "Verified Trader",
                "rating": 4.9,
                "trades": 1523,
                "payment_methods": ["bank_transfer", "upi"],
                "min_amount": 10,
                "max_amount": 5000,
                "rate": 1.005,  # 0.5% above market
            },
            {
                "buyer_id": "buyer_002",
                "name": "Quick Cash P2P",
                "rating": 4.7,
                "trades": 892,
                "payment_methods": ["bank_transfer", "paypal"],
                "min_amount": 50,
                "max_amount": 10000,
                "rate": 0.998,  # 0.2% below market
            },
        ]

    async def confirm_payment(
        self,
        order_id: str,
        payment_proof: str = "",
    ) -> bool:
        """
        Confirm payment received from buyer.
        """
        order = self.orders.get(order_id)
        if not order:
            return False

        if order.status not in (
            CashoutStatus.ORDER_CREATED,
            CashoutStatus.BUYER_FOUND,
        ):
            return False

        order.status = CashoutStatus.PAYMENT_RECEIVED
        order.payment_proof = payment_proof
        self._save_orders()

        self.logger.info(
            "Cashout %s: Payment confirmed from %s",
            order_id[:8],
            order.buyer_name,
        )
        return True

    async def release_usdc(self, order_id: str) -> dict:
        """
        Release USDC to buyer after confirming payment.
        """
        order = self.orders.get(order_id)
        if not order:
            return {"success": False, "error": "Order not found"}

        if order.status != CashoutStatus.PAYMENT_RECEIVED:
            return {"success": False, "error": "Payment not yet confirmed"}

        order.status = CashoutStatus.USDC_RELEASED
        self._save_orders()

        self.logger.info(
            "Cashout %s: Released %s USDC to buyer",
            order_id[:8],
            order.amount_usdc,
        )

        return {
            "success": True,
            "order_id": order_id,
            "amount_released": order.amount_usdc,
            "status": "USDC released — deal complete",
        }

    async def complete_order(self, order_id: str) -> bool:
        """Mark cashout order as completed."""
        order = self.orders.get(order_id)
        if not order:
            return False

        order.status = CashoutStatus.COMPLETED
        order.completed_at = datetime.now(timezone.utc).isoformat()
        self._save_orders()

        self.logger.info(
            "Cashout %s: COMPLETED — %s USDC cashed out",
            order_id[:8],
            order.amount_usdc,
        )
        return True

    def get_cashout_guide(self) -> dict:
        """
        Get step-by-step cashout guide.
        """
        return {
            "binance_p2p": {
                "name": "Binance P2P",
                "steps": [
                    "Create Binance account (KYC required)",
                    "Go to Trade > P2P",
                    "Select 'Sell' tab",
                    "Choose USDC and your currency",
                    "Set amount and payment method",
                    "Select a verified buyer",
                    "Release USDC after receiving payment",
                ],
                "fees": "0.1% trading fee",
                "settlement": "Instant to minutes",
                "min_kyc": "Identity verification required",
            },
            "paxful": {
                "name": "Paxful",
                "steps": [
                    "Create Paxful account",
                    "Go to 'Sell' tab",
                    "Choose USDC",
                    "Select payment method (bank, gift card, etc.)",
                    "Set your rate and amount",
                    "Wait for buyer",
                    "Release after payment confirmed",
                ],
                "fees": "1-3% depending on payment method",
                "settlement": "5-60 minutes",
                "min_kyc": "Basic verification for small amounts",
            },
            "manual_p2p": {
                "name": "Manual P2P (Telegram/Discord)",
                "steps": [
                    "Find verified P2P traders in crypto groups",
                    "Agree on rate and payment method",
                    "Use escrow bot for safety",
                    "Buyer sends payment first",
                    "You release USDC after confirming payment",
                    "Always use escrow for strangers",
                ],
                "fees": "0% (negotiate rate)",
                "settlement": "Depends on payment method",
                "min_kyc": "None (higher risk)",
            },
        }

    def get_order(self, order_id: str) -> Optional[CashoutOrder]:
        """Get cashout order by ID."""
        return self.orders.get(order_id)

    def list_active_orders(self) -> list[CashoutOrder]:
        """List all active orders."""
        active_states = {
            CashoutStatus.PENDING,
            CashoutStatus.ORDER_CREATED,
            CashoutStatus.BUYER_FOUND,
            CashoutStatus.PAYMENT_RECEIVED,
        }
        return [o for o in self.orders.values() if o.status in active_states]

    def get_status(self) -> dict:
        """Get overall cashout status."""
        active = self.list_active_orders()
        total_cashed_out = sum(
            o.amount_usdc
            for o in self.orders.values()
            if o.status == CashoutStatus.COMPLETED
        )
        return {
            "total_orders": len(self.orders),
            "active_orders": len(active),
            "total_cashed_out_usdc": total_cashed_out,
            "orders": [
                {
                    "id": o.order_id[:8],
                    "amount": o.amount_usdc,
                    "method": o.method,
                    "status": o.status,
                }
                for o in active
            ],
        }
