# ZeroClaw Home Assistant Addon + Integration — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Home Assistant addon that runs ZeroClaw in a Docker container, plus a custom integration that provides a conversation agent, sensors, and a service call.

**Architecture:** Two components in one repo — a Docker-based HA addon (`zeroclaw_assistant/`) downloads and runs the ZeroClaw binary, and a Python custom integration (`custom_components/zeroclaw/`) communicates with it via ZeroClaw's native HTTP API (`/health`, `/api/status`, `/webhook`, `/pair`).

**Tech Stack:** Bash + Docker (addon), Python 3.12 + aiohttp + Home Assistant APIs (integration), pytest + pytest-homeassistant-custom-component (tests)

**Design doc:** `docs/plans/2026-03-15-zeroclaw-ha-addon-design.md`

---

### Task 1: Repository Scaffold

**Files:**
- Create: `repository.yaml`
- Create: `.gitignore`

**Step 1: Create repository.yaml**

```yaml
name: ZeroClaw Assistant Add-ons
url: https://github.com/zeroclaw-labs/zeroclaw-homeassistant
maintainer: Slayer
```

**Step 2: Create .gitignore**

```gitignore
__pycache__/
*.py[cod]
*.egg-info/
.eggs/
dist/
build/
.venv/
.pytest_cache/
.mypy_cache/
*.log
```

**Step 3: Initialize git repo**

Run: `git init && git add -A && git commit -m "init: repository scaffold"`

---

### Task 2: Addon — config.yaml

**Files:**
- Create: `zeroclaw_assistant/config.yaml`

**Step 1: Create addon manifest**

```yaml
name: ZeroClaw Assistant
version: "0.1.0"
slug: zeroclaw_assistant
description: Run ZeroClaw AI agent runtime as a Home Assistant addon
url: https://github.com/zeroclaw-labs/zeroclaw
arch:
  - amd64
  - aarch64
  - armv7
startup: services
boot: auto
init: false
host_network: true
ports:
  42617/tcp: 42617
ports_description:
  42617/tcp: ZeroClaw Gateway
map:
  - addon_config:rw
  - share:rw
options:
  zeroclaw_version: "latest"
  llm_provider: "openrouter"
  api_key: ""
  default_model: ""
  gateway_port: 42617
  env_vars: []
schema:
  zeroclaw_version: str
  llm_provider: list(openrouter|anthropic|openai|groq|mistral|deepseek|together|fireworks|ollama|custom)
  api_key: password
  default_model: str?
  gateway_port: int(1024,65535)
  env_vars:
    - name: str
      value: str
```

**Step 2: Commit**

```bash
git add zeroclaw_assistant/config.yaml
git commit -m "feat: addon config.yaml with options schema"
```

---

### Task 3: Addon — build.yaml

**Files:**
- Create: `zeroclaw_assistant/build.yaml`

**Step 1: Create build config**

HA addon builder uses `build_from` to select base image per arch. We use Alpine (smaller, ZeroClaw is a static musl binary).

```yaml
build_from:
  amd64: ghcr.io/home-assistant/amd64-base:3.19
  aarch64: ghcr.io/home-assistant/aarch64-base:3.19
  armv7: ghcr.io/home-assistant/armv7-base:3.19
args:
  ZEROCLAW_VERSION: "latest"
```

**Step 2: Commit**

```bash
git add zeroclaw_assistant/build.yaml
git commit -m "feat: addon build.yaml with multi-arch base images"
```

---

### Task 4: Addon — Dockerfile

**Files:**
- Create: `zeroclaw_assistant/Dockerfile`

**Step 1: Create Dockerfile**

The Dockerfile downloads the ZeroClaw binary at build time, mapping Docker `TARGETARCH` to ZeroClaw release artifact names. Uses a helper script to resolve the download URL. At runtime, `run.sh` handles config generation.

