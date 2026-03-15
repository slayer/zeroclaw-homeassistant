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


class ZeroClawConnectedSensor(
    CoordinatorEntity[ZeroClawCoordinator], BinarySensorEntity
):
    """Binary sensor indicating gateway connectivity."""

    _attr_has_entity_name = True
    _attr_translation_key = "connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: ZeroClawCoordinator, entry: ConfigEntry) -> None:
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
