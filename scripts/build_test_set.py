"""Build the evaluation wallet set on the running fork.

Run this after scripts/probe_positions.py, every time the fork is restarted:

    .venv/bin/python scripts/build_test_set.py

It picks real Uniswap positions with collectable fees, deploys two airdrop distributors
(one open, one whose window has closed), funds them with USDC from a large holder on the
fork, claims a few entries so some wallets are "already claimed", and writes:

    data/airdrops.json   the airdrop registry (distributor address, entries, proofs)
    data/wallets.json    the wallet set with cohort labels and ground truth
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from eth_utils import keccak
from web3 import Web3

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from salvage.chain import get_chain  # noqa: E402
from salvage.config import DATA_DIR, ROOT  # noqa: E402
from salvage.contracts import PRICED_TOKENS  # noqa: E402
from salvage.tools import airdrops, claims, uniswap  # noqa: E402

USDC = PRICED_TOKENS["USDC"][0]
DEPLOYER = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"  # first Anvil dev account
MAX_POSITIONS_PER_WALLET = 8
USDC_HOLDERS = [
    "0x55FE002aefF02F77364de339a1292923A15844B8",
    "0x28C6c06298d514Db089934071355E5743bf21d60",
    "0xF977814e90dA44bFA03b6295A0616a897441aceC",
    "0x40ec5B33f54e0E8A33A975908C5BA1c14e5BbbDf",
    "0xcEe284F754E854890e311e3280b767F80797180d",
    "0x2FAF487A4414Fe77e2327F0bf4AE2a264a776AD2",
]


def synthetic_address(i: int) -> str:
    return Web3.to_checksum_address(keccak(b"salvage-wallet-" + str(i).encode())[-20:].hex())


def pick_holder(chain, needed: int) -> str:
    best, best_bal = None, 0
    for h in USDC_HOLDERS:
        bal = int(chain.erc20(USDC).functions.balanceOf(chain.checksum(h)).call())
        if bal > best_bal:
            best, best_bal = h, bal
    if best is None or best_bal < needed:
        raise SystemExit("no known USDC holder on this fork has enough balance")
    return best


def deploy_airdrop(chain, root: str, deadline: int) -> str:
    artifact = json.loads((ROOT / "contracts" / "out" / "MerkleAirdrop.sol" / "MerkleAirdrop.json").read_text())
    bytecode = artifact["bytecode"]["object"]
    chain.impersonate(DEPLOYER)
    chain.set_balance(DEPLOYER, 100 * 10**18)
    factory = chain.w3.eth.contract(abi=artifact["abi"], bytecode=bytecode)
    tx = factory.constructor(chain.checksum(USDC), bytes.fromhex(root[2:]), deadline).transact({"from": DEPLOYER, "gas": 2_000_000})
    receipt = chain.w3.eth.wait_for_transaction_receipt(tx)
    assert receipt["status"] == 1, "airdrop deployment reverted"
    return receipt["contractAddress"]


def main() -> None:
    chain = get_chain()
    candidates = json.loads((DATA_DIR / "candidates.json").read_text())["candidates"]
    if not candidates:
        raise SystemExit("run scripts/probe_positions.py first")

    # distinct owners, richest first, up to 12 fee wallets. Wallets with many positions are skipped:
    # each position costs several node reads, and a scan that takes minutes is no good for a demo.
    by_owner: dict[str, dict] = {}
    for c in sorted(candidates, key=lambda c: -c["usd"]):
        by_owner.setdefault(c["owner"].lower(), c)
    fee_wallets = []
    for c in by_owner.values():
        n = uniswap.position_count(c["owner"], chain)
        if n <= MAX_POSITIONS_PER_WALLET:
            fee_wallets.append(c)
        else:
            print(f"  skipping {c['owner']} ({n} positions)")
        if len(fee_wallets) == 12:
            break
    print(f"{len(fee_wallets)} fee wallets from {len(candidates)} candidates")

    wallets: list[dict] = []
    for k, c in enumerate(fee_wallets):
        cohort = "both" if k < 6 else "fees"
        wallets.append({"label": f"{cohort}_{k+1:02d}", "address": chain.checksum(c["owner"]), "cohort": cohort})
    for k in range(1, 7):
        wallets.append({"label": f"airdrop_{k:02d}", "address": synthetic_address(k), "cohort": "airdrop"})
    for k in range(7, 10):
        wallets.append({"label": f"claimed_{k:02d}", "address": synthetic_address(k), "cohort": "claimed_airdrop"})
    for k in range(10, 13):
        wallets.append({"label": f"expired_{k:02d}", "address": synthetic_address(k), "cohort": "expired_airdrop"})
    for k in range(13, 17):
        wallets.append({"label": f"empty_{k:02d}", "address": synthetic_address(k), "cohort": "empty"})

    # airdrop entries in USDC (6 decimals). A realistic spread on purpose: a couple just above the
    # gas an airdrop claim costs (about a quarter), a couple just below it, some mid sized, a few large.
    amounts = {
        "both_01": 12.40, "both_02": 48.75, "both_03": 137.00, "both_04": 310.50, "both_05": 620.00, "both_06": 980.25,
        "airdrop_01": 0.31, "airdrop_02": 0.19, "airdrop_03": 3.75, "airdrop_04": 22.10, "airdrop_05": 75.00, "airdrop_06": 410.00,
        "claimed_07": 55.00, "claimed_08": 120.00, "claimed_09": 260.00,
        "expired_10": 250.00, "expired_11": 0.21, "expired_12": 370.00,
    }
    open_entries, closed_entries = [], []
    for i, w in enumerate(w for w in wallets if w["cohort"] in ("both", "airdrop", "claimed_airdrop")):
        open_entries.append((i, w["address"], int(round(amounts[w["label"]] * 10**6))))
    for i, w in enumerate(w for w in wallets if w["cohort"] == "expired_airdrop"):
        closed_entries.append((i, w["address"], int(round(amounts[w["label"]] * 10**6))))

    open_root, open_proofs = airdrops.build_tree(open_entries)
    closed_root, closed_proofs = airdrops.build_tree(closed_entries)
    now = int(chain.w3.eth.get_block("latest")["timestamp"])
    open_addr = deploy_airdrop(chain, open_root, now + 30 * 86400)
    closed_addr = deploy_airdrop(chain, closed_root, now - 3600)
    print(f"deployed open airdrop at {open_addr}, closed airdrop at {closed_addr}")

    needed = sum(a for _, _, a in open_entries) + sum(a for _, _, a in closed_entries)
    holder = pick_holder(chain, needed)
    usdc = chain.erc20(USDC)
    for addr, amt in ((open_addr, sum(a for _, _, a in open_entries)), (closed_addr, sum(a for _, _, a in closed_entries))):
        r = chain.send_as(holder, usdc.functions.transfer(chain.checksum(addr), amt), gas=120_000)
        assert r["status"] == "success", f"funding failed: {r}"
    print(f"funded both distributors with {needed / 1e6:,.2f} USDC from {holder}")

    airdrops.save_registry([
        {"name": "Season 1 rewards", "address": open_addr, "token": USDC, "symbol": "USDC", "deadline": now + 30 * 86400, "entries": open_proofs},
        {"name": "Season 0 rewards", "address": closed_addr, "token": USDC, "symbol": "USDC", "deadline": now - 3600, "entries": closed_proofs},
    ])

    # make the "claimed" cohort already claimed
    for w in wallets:
        if w["cohort"] == "claimed_airdrop":
            r = claims.claim_airdrop(open_addr, w["address"], chain)
            assert r["status"] == "success", f"pre claim failed for {w['label']}: {r}"
    print("pre claimed the claimed_airdrop cohort")

    # ground truth from the verified tools
    for w in wallets:
        fees = uniswap.scan_fees(w["address"], chain)
        drops = airdrops.scan_airdrops(w["address"], chain)
        w["ground_truth"] = {
            "usd_total": round(fees["usd_total"] + drops["usd_total"], 2),
            "fee_positions": [{"token_id": p["token_id"], "usd": p["usd_total"]} for p in fees["positions"] if p["usd_total"] > 0],
            "airdrops": [{"distributor": d["distributor"], "status": d["status"], "usd": d["usd"]} for d in drops["airdrops"]],
        }
        print(f"  {w['label']:12} {w['address']}  ${w['ground_truth']['usd_total']:>10,.2f}")

    out = DATA_DIR / "wallets.json"
    out.write_text(json.dumps({"block": chain.block_number, "wallets": wallets}, indent=2))
    print(f"wrote {len(wallets)} wallets to {out}")


if __name__ == "__main__":
    main()
