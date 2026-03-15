# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Home Assistant addon + custom integration for [ZeroClaw](https://github.com/zeroclaw-labs/zeroclaw), a Rust-based AI agent runtime. Two components in one repo:

- **Addon** (`zeroclaw_assistant/`) — Docker container that downloads and runs the ZeroClaw binary
- **Integration** (`custom_components/zeroclaw/`) — Python custom integration for HA (HACS-compatible)

## Architecture

The integration talks to ZeroClaw's **native HTTP API** (not OpenAI-compatible):

```
HA Assist / Service call
  → Integration (api.py)
    → POST /webhook  {"message": "..."}  →  {"response": "...", "model": "..."}
    → GET  /health                        →  status, pairing, uptime, components
    → GET  /api/status (Bearer auth)      →  model, provider, temperature
    → POST /pair (X-Pairing-Code header)  →  Bearer token
```

Key design choices:
- Uses HA-managed `aiohttp` session (`async_get_clientsession(hass)`), not standalone sessions
- `DataUpdateCoordinator` polls `/health` + `/api/status` every 30s
- Config flow uses ZeroClaw's pairing code mechanism (no auto-discovery yet)
- `CONF_HOST` and `CONF_PORT` come from `homeassistant.const`, not redefined locally
- Addon generates `config.toml` from HA addon options on every start (`run.sh`)

## Commands

```bash
# Verify Python syntax compiles
python3 -c "import py_compile; import glob; [py_compile.compile(f, doraise=True) for f in glob.glob('custom_components/zeroclaw/*.py')]"

# Verify JSON files
python3 -c "import json; json.load(open('custom_components/zeroclaw/manifest.json')); json.load(open('custom_components/zeroclaw/strings.json')); print('OK')"
```

No test suite exists yet. When adding tests, use `pytest` with `pytest-homeassistant-custom-component`.

## Known Debt and TODOs

See `docs/plans/2026-03-15-zeroclaw-ha-addon-design.md` for the full TODO list. Key items:

- **WebSocket streaming** (`/ws/chat`) for conversation agent — currently uses synchronous `/webhook`
- **SSE events** (`/api/events`) for real-time tool call monitoring
- **Auto-discovery** via HA Supervisor API (detect addon, skip manual config)
- **Reauth flow** (`async_step_reauth`) — token expiry currently bricks the integration
- **`host_network: true` should be replaced** with bridge networking
- **`zeroclaw_version` addon option has no runtime effect** — binary is baked at build time
- Additional entities: model selector, tool call sensors, memory count, buttons, event entities
- Lovelace chat card, MCP server registration, node registration

See `docs/2026-03-15-decision-justification.md` for rationale behind architectural choices.
