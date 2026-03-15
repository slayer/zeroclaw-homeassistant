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
    async_add_entities(
        [
            ZeroClawStatusSensor(coordinator, entry),
            ZeroClawActiveModelSensor(coordinator, entry),
        ]
    )


class ZeroClawStatusSensor(CoordinatorEntity[ZeroClawCoordinator], SensorEntity):
    """Sensor showing gateway status (ok/error)."""

    _attr_has_entity_name = True
    _attr_translation_key = "status"
    _attr_icon = "mdi:robot"

    def __init__(self, coordinator: ZeroClawCoordinator, entry: ConfigEntry) -> None:
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

    def __init__(self, coordinator: ZeroClawCoordinator, entry: ConfigEntry) -> None:
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
