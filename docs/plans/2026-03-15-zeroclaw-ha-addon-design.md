# ZeroClaw Home Assistant Addon — Design Document

Date: 2026-03-15

## Overview

Home Assistant addon + custom integration for [ZeroClaw](https://github.com/zeroclaw-labs/zeroclaw) — a Rust-based AI agent runtime. Inspired by [OpenClaw HA addon](https://github.com/techartdev/OpenClawHomeAssistant).

**Scope (v1):** Addon running ZeroClaw in a Docker container + basic custom integration with conversation agent, sensors, and a service call. Future versions will add streaming, richer entities, and deeper HA integration.

## Architecture

Two-component architecture in a single repo:

```
zeroclaw-homeassistant/
├── repository.yaml                    # HA addon repository metadata
├── zeroclaw_assistant/                # HA Addon (Docker container)
│   ├── config.yaml                    # Addon manifest (name, options, ports, arch)
│   ├── build.yaml                     # Base images per architecture
│   ├── Dockerfile                     # Multi-arch: downloads ZeroClaw binary from GitHub releases
│   ├── run.sh                         # Entrypoint: config generation + zeroclaw daemon
│   └── icon.png / logo.png            # Branding
├── custom_components/zeroclaw/        # HA Custom Integration (HACS-compatible)
│   ├── manifest.json                  # Integration metadata
│   ├── __init__.py                    # Setup, service registration
│   ├── api.py                         # HTTP client for ZeroClaw gateway
│   ├── config_flow.py                 # Auto-discovery + manual config
│   ├── coordinator.py                 # DataUpdateCoordinator (polls /health + /api/status)
│   ├── const.py                       # Constants
│   ├── binary_sensor.py               # Connected entity
│   ├── sensor.py                      # Status + Active Model entities
│   ├── conversation.py                # HA Assist conversation agent (POST /webhook)
│   ├── services.yaml                  # Service definitions
│   └── strings.json / translations/   # UI strings
└── docs/
    └── plans/                         # Design docs
```

### Data Flow

```
User (HA Assist / Service call)
  → Custom Integration (Python)
    → POST /webhook or GET /health
      → ZeroClaw Gateway (inside addon container, port 42617)
        → LLM Provider (OpenRouter/Anthropic/OpenAI/Ollama/etc.)
```

## Addon (Docker Container)

### Configuration Options (`config.yaml`)

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `zeroclaw_version` | str | `"latest"` | GitHub release tag to install |
| `llm_provider` | str | `"openrouter"` | Provider name |
| `api_key` | password | required | API key for the provider |
| `default_model` | str | `""` | Model identifier (empty = provider default) |
| `gateway_port` | int | `42617` | Gateway bind port |
| `env_vars` | list | `[]` | Additional env vars (name/value pairs) |

### Dockerfile — Multi-Arch Strategy

- Base image: `ghcr.io/home-assistant/{arch}-base:3.19` (via `build.yaml`)
- At build time: download ZeroClaw binary matching target arch from GitHub releases
- Arch mapping:
  - `amd64` → `zeroclaw-x86_64-unknown-linux-musl`
  - `aarch64` → `zeroclaw-aarch64-unknown-linux-musl`
  - `armv7` → `zeroclaw-armv7-unknown-linux-musleabihf`

### Supported Architectures

```yaml
arch:
  - amd64
  - aarch64
  - armv7
```

### Entrypoint (`run.sh`)

1. Read addon options from `/data/options.json`
2. Generate `config.toml` from options (provider, api key, model, port)
3. Apply any extra env vars
4. Run `zeroclaw daemon`

## Custom Integration

### Setup Flow (`config_flow.py`)

- Auto-discovery via mDNS/zeroconf if the addon is running locally
- Manual config: host, port, pairing code (used to obtain Bearer token via `POST /pair`)
- Stores token after successful pairing

### API Client (`api.py`)

ZeroClaw exposes its own protocol (not OpenAI-compatible):

| Method | Endpoint | Purpose | Timeout |
|--------|----------|---------|---------|
| `GET` | `/health` | Status, paired state, uptime, components | 30s |
| `GET` | `/api/status` | Model, temperature, active channels | 30s |
| `POST` | `/webhook` | Send message, get LLM response | 120s |
| `POST` | `/pair` | Exchange pairing code for Bearer token | 30s |

All calls use `aiohttp` with `Authorization: Bearer <token>`.

### Data Coordinator (`coordinator.py`)

Polls `/health` + `/api/status` every 30 seconds.

### Entities

| Entity | Platform | Source | Details |
|--------|----------|--------|---------|
| ZeroClaw Connected | `binary_sensor` | `/health` | `device_class: connectivity` |
| ZeroClaw Status | `sensor` | `/health` | "ok"/"error", attrs: uptime, paired, component count |
| ZeroClaw Active Model | `sensor` | `/api/status` | Model name, attrs: provider |

### Conversation Agent (`conversation.py`)

- Registers as `zeroclaw` in HA Assist pipeline
- `async_process(user_input)` → calls `POST /webhook` with message
- Returns LLM response as conversation result

### Service (`services.yaml`)

- `zeroclaw.send_message` — fields: `message` (required), returns response in service response data

## ZeroClaw Gateway API Reference

Key endpoints used by this integration:

### `GET /health` (no auth)
```json
{
  "status": "ok",
  "paired": true,
  "require_pairing": true,
  "runtime": {
    "pid": 12345,
    "uptime_seconds": 3600,
    "components": {
      "<name>": { "status": "ok", "restart_count": 0 }
    }
  }
}
```

### `POST /pair` (no auth, rate-limited)
Header: `X-Pairing-Code: <code>`
```json
{ "paired": true, "token": "zc_...", "message": "..." }
```

### `POST /webhook` (Bearer auth)
Request: `{"message": "Hello"}`
Response: `{"response": "Hi!", "model": "gpt-4o"}`

### `GET /api/status` (Bearer auth)
Returns: uptime, model, temperature, active channels.

## TODO — Future Versions

### Communication
- [ ] WebSocket `/ws/chat` support for streaming responses (typing indicators, chunked output in Lovelace)
- [ ] SSE `/api/events` subscription for real-time tool call / error monitoring

### Entities
- [ ] Select entity for switching active model (via `/api/config` PUT)
- [ ] Sensor for last tool call (name, status, duration) — from `/api/events`
- [ ] Sensor for token/cost tracking — from `/api/cost`
- [ ] Sensor for memory entries count — from `/api/memory`
- [ ] Button: clear memory (`DELETE /api/memory`)
- [ ] Button: run diagnostics (`POST /api/doctor`)
- [ ] Event entities for `tool_call`, `llm_request`, `agent_start`/`agent_end`

### Integration
- [ ] Lovelace chat card with streaming, typing indicator, message history
- [ ] MCP server auto-registration (expose HA to ZeroClaw as a tool source)
- [ ] Node registration via `/ws/nodes` (register HA devices as ZeroClaw capabilities)
- [ ] Expose ZeroClaw tools as HA services dynamically (from `/api/tools`)

### Addon
- [ ] Built-in ttyd web terminal for debugging
- [ ] Nginx ingress proxy for sidebar UI (ZeroClaw dashboard inside HA)
- [ ] Version auto-update mechanism
- [ ] Configurable gateway bind mode (loopback/LAN)
