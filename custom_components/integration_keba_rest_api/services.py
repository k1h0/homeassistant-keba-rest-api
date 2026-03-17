#!/usr/bin/env python3
"""Service handlers for the KEBA REST API integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall

    from .data import KebaRestIntegrationConfigEntry

_LOGGER = logging.getLogger(__name__)

SERVICE_FETCH_DATA = "fetch_data"
SERVICE_START_CHARGING = "start_charging"
SERVICE_STOP_CHARGING = "stop_charging"
GLOBAL_SERVICE_SCHEMA = vol.Schema({}, extra=vol.ALLOW_EXTRA)


def _as_list(value: Any) -> list[str]:
    """Normalize service target values to a list of strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def _resolve_device_target(
    hass: HomeAssistant,
    call: ServiceCall,
) -> tuple[KebaRestIntegrationConfigEntry, str]:
    """
    Resolve selected device target to integration entry and wallbox serial.

    The selected device must belong to this integration and expose a
    `(DOMAIN, serial)` device identifier.
    """
    device_ids = _as_list(call.data.get("device_id"))
    if not device_ids and isinstance(call.data.get("target"), dict):
        device_ids = _as_list(call.data["target"].get("device_id"))

    if not device_ids:
        msg = "No wallbox selected. Please select a device."
        raise HomeAssistantError(msg)

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get(device_ids[0])
    if device_entry is None:
        msg = "Selected wallbox device was not found."
        raise HomeAssistantError(msg)

    entries_by_id: dict[str, KebaRestIntegrationConfigEntry] = {
        e.entry_id: e
        for e in hass.config_entries.async_entries(DOMAIN)
        if getattr(e, "runtime_data", None) is not None
    }

    if not entries_by_id:
        msg = "No loaded config entry available for this integration."
        raise HomeAssistantError(msg)

    target_entry: KebaRestIntegrationConfigEntry | None = None
    for entry_id in device_entry.config_entries:
        if entry_id in entries_by_id:
            target_entry = entries_by_id[entry_id]
            break

    if target_entry is None:
        msg = "Selected device is not linked to a loaded entry."
        raise HomeAssistantError(msg)

    serial_candidates = [
        value
        for (identifier_domain, value) in device_entry.identifiers
        if identifier_domain == DOMAIN and value != target_entry.entry_id
    ]
    if not serial_candidates:
        msg = "Unable to determine wallbox serial number."
        raise HomeAssistantError(msg)

    return target_entry, str(serial_candidates[0])


async def _handle_fetch_data(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle global fetch_data service call."""
    entry, _serial = _resolve_device_target(hass, call)
    await entry.runtime_data.coordinator.async_request_refresh()


async def _handle_start_charging(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle global start_charging service call."""
    entry, serial = _resolve_device_target(hass, call)
    await entry.runtime_data.client.async_set_wallbox_start_charging(serial)
    await entry.runtime_data.coordinator.async_request_refresh()


async def _handle_stop_charging(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle global stop_charging service call."""
    entry, serial = _resolve_device_target(hass, call)
    await entry.runtime_data.client.async_set_wallbox_stop_charging(serial)
    await entry.runtime_data.coordinator.async_request_refresh()


def _build_service_handlers(
    hass: HomeAssistant,
) -> dict[str, Any]:
    """Return service handlers bound to the Home Assistant instance."""

    async def _fetch_data_handler(call: ServiceCall) -> None:
        await _handle_fetch_data(hass, call)

    async def _start_charging_handler(call: ServiceCall) -> None:
        await _handle_start_charging(hass, call)

    async def _stop_charging_handler(call: ServiceCall) -> None:
        await _handle_stop_charging(hass, call)

    return {
        SERVICE_FETCH_DATA: _fetch_data_handler,
        SERVICE_START_CHARGING: _start_charging_handler,
        SERVICE_STOP_CHARGING: _stop_charging_handler,
    }


def async_register_wallbox_services(
    hass: HomeAssistant,
) -> None:
    """
    Register integration-wide target-based services.

    The services are registered once per Home Assistant instance and reused
    for all loaded config entries.
    """
    handlers = _build_service_handlers(hass)
    for service_name, handler in handlers.items():
        if hass.services.has_service(DOMAIN, service_name):
            continue

        hass.services.async_register(
            DOMAIN,
            service_name,
            handler,
            schema=GLOBAL_SERVICE_SCHEMA,
        )
        _LOGGER.debug("Registered service %s.%s", DOMAIN, service_name)
