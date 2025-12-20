#!/usr/bin/env python3
"""Sensor platform for integration_keba_rest-api."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (  # type: ignore[import]
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (  # type: ignore[import]
    UnitOfElectricCurrent,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)

from .entity import KebaRestIntegrationEntity
from homeassistant.helpers.device_registry import DeviceInfo  # type: ignore[import]
from .const import DOMAIN

if TYPE_CHECKING:  # isort: skip
    from homeassistant.core import HomeAssistant  # type: ignore[import]
    from homeassistant.helpers.entity_platform import (
        AddEntitiesCallback,  # type: ignore[import]
    )

    from .coordinator import KebaDataUpdateCoordinator
    from .data import KebaRestIntegrationConfigEntry

ENTITY_DESCRIPTIONS = (
    SensorEntityDescription(
        key="integration_keba_rest-api",
        name="Integration Sensor",
        icon="mdi:format-quote-close",
    ),
)


SENSOR_DEFINITIONS: dict[str, SensorEntityDescription] = {
    "state": SensorEntityDescription(
        key="state",
        name="State of Wallbox",
    ),
    "maxPhases": SensorEntityDescription(
        key="maxPhases",
        name="Max Phases",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "maxCurrent": SensorEntityDescription(
        key="maxCurrent",
        name="Max Current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "phasesUsed": SensorEntityDescription(
        key="phasesUsed",
        name="Phases Used",
    ),
    "meterValue": SensorEntityDescription(
        key="meterValue",
        name="Meter Value",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=3,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "totalActivePower": SensorEntityDescription(
        key="totalActivePower",
        name="Total Active Power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "currentOffered": SensorEntityDescription(
        key="currentOffered",
        name="Current Offered",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "temperature": SensorEntityDescription(
        key="temperature",
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: KebaRestIntegrationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = entry.runtime_data.coordinator
    # ensure initial refresh already passiert (wenn nicht an anderer Stelle gemacht)
    await coordinator.async_config_entry_first_refresh()

    # Create sensors per wallbox serial using typed descriptions
    entities: list[WallboxSensor] = [
        WallboxSensor(
            coordinator,
            serial,
            descr.key,
            str(descr.name or ""),
        )
        for serial in coordinator.data
        for descr in SENSOR_DEFINITIONS.values()
    ]

    async_add_entities(entities)
    # Listen for new wallboxes and add sensors dynamically
    known = set(coordinator.data)

    def _update_entities() -> None:
        """Add new sensors when new wallboxes are discovered."""
        nonlocal known
        current = set(coordinator.data)
        added = current - known
        if added:
            new_entities = [
                WallboxSensor(
                    coordinator,
                    serial,
                    descr.key,
                    str(descr.name or ""),
                )
                for serial in added
                for descr in SENSOR_DEFINITIONS.values()
            ]
            async_add_entities(new_entities)
            known = current

    coordinator.async_add_listener(_update_entities)


def _safe_get_meter_value(wb: dict, path: str) -> Any | None:
    """Return a value from the nested `meter` object or None if unavailable."""
    meter = wb.get("meter") or {}
    return meter.get(path)


def _safe_mul(value: Any | None, multiplier: float) -> Any | None:
    """
    Multiply a value by multiplier.

    Returns None if the value is missing or cannot be converted to a number.
    """
    if value is None:
        return None
    try:
        return float(value) * multiplier
    except (TypeError, ValueError):
        return None


class WallboxSensor(KebaRestIntegrationEntity, SensorEntity):
    """Sensor for a single Wallbox metric."""

    def __init__(
        self,
        coordinator: KebaDataUpdateCoordinator,
        serial: str,
        key: str,
        name: str,
    ) -> None:
        """Initialize a WallboxSensor for the given serial and metric."""
        super().__init__(coordinator)
        self.serial = serial
        self.key = key
        self._attr_name = f"Wallbox {serial} {name}"
        self._attr_unique_id = f"wallbox_{serial}_{key}"

        # Apply device-specific metadata from our definitions when available
        descr = SENSOR_DEFINITIONS.get(key)
        if descr is not None:
            if getattr(descr, "native_unit_of_measurement", None) is not None:
                self._attr_native_unit_of_measurement = descr.native_unit_of_measurement
            if getattr(descr, "device_class", None) is not None:
                self._attr_device_class = descr.device_class
            if getattr(descr, "state_class", None) is not None:
                self._attr_state_class = descr.state_class

        # Expose each wallbox as its own Home Assistant device using the serial
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            name=f"Wallbox {serial}",
        )

    @property
    def native_value(self) -> Any | None:
        """Return the sensor value for the associated wallbox metric."""
        wb = self.coordinator.data.get(self.serial)
        if not wb:
            return None

        mapping = {
            "state": lambda s: s.get("state"),
            "vehiclePlugged": lambda s: bool(s.get("vehiclePlugged")),
            "sessionActive": lambda s: bool(s.get("sessionActive")),
            "maxPhases": lambda s: s.get("maxPhases"),
            "maxCurrent": lambda s: _safe_mul(s.get("maxCurrent"), 0.001),
            "phasesUsed": lambda s: s.get("phasesUsed") or s.get("phaseUsed"),
            "meterValue": lambda s: _safe_mul(
                _safe_get_meter_value(s, "meterValue"), 0.001
            ),
            "totalActivePower": lambda s: _safe_mul(
                _safe_get_meter_value(s, "totalActivePower"), 0.001
            ),
            "currentOffered": lambda s: _safe_mul(
                _safe_get_meter_value(s, "currentOffered"), 0.001
            ),
            "temperature": lambda s: _safe_mul(
                _safe_get_meter_value(s, "temperature"), 0.01
            ),
        }

        func = mapping.get(self.key)
        return func(wb) if func else None

    @property
    def extra_state_attributes(self) -> dict:
        """
        Return additional attributes from the wallbox detail object and metadata.

        Includes optional fields when available: alias, model, firmwareVersion,
        macAddress, ipAddress.
        """
        wb = self.coordinator.data.get(self.serial)
        if not wb:
            return {}

        attrs: dict[str, Any] = {}

        # Include errorCode if present
        if wb.get("errorCode") is not None:
            attrs["errorCode"] = wb.get("errorCode")

        for key in (
            "alias",
            "model",
            "firmwareVersion",
            "macAddress",
            "ipAddress",
            "serialNumber",
        ):
            value = wb.get(key)
            if value is not None:
                attrs[key] = value

        return attrs
