"""Tool definitions the model sees, and the executors behind them, for v1 and v2."""

from __future__ import annotations

from typing import Callable

from ..chain import Chain, available_chains
from ..tools import airdrops, claims, pricing, uniswap

ADDRESS_PARAM = {"type": "string", "description": "wallet address, 0x followed by 40 hex characters (the same address is scanned on every chain)"}
CHAIN_PARAM = {"type": "string", "enum": ["ethereum", "base"], "description": "the chain the position lives on, as reported by the scan (default ethereum)"}


# ---------- v1: raw tools, a first draft ----------

V1_TOOLS = [
    {
        "name": "scan_wallet",
        "description": "Scan a wallet on Ethereum and Base for uncollected Uniswap v3 LP fees and unclaimed airdrops. Returns the positions (each with its chain) and airdrop entries with their amounts as reported by the contracts.",
        "input_schema": {"type": "object", "properties": {"address": ADDRESS_PARAM}, "required": ["address"]},
    },
    {
        "name": "get_price",
        "description": "Get the latest Chainlink USD price data for a token address on a chain.",
        "input_schema": {"type": "object", "properties": {"token": {"type": "string", "description": "token contract address"}, "chain": CHAIN_PARAM}, "required": ["token"]},
    },
    {
        "name": "collect_fees",
        "description": "Collect the fees of a Uniswap v3 position for the active wallet. Returns the transaction hash.",
        "input_schema": {"type": "object", "properties": {"token_id": {"type": "integer", "description": "the position NFT id"}, "chain": CHAIN_PARAM}, "required": ["token_id"]},
    },
    {
        "name": "claim_airdrop",
        "description": "Claim an airdrop for the active wallet. Returns the transaction hash.",
        "input_schema": {"type": "object", "properties": {"distributor": {"type": "string", "description": "airdrop distributor contract address"}}, "required": ["distributor"]},
    },
]

# ---------- v2: verified tools ----------

V2_TOOLS = [
    {
        "name": "scan_wallet",
        "description": "Scan a wallet on Ethereum and Base for uncollected Uniswap v3 LP fees and unclaimed airdrops. Amounts are already converted to token units and priced in USD, and every position says which chain it is on. Includes a plain text summary you can quote.",
        "input_schema": {"type": "object", "properties": {"address": ADDRESS_PARAM}, "required": ["address"]},
    },
    {
        "name": "estimate_gas_cost",
        "description": "Gas costs for everything claimable in the last scanned wallet, at the current network fee: one line per action (each fee collection, each airdrop claim) with its value, its gas, and the net, plus totals. Call this whenever the user asks about gas or whether claiming is worth it.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "collect_fees",
        "description": "Collect the fees of a Uniswap v3 position for the active wallet on the chain the scan reported it on. Simulates first, executes, reads the receipt, and reports status and the amounts that actually arrived.",
        "input_schema": {"type": "object", "properties": {"token_id": {"type": "integer", "description": "the position NFT id"}, "chain": CHAIN_PARAM}, "required": ["token_id", "chain"]},
    },
    {
        "name": "claim_airdrop",
        "description": "Claim an airdrop for the active wallet. Simulates first, executes, reads the receipt, and reports status and the amount that actually arrived.",
        "input_schema": {"type": "object", "properties": {"distributor": {"type": "string", "description": "airdrop distributor contract address"}}, "required": ["distributor"]},
    },
]


def _summary(fees: dict, drops: dict) -> str:
    lines = []
    for pos in fees["positions"]:
        parts = [f"{f['amount']:.6f} {f['symbol']}" + (f" (${f['usd']:.2f})" if f["usd"] is not None else " (unpriced)") for f in pos["fees"] if f["amount_raw"] > 0]
        if parts:
            lines.append(f"Uniswap position #{pos['token_id']} on {pos['chain'].capitalize()} ({pos['pool']}): " + " and ".join(parts) + f", total ${pos['usd_total']:.2f}")
    for d in drops["airdrops"]:
        value = f"${d['usd']:.2f}" if d["usd"] is not None else "unpriced"
        lines.append(f"Airdrop {d['name']}: {d['amount_units']:.6f} {d['symbol']} ({value}), status {d['status']}")
    total = fees["usd_total"] + drops["usd_total"]
    if not lines:
        return "Nothing claimable in this wallet."
    return "\n".join(lines) + f"\nTotal claimable now: ${total:.2f}"


def _gas_round(usd: float) -> float:
    return round(usd, 2) if usd >= 0.01 else round(usd, 4)


