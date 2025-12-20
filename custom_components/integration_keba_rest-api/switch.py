#!/usr/bin/env python3
"""Switch platform for integration_keba_rest-api."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription

from .entity import KebaRestIntegrationEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import KebaDataUpdateCoordinator
    from .data import KebaRestIntegrationConfigEntry

ENTITY_DESCRIPTIONS = (
    SwitchEntityDescription(
        key="integration_keba_rest-api",
        name="Integration Switch",
        icon="mdi:format-quote-close",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: KebaRestIntegrationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    # Create a switch per wallbox serial to start/stop charging
    coordinator = entry.runtime_data.coordinator
    entities: list[WallboxChargeSwitch] = [
        WallboxChargeSwitch(coordinator, serial) for serial in coordinator.data
    ]

    async_add_entities(entities)

    # Listen for newly discovered wallboxes and add switches dynamically
    known = set(coordinator.data)

    def _update_switches() -> None:
        """Add switches for newly discovered wallboxes."""
        nonlocal known
        current = set(coordinator.data)
        added = current - known
        if added:
            new_entities = [
                WallboxChargeSwitch(coordinator, serial) for serial in added
            ]
            async_add_entities(new_entities)
            known = current

    coordinator.async_add_listener(_update_switches)


class WallboxChargeSwitch(KebaRestIntegrationEntity, SwitchEntity):
    """Switch to start/stop charging for a wallbox."""

    def __init__(self, coordinator: KebaDataUpdateCoordinator, serial: str) -> None:
        """Initialize switch for a given wallbox serial."""
        super().__init__(coordinator)
        self.serial = serial
        self._attr_name = f"Wallbox {serial} Charging"
        self._attr_unique_id = f"wallbox_{serial}_charging"

    @property
    def is_on(self) -> bool:
        """Return True if wallbox is currently charging (if available)."""
        wb = self.coordinator.data.get(self.serial)
        if not wb:
            return False
        state = wb.get("state", {})
        return state == "CHARGING"

    async def async_turn_on(self, **_: Any) -> None:
        """Start charging on the wallbox."""
        client = self.coordinator.config_entry.runtime_data.client
        await client.async_set_wallbox_start_charging(self.serial)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **_: Any) -> None:
        """Stop charging on the wallbox."""
        client = self.coordinator.config_entry.runtime_data.client
        await client.async_set_wallbox_stop_charging(self.serial)
        await self.coordinator.async_request_refresh()
