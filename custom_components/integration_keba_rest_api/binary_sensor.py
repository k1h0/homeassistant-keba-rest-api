#!/usr/bin/env python3
"""Binary sensor platform for integration_keba_rest-api."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.helpers.device_registry import DeviceInfo  # type: ignore[import]

from .const import DOMAIN
from .entity import KebaRestIntegrationEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import KebaDataUpdateCoordinator
    from .data import KebaRestIntegrationConfigEntry


BINARY_SENSOR_DEFINITIONS: dict[str, BinarySensorEntityDescription] = {
    "vehiclePlugged": BinarySensorEntityDescription(
        key="vehiclePlugged",
        name="Vehicle Plugged In",
        device_class=BinarySensorDeviceClass.PLUG,
    ),
    "sessionActive": BinarySensorEntityDescription(
        key="sessionActive",
        name="Charging Session Active",
        device_class=BinarySensorDeviceClass.POWER,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: KebaRestIntegrationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary_sensor platform."""
    coordinator = entry.runtime_data.coordinator

    # Create binary sensors for each wallbox serial
    entities = [
        WallboxBinarySensor(coordinator, serial, descr.key, descr)
        for serial in coordinator.data
        for descr in BINARY_SENSOR_DEFINITIONS.values()
    ]

    async_add_entities(entities)

    # Listen for new wallboxes and add binary sensors dynamically
    known = set(coordinator.data)

    def _update_binary_sensors() -> None:
        """Add new binary sensors when new wallboxes are discovered."""
        nonlocal known
        current = set(coordinator.data)
        added = current - known
        if added:
            new_entities = [
                WallboxBinarySensor(coordinator, serial, descr.key, descr)
                for serial in added
                for descr in BINARY_SENSOR_DEFINITIONS.values()
            ]
            async_add_entities(new_entities)
            known = current

    coordinator.async_add_listener(_update_binary_sensors)


class WallboxBinarySensor(KebaRestIntegrationEntity, BinarySensorEntity):
    """Binary sensor for wallbox boolean flags like vehiclePlugged or sessionActive."""

    def __init__(
        self,
        coordinator: KebaDataUpdateCoordinator,
        serial: str,
        key: str,
        entity_description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize a binary sensor for a wallbox serial and key."""
        super().__init__(coordinator)
        self.serial = serial
        self.key = key
        self.entity_description = entity_description
        self._attr_name = f"Wallbox {serial} {entity_description.name}"
        self._attr_unique_id = f"wallbox_{serial}_{key}"

        # Expose wallbox as its own device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)}, name=f"Wallbox {serial}"
        )

    @property
    def is_on(self) -> bool:
        """Return the boolean state for the binary sensor."""
        wb = self.coordinator.data.get(self.serial)
        if not wb:
            return False
        return bool(wb.get(self.key))

    @property
    def extra_state_attributes(self) -> dict:
        """Expose helpful metadata for the binary sensor."""
        wb = self.coordinator.data.get(self.serial)
        if not wb:
            return {}
        attrs: dict[str, Any] = {}
        for key in ("alias", "model", "firmwareVersion", "serialNumber"):
            value = wb.get(key)
            if value is not None:
                attrs[key] = value
        return attrs
