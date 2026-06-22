"""
Binance P2P Helper — Guide for selling USDC without bank account.
Run: python -m src.trading.binance_guide
"""

from __future__ import annotations

import json


def print_guide():
    print("=" * 60)
    print("  BINANCE P2P SETUP - PAKISTAN (NO BANK NEEDED)")
    print("=" * 60)
    
    print("""
STEP 1: CREATE BINANCE ACCOUNT (2 min)
---------------------------------------
1. Go to https://www.binance.com
2. Click "Register"
3. Enter email + password
4. Verify email
5. Done! (no bank needed)

STEP 2: KYC VERIFICATION (5-30 min)
---------------------------------------
1. Go to Account > Identification
2. Click "Verify"
3. Select "Pakistan"
4. Choose ID type:
   - CNIC (National ID) - recommended
   - Passport
   - Driver's license
5. Upload front + back photo
6. Take selfie
7. Wait for approval (5-30 min)

STEP 3: ADD PAYMENT METHOD (Pakistan)
---------------------------------------
Option A: JazzCash (Recommended)
  1. Go to Trade > P2P
  2. Click avatar > Payment Methods
  3. Add "JazzCash"
  4. Enter your JazzCash mobile number
  5. Enter your name as on CNIC

Option B: EasyPaisa
  1. Go to Trade > P2P
  2. Click avatar > Payment Methods
  3. Add "EasyPaisa"
  4. Enter your EasyPaisa mobile number
  5. Enter your name as on CNIC

Option C: SadaPay
  1. Go to Trade > P2P
  2. Click avatar > Payment Methods
  3. Add "SadaPay"
  4. Enter your SadaPay account number
  5. Enter your name as on CNIC

Option D: NayaPay
  1. Go to Trade > P2P
  2. Click avatar > Payment Methods
  3. Add "NayaPay"
  4. Enter your NayaPay account
  5. Enter your name as on CNIC

STEP 4: SELL USDC FOR PKR
---------------------------------------
1. Go to Trade > P2P
2. Select "Sell" tab
3. Choose "USDC" or "USDT"
4. Currency: PKR
5. Select payment method (JazzCash/EasyPaisa/etc)
6. Find verified buyer (checkmark badge, 4.8+ rating)
7. Click "Sell USDC"
8. Wait for buyer to send PKR to your JazzCash/EasyPaisa
9. Confirm payment received in your app
10. Click "Release USDC"

SAFETY RULES
---------------------------------------
+ Always use Binance escrow
+ Check buyer rating (4.8+)
+ Verify payment in YOUR app BEFORE releasing
+ Start with $10 test trade
+ Screenshot payment confirmation
- Never release first
- Never trade outside Binance
- Never share OTP/PIN
""")


def get_payment_methods():
    """Return available payment methods for Pakistan."""
    return {
        "jazzcash": {
            "name": "JazzCash (Pakistan)",
            "needs_bank": False,
            "needs_id": "CNIC",
            "fees": "0%",
            "settlement": "Instant",
            "how_to_get": "Download JazzCash app, register with CNIC",
            "limits": "500 PKR - 500,000 PKR per transaction",
        },
        "easypaisa": {
            "name": "EasyPaisa (Pakistan)",
            "needs_bank": False,
            "needs_id": "CNIC",
            "fees": "0%",
            "settlement": "Instant",
            "how_to_get": "Download EasyPaisa app, register with CNIC",
            "limits": "500 PKR - 500,000 PKR per transaction",
        },
        "sadapay": {
            "name": "SadaPay (Pakistan)",
            "needs_bank": False,
            "needs_id": "CNIC + selfie",
            "fees": "0%",
            "settlement": "Instant",
            "how_to_get": "Download SadaPay app, register with CNIC",
            "limits": "No limit on receiving",
        },
        "nayapay": {
            "name": "NayaPay (Pakistan)",
            "needs_bank": False,
            "needs_id": "CNIC",
            "fees": "0%",
            "settlement": "Instant",
            "how_to_get": "Download NayaPay app, register with CNIC",
            "limits": "500 PKR - 500,000 PKR per transaction",
        },
        "bank_transfer": {
            "name": "Bank Transfer (Pakistan)",
            "needs_bank": True,
            "needs_id": "CNIC",
            "fees": "0%",
            "settlement": "10-30 min",
            "banks": ["HBL", "Meezan", "UBL", "MCB", "Allied"],
        },
    }


if __name__ == "__main__":
    print_guide()
    
    print("\n" + "=" * 60)
    print("  AVAILABLE PAYMENT METHODS (No Bank Needed)")
    print("=" * 60 + "\n")
    
    methods = get_payment_methods()
    for key, method in methods.items():
        print(f"  {key.upper()}")
        print(f"    Name: {method['name']}")
        print(f"    Needs Bank: {method['needs_bank']}")
        print(f"    Needs ID: {method['needs_id']}")
        print(f"    Fees: {method['fees']}")
        print(f"    Settlement: {method['settlement']}")
        print()
