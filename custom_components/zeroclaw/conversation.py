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
            "manufacturer": "ZeroClaw Labs",
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
