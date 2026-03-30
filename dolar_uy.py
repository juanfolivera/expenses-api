"""
dolar_uy.py
-----------
Fetches the current USD/UYU exchange rate from DolarApi.com
and provides utilities to convert expenses between Uruguayan pesos and dollars.

API: https://uy.dolarapi.com  (open-source, no API key required)
"""

import requests
from dataclasses import dataclass
from datetime import datetime
import time


# ── Constants ─────────────────────────────────────────────────────────────────

BASE_URL = "https://uy.dolarapi.com"
TIMEOUT  = 10  # seconds


# ── Types ─────────────────────────────────────────────────────────────────────

@dataclass
class ExchangeRate:
    currency:   str
    name:       str
    buy:        float
    sell:       float
    updated_at: datetime

    @property
    def average(self) -> float:
        """Average between buy and sell price."""
        return (self.buy + self.sell) / 2

    def __str__(self) -> str:
        return (
            f"{self.name} ({self.currency})\n"
            f"  Buy    : $ {self.buy:.2f}\n"
            f"  Sell   : $ {self.sell:.2f}\n"
            f"  Average: $ {self.average:.2f}\n"
            f"  At     : {self.updated_at.strftime('%d/%m/%Y %H:%M')}"
        )


# ── API access ────────────────────────────────────────────────────────────────

def _get(endpoint: str) -> dict:
    """Performs a GET request to the API and returns the JSON response."""
    url = f"{BASE_URL}{endpoint}"
    response = requests.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def _parse_rate(data: dict) -> ExchangeRate:
    """Converts the API dict into an ExchangeRate object."""
    return ExchangeRate(
        currency   = data.get("moneda", ""),
        name       = data.get("nombre", ""),
        buy        = float(data.get("compra", 0)),
        sell       = float(data.get("venta", 0)),
        updated_at = datetime.fromisoformat(data.get("fechaActualizacion", datetime.now().isoformat())),
    )


def get_dollar() -> ExchangeRate:
    """Returns the current USD/UYU exchange rate."""
    data = _get("/v1/cotizaciones/usd")
    return _parse_rate(data)


def get_all_rates() -> list[ExchangeRate]:
    """Returns all available exchange rates (USD, EUR, BRL, etc.)."""
    data = _get("/v1/cotizaciones")
    return [_parse_rate(item) for item in data]


# ── Conversion utilities ──────────────────────────────────────────────────────

def pesos_to_dollars(amount_uyu: float, price: str = "sell") -> dict:
    """
    Converts an amount in Uruguayan pesos to US dollars.

    Args:
        amount_uyu: Amount in Uruguayan pesos.
        price:      'buy', 'sell', or 'average'.
                    For everyday expenses, 'sell' is recommended.

    Returns:
        Dict with the USD amount, rate used, and metadata.
    """
    rate = get_dollar()
    chosen_rate = {"buy": rate.buy, "sell": rate.sell, "average": rate.average}.get(price, rate.sell)
    return {
        "amount_uyu": amount_uyu,
        "amount_usd": round(amount_uyu / chosen_rate, 2),
        "rate_used":  chosen_rate,
        "price_type": price,
        "updated_at": rate.updated_at,
    }


def dollars_to_pesos(amount_usd: float, price: str = "buy") -> dict:
    """
    Converts an amount in US dollars to Uruguayan pesos.

    Args:
        amount_usd: Amount in US dollars.
        price:      'buy', 'sell', or 'average'.

    Returns:
        Dict with the UYU amount, rate used, and metadata.
    """
    rate = get_dollar()
    chosen_rate = {"buy": rate.buy, "sell": rate.sell, "average": rate.average}.get(price, rate.buy)
    return {
        "amount_usd": amount_usd,
        "amount_uyu": round(amount_usd * chosen_rate, 2),
        "rate_used":  chosen_rate,
        "price_type": price,
        "updated_at": rate.updated_at,
    }


# ── Cached version (avoids redundant API calls when processing multiple expenses) ──

_cache: dict = {"rate": None, "timestamp": 0}
import config as _config
CACHE_TTL = _config.DOLLAR_CACHE_TTL


def get_dollar_cached() -> ExchangeRate:
    """
    Same as get_dollar() but caches the result for 5 minutes.
    Ideal for batch processing expenses without a request per item.
    """
    now = time.time()
    if _cache["rate"] is None or (now - _cache["timestamp"]) > CACHE_TTL:
        _cache["rate"]      = get_dollar()
        _cache["timestamp"] = now
    return _cache["rate"]


def convert_expenses(amounts_uyu: list[float], price: str = "sell") -> list[dict]:
    """
    Converts a list of peso expenses to dollars using a single API request.

    Args:
        amounts_uyu: List of amounts in UYU.
        price:       'buy', 'sell', or 'average'.

    Returns:
        List of dicts with each conversion result.
    """
    rate = get_dollar_cached()
    chosen_rate = {"buy": rate.buy, "sell": rate.sell, "average": rate.average}.get(price, rate.sell)
    return [{"amount_uyu": a, "amount_usd": round(a / chosen_rate, 2), "rate": chosen_rate} for a in amounts_uyu]


# ── Demo ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("  USD/UYU Exchange Rate")
    print("=" * 50)
    rate = get_dollar()
    print(rate)

    print("\n── Conversion examples ──")
    r1 = pesos_to_dollars(1500.0)
    print(f"\n$ {r1['amount_uyu']:.2f} UYU → USD {r1['amount_usd']:.2f}  (sell rate: {r1['rate_used']:.2f})")

    r2 = dollars_to_pesos(100.0)
    print(f"USD {r2['amount_usd']:.2f} → $ {r2['amount_uyu']:.2f} UYU  (buy rate: {r2['rate_used']:.2f})")

    print(f"\nBatch: {[500, 1200, 3400]} UYU")
    for c in convert_expenses([500, 1200, 3400]):
        print(f"  $ {c['amount_uyu']:.2f} → USD {c['amount_usd']:.2f}")
