"""Environment configuration. Everything comes from .env or the process environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
RUNS_DIR = DATA_DIR / "runs"


@dataclass(frozen=True)
class Settings:
    eth_rpc_url: str
    fork_rpc_url: str
    fork_block: int | None
    anthropic_api_key: str
    model_id: str
    prism_host: str
    prism_project_id: str
    prism_api_key: str
    agent_version: str

    @property
    def prism_enabled(self) -> bool:
        return bool(self.prism_api_key and self.prism_project_id)

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_api_key and self.model_id)


def _int_or_none(value: str) -> int | None:
    value = (value or "").strip()
    return int(value) if value else None


def load_settings() -> Settings:
    return Settings(
        eth_rpc_url=os.getenv("ETH_RPC_URL", "https://ethereum-rpc.publicnode.com"),
        fork_rpc_url=os.getenv("FORK_RPC_URL", "http://127.0.0.1:8545"),
        fork_block=_int_or_none(os.getenv("FORK_BLOCK", "")),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        model_id=os.getenv("MODEL_ID", ""),
        prism_host=os.getenv("PRISMTRACE_HOST", "https://prism.blockconvey.com").rstrip("/"),
        prism_project_id=os.getenv("PRISMTRACE_PROJECT_ID", ""),
        prism_api_key=os.getenv("PRISMTRACE_API_KEY", ""),
        agent_version=os.getenv("AGENT_VERSION", "v2").strip().lower(),
    )


settings = load_settings()
