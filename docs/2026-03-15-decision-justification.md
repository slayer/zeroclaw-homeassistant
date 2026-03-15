# Decision Justification Report

Date: 2026-03-15

## Architecture

| Decision | Verdict | Confidence |
|----------|---------|------------|
| A1. Single repo for addon + integration | Correct — both components are tightly coupled, same author, same version | **High** |
| A2. Native `/webhook` API (no OpenAI shim) | Defensible today, but if ZeroClaw adds OpenAI-compatible endpoints, this whole integration becomes redundant | **Medium** |
| A3. `host_network: true` | **Questionable** — exposes gateway on all LAN interfaces over unencrypted HTTP. Should use bridge networking. | **Low** |

## Addon

| Decision | Verdict | Confidence |
|----------|---------|------------|
| B1. Alpine base image | Correct — musl binary on musl Alpine, ~100MB smaller than Debian | **High** |
| B2. Binary download at build time | Right pattern, but `zeroclaw_version` option is a **UX trap** — it's visible in addon UI but has zero effect at runtime | **Medium** |
| B3. Config.toml generation on every start | Fine for MVP, but will frustrate power users who want to edit config directly | **Medium** |
| B4. bashio shebang/logging | Standard HA addon pattern, unambiguously correct | **High** |

## Integration

| Decision | Verdict | Confidence |
|----------|---------|------------|
| C1. HA-managed aiohttp session | Correct — avoids session leaks, idiomatic HA | **High** |
| C2. DataUpdateCoordinator 30s polling | Correct for v1, clean upgrade path to WebSocket/SSE later | **High** |
| C3. Pairing code config flow | Good UX, but **missing reauth flow** — token expiry bricks the integration permanently | **Medium** |
| C4. `ConversationEntity` (vs legacy `AbstractConversationAgent`) | Correct modern approach | **High** |
| C5. `SupportsResponse.ONLY` | Correct, but service handler **can't target a specific instance** in multi-setup | **High/Low** |
| C6. No tests in v1 | **Clear debt** — API client, config flow, and coordinator all have easily testable error paths | **Low** |

## Two Genuinely Questionable Decisions

### 1. `host_network: true` + `0.0.0.0` bind

The addon binds ZeroClaw's gateway on `0.0.0.0:42617` with host networking. This means the gateway is accessible from the entire LAN (and potentially the internet, depending on the user's router). The `/health` endpoint requires no authentication. Once a token is obtained, all communication is over unencrypted HTTP.

**Fix:** Remove `host_network: true` from `config.yaml` and rely on the already-declared `ports` mapping. The integration should use the Supervisor internal DNS name instead of hardcoding `127.0.0.1`. For non-Supervisor installs, bridge networking with explicit port exposure is standard.

### 2. `zeroclaw_version` option does nothing at runtime

The addon `config.yaml` exposes `zeroclaw_version` as a user-configurable option with a default of `"latest"`. The user sees this in the addon configuration UI and might change it expecting something to happen. But the binary is downloaded at build time via the `ZEROCLAW_VERSION` build arg, which is hardcoded to `"latest"` in `build.yaml`. Changing the option at runtime has zero effect.

**Fix:** Either remove the version from the addon options (since it is a build arg) or download the binary at runtime in `run.sh` so the option is honored.

## If Starting Over

1. **Auto-discovery first, not last** — The addon and integration are in the same repo; seamless setup should be table stakes, not a TODO.
2. **Bridge networking + localhost bind by default** — Opt-in LAN exposure, not opt-out.
3. **Reauth flow from day one** — Token invalidation currently bricks the integration.
4. **Minimal test suite with v1** — ~200 lines covering api.py, config_flow, and coordinator error paths.
5. **Evaluate if a custom integration is even needed** — If ZeroClaw ever adds `/v1/chat/completions`, HA's built-in OpenAI integration could replace this entire codebase.

## Detailed Analysis

### A1. Single repo for addon + integration (vs separate repos)

**What was done:** Both the Docker-based HA addon (`zeroclaw_assistant/`) and the Python custom integration (`custom_components/zeroclaw/`) live in one repository.

**Why:** Reduces coordination overhead. The addon and integration are tightly coupled — the integration's API client is shaped exactly around the addon's gateway endpoints. Shipping them from one repo means version alignment is trivial and users get a single add-on repository URL.

