"""Config flow for ZeroClaw integration."""

from __future__ import annotations

import logging
from pathlib import Path
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
    ADDON_TOKEN_PATH,
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


def _read_addon_token() -> str | None:
    """Read pre-seeded bearer token from addon shared config."""
    try:
        token = Path(ADDON_TOKEN_PATH).read_text().strip()
        if token:
            return token
    except (OSError, PermissionError):
        pass
    return None


class ZeroClawConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ZeroClaw."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Try addon auto-discovery first, fall back to manual pairing."""

        # Auto-discover if addon token file exists
        token = await self.hass.async_add_executor_job(_read_addon_token)
        if token is not None:
            host = DEFAULT_HOST
            port = DEFAULT_PORT

            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)
            client = ZeroClawApiClient(
                host=host, port=port, token=token, session=session
            )
            try:
                await client.async_get_health()
            except ZeroClawConnectionError:
                _LOGGER.debug("Addon token found but gateway unreachable, falling back")
            else:
                return self.async_create_entry(
                    title=f"ZeroClaw ({host}:{port})",
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_TOKEN: token,
                    },
                )

        return await self.async_step_manual(user_input)

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual setup: host, port, pairing code."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            pairing_code = user_input[CONF_PAIRING_CODE]

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
            step_id="manual",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
