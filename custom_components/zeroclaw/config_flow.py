"""Config flow for ZeroClaw integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession

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

            # Check for duplicates before wasting a pairing code
            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)
            client = ZeroClawApiClient(host=host, port=port, session=session)
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
                return self.async_create_entry(
                    title=f"ZeroClaw ({host}:{port})",
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_TOKEN: token,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
