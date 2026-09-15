"""Find real Uniswap v3 positions on a fork that have collectable fees in priced tokens.

Usage: .venv/bin/python scripts/probe_positions.py [how_many] [start_token_id] [--chain ethereum|base] [--min-usd 0.25]
Writes candidates to data/candidates.json (Ethereum) or data/candidates_<chain>.json.
Recent positions have collected little; start further back (a lower token id) and set a minimum to find real fees.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from salvage.chain import get_chain  # noqa: E402
from salvage.tools.pricing import usd_price  # noqa: E402
from salvage.tools.uniswap import collectable_raw, position_info  # noqa: E402


def candidates_path(chain_name: str) -> Path:
    data = Path(__file__).resolve().parent.parent / "data"
    return data / ("candidates.json" if chain_name == "ethereum" else f"candidates_{chain_name}.json")


def main() -> None:
    args = list(sys.argv[1:])
    chain_name = "ethereum"
    if "--chain" in args:
        i = args.index("--chain")
        chain_name = args[i + 1]
        del args[i:i + 2]
    min_usd = 0.0
    if "--min-usd" in args:
        i = args.index("--min-usd")
        min_usd = float(args[i + 1])
        del args[i:i + 2]
    want = int(args[0]) if args else 40
    chain = get_chain(chain_name)
    npm = chain.position_manager
    total = int(npm.functions.totalSupply().call())
    start = int(args[1]) if len(args) > 1 else int(npm.functions.tokenByIndex(total - 1).call())
    print(f"{chain.label}: block {chain.block_number}, totalSupply {total}, probing downward from tokenId {start}")

    prices = {t: usd_price(t, chain) for t in chain.token_to_feed}
    found: list[dict] = []
    token_id = start
    probed = 0
    while len(found) < want and token_id > 0 and probed < 4000:
        token_id -= 1
        probed += 1
        try:
            owner = npm.functions.ownerOf(token_id).call()
        except Exception:
            continue  # burned
        info = position_info(token_id, chain)
        t0, t1 = info["token0"].lower(), info["token1"].lower()
        if t0 not in prices or t1 not in prices:
            continue
        try:
            a0, a1 = collectable_raw(token_id, owner, chain)
        except Exception as exc:
            print(f"  collect sim failed for {token_id}: {str(exc)[:80]}")
            continue
        if a0 == 0 and a1 == 0:
            continue
        _, d0 = chain.token_meta(info["token0"])
        _, d1 = chain.token_meta(info["token1"])
        usd = a0 / 10**d0 * prices[t0] + a1 / 10**d1 * prices[t1]
        if usd < min_usd:
            continue
        found.append({"token_id": token_id, "chain": chain.name, "owner": owner, "token0": info["token0"], "token1": info["token1"], "fee_tier": info["fee_tier"], "amount0_raw": a0, "amount1_raw": a1, "usd": round(usd, 2)})
        print(f"  #{len(found)} tokenId {token_id} owner {owner} fees ~${usd:,.2f}")

    out = candidates_path(chain.name)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():  # merge with earlier probes so several ranges can be combined
        seen = {c["token_id"] for c in found}
        found += [c for c in json.loads(out.read_text()).get("candidates", []) if c["token_id"] not in seen]
    found.sort(key=lambda c: -c["usd"])
    out.write_text(json.dumps({"chain": chain.name, "block": chain.block_number, "candidates": found}, indent=2))
    print(f"wrote {len(found)} candidates to {out} after probing {probed} token ids")


if __name__ == "__main__":
    main()
