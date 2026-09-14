"""Command line entry points.

    python -m salvage.cli doctor                 check the fork, the model, and PRISM
    python -m salvage.cli scan <address>         verified scan of one wallet (what v2 sees)
    python -m salvage.cli raw <address>          raw scan of one wallet (what v1 sees)
    python -m salvage.cli chat [v1|v2]           talk to the agent
    python -m salvage.cli eval <v1|v2> [limit]   run the wallet set through a version and score it
    python -m salvage.cli rescore                re-score the latest runs with the current rules (no model calls)
    python -m salvage.cli report                 before and after table for the latest v1 and v2 runs
    python -m salvage.cli evidence               write EVIDENCE.md: the table, the PRISM session names, the worst replies
    python -m salvage.cli serve [port]           start the web UI
"""

from __future__ import annotations

import json
import sys

from .config import settings


def cmd_doctor() -> None:
    from .chain import get_chain
    from .prism.tracer import get_tracer

    print("fork:", end=" ")
    try:
        chain = get_chain()
        print(f"ok, block {chain.block_number} at {chain.rpc_url}")
    except Exception as exc:
        print(f"not reachable ({exc})")
    print("model:", "configured" if settings.llm_enabled else "missing ANTHROPIC_API_KEY or MODEL_ID")
    print("prism:", json.dumps(get_tracer().doctor(), indent=2, default=str))


def cmd_scan(address: str, raw: bool = False) -> None:
    from .tools import airdrops, uniswap

    if raw:
        print(json.dumps({"uniswap": uniswap.scan_fees_raw(address), "airdrops": airdrops.scan_airdrops_raw(address)}, indent=2, default=str))
    else:
        fees, drops = uniswap.scan_fees(address), airdrops.scan_airdrops(address)
        print(json.dumps({"uniswap": fees, "airdrops": drops, "usd_total": round(fees["usd_total"] + drops["usd_total"], 2)}, indent=2, default=str))


def cmd_chat(version: str) -> None:
    from .agent.loop import Agent

    agent = Agent(version)
    print(f"Salvage {version}, session {agent.session_id}. Type a wallet address or a question. Ctrl+C to quit.")
    while True:
        try:
            text = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue
        turn = agent.chat(text)
        for call in turn["tool_calls"]:
            print(f"  [tool {call['name']}] {json.dumps(call['input'])} -> {json.dumps(call['output'], default=str)[:400]}")
        print(turn["reply"])


def cmd_eval(version: str, limit: int | None) -> None:
    from .eval.runner import run_eval

    run_eval(version, limit=limit)


def cmd_rescore() -> None:
    from .eval.runner import latest_run, rescore

    for version in ("v1", "v2"):
        path = latest_run(version)
        if path:
            print(version, json.dumps(rescore(path), indent=2))


def cmd_report() -> None:
    from .eval.report import compare, worst_examples

    print(compare())
    for version in ("v1", "v2"):
        bad = worst_examples(version)
        if bad:
            print(f"\nworst {version} examples:")
            for b in bad:
                print(f"  {b['label']}: truth ${b['truth']:,.2f}, reported {b['reported']}, phantom={b['phantom']}\n    {b['reply1'][:200]}")


def cmd_evidence() -> None:
    from pathlib import Path

    from .config import ROOT
    from .eval.report import evidence_bundle

    path = evidence_bundle(Path(ROOT) / "EVIDENCE.md")
    print(f"wrote {path}")


def cmd_serve(port: int) -> None:
    import uvicorn

    uvicorn.run("salvage.server:app", host="127.0.0.1", port=port, reload=False)


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("help", "h"):
        print(__doc__)
        return
    cmd, args = argv[0], argv[1:]
    if cmd == "doctor":
        cmd_doctor()
    elif cmd == "scan":
        cmd_scan(args[0])
    elif cmd == "raw":
        cmd_scan(args[0], raw=True)
    elif cmd == "chat":
        cmd_chat(args[0] if args else settings.agent_version)
    elif cmd == "eval":
        cmd_eval(args[0], int(args[1]) if len(args) > 1 else None)
    elif cmd == "rescore":
        cmd_rescore()
    elif cmd == "report":
        cmd_report()
    elif cmd == "evidence":
        cmd_evidence()
    elif cmd == "serve":
        cmd_serve(int(args[0]) if args else 8000)
    else:
        print(f"unknown command {cmd}\n{__doc__}")


if __name__ == "__main__":
    main()
