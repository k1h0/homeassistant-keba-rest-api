#!/usr/bin/env python3
"""Button platform for integration_keba_rest_api."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo

from .api import KebaRestIntegrationApiClientError
from .const import DOMAIN
from .entity import KebaRestIntegrationEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import KebaDataUpdateCoordinator
    from .data import KebaRestIntegrationConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: KebaRestIntegrationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities for each discovered wallbox."""
    coordinator = entry.runtime_data.coordinator

    entities: list[WallboxActionButton] = []
    for serial in coordinator.data:
        entities.append(WallboxActionButton(coordinator, serial, action="fetch_data"))
        entities.append(WallboxActionButton(coordinator, serial, action="start"))
        entities.append(WallboxActionButton(coordinator, serial, action="stop"))

    async_add_entities(entities)

    known = set(coordinator.data)

    def _update_buttons() -> None:
        """Add button entities when new wallboxes are discovered."""
        nonlocal known
        current = set(coordinator.data)
        added = current - known
        if added:
            new_entities: list[WallboxActionButton] = []
            for serial in added:
                new_entities.append(
                    WallboxActionButton(coordinator, serial, action="fetch_data")
                )
                new_entities.append(
                    WallboxActionButton(coordinator, serial, action="start")
                )
                new_entities.append(
                    WallboxActionButton(coordinator, serial, action="stop")
                )
            async_add_entities(new_entities)
            known = current

    coordinator.async_add_listener(_update_buttons)


class WallboxActionButton(KebaRestIntegrationEntity, ButtonEntity):
    """Action button bound to a specific wallbox."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: KebaDataUpdateCoordinator,
        serial: str,
        *,
        action: str,
    ) -> None:
        """Initialize an action button for one wallbox."""
        super().__init__(coordinator)
        self.serial = serial
        self.action = action

        if action == "fetch_data":
            self._attr_translation_key = "fetch_data"
            self._attr_icon = "mdi:sync"
            self._attr_unique_id = f"wallbox_{serial}_fetch_data_button"
        elif action == "start":
            self._attr_translation_key = "start_charging"
            self._attr_icon = "mdi:play-circle-outline"
            self._attr_unique_id = f"wallbox_{serial}_start_charging_button"
        else:
            self._attr_translation_key = "stop_charging"
            self._attr_icon = "mdi:stop-circle-outline"
            self._attr_unique_id = f"wallbox_{serial}_stop_charging_button"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            name=f"Wallbox {serial}",
        )

    async def async_press(self) -> None:
        """Execute the configured action for this wallbox."""
        client = self.coordinator.config_entry.runtime_data.client
        try:
            if self.action == "fetch_data":
                await self.coordinator.async_request_refresh()
                return

            if self.action == "start":
                await client.async_set_wallbox_start_charging(self.serial)
            else:
                await client.async_set_wallbox_stop_charging(self.serial)
        except KebaRestIntegrationApiClientError as exc:
            msg = f"Unable to {self.action} charging for wallbox {self.serial}: {exc}"
            raise HomeAssistantError(msg) from exc

        await self.coordinator.async_request_refresh()
