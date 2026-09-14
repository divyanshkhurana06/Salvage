"""USD pricing through Chainlink feeds on the fork."""

from __future__ import annotations

from ..chain import Chain, get_chain
from ..contracts import TOKEN_TO_FEED, TOKEN_TO_SYMBOL


def raw_price(token: str, chain: Chain | None = None) -> dict:
    """The raw Chainlink round for a token. What v1 sees: an integer and a feed decimals count."""
    chain = chain or get_chain()
    feed = TOKEN_TO_FEED.get(token.lower())
    if not feed:
        return {"token": token, "priced": False, "reason": "no Chainlink USD feed configured for this token"}
    agg = chain.chainlink(feed)
    _, answer, _, updated_at, _ = agg.functions.latestRoundData().call()
    return {
        "token": token,
        "symbol": TOKEN_TO_SYMBOL.get(token.lower(), "?"),
        "priced": True,
        "feed": feed,
        "answer": int(answer),
        "feed_decimals": int(agg.functions.decimals().call()),
        "updated_at": int(updated_at),
    }


def usd_price(token: str, chain: Chain | None = None) -> float | None:
    """The USD price as a float, computed in code. What v2 uses."""
    data = raw_price(token, chain)
    if not data.get("priced"):
        return None
    return data["answer"] / (10 ** data["feed_decimals"])


def to_units(amount_raw: int, decimals: int) -> float:
    return amount_raw / (10 ** decimals)


def usd_value(amount_raw: int, decimals: int, token: str, chain: Chain | None = None) -> float | None:
    price = usd_price(token, chain)
    if price is None:
        return None
    return to_units(amount_raw, decimals) * price
