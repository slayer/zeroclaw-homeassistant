# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Home Assistant addon for [ZeroClaw](https://github.com/zeroclaw-labs/zeroclaw), a Rust-based AI agent runtime.

- **Addon** (`zeroclaw_assistant/`) — Docker container that downloads and runs the ZeroClaw binary
- **Integration** lives in a separate repo: [`slayer/zeroclaw-homeassistant-integration`](https://github.com/slayer/zeroclaw-homeassistant-integration)

## Architecture

The addon generates `config.toml` from HA addon options on every start (`run.sh`) and runs the ZeroClaw binary.

ZeroClaw exposes an HTTP API:
```
POST /webhook  {"message": "..."}  →  {"response": "...", "model": "..."}
GET  /health                        →  status, pairing, uptime, components
GET  /api/status (Bearer auth)      →  model, provider, temperature
POST /pair (X-Pairing-Code header)  →  Bearer token
```

## Known Debt and TODOs

See `docs/plans/2026-03-15-zeroclaw-ha-addon-design.md` for the full TODO list. Key addon items:

- **`host_network: true` should be replaced** with bridge networking
- **`zeroclaw_version` addon option has no runtime effect** — binary is baked at build time

See `docs/2026-03-15-decision-justification.md` for rationale behind architectural choices.