class Executors:
    """Builds the name to function map for a version, bound to the chains and a mutable active wallet.

    Uniswap positions are scanned on every chain whose fork is up. Airdrops live on Ethereum, where
    the distributors are deployed. A claim names its chain, as the scan reported it.
    """

    def __init__(self, version: str, chain: Chain, state: dict, chains: list[Chain] | None = None):
        self.version = version
        self.chain = chain  # Ethereum: airdrops, and the default for anything that does not name a chain
        self.chains = chains if chains is not None else (available_chains() if chain.name == "ethereum" else [chain])
        self.state = state  # {"active_wallet": str | None}

    def _set_active(self, address: str) -> None:
        self.state["active_wallet"] = self.chain.checksum(address)

    def _on(self, chain: str | None) -> Chain:
        name = (chain or self.chain.name).lower()
        for c in self.chains:
            if c.name == name:
                return c
        raise ValueError(f"chain {name} is not available; scanned chains are {', '.join(c.name for c in self.chains)}")

    # v1
    def v1_scan(self, address: str) -> dict:
        self._set_active(address)
        return {"uniswap": uniswap.scan_fees_raw_all(address, self.chains), "airdrops": airdrops.scan_airdrops_raw(address, self.chain)}

    def v1_price(self, token: str, chain: str | None = None) -> dict:
        return pricing.raw_price(token, self._on(chain))

    def v1_collect(self, token_id: int, chain: str | None = None) -> dict:
        return claims.collect_fees_v1(int(token_id), self._owner(), self._on(chain))

    def v1_claim(self, distributor: str) -> dict:
        return claims.claim_airdrop_v1(distributor, self._owner(), self.chain)

    # v2
    def v2_scan(self, address: str) -> dict:
        self._set_active(address)
        fees = uniswap.scan_fees_all(address, self.chains)
        drops = airdrops.scan_airdrops(address, self.chain)
        return {"uniswap": fees, "airdrops": drops, "chains_scanned": [c.name for c in self.chains],
                "usd_total": round(fees["usd_total"] + drops["usd_total"], 2), "summary": _summary(fees, drops)}

    def v2_gas(self, kind: str | None = None) -> dict:
        """Gas for every pending action on the active wallet, on the chain each action runs on, so the model always sees the whole picture."""
        # gas under a cent (Base) keeps four decimals so it never reads as zero
        collect_gas = {c.name: _gas_round(claims.gas_cost_usd(160_000, c)) for c in self.chains}
        collect_usd = collect_gas[self.chain.name]
        airdrop_usd = _gas_round(claims.gas_cost_usd(90_000, self.chain))
        out = {"collect_gas_usd": collect_usd, "collect_gas_usd_by_chain": collect_gas, "airdrop_gas_usd": airdrop_usd, "actions": []}
        owner = self.state.get("active_wallet")
        if owner:
            fees = uniswap.scan_fees_all(owner, self.chains)
            drops = airdrops.scan_airdrops(owner, self.chain)
            for p in fees["positions"]:
                if p["usd_total"] > 0:
                    gas = collect_gas[p["chain"]]
                    out["actions"].append({"action": f"collect fees on position {p['token_id']} on {p['chain'].capitalize()}", "chain": p["chain"],
                                           "value_usd": p["usd_total"], "gas_usd": gas, "net_usd": round(p["usd_total"] - gas, 2),
                                           "worth_it": p["usd_total"] > gas})
            for d in drops["airdrops"]:
                if d["claimable"] and d["usd"] is not None:
                    out["actions"].append({"action": f"claim airdrop {d['name']} on Ethereum", "chain": "ethereum", "value_usd": round(d["usd"], 2),
                                           "gas_usd": airdrop_usd, "net_usd": round(d["usd"] - airdrop_usd, 2),
                                           "worth_it": d["usd"] > airdrop_usd})
            out["total_value_usd"] = round(sum(a["value_usd"] for a in out["actions"]), 2)
            out["total_gas_usd"] = round(sum(a["gas_usd"] for a in out["actions"]), 2)
            out["total_net_usd"] = round(out["total_value_usd"] - out["total_gas_usd"], 2)
            out["summary"] = "; ".join(f"{a['action']}: ${a['value_usd']:.2f} value, ${a['gas_usd']:.2f} gas, net ${a['net_usd']:.2f}" for a in out["actions"]) \
                + (f". Total ${out['total_value_usd']:.2f} value, ${out['total_gas_usd']:.2f} gas, net ${out['total_net_usd']:.2f}." if out["actions"] else "Nothing claimable, so no gas to spend.")
        return out

    def v2_collect(self, token_id: int, chain: str | None = None) -> dict:
        target = self._on(chain)
        return {**claims.collect_fees(int(token_id), self._owner(), target), "chain": target.name}

    def v2_claim(self, distributor: str) -> dict:
        return claims.claim_airdrop(distributor, self._owner(), self.chain)

    def _owner(self) -> str:
        owner = self.state.get("active_wallet")
        if not owner:
            raise ValueError("no wallet has been scanned in this conversation yet")
        return owner

    def mapping(self) -> dict[str, Callable]:
        if self.version == "v1":
            return {"scan_wallet": self.v1_scan, "get_price": self.v1_price, "collect_fees": self.v1_collect, "claim_airdrop": self.v1_claim}
        return {"scan_wallet": self.v2_scan, "estimate_gas_cost": self.v2_gas, "collect_fees": self.v2_collect, "claim_airdrop": self.v2_claim}


def tools_for(version: str) -> list[dict]:
    return V1_TOOLS if version == "v1" else V2_TOOLS
