"""USD pricing through Chainlink feeds on the fork of whichever chain the token lives on."""

from __future__ import annotations

from ..chain import Chain, get_chain


def raw_price(token: str, chain: Chain | None = None) -> dict:
    """The raw Chainlink round for a token. What v1 sees: an integer and a feed decimals count."""
    chain = chain or get_chain()
    feed = chain.token_to_feed.get(token.lower())
    if not feed:
        return {"token": token, "chain": chain.name, "priced": False, "reason": f"no Chainlink USD feed configured for this token on {chain.label}"}
    agg = chain.chainlink(feed)
    _, answer, _, updated_at, _ = agg.functions.latestRoundData().call()
    return {
        "token": token,
        "chain": chain.name,
        "symbol": chain.token_to_symbol.get(token.lower(), "?"),
        "priced": True,
        "feed": feed,
        "answer": int(answer),
        "feed_decimals": int(agg.functions.decimals().call()),
        "updated_at": int(updated_at),
    }


# A simulated market shock for the demo: multipliers applied on top of the live Chainlink price,
# keyed by token symbol so one shock moves the same asset on every chain. Set through the UI's crash button.
SHOCK: dict[str, float] = {}


def usd_price(token: str, chain: Chain | None = None) -> float | None:
    """The USD price as a float, computed in code. What v2 uses."""
    chain = chain or get_chain()
    data = raw_price(token, chain)
    if not data.get("priced"):
        return None
    return data["answer"] / (10 ** data["feed_decimals"]) * SHOCK.get(data["symbol"], 1.0)


def to_units(amount_raw: int, decimals: int) -> float:
    return amount_raw / (10 ** decimals)


def usd_value(amount_raw: int, decimals: int, token: str, chain: Chain | None = None) -> float | None:
    price = usd_price(token, chain)
    if price is None:
        return None
    return to_units(amount_raw, decimals) * price
