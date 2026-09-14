"""Airdrop eligibility and claim status.

An airdrop is a merkle distributor contract plus a published list of (index, account, amount)
leaves with proofs. Salvage keeps that list in data/airdrops.json (the same shape a project
publishes for a real airdrop) and checks eligibility, claim status, and the claim window onchain.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from eth_utils import keccak

from ..chain import Chain, get_chain
from ..config import DATA_DIR

REGISTRY_PATH = DATA_DIR / "airdrops.json"


# ---------- merkle tree (matches MerkleAirdrop.sol: sorted pair hashing, packed leaves) ----------

def leaf_hash(index: int, account: str, amount: int) -> bytes:
    return keccak(index.to_bytes(32, "big") + bytes.fromhex(account[2:].lower()) + amount.to_bytes(32, "big"))


def _pair_hash(a: bytes, b: bytes) -> bytes:
    return keccak(a + b) if a <= b else keccak(b + a)


def build_tree(entries: list[tuple[int, str, int]]) -> tuple[str, dict[str, dict]]:
    """Returns (root_hex, {account_lower: {index, amount, proof: [hex...]}})."""
    leaves = [leaf_hash(i, a, amt) for i, a, amt in entries]
    if not leaves:
        raise ValueError("no entries")
    layers = [leaves]
    while len(layers[-1]) > 1:
        cur = layers[-1]
        nxt = []
        for k in range(0, len(cur), 2):
            if k + 1 < len(cur):
                nxt.append(_pair_hash(cur[k], cur[k + 1]))
            else:
                nxt.append(cur[k])
        layers.append(nxt)
    root = layers[-1][0]

    proofs: dict[str, dict] = {}
    for pos, (i, a, amt) in enumerate(entries):
        proof = []
        idx = pos
        for layer in layers[:-1]:
            sib = idx ^ 1
            if sib < len(layer):
                proof.append("0x" + layer[sib].hex())
            idx //= 2
        proofs[a.lower()] = {"index": i, "amount": amt, "proof": proof}
    return "0x" + root.hex(), proofs


def verify_proof(root_hex: str, index: int, account: str, amount: int, proof: list[str]) -> bool:
    node = leaf_hash(index, account, amount)
    for p in proof:
        node = _pair_hash(node, bytes.fromhex(p[2:]))
    return "0x" + node.hex() == root_hex.lower()


# ---------- registry ----------

def load_registry() -> list[dict]:
    if not REGISTRY_PATH.exists():
        return []
    return json.loads(REGISTRY_PATH.read_text()).get("airdrops", [])


def save_registry(airdrops: list[dict]) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps({"airdrops": airdrops}, indent=2))


# ---------- scanning ----------

def scan_airdrops_raw(owner: str, chain: Chain | None = None) -> dict:
    """What v1 sees: raw amounts and the chain's booleans."""
    chain = chain or get_chain()
    owner_l = owner.lower()
    now = int(time.time())
    found = []
    for drop in load_registry():
        entry = drop["entries"].get(owner_l)
        if not entry:
            continue
        c = chain.airdrop(drop["address"])
        claimed = bool(c.functions.isClaimed(entry["index"]).call())
        deadline = int(c.functions.deadline().call())
        found.append({
            "name": drop["name"],
            "distributor": drop["address"],
            "token": drop["token"],
            "symbol": drop["symbol"],
            "index": entry["index"],
            "amount": entry["amount"],
            "claimed": claimed,
            "deadline": deadline,
            "window_open": now <= deadline,
        })
    return {"owner": chain.checksum(owner), "airdrops": found}


def scan_airdrops(owner: str, chain: Chain | None = None) -> dict:
    """What v2 sees: converted amounts, USD values in code, and a plain claimable flag."""
    from .pricing import usd_price, to_units

    chain = chain or get_chain()
    raw = scan_airdrops_raw(owner, chain)
    out = []
    total = 0.0
    for d in raw["airdrops"]:
        _, decimals = chain.token_meta(d["token"])
        units = to_units(d["amount"], decimals)
        price = usd_price(d["token"], chain)
        usd = units * price if price is not None else None
        claimable = (not d["claimed"]) and d["window_open"]
        if claimable and usd:
            total += usd
        out.append({**d, "decimals": decimals, "amount_units": units, "usd": usd, "claimable": claimable,
                    "status": "claimable" if claimable else ("already claimed" if d["claimed"] else "window closed")})
    return {"owner": raw["owner"], "airdrops": out, "usd_total": round(total, 2)}


def proof_for(owner: str, distributor: str) -> dict | None:
    for drop in load_registry():
        if drop["address"].lower() == distributor.lower():
            return drop["entries"].get(owner.lower())
    return None
