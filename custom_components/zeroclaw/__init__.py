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