```dockerfile
ARG BUILD_FROM
FROM ${BUILD_FROM}

ARG ZEROCLAW_VERSION=latest

# Install runtime dependencies
# jq: parse /data/options.json
# curl: download zeroclaw binary (if version=latest, resolve at runtime)
# ca-certificates: TLS for HTTPS calls to LLM providers
RUN apk add --no-cache jq curl ca-certificates

# Download ZeroClaw binary matching container architecture
RUN set -eux; \
    case "$(uname -m)" in \
      x86_64)  ARCH="x86_64-unknown-linux-musl" ;; \
      aarch64) ARCH="aarch64-unknown-linux-musl" ;; \
      armv7l)  ARCH="armv7-unknown-linux-musleabihf" ;; \
      *)       echo "Unsupported arch: $(uname -m)" && exit 1 ;; \
    esac; \
    if [ "${ZEROCLAW_VERSION}" = "latest" ]; then \
      DOWNLOAD_URL="https://github.com/zeroclaw-labs/zeroclaw/releases/latest/download/zeroclaw-${ARCH}.tar.gz"; \
    else \
      DOWNLOAD_URL="https://github.com/zeroclaw-labs/zeroclaw/releases/download/${ZEROCLAW_VERSION}/zeroclaw-${ARCH}.tar.gz"; \
    fi; \
    curl -fsSL "${DOWNLOAD_URL}" -o /tmp/zeroclaw.tar.gz && \
    tar xzf /tmp/zeroclaw.tar.gz -C /usr/local/bin/ && \
    chmod +x /usr/local/bin/zeroclaw && \
    rm /tmp/zeroclaw.tar.gz

COPY run.sh /
RUN chmod +x /run.sh

CMD [ "/run.sh" ]
```

> Note: The exact archive structure (tar.gz with binary inside) may vary. If ZeroClaw releases a bare binary instead of a tarball, change `tar xzf` to a direct `curl -o /usr/local/bin/zeroclaw`. Verify against actual release artifacts before first build.

**Step 2: Commit**

```bash
git add zeroclaw_assistant/Dockerfile
git commit -m "feat: multi-arch Dockerfile downloading ZeroClaw binary"
```

---

### Task 5: Addon — run.sh Entrypoint

**Files:**
- Create: `zeroclaw_assistant/run.sh`

**Step 1: Create entrypoint script**

```bash
#!/usr/bin/with-contenv bashio
# ZeroClaw Home Assistant Addon Entrypoint
# Reads HA addon options, generates config.toml, starts zeroclaw daemon.

set -euo pipefail

CONFIG_DIR="/config/zeroclaw"
CONFIG_FILE="${CONFIG_DIR}/config.toml"
OPTIONS_FILE="/data/options.json"

# --- Read addon options ---
LLM_PROVIDER=$(jq -r '.llm_provider' "${OPTIONS_FILE}")
API_KEY=$(jq -r '.api_key' "${OPTIONS_FILE}")
DEFAULT_MODEL=$(jq -r '.default_model // ""' "${OPTIONS_FILE}")
GATEWAY_PORT=$(jq -r '.gateway_port // 42617' "${OPTIONS_FILE}")

# --- Apply extra env vars ---
ENV_COUNT=$(jq '.env_vars | length' "${OPTIONS_FILE}")
for i in $(seq 0 $((ENV_COUNT - 1))); do
  NAME=$(jq -r ".env_vars[$i].name" "${OPTIONS_FILE}")
  VALUE=$(jq -r ".env_vars[$i].value" "${OPTIONS_FILE}")
  export "${NAME}=${VALUE}"
done

# --- Generate config.toml ---
mkdir -p "${CONFIG_DIR}"

cat > "${CONFIG_FILE}" <<EOF
# Auto-generated by ZeroClaw HA addon — edits will be overwritten on restart.

default_provider = "${LLM_PROVIDER}"
api_key = "${API_KEY}"
EOF

if [ -n "${DEFAULT_MODEL}" ]; then
  echo "default_model = \"${DEFAULT_MODEL}\"" >> "${CONFIG_FILE}"
fi

cat >> "${CONFIG_FILE}" <<EOF

[gateway]
bind = "0.0.0.0:${GATEWAY_PORT}"
EOF

bashio::log.info "Starting ZeroClaw daemon (provider=${LLM_PROVIDER}, port=${GATEWAY_PORT})"

# --- Start ZeroClaw ---
exec zeroclaw daemon --config "${CONFIG_FILE}"
```

> Note: `bashio` is the standard HA addon shell library available in all HA base images. The `#!/usr/bin/with-contenv bashio` shebang loads the S6 container environment. If the base image doesn't include bashio, fall back to `#!/bin/sh` and remove `bashio::log.info` calls in favor of plain `echo`.

