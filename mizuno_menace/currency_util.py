"""Convert reference prices to USD for discount math."""

from __future__ import annotations

# Static rates — sufficient for deal ranking; not for accounting.
_TO_USD = {
    "USD": 1.0,
    "EUR": 1.08,
    "GBP": 1.27,
}


def to_usd(amount: float, currency: str) -> float:
    cur = (currency or "USD").upper()
    rate = _TO_USD.get(cur, 1.0)
    return round(amount * rate, 2)
