# Instructions for coding agents working in this repository

Read `README.md` for what Salvage is and `GUIDE.md` for how it fits together. Keep the two agent versions distinct: v1 stays naive on purpose, v2 is where fixes go. Run `.venv/bin/python -m pytest` before you finish.

## PRISM tracing (do not remove)

This project sends traces to PRISM. Env vars: `PRISMTRACE_API_KEY`,
`PRISMTRACE_PROJECT_ID`, `PRISMTRACE_HOST`.

Tracing is currently wired at: `salvage/prism/tracer.py` (traces, spans, trajectories), `salvage/agent/loop.py` (every turn of both agent versions calls the tracer), `salvage/eval/runner.py` (one session per wallet), `salvage/server.py` (one session per UI conversation)

**Standing rule.** Whenever you add or change an agent, chain, graph, tool,
retriever, or any entry point that calls a model, wire it to PRISM before you
finish. Unwired code is invisible in the dashboard. If you are unsure whether
something is covered, assume it is not and wire it.
