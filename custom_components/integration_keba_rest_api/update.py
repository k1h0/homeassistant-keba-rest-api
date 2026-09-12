#!/usr/bin/env python3
"""KEBA firmware update entity."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import KebaRestIntegrationApiClientError
from .const import DOMAIN
from .coordinator import KebaUpdateCoordinator
from .data import KebaUpdateState

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

_POLL_INTERVAL = 5
_MAX_INSTALL_SECONDS = 3600
_LOG_COUNT = 50
_ERR_NO_UPDATE = "KEBA did not provide an installable update"
_ERR_UPDATE_RUNNING = "A KEBA firmware update is already running"
_ERR_VERSION_UNAVAILABLE = "The requested KEBA firmware version is unavailable"
_ERR_UPDATE_FAILED = "KEBA firmware update failed"
_ERR_UPDATE_TIMEOUT = "KEBA firmware update timed out"
_ACTIVE_STATUSES = {
    "DOWNLOADING",
    "DOWNLOADED",
    "DOWNLOAD_SCHEDULED",
    "INSTALL_SCHEDULED",
    "INSTALLING",
    "PREPARING",
    "SIGNATURE_VERIFIED",
}
_TERMINAL_STATUSES = {
    "CANCELLED",
    "DOWNLOAD_FAILED",
    "INSTALLATION_FAILED",
    "INSTALLED",
    "INVALID_SIGNATURE",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the KEBA firmware update entity."""
    del hass
    coordinator = entry.runtime_data.update_coordinator
    if coordinator is not None:
        async_add_entities([KebaFirmwareUpdateEntity(coordinator)])


class KebaFirmwareUpdateEntity(CoordinatorEntity[KebaUpdateCoordinator], UpdateEntity):
    """Represent the system-wide KEBA firmware update."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_has_entity_name = True
    _attr_name = "Firmware"

    def __init__(self, coordinator: KebaUpdateCoordinator) -> None:
        """Initialize the firmware update entity."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_firmware_update"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="KEBA firmware",
        )

    @property
    def _state(self) -> KebaUpdateState:
        """Return the coordinator state."""
        return self.coordinator.data or KebaUpdateState()

    @property
    def installed_version(self) -> str | None:
        """Return the installed package version."""
        return self._state.installed_version

    @property
    def latest_version(self) -> str | None:
        """Return the strictly recognized portal version."""
        return self._state.latest_version

    @property
    def release_summary(self) -> str | None:
        """Return a short release summary."""
        description = self._state.description
        return description[:255] if description else None

    @property
    def supported_features(self) -> UpdateEntityFeature:
        """Return features supported by the current update payload."""
        features = UpdateEntityFeature(0)
        if self._state.description:
            features |= UpdateEntityFeature.RELEASE_NOTES
        if self._state.location and self._state.latest_version:
            features |= UpdateEntityFeature.INSTALL
        if self._state.status or self._state.update_percentage is not None:
            features |= UpdateEntityFeature.PROGRESS
        return features

    @property
    def in_progress(self) -> bool:
        """Return whether an update is currently running."""
        return self._state.status in _ACTIVE_STATUSES

    @property
    def update_percentage(self) -> int | None:
        """Return the bounded download percentage."""
        return self._state.update_percentage

    async def async_release_notes(self) -> str | None:
        """Return the full portal description as release notes."""
        return self._state.description

    async def async_update(self) -> None:
        """Request a fresh portal check when the entity is refreshed."""
        await self.coordinator.async_check_for_updates()

    async def async_install(
        self,
        version: str | None,
        backup: bool,
        **kwargs: Any,  # noqa: FBT001
    ) -> None:
        """Install the currently offered portal update and monitor it."""
        del backup, kwargs
        state = self._state
        if not state.location or not state.latest_version:
            raise HomeAssistantError(_ERR_NO_UPDATE)
        if self.in_progress:
            raise HomeAssistantError(_ERR_UPDATE_RUNNING)
        if version and version != state.latest_version:
            raise HomeAssistantError(_ERR_VERSION_UNAVAILABLE)

        payload = {
            key: value
            for key, value in {
                "location": state.location,
                "retrieveDate": state.retrieve_date,
                "installDate": state.install_date,
                "checkDate": state.check_date,
                "retries": state.retries,
                "retryInterval": state.retry_interval,
                "signingCertificate": state.signing_certificate,
                "signature": state.signature,
                "description": state.description,
            }.items()
            if value is not None
        }
        client = self._entry.runtime_data.client
        try:
            await client.async_request_update(payload)
            await self._poll_installation()
        except HomeAssistantError:
            raise
        except KebaRestIntegrationApiClientError as exc:
            await self._load_diagnostic_logs()
            raise HomeAssistantError(_ERR_UPDATE_FAILED) from exc

    async def _poll_installation(self) -> None:
        """Poll the KEBA request status until it reaches a terminal state."""
        client = self._entry.runtime_data.client
        elapsed = 0
        while elapsed < _MAX_INSTALL_SECONDS:
            response = await client.async_get_update_request_status()
            self._apply_status(response)
            status = self._state.status
            if status in _TERMINAL_STATUSES:
                if status != "INSTALLED":
                    await self._load_diagnostic_logs()
                    message = f"KEBA update ended with {status}"
                    raise HomeAssistantError(message)
                await self.coordinator.async_request_refresh()
                return
            await asyncio.sleep(_POLL_INTERVAL)
            elapsed += _POLL_INTERVAL

        await self._load_diagnostic_logs()
        raise HomeAssistantError(_ERR_UPDATE_TIMEOUT)

    def _apply_status(self, response: Any) -> None:
        """Apply a status response to the coordinator state."""
        if not isinstance(response, dict):
            return
        percentage = response.get("firmwareDownloadPercent")
        if isinstance(percentage, int):
            percentage = max(0, min(percentage, 100))
        else:
            percentage = None
        self.coordinator.async_set_updated_data(
            replace(
                self._state,
                status=response.get("updateProcessStatus"),
                update_percentage=percentage,
                length=response.get("length"),
                size=response.get("size"),
            )
        )

    async def _load_diagnostic_logs(self) -> None:
        """Load bounded update logs without exposing them in the UI."""
        try:
            response = await self._entry.runtime_data.client.async_get_update_log(
                _LOG_COUNT
            )
        except KebaRestIntegrationApiClientError:
            return
        if isinstance(response, dict) and isinstance(response.get("msg"), str):
            self.coordinator.async_set_updated_data(
                replace(self._state, logs=response["msg"])
            )