**Alternatives not taken:**
- Separate repos (addon repo vs HACS integration repo) — standard in the HA ecosystem when the addon and integration have different maintainers or different release cadences.
- Monorepo with shared CI but separate release artifacts.

**Honest assessment:** This is the right call for v1 and probably long-term. The two components are developed by the same person, share the same version (0.1.0), and there is no realistic scenario where you would ship one without the other. The main risk is that HACS expects `custom_components/<domain>/` at the repository root — this layout satisfies that. The addon repository structure (`repository.yaml` + `zeroclaw_assistant/`) also expects a specific layout, and this satisfies that too.

### A2. Using ZeroClaw's native `/webhook` API (vs implementing an OpenAI-compatible shim)

**What was done:** The integration communicates directly with ZeroClaw's custom HTTP endpoints (`/health`, `/api/status`, `/webhook`, `/pair`). No translation layer.

**Why:** ZeroClaw has its own protocol — `/webhook` accepts `{"message": "..."}` and returns `{"response": "...", "model": "..."}`. Wrapping this in an OpenAI-compatible layer would add complexity for no clear benefit since the HA integration is the only consumer.

**Alternatives not taken:**
- Adding an OpenAI-compatible `/v1/chat/completions` shim in the addon (nginx or a sidecar) so the HA OpenAI integration could be used out of the box.
- Using the existing HA `openai_conversation` integration with a custom `base_url` pointed at ZeroClaw (if ZeroClaw supported that).

**Honest assessment:** Defensible but has a real cost. If ZeroClaw ever adds OpenAI-compatible endpoints, this custom integration becomes redundant boilerplate. The OpenAI-compatible approach would have given streaming, tool use, and conversation history "for free" via HA's existing OpenAI conversation integration. For v1 with simple request/response, the native API is fine. But the moment you need streaming or multi-turn context, the cost of this choice escalates.

### A3. `host_network: true` in addon config

**What was done:** The addon runs with `host_network: true`, sharing the host's network namespace.

**Alternatives not taken:**
- Bridge networking with only port 42617 exposed (the `ports` mapping is already declared).
- Using the HA Supervisor's internal DNS (`<addon-slug>.local.hass.io`) which works without host networking.

**Honest assessment:** `host_network: true` is a security antipattern in the HA addon ecosystem. The gateway binds on `0.0.0.0:42617`, meaning it is exposed on ALL host interfaces. Most well-behaved addons use bridge networking.

### B2. Downloading binary at Docker build time

**What was done:** The Dockerfile downloads the ZeroClaw binary from GitHub Releases at `docker build` time.

**Honest assessment:** Build-time download is the standard pattern and correct here. The downside: `ZEROCLAW_VERSION` build arg is hardcoded to `"latest"` in `build.yaml`, which means every rebuild gets whatever "latest" is at that moment. This is not reproducible.

### B3. Generating config.toml from run.sh on every start

**What was done:** `run.sh` reads `/data/options.json` and generates `/config/zeroclaw/config.toml` on every startup.

**Honest assessment:** Correct for v1. However, the generated config is very minimal — just provider, API key, model, and gateway bind. ZeroClaw has many more config options that are not exposed. Power users will want to edit `config.toml` directly, and the current approach destroys their edits on every restart.

### C3. Config flow uses pairing code

**What was done:** The config flow asks for host, port, and a pairing code, then exchanges it for a Bearer token.

**Honest assessment:** Good UX for manual setup. The main risk is that `unique_id` is `"{host}:{port}"`, which means you cannot re-pair if the token expires without removing and re-adding the integration. There is no `async_step_reauth` flow. The missing auto-discovery is a significant UX gap for the addon case.

### C5. Service handler multi-instance behavior

**What was done:** The `send_message` service iterates over all entries and uses the first available client.

**Honest assessment:** With multiple ZeroClaw instances, there is no way to target a specific one. The service should accept an optional `entry_id` or `device_id` parameter.

### C6. No tests shipped in v1

**What was done:** No `tests/` directory exists. The "smoke test" is just file existence and syntax checks.

**Honest assessment:** Clear debt. The API client has four methods with three error branches each — easily testable with `aioresponses`. The config flow has three error paths. The coordinator has a fallback when `/api/status` fails. None of this is tested.