> Note: The `--config` flag for `zeroclaw daemon` needs verification against actual CLI. ZeroClaw may use `--config-file`, `ZEROCLAW_CONFIG` env var, or `~/.zeroclaw/config.toml` by default. Adjust before first build.

**Step 2: Commit**

```bash
git add zeroclaw_assistant/run.sh
git commit -m "feat: addon entrypoint - config generation and daemon start"
```

---

### Task 6: Integration — Constants and Manifest

**Files:**
- Create: `custom_components/zeroclaw/__init__.py` (empty placeholder)
- Create: `custom_components/zeroclaw/const.py`
- Create: `custom_components/zeroclaw/manifest.json`

**Step 1: Create const.py**

```python
DOMAIN = "zeroclaw"

PLATFORMS = ["sensor", "binary_sensor", "conversation"]

# Addon discovery
ADDON_SLUG = "zeroclaw_assistant"

# API endpoints
ENDPOINT_HEALTH = "/health"
ENDPOINT_STATUS = "/api/status"
ENDPOINT_WEBHOOK = "/webhook"
ENDPOINT_PAIR = "/pair"

# Defaults
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 42617
POLL_INTERVAL_SECONDS = 30

# Config keys
CONF_HOST = "host"
CONF_PORT = "port"
CONF_TOKEN = "token"
CONF_PAIRING_CODE = "pairing_code"

# Data keys
DATA_CLIENT = "client"
DATA_COORDINATOR = "coordinator"
```

**Step 2: Create manifest.json**

```json
{
  "domain": "zeroclaw",
  "name": "ZeroClaw Assistant",
  "codeowners": [],
  "config_flow": true,
  "dependencies": ["conversation"],
  "documentation": "https://github.com/zeroclaw-labs/zeroclaw",
  "integration_type": "hub",
  "iot_class": "local_polling",
  "issue_tracker": "https://github.com/zeroclaw-labs/zeroclaw-homeassistant/issues",
  "requirements": [],
  "version": "0.1.0"
}
```

**Step 3: Create empty __init__.py placeholder**

```python
"""ZeroClaw Assistant integration for Home Assistant."""
```

**Step 4: Commit**

```bash
git add custom_components/zeroclaw/
git commit -m "feat: integration scaffold - const, manifest, init placeholder"
```

---

### Task 7: Integration — API Client

**Files:**
- Create: `custom_components/zeroclaw/api.py`

**Step 1: Create API client**

```python
"""HTTP client for ZeroClaw gateway API."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from .const import (
    ENDPOINT_HEALTH,
    ENDPOINT_PAIR,
    ENDPOINT_STATUS,
    ENDPOINT_WEBHOOK,
)

_LOGGER = logging.getLogger(__name__)

TIMEOUT_DEFAULT = aiohttp.ClientTimeout(total=30)
TIMEOUT_WEBHOOK = aiohttp.ClientTimeout(total=120)


class ZeroClawConnectionError(Exception):
    """Error connecting to ZeroClaw gateway."""


class ZeroClawAuthError(Exception):
    """Authentication error (invalid or missing token)."""


class ZeroClawApiError(Exception):
    """General API error from gateway."""


class ZeroClawApiClient:
    """Client for ZeroClaw gateway HTTP API."""

    def __init__(
        self,
        host: str,
        port: int,
        token: str | None = None,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._token = token
        self._session = session
        self._base_url = f"http://{host}:{port}"

    def _headers(self, auth: bool = True) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if auth and self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def async_pair(self, pairing_code: str) -> str:
        """Exchange pairing code for Bearer token. Returns the token."""
        session = await self._get_session()
        try:
            resp = await session.post(
                f"{self._base_url}{ENDPOINT_PAIR}",
                headers={"X-Pairing-Code": pairing_code},
                timeout=TIMEOUT_DEFAULT,
            )
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise ZeroClawConnectionError(
                f"Cannot connect to ZeroClaw at {self._base_url}"
            ) from err

        if resp.status == 403:
            raise ZeroClawAuthError("Invalid pairing code")
        if resp.status == 429:
            raise ZeroClawApiError("Too many pairing attempts, try later")
        resp.raise_for_status()

        data = await resp.json()
        self._token = data["token"]
        return data["token"]

    async def async_get_health(self) -> dict[str, Any]:
        """GET /health — no auth required."""
        session = await self._get_session()
        try:
            resp = await session.get(
                f"{self._base_url}{ENDPOINT_HEALTH}",
                timeout=TIMEOUT_DEFAULT,
            )
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise ZeroClawConnectionError(
                f"Cannot connect to ZeroClaw at {self._base_url}"
            ) from err
        resp.raise_for_status()
        return await resp.json()

    async def async_get_status(self) -> dict[str, Any]:
        """GET /api/status — requires auth."""
        session = await self._get_session()
        try:
            resp = await session.get(
                f"{self._base_url}{ENDPOINT_STATUS}",
                headers=self._headers(),
                timeout=TIMEOUT_DEFAULT,
            )
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise ZeroClawConnectionError(
                f"Cannot connect to ZeroClaw at {self._base_url}"
            ) from err
        if resp.status == 401:
            raise ZeroClawAuthError("Invalid or expired token")
        resp.raise_for_status()
        return await resp.json()

    async def async_send_message(self, message: str) -> dict[str, Any]:
        """POST /webhook — send message, get LLM response."""
        session = await self._get_session()
        try:
            resp = await session.post(
                f"{self._base_url}{ENDPOINT_WEBHOOK}",
                headers=self._headers(),
                json={"message": message},
                timeout=TIMEOUT_WEBHOOK,
            )
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise ZeroClawConnectionError(
                f"Cannot connect to ZeroClaw at {self._base_url}"
            ) from err
        if resp.status == 401:
            raise ZeroClawAuthError("Invalid or expired token")
        resp.raise_for_status()
        return await resp.json()

    async def async_close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
```

