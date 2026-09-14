"""Tool definitions the model sees, and the executors behind them, for v1 and v2."""

from __future__ import annotations

from typing import Callable

from ..chain import Chain
from ..tools import airdrops, claims, pricing, uniswap

ADDRESS_PARAM = {"type": "string", "description": "Ethereum wallet address, 0x followed by 40 hex characters"}


# ---------- v1: raw tools, a first draft ----------

V1_TOOLS = [
    {
        "name": "scan_wallet",
        "description": "Scan a wallet for uncollected Uniswap v3 LP fees and unclaimed airdrops. Returns the positions and airdrop entries with their amounts as reported by the contracts.",
        "input_schema": {"type": "object", "properties": {"address": ADDRESS_PARAM}, "required": ["address"]},
    },
    {
        "name": "get_price",
        "description": "Get the latest Chainlink USD price data for a token address.",
        "input_schema": {"type": "object", "properties": {"token": {"type": "string", "description": "token contract address"}}, "required": ["token"]},
    },
    {
        "name": "collect_fees",
        "description": "Collect the fees of a Uniswap v3 position for the active wallet. Returns the transaction hash.",
        "input_schema": {"type": "object", "properties": {"token_id": {"type": "integer", "description": "the position NFT id"}}, "required": ["token_id"]},
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
        "description": "Scan a wallet for uncollected Uniswap v3 LP fees and unclaimed airdrops. Amounts are already converted to token units and priced in USD. Includes a plain text summary you can quote.",
        "input_schema": {"type": "object", "properties": {"address": ADDRESS_PARAM}, "required": ["address"]},
    },
    {
        "name": "estimate_gas_cost",
        "description": "Estimate the USD gas cost of one collect or one airdrop claim at the current network fee.",
        "input_schema": {"type": "object", "properties": {"kind": {"type": "string", "enum": ["collect", "airdrop"]}}, "required": ["kind"]},
    },
    {
        "name": "collect_fees",
        "description": "Collect the fees of a Uniswap v3 position for the active wallet. Simulates first, executes, reads the receipt, and reports status and the amounts that actually arrived.",
        "input_schema": {"type": "object", "properties": {"token_id": {"type": "integer", "description": "the position NFT id"}}, "required": ["token_id"]},
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
            lines.append(f"Uniswap position #{pos['token_id']} ({pos['pool']}): " + " and ".join(parts) + f", total ${pos['usd_total']:.2f}")
    for d in drops["airdrops"]:
        value = f"${d['usd']:.2f}" if d["usd"] is not None else "unpriced"
        lines.append(f"Airdrop {d['name']}: {d['amount_units']:.6f} {d['symbol']} ({value}), status {d['status']}")
    total = fees["usd_total"] + drops["usd_total"]
    if not lines:
        return "Nothing claimable in this wallet."
    return "\n".join(lines) + f"\nTotal claimable now: ${total:.2f}"


class Executors:
    """Builds the name to function map for a version, bound to a chain and a mutable active wallet."""

    def __init__(self, version: str, chain: Chain, state: dict):
        self.version = version
        self.chain = chain
        self.state = state  # {"active_wallet": str | None}

    def _set_active(self, address: str) -> None:
        self.state["active_wallet"] = self.chain.checksum(address)

    # v1
    def v1_scan(self, address: str) -> dict:
        self._set_active(address)
        return {"uniswap": uniswap.scan_fees_raw(address, self.chain), "airdrops": airdrops.scan_airdrops_raw(address, self.chain)}

    def v1_price(self, token: str) -> dict:
        return pricing.raw_price(token, self.chain)

    def v1_collect(self, token_id: int) -> dict:
        return claims.collect_fees_v1(int(token_id), self._owner(), self.chain)

    def v1_claim(self, distributor: str) -> dict:
        return claims.claim_airdrop_v1(distributor, self._owner(), self.chain)

    # v2
    def v2_scan(self, address: str) -> dict:
        self._set_active(address)
        fees = uniswap.scan_fees(address, self.chain)
        drops = airdrops.scan_airdrops(address, self.chain)
        return {"uniswap": fees, "airdrops": drops, "usd_total": round(fees["usd_total"] + drops["usd_total"], 2), "summary": _summary(fees, drops)}

    def v2_gas(self, kind: str) -> dict:
        gas = 160_000 if kind == "collect" else 90_000
        return {"kind": kind, "estimated_gas": gas, "usd": round(claims.gas_cost_usd(gas, self.chain), 2)}

    def v2_collect(self, token_id: int) -> dict:
        return claims.collect_fees(int(token_id), self._owner(), self.chain)

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
