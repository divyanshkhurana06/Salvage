"""Claiming: simulate, execute, and read the receipt.

Two families of functions live here on purpose.

The naive ones (suffix _v1) do what a first implementation usually does: send the transaction
and hand back a hash. They never look at the receipt.

The verified ones (used by v2) simulate first, execute, read the receipt, and measure what
actually arrived in the wallet by comparing token balances before and after.
"""

from __future__ import annotations

from ..chain import Chain, get_chain
from ..contracts import MAX_UINT128
from .airdrops import proof_for
from .pricing import to_units, usd_price


# ---------- shared helpers ----------

def _balances(chain: Chain, owner: str, tokens: list[str]) -> dict[str, int]:
    return {t.lower(): int(chain.erc20(t).functions.balanceOf(chain.checksum(owner)).call()) for t in tokens}


def _received(chain: Chain, owner: str, before: dict[str, int], tokens: list[str]) -> list[dict]:
    after = _balances(chain, owner, tokens)
    out = []
    for t in tokens:
        delta = after[t.lower()] - before[t.lower()]
        sym, dec = chain.token_meta(t)
        price = usd_price(t, chain)
        units = to_units(delta, dec)
        out.append({"symbol": sym, "token": t, "amount_raw": delta, "decimals": dec, "amount": units,
                    "usd": units * price if price is not None else None})
    return out


# ---------- uniswap fees ----------

def simulate_collect(token_id: int, owner: str, chain: Chain | None = None) -> dict:
    chain = chain or get_chain()
    npm = chain.position_manager
    owner = chain.checksum(owner)
    try:
        a0, a1 = npm.functions.collect((token_id, owner, MAX_UINT128, MAX_UINT128)).call({"from": owner})
        return {"ok": True, "amount0_raw": int(a0), "amount1_raw": int(a1)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:300]}


def collect_fees_v1(token_id: int, owner: str, chain: Chain | None = None) -> dict:
    """Naive: send and return the hash. No receipt, no balance check."""
    chain = chain or get_chain()
    npm = chain.position_manager
    owner = chain.checksum(owner)
    chain.impersonate(owner)
    if chain.w3.eth.get_balance(owner) < 10**18:
        chain.set_balance(owner, 10 * 10**18)
    tx_hash = npm.functions.collect((token_id, owner, MAX_UINT128, MAX_UINT128)).transact({"from": owner, "gas": 600_000})
    return {"tx_hash": tx_hash.hex(), "token_id": token_id}


def collect_fees(token_id: int, owner: str, chain: Chain | None = None) -> dict:
    """Verified: simulate, execute, read the receipt, and report what actually arrived."""
    chain = chain or get_chain()
    owner = chain.checksum(owner)
    sim = simulate_collect(token_id, owner, chain)
    if not sim["ok"]:
        return {"status": "simulation reverted", "token_id": token_id, "error": sim["error"], "received": []}
    if sim["amount0_raw"] == 0 and sim["amount1_raw"] == 0:
        return {"status": "nothing to collect", "token_id": token_id, "received": []}

    npm = chain.position_manager
    p = npm.functions.positions(token_id).call()
    tokens = [p[2], p[3]]
    before = _balances(chain, owner, tokens)
    receipt = chain.send_as(owner, npm.functions.collect((token_id, owner, MAX_UINT128, MAX_UINT128)), gas=600_000)
    received = _received(chain, owner, before, tokens) if receipt["status"] == "success" else []
    usd = sum((r["usd"] or 0.0) for r in received)
    return {
        "status": receipt["status"], "token_id": token_id, "tx_hash": receipt.get("tx_hash"),
        "gas_used": receipt.get("gas_used", 0), "received": received, "usd_received": round(usd, 2),
        "error": receipt.get("error"),
    }


# ---------- airdrops ----------

def simulate_airdrop_claim(distributor: str, owner: str, chain: Chain | None = None) -> dict:
    chain = chain or get_chain()
    entry = proof_for(owner, distributor)
    if not entry:
        return {"ok": False, "error": "wallet is not in this airdrop"}
    c = chain.airdrop(distributor)
    try:
        c.functions.claim(entry["index"], chain.checksum(owner), entry["amount"], entry["proof"]).call({"from": chain.checksum(owner)})
        return {"ok": True, "amount_raw": entry["amount"]}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:300]}


def claim_airdrop_v1(distributor: str, owner: str, chain: Chain | None = None) -> dict:
    """Naive: send with a fixed gas limit and return the hash, whatever happened."""
    chain = chain or get_chain()
    owner = chain.checksum(owner)
    entry = proof_for(owner, distributor)
    if not entry:
        return {"error": "wallet is not in this airdrop"}
    chain.impersonate(owner)
    if chain.w3.eth.get_balance(owner) < 10**18:
        chain.set_balance(owner, 10 * 10**18)
    c = chain.airdrop(distributor)
    tx_hash = c.functions.claim(entry["index"], owner, entry["amount"], entry["proof"]).transact({"from": owner, "gas": 300_000})
    return {"tx_hash": tx_hash.hex(), "distributor": distributor}


def claim_airdrop(distributor: str, owner: str, chain: Chain | None = None) -> dict:
    """Verified: simulate, execute, read the receipt, and report what arrived."""
    chain = chain or get_chain()
    owner = chain.checksum(owner)
    sim = simulate_airdrop_claim(distributor, owner, chain)
    if not sim["ok"]:
        return {"status": "simulation reverted", "distributor": distributor, "error": sim["error"], "received": []}
    entry = proof_for(owner, distributor)
    c = chain.airdrop(distributor)
    token = c.functions.token().call()
    before = _balances(chain, owner, [token])
    receipt = chain.send_as(owner, c.functions.claim(entry["index"], owner, entry["amount"], entry["proof"]), gas=300_000)
    received = _received(chain, owner, before, [token]) if receipt["status"] == "success" else []
    usd = sum((r["usd"] or 0.0) for r in received)
    return {
        "status": receipt["status"], "distributor": distributor, "tx_hash": receipt.get("tx_hash"),
        "gas_used": receipt.get("gas_used", 0), "received": received, "usd_received": round(usd, 2),
        "error": receipt.get("error"),
    }


def gas_cost_usd(gas_used: int, chain: Chain | None = None) -> float:
    """Rough USD cost of a transaction at the fork's current base fee."""
    chain = chain or get_chain()
    from ..contracts import PRICED_TOKENS
    eth_price = usd_price(PRICED_TOKENS["WETH"][0], chain) or 0.0
    gas_price = chain.w3.eth.gas_price
    return gas_used * gas_price / 1e18 * eth_price