**Step 2: Commit**

```bash
git add custom_components/zeroclaw/api.py
git commit -m "feat: ZeroClaw API client - health, status, webhook, pairing"
```

---

### Task 8: Integration — Data Coordinator

**Files:**
- Create: `custom_components/zeroclaw/coordinator.py`

**Step 1: Create coordinator**

```python
"""DataUpdateCoordinator for ZeroClaw gateway polling."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ZeroClawApiClient, ZeroClawConnectionError, ZeroClawAuthError
from .const import DOMAIN, POLL_INTERVAL_SECONDS

_LOGGER = logging.getLogger(__name__)


class ZeroClawCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls /health and /api/status every 30s."""

    def __init__(self, hass: HomeAssistant, client: ZeroClawApiClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=POLL_INTERVAL_SECONDS),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        # Always check health first (no auth needed)
        try:
            health = await self.client.async_get_health()
        except ZeroClawConnectionError as err:
            raise UpdateFailed(f"Cannot reach ZeroClaw gateway: {err}") from err

        connected = health.get("status") == "ok"
        result: dict[str, Any] = {
            "connected": connected,
            "status": health.get("status", "unknown"),
            "paired": health.get("paired", False),
            "uptime_seconds": health.get("runtime", {}).get("uptime_seconds"),
            "components": health.get("runtime", {}).get("components", {}),
            "model": None,
            "provider": None,
        }

        # Best-effort status fetch (needs auth, may fail)
        if connected:
            try:
                status = await self.client.async_get_status()
                result["model"] = status.get("model")
                result["provider"] = status.get("provider")
            except (ZeroClawConnectionError, ZeroClawAuthError):
                _LOGGER.debug("Could not fetch /api/status, skipping")
            except Exception:
                _LOGGER.debug("Unexpected error fetching /api/status", exc_info=True)

        return result
```

**Step 2: Commit**

```bash
git add custom_components/zeroclaw/coordinator.py
git commit -m "feat: data coordinator polling health and status"
```

---

### Task 9: Integration — Config Flow

**Files:**
- Create: `custom_components/zeroclaw/config_flow.py`
- Create: `custom_components/zeroclaw/strings.json`

**Step 1: Create config_flow.py**

