"""Uniswap v3 LP positions and the fees they can collect right now.

The only reliable way to know what a position can collect is to simulate
collect() from the owner with eth_call. tokensOwed in positions() is stale
until the position is poked, so we do not trust it.
"""

from __future__ import annotations

from ..chain import Chain, get_chain
from ..contracts import MAX_UINT128

# Some wallets hold hundreds of positions. Every position costs several node reads, so scans
# stop after this many and report how many exist, instead of taking minutes.
MAX_POSITIONS = 20


def position_count(owner: str, chain: Chain | None = None) -> int:
    chain = chain or get_chain()
    return int(chain.position_manager.functions.balanceOf(chain.checksum(owner)).call())


def owned_position_ids(owner: str, chain: Chain | None = None, limit: int = MAX_POSITIONS) -> list[int]:
    chain = chain or get_chain()
    npm = chain.position_manager
    owner = chain.checksum(owner)
    count = min(int(npm.functions.balanceOf(owner).call()), limit)
    return [int(npm.functions.tokenOfOwnerByIndex(owner, i).call()) for i in range(count)]


def position_info(token_id: int, chain: Chain | None = None) -> dict:
    chain = chain or get_chain()
    npm = chain.position_manager
    p = npm.functions.positions(token_id).call()
    return {
        "token_id": token_id,
        "token0": p[2],
        "token1": p[3],
        "fee_tier": int(p[4]),
        "tick_lower": int(p[5]),
        "tick_upper": int(p[6]),
        "liquidity": int(p[7]),
    }


def collectable_raw(token_id: int, owner: str, chain: Chain | None = None) -> tuple[int, int]:
    """Simulate collect() as the owner. Returns (amount0_raw, amount1_raw)."""
    chain = chain or get_chain()
    npm = chain.position_manager
    owner = chain.checksum(owner)
    amount0, amount1 = npm.functions.collect((token_id, owner, MAX_UINT128, MAX_UINT128)).call({"from": owner})
    return int(amount0), int(amount1)


def scan_fees_raw(owner: str, chain: Chain | None = None) -> dict:
    """What v1 sees: the chain's integers, nothing converted, nothing priced."""
    chain = chain or get_chain()
    owner = chain.checksum(owner)
    total = position_count(owner, chain)
    positions = []
    for token_id in owned_position_ids(owner, chain):
        info = position_info(token_id, chain)
        a0, a1 = collectable_raw(token_id, owner, chain)
        sym0, _ = chain.token_meta(info["token0"])
        sym1, _ = chain.token_meta(info["token1"])
        positions.append({
            "token_id": token_id,
            "pool": f"{sym0}/{sym1} {info['fee_tier'] / 10000:.2f}%",
            "token0": info["token0"], "token1": info["token1"],
            "symbol0": sym0, "symbol1": sym1,
            "amount0": a0, "amount1": a1,
        })
    return {"owner": owner, "positions": positions, "positions_total": total, "positions_scanned": len(positions), "block": chain.block_number}


def scan_fees(owner: str, chain: Chain | None = None) -> dict:
    """What v2 sees: converted amounts, USD values computed in code, per position totals."""
    from .pricing import usd_price, to_units  # local import keeps pricing optional for tests

    chain = chain or get_chain()
    raw = scan_fees_raw(owner, chain)
    out = []
    total_usd = 0.0
    for pos in raw["positions"]:
        _, dec0 = chain.token_meta(pos["token0"])
        _, dec1 = chain.token_meta(pos["token1"])
        units0 = to_units(pos["amount0"], dec0)
        units1 = to_units(pos["amount1"], dec1)
        p0 = usd_price(pos["token0"], chain)
        p1 = usd_price(pos["token1"], chain)
        usd0 = units0 * p0 if p0 is not None else None
        usd1 = units1 * p1 if p1 is not None else None
        pos_usd = (usd0 or 0.0) + (usd1 or 0.0)
        total_usd += pos_usd
        out.append({
            "token_id": pos["token_id"],
            "pool": pos["pool"],
            "fees": [
                {"symbol": pos["symbol0"], "token": pos["token0"], "amount_raw": pos["amount0"], "decimals": dec0, "amount": units0, "usd": usd0},
                {"symbol": pos["symbol1"], "token": pos["token1"], "amount_raw": pos["amount1"], "decimals": dec1, "amount": units1, "usd": usd1},
            ],
            "usd_total": round(pos_usd, 2),
            "fully_priced": usd0 is not None and usd1 is not None,
        })
    return {"owner": raw["owner"], "block": raw["block"], "positions": out, "positions_total": raw["positions_total"],
            "positions_scanned": raw["positions_scanned"], "usd_total": round(total_usd, 2)}
