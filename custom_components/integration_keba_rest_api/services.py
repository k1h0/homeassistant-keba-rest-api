#!/usr/bin/env python3
"""Service handlers for the KEBA REST API integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import voluptuous as vol

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant, ServiceCall

    from .data import KebaRestIntegrationConfigEntry

_LOGGER = logging.getLogger(__name__)

FETCH_DATA_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): str,
    }
)


def _resolve_target(
    hass: HomeAssistant,
    call_data: dict,
) -> tuple[str, ConfigEntry] | None:
    """Resolve target config entry from service call data."""
    all_entries = hass.config_entries.async_entries(DOMAIN)
    entries = {e.entry_id: e for e in all_entries}

    target_entry_id = call_data.get("entry_id")
    if target_entry_id:
        target_entry = entries.get(target_entry_id)
        if target_entry is None:
            _LOGGER.error(
                "Keba service: unknown entry_id %s",
                target_entry_id,
            )
            return None
        return target_entry_id, target_entry

    if len(entries) != 1:
        _LOGGER.error(
            "Keba service: multiple entries configured; specify entry_id",
        )
        return None

    target_entry_id, target_entry = next(iter(entries.items()))
    return target_entry_id, target_entry


async def async_handle_fetch_data(call: ServiceCall) -> None:
    """Handle fetch_data service call."""
    hass = call.hass
    resolved = _resolve_target(hass, call.data)
    if not resolved:
        return

    target_entry_id, target_entry = resolved

    entry: KebaRestIntegrationConfigEntry = target_entry  # type: ignore[assignment]
    runtime = entry.runtime_data if hasattr(entry, "runtime_data") else None
    coordinator = runtime.coordinator if runtime is not None else None
    if not coordinator:
        _LOGGER.error(
            "Keba fetch_data: no coordinator found for entry %s",
            target_entry_id,
        )
        return

    _LOGGER.debug(
        "Keba fetch_data: triggering coordinator refresh for entry %s",
        target_entry_id,
    )
    await coordinator.async_request_refresh()


def async_register_services(hass: HomeAssistant) -> None:
    """Register all KEBA services (no-op if already registered)."""
    if not hass.services.has_service(DOMAIN, "fetch_data"):
        hass.services.async_register(
            DOMAIN,
            "fetch_data",
            async_handle_fetch_data,
            schema=FETCH_DATA_SERVICE_SCHEMA,
        )
        _LOGGER.debug("Registered service %s.%s", DOMAIN, "fetch_data")


def async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister all KEBA services (only when no entries remain)."""
    if hass.config_entries.async_entries(DOMAIN):
        return
    for service in ("fetch_data",):
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)
            _LOGGER.debug("Unregistered service %s.%s", DOMAIN, service)
