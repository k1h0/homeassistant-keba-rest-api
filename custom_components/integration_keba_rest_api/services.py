#!/usr/bin/env python3
"""Service handlers for the KEBA REST API integration."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from .const import DOMAIN

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from homeassistant.core import HomeAssistant, ServiceCall

    from .data import KebaRestIntegrationConfigEntry

_LOGGER = logging.getLogger(__name__)

FETCH_DATA_SERVICE_SCHEMA = vol.Schema({})


def _sanitize_name(name: str) -> str:
    """Sanitize a string for use as part of a service name."""
    sanitized = re.sub(r"[^a-z0-9_]", "_", name.lower())
    return re.sub(r"_+", "_", sanitized).strip("_")


def _make_wallbox_service_name(alias: str | None, serial: str) -> str:
    """
    Return the service name for a per-wallbox fetch_data action.

    Uses the wallbox alias when available, otherwise falls back to
    ``wallbox{serial}``.  Both are sanitized to only contain lowercase
    letters, digits and underscores.
    """
    label = alias or f"wallbox{serial}"
    return f"fetch_data_{_sanitize_name(label)}"


def async_register_wallbox_services(
    hass: HomeAssistant,
    entry: KebaRestIntegrationConfigEntry,
) -> None:
    """
    Register one fetch_data service per discovered wallbox for *entry*.

    Calling this function is idempotent: services that already exist are
    skipped and only newly discovered wallboxes produce new registrations.
    The service names are stored on ``entry.runtime_data.wallbox_service_names``
    so they can be removed when the entry is unloaded.
    """
    coordinator = entry.runtime_data.coordinator
    if not coordinator.data:
        return

    for serial, wb_data in coordinator.data.items():
        alias: str | None = wb_data.get("alias") if wb_data else None
        service_name = _make_wallbox_service_name(alias, serial)

        if hass.services.has_service(DOMAIN, service_name):
            continue

        def _make_handler(
            _entry: KebaRestIntegrationConfigEntry,
        ) -> Callable[[ServiceCall], Coroutine[Any, Any, None]]:
            async def _handle_fetch_wallbox(_call: ServiceCall) -> None:
                """Trigger coordinator refresh for the associated wallbox entry."""
                _coordinator = _entry.runtime_data.coordinator
                _LOGGER.debug(
                    "fetch_data service called - refreshing coordinator for entry %s",
                    _entry.entry_id,
                )
                await _coordinator.async_request_refresh()

            return _handle_fetch_wallbox

        hass.services.async_register(
            DOMAIN,
            service_name,
            _make_handler(entry),
            schema=FETCH_DATA_SERVICE_SCHEMA,
        )
        entry.runtime_data.wallbox_service_names.append(service_name)
        _LOGGER.debug("Registered service %s.%s", DOMAIN, service_name)


def async_unregister_wallbox_services(
    hass: HomeAssistant,
    entry: KebaRestIntegrationConfigEntry,
) -> None:
    """Unregister all per-wallbox fetch_data services registered for *entry*."""
    for service_name in list(entry.runtime_data.wallbox_service_names):
        if hass.services.has_service(DOMAIN, service_name):
            hass.services.async_remove(DOMAIN, service_name)
            _LOGGER.debug("Unregistered service %s.%s", DOMAIN, service_name)
    entry.runtime_data.wallbox_service_names.clear()
