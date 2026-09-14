"""Connection to the local Anvil fork plus the fork-only helpers Salvage relies on."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from web3 import Web3
from web3.contract import Contract

from .config import settings
from .contracts import CHAINLINK_ABI, ERC20_ABI, MERKLE_AIRDROP_ABI, NONFUNGIBLE_POSITION_MANAGER, POSITION_MANAGER_ABI


class Chain:
    """Thin wrapper around web3 for a local Anvil fork."""

    def __init__(self, rpc_url: str | None = None):
        self.rpc_url = rpc_url or settings.fork_rpc_url
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url, request_kwargs={"timeout": 120}))
        if not self.w3.is_connected():
            raise ConnectionError(f"No node at {self.rpc_url}. Start the fork with scripts/start_fork.sh")
        self._erc20_cache: dict[str, Contract] = {}

    # ---------- generic rpc ----------
    def rpc(self, method: str, params: list[Any] | None = None) -> Any:
        resp = self.w3.provider.make_request(method, params or [])
        if "error" in resp:
            raise RuntimeError(f"{method} failed: {resp['error']}")
        return resp.get("result")

    @property
    def block_number(self) -> int:
        return self.w3.eth.block_number

    def checksum(self, address: str) -> str:
        return Web3.to_checksum_address(address)

    # ---------- anvil only ----------
    def impersonate(self, address: str) -> None:
        self.rpc("anvil_impersonateAccount", [self.checksum(address)])

    def stop_impersonating(self, address: str) -> None:
        self.rpc("anvil_stopImpersonatingAccount", [self.checksum(address)])

    def set_balance(self, address: str, wei: int) -> None:
        self.rpc("anvil_setBalance", [self.checksum(address), hex(wei)])

    def snapshot(self) -> str:
        return self.rpc("evm_snapshot")

    def revert(self, snapshot_id: str) -> bool:
        return bool(self.rpc("evm_revert", [snapshot_id]))

    def mine(self, blocks: int = 1) -> None:
        self.rpc("anvil_mine", [hex(blocks)])

    # ---------- contracts ----------
    @property
    def position_manager(self) -> Contract:
        return self.w3.eth.contract(address=self.checksum(NONFUNGIBLE_POSITION_MANAGER), abi=POSITION_MANAGER_ABI)

    def erc20(self, address: str) -> Contract:
        key = address.lower()
        if key not in self._erc20_cache:
            self._erc20_cache[key] = self.w3.eth.contract(address=self.checksum(address), abi=ERC20_ABI)
        return self._erc20_cache[key]

    def chainlink(self, feed: str) -> Contract:
        return self.w3.eth.contract(address=self.checksum(feed), abi=CHAINLINK_ABI)

    def airdrop(self, address: str) -> Contract:
        return self.w3.eth.contract(address=self.checksum(address), abi=MERKLE_AIRDROP_ABI)

    # ---------- token metadata (cached per process) ----------
    @lru_cache(maxsize=512)
    def token_meta(self, address: str) -> tuple[str, int]:
        token = self.erc20(address)
        try:
            symbol = token.functions.symbol().call()
        except Exception:
            symbol = address[:6] + "..." + address[-4:]
        try:
            decimals = int(token.functions.decimals().call())
        except Exception:
            decimals = 18
        return symbol, decimals

    # ---------- transactions from an impersonated account ----------
    def send_as(self, sender: str, fn, value: int = 0, gas: int = 1_500_000) -> dict:
        """Send a contract function call from an impersonated address and wait for the receipt.

        Returns a plain dict with status, tx hash, gas used, and logs. Never raises on a revert:
        the caller decides what a failed receipt means.
        """
        sender = self.checksum(sender)
        self.impersonate(sender)
        if self.w3.eth.get_balance(sender) < Web3.to_wei(1, "ether"):
            self.set_balance(sender, Web3.to_wei(10, "ether"))
        try:
            tx_hash = fn.transact({"from": sender, "value": value, "gas": gas})
        except Exception as exc:  # anvil rejects transactions that revert at estimation time
            return {"status": "reverted", "tx_hash": None, "gas_used": 0, "error": str(exc)[:300], "logs": []}
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        return {
            "status": "success" if receipt["status"] == 1 else "reverted",
            "tx_hash": receipt["transactionHash"].hex(),
            "gas_used": int(receipt["gasUsed"]),
            "block": int(receipt["blockNumber"]),
            "logs": [dict(log) for log in receipt["logs"]],
        }


_chain: Chain | None = None


def get_chain() -> Chain:
    global _chain
    if _chain is None:
        _chain = Chain()
    return _chain
