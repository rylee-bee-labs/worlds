# Small Model Decision — Worlds

> **Status:** Reference · **Verified:** 2026-09-26 · **Canonical for:** which small local model Worlds defaults to, and why · **Read this if:** you are changing the default brain, the fallback, or the `reasoning` provider.

**In short:** the default small brain is **Qwen3 1.7B Q4_K_M**, with **LFM2.5 2.6B Q4_K_M** as fallback — chosen from a 14-task, CPU-only pass on 2026-09-13. The brain is wired through the optional `reasoning` capability; it helps the world operate without ever having write access to world state.

Date: 2026-09-13
Benchmark commit: 78e3fb0

## Decision

**Default small brain: Qwen3 1.7B Q4_K_M**

**Fallback: LFM2.5 2.6B Q4_K_M**

## Evidence

Quick-final pass: 14 high-signal tasks, 1 run each, CPU-only (AMD Ryzen 7 7800X3D).

| Model | PASS | PARTIAL | FAIL | Avg latency |
|-------|------|---------|------|-------------|
| Qwen3 1.7B | 6 | 8 | 0 | 12.4s |
| LFM2.5 2.6B | 4 | 10 | 0 | 15.4s |

## Why Qwen3

- Produces structured prose with clear status, reasoning, and action
- Correctly handles "boring healthy" — says "nothing needs attention" without inventing work
- Preserves UNKNOWN — says "unknown" when data is missing
- Identifies reservation patterns — flags "backup completed in 2 minutes" as suspicious
- Preserves unknown enum values — does not coerce unrecognized values to defaults
- Notices lock/sensor mismatches in multi-step scenarios
- Faster average latency (12.4s vs 15.4s)

## Why not LFM2.5 as default

- Tends to output tool-call syntax (`<|tool_call_start|>[tool()]`) instead of prose reasoning
- For "boring healthy" states, calls `read_tool` instead of reporting "nothing needs attention"
- Empty response observed on trusted-translation task
- More PARTIAL results overall (10 vs 8)

## Architecture

The brain is wired through the existing `reasoning` capability in the provider registry:

```
config/connections.json
  type: openai_compat
  capability: reasoning
  base_url: <llama.cpp endpoint serving Qwen3>
  model: <alias>
```

The brain helps the world operate without becoming the world. It does not have write access to world state, policies, or authoritative facts.

## Files

- Quick-final results: `bench/finals/runs/quick-worlds-qwen3-1.7b-*.jsonl` — these raw run files are not tracked in this repo (there is no `bench/` directory as of 2026-09-26); the numbers above are the record
- Decision packet: `bench/finals/DECISION-PACKET.md` — same; not present in the repo
- This document: `docs/adr/0002-default-brain-selection.md`
