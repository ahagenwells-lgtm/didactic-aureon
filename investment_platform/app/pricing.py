from datetime import datetime, timezone
from decimal import Decimal

import httpx
from sqlalchemy.orm import Session

from .models import PriceQuote

COINGECKO_IDS = {"BTC": "bitcoin", "ETH": "ethereum", "USDT": "tether"}
FALLBACK_PRICES = {"BTC": Decimal("60000"), "ETH": Decimal("3000"), "USDT": Decimal("1")}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def refresh_prices(db: Session) -> list[PriceQuote]:
    """Refresh public market snapshots. Never use this informational feed to execute trades."""
    results: dict[str, Decimal] = {}
    source = "coingecko"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            response = await client.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": ",".join(COINGECKO_IDS.values()), "vs_currencies": "usd"},
                headers={"Accept": "application/json", "User-Agent": "investment-platform-simulator/1.0"},
            )
            response.raise_for_status()
            data = response.json()
        for asset, coin_id in COINGECKO_IDS.items():
            price = data.get(coin_id, {}).get("usd")
            if price is None or Decimal(str(price)) <= 0:
                raise ValueError(f"missing price for {asset}")
            results[asset] = Decimal(str(price))
    except (httpx.HTTPError, ValueError, TypeError):
        source = "fallback"
        results = FALLBACK_PRICES

    timestamp = utcnow()
    quotes: list[PriceQuote] = []
    for asset, price in results.items():
        quote = db.get(PriceQuote, asset)
        if quote is None:
            quote = PriceQuote(asset=asset, usd_price=price, source=source, updated_at=timestamp)
            db.add(quote)
        else:
            quote.usd_price = price
            quote.source = source
            quote.updated_at = timestamp
        quotes.append(quote)
    db.commit()
    return quotes


def ensure_price_quotes(db: Session) -> None:
    if db.get(PriceQuote, "BTC") is not None:
        return
    timestamp = utcnow()
    for asset, price in FALLBACK_PRICES.items():
        db.add(PriceQuote(asset=asset, usd_price=price, source="fallback", updated_at=timestamp))
    db.commit()