```python
"""Config flow for ZeroClaw integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT

from .api import (
    ZeroClawApiClient,
    ZeroClawAuthError,
    ZeroClawConnectionError,
)
from .const import (
    CONF_PAIRING_CODE,
    CONF_TOKEN,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_PAIRING_CODE): str,
    }
)


class ZeroClawConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ZeroClaw."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user-initiated setup: host, port, pairing code."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            pairing_code = user_input[CONF_PAIRING_CODE]

            client = ZeroClawApiClient(host=host, port=port)
            try:
                token = await client.async_pair(pairing_code)
            except ZeroClawConnectionError:
                errors["base"] = "cannot_connect"
            except ZeroClawAuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected error during pairing")
                errors["base"] = "unknown"
            else:
                # Check for duplicate entries
                await self.async_set_unique_id(f"{host}:{port}")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"ZeroClaw ({host}:{port})",
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_TOKEN: token,
                    },
                )
            finally:
                await client.async_close()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
```

**Step 2: Create strings.json**

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Connect to ZeroClaw",
        "description": "Enter the ZeroClaw gateway address and pairing code. Find the pairing code in ZeroClaw logs or run `zeroclaw gateway` to see it.",
        "data": {
          "host": "Host",
          "port": "Port",
          "pairing_code": "Pairing Code"
        }
      }
    },
    "error": {
      "cannot_connect": "Cannot connect to ZeroClaw gateway",
      "invalid_auth": "Invalid pairing code",
      "unknown": "Unexpected error"
    },
    "abort": {
      "already_configured": "This ZeroClaw instance is already configured"
    }
  },
  "entity": {
    "binary_sensor": {
      "connected": {
        "name": "Connected"
      }
    },
    "sensor": {
      "status": {
        "name": "Status"
      },
      "active_model": {
        "name": "Active Model"
      }
    }
  },
  "services": {
    "send_message": {
      "name": "Send Message",
      "description": "Send a message to ZeroClaw and get a response.",
      "fields": {
        "message": {
          "name": "Message",
          "description": "The message to send"
        }
      }
    }
  }
}
```

**Step 3: Commit**

```bash
git add custom_components/zeroclaw/config_flow.py custom_components/zeroclaw/strings.json
git commit -m "feat: config flow with pairing code auth"
```

---

### Task 10: Integration — __init__.py (Setup + Service)

**Files:**
- Modify: `custom_components/zeroclaw/__init__.py`

**Step 1: Implement integration setup**

Replace the placeholder `__init__.py` with full setup:

```python
"""ZeroClaw Assistant integration for Home Assistant."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.helpers import config_validation as cv

from .api import ZeroClawApiClient
from .const import (
    CONF_TOKEN,
    DATA_CLIENT,
    DATA_COORDINATOR,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import ZeroClawCoordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_SEND_MESSAGE = "send_message"
SERVICE_SEND_MESSAGE_SCHEMA = vol.Schema(
    {vol.Required("message"): cv.string}
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ZeroClaw from a config entry."""
    client = ZeroClawApiClient(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        token=entry.data[CONF_TOKEN],
        session=None,
    )

    coordinator = ZeroClawCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_CLIENT: client,
        DATA_COORDINATOR: coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register service once (shared across all entries)
    if not hass.services.has_service(DOMAIN, SERVICE_SEND_MESSAGE):
        async def handle_send_message(call: ServiceCall) -> ServiceResponse:
            """Handle send_message service call."""
            message = call.data["message"]
            # Use the first available client
            for entry_data in hass.data[DOMAIN].values():
                if DATA_CLIENT in entry_data:
                    result = await entry_data[DATA_CLIENT].async_send_message(message)
                    return {
                        "response": result.get("response", ""),
                        "model": result.get("model", ""),
                    }
            return {"response": "No ZeroClaw instance available", "model": ""}

        hass.services.async_register(
            DOMAIN,
            SERVICE_SEND_MESSAGE,
            handle_send_message,
            schema=SERVICE_SEND_MESSAGE_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a ZeroClaw config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        entry_data = hass.data[DOMAIN].pop(entry.entry_id)
        await entry_data[DATA_CLIENT].async_close()

    # Remove service if no entries left
    if not hass.data.get(DOMAIN):
        hass.services.async_remove(DOMAIN, SERVICE_SEND_MESSAGE)

    return unload_ok
```

**Step 2: Commit**

```bash
git add custom_components/zeroclaw/__init__.py
git commit -m "feat: integration setup with service registration"
```

---

### Task 11: Integration — services.yaml

**Files:**
- Create: `custom_components/zeroclaw/services.yaml`

**Step 1: Create services definition**

```yaml
send_message:
  name: Send Message
  description: Send a message to ZeroClaw and get a response.
  fields:
    message:
      name: Message
      description: The message to send to ZeroClaw
      required: true
      selector:
        text:
```

**Step 2: Commit**

```bash
git add custom_components/zeroclaw/services.yaml
git commit -m "feat: services.yaml for send_message"
```

---

### Task 12: Integration — Binary Sensor (Connected)

**Files:**
- Create: `custom_components/zeroclaw/binary_sensor.py`

**Step 1: Create binary sensor entity**

```python
"""Binary sensor for ZeroClaw connectivity status."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import ZeroClawCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ZeroClaw binary sensor."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities([ZeroClawConnectedSensor(coordinator, entry)])


class ZeroClawConnectedSensor(CoordinatorEntity[ZeroClawCoordinator], BinarySensorEntity):
    """Binary sensor indicating gateway connectivity."""

    _attr_has_entity_name = True
    _attr_translation_key = "connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(
        self, coordinator: ZeroClawCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_connected"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "ZeroClaw Assistant",
            "manufacturer": "Slayer",
        }

    @property
    def is_on(self) -> bool | None:
        """Return True if connected."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("connected", False)
```

**Step 2: Commit**

```bash
git add custom_components/zeroclaw/binary_sensor.py
git commit -m "feat: binary sensor for gateway connectivity"
```

---

### Task 13: Integration — Sensors (Status + Active Model)

**Files:**
- Create: `custom_components/zeroclaw/sensor.py`

**Step 1: Create sensor entities**

```python
"""Sensors for ZeroClaw status and active model."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import ZeroClawCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ZeroClaw sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities([
        ZeroClawStatusSensor(coordinator, entry),
        ZeroClawActiveModelSensor(coordinator, entry),
    ])


class ZeroClawStatusSensor(CoordinatorEntity[ZeroClawCoordinator], SensorEntity):
    """Sensor showing gateway status (ok/error)."""

    _attr_has_entity_name = True
    _attr_translation_key = "status"
    _attr_icon = "mdi:robot"

    def __init__(
        self, coordinator: ZeroClawCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_status"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "ZeroClaw Assistant",
            "manufacturer": "Slayer",
        }

    @property
    def native_value(self) -> str | None:
        """Return gateway status."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("status")

    @property
    def extra_state_attributes(self) -> dict:
        """Return uptime, paired state, component count."""
        if self.coordinator.data is None:
            return {}
        return {
            "uptime_seconds": self.coordinator.data.get("uptime_seconds"),
            "paired": self.coordinator.data.get("paired"),
            "component_count": len(self.coordinator.data.get("components", {})),
        }


class ZeroClawActiveModelSensor(CoordinatorEntity[ZeroClawCoordinator], SensorEntity):
    """Sensor showing the current active LLM model."""

    _attr_has_entity_name = True
    _attr_translation_key = "active_model"
    _attr_icon = "mdi:brain"

    def __init__(
        self, coordinator: ZeroClawCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_active_model"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "ZeroClaw Assistant",
            "manufacturer": "Slayer",
        }

    @property
    def native_value(self) -> str | None:
        """Return model name."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("model")

    @property
    def extra_state_attributes(self) -> dict:
        """Return provider info."""
        if self.coordinator.data is None:
            return {}
        provider = self.coordinator.data.get("provider")
        if provider:
            return {"provider": provider}
        return {}
```

**Step 2: Commit**

```bash
git add custom_components/zeroclaw/sensor.py
git commit -m "feat: status and active model sensors"
```

---

### Task 14: Integration — Conversation Agent

**Files:**
- Create: `custom_components/zeroclaw/conversation.py`

**Step 1: Create conversation agent**

```python
"""Conversation agent for ZeroClaw — integrates with HA Assist pipeline."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import ZeroClawApiClient, ZeroClawConnectionError, ZeroClawAuthError
from .const import DATA_CLIENT, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ZeroClaw conversation agent."""
    client = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
    agent = ZeroClawConversationEntity(entry, client)
    async_add_entities([agent])


class ZeroClawConversationEntity(conversation.ConversationEntity):
    """Conversation agent that sends messages to ZeroClaw via POST /webhook."""

    _attr_has_entity_name = True
    _attr_name = "ZeroClaw"

    def __init__(
        self,
        entry: ConfigEntry,
        client: ZeroClawApiClient,
    ) -> None:
        self._entry = entry
        self._client = client
        self._attr_unique_id = f"{entry.entry_id}_conversation"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "ZeroClaw Assistant",
            "manufacturer": "Slayer",
        }

    @property
    def supported_languages(self) -> list[str] | str:
        """ZeroClaw supports any language the underlying LLM supports."""
        return conversation.MATCH_ALL

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        """Send user message to ZeroClaw and return the response."""
        intent_response = conversation.IntentResponse(language=user_input.language)

        try:
            result = await self._client.async_send_message(user_input.text)
            response_text = result.get("response", "No response from ZeroClaw")
        except ZeroClawConnectionError:
            response_text = "Cannot connect to ZeroClaw gateway"
            _LOGGER.error("ZeroClaw connection error during conversation")
        except ZeroClawAuthError:
            response_text = "ZeroClaw authentication failed"
            _LOGGER.error("ZeroClaw auth error during conversation")
        except Exception:
            response_text = "Unexpected error communicating with ZeroClaw"
            _LOGGER.exception("Unexpected error in ZeroClaw conversation")

        intent_response.async_set_speech(response_text)

        return conversation.ConversationResult(
            response=intent_response,
            conversation_id=user_input.conversation_id,
        )
```

**Step 2: Commit**

```bash
git add custom_components/zeroclaw/conversation.py
git commit -m "feat: conversation agent for HA Assist pipeline"
```

---

### Task 15: Smoke Test — Verify Structure

**Step 1: Verify all files exist**

Run:
```bash
find zeroclaw_assistant/ custom_components/ repository.yaml -type f | sort
```

Expected output:
```
custom_components/zeroclaw/__init__.py
custom_components/zeroclaw/api.py
custom_components/zeroclaw/binary_sensor.py
custom_components/zeroclaw/config_flow.py
custom_components/zeroclaw/const.py
custom_components/zeroclaw/conversation.py
custom_components/zeroclaw/coordinator.py
custom_components/zeroclaw/manifest.json
custom_components/zeroclaw/sensor.py
custom_components/zeroclaw/services.yaml
custom_components/zeroclaw/strings.json
repository.yaml
zeroclaw_assistant/Dockerfile
zeroclaw_assistant/build.yaml
zeroclaw_assistant/config.yaml
zeroclaw_assistant/run.sh
```

**Step 2: Verify Python syntax**

Run:
```bash
python3 -c "import py_compile; import glob; [py_compile.compile(f, doraise=True) for f in glob.glob('custom_components/zeroclaw/*.py')]"
```

Expected: No errors.

**Step 3: Verify JSON syntax**

Run:
```bash
python3 -c "import json; json.load(open('custom_components/zeroclaw/manifest.json')); json.load(open('custom_components/zeroclaw/strings.json')); print('OK')"
```

Expected: `OK`

**Step 4: Commit if any fixes needed**

---

### Task 16: Final Commit — Tag v0.1.0

**Step 1: Review all changes**

Run: `git log --oneline`

Verify ~10 commits covering scaffold, addon, and integration.

**Step 2: Tag**

Run: `git tag v0.1.0`

---

## Notes for Implementer

1. **ZeroClaw binary packaging**: The Dockerfile assumes releases are `.tar.gz` archives. Check actual release artifacts at `https://github.com/zeroclaw-labs/zeroclaw/releases` — if they're bare binaries, change `tar xzf` to direct `curl -o`.

2. **ZeroClaw CLI flags**: The `run.sh` uses `zeroclaw daemon --config <path>`. Verify the actual flag name against `zeroclaw daemon --help`. It may be `--config-file` or read from `ZEROCLAW_CONFIG` env var.

3. **bashio availability**: The `run.sh` uses `bashio::log.info`. The Alpine HA base images include bashio. If it's missing, use plain `echo`.

4. **Conversation agent API**: The `ConversationEntity` base class was introduced in HA 2024.1+. The `async_process` method signature and `ConversationResult` may have evolved. Test against current HA dev docs.

5. **Config flow auto-discovery**: v1 is manual-only. TODO for future: add Supervisor API detection to auto-discover the addon and read token from shared filesystem.
