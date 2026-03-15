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
