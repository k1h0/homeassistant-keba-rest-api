"""Device actions for the KEBA REST API integration.

Expose a device action to trigger an immediate data refresh for the
targeted wallbox. This wires the UI device action to the existing
`integration_keba_rest_api.fetch_data` service.
"""
from __future__ import annotations

from typing import Any, Dict, List

import voluptuous as vol


from homeassistant.helpers import device_registry as dr
from homeassistant.core import HomeAssistant

from .const import DOMAIN

ACTION_FETCH_DATA = "fetch_data"


async def async_get_actions(hass: HomeAssistant, device_id: str) -> List[Dict[str, Any]]:
    """Return a list of device actions for a device."""
    device = dr.async_get(hass).async_get(device_id)
    if not device:
        return []

    actions: List[Dict[str, Any]] = []

    # Determine which config entry(ies) this device belongs to. Prefer the
    # device.registry's recorded config_entries, but fall back to resolving
    # via the device identifiers (e.g. the wallbox serial) when empty. This
    # allows offering device actions for wallbox devices that are not
    # directly linked to the config entry in some setups.
    entry_ids: set[str] = set(device.config_entries)

    if not entry_ids:
        # Look for identifiers owned by this integration and try to match
        # them against the coordinator data of each config entry.
        for ident in device.identifiers:
            if not isinstance(ident, tuple) or len(ident) != 2:
                continue
            ident_domain, ident_value = ident
            if ident_domain != DOMAIN:
                continue

            # Treat identifier value as possible wallbox serial and check
            # all config entries for this integration to see which one
            # knows about that serial.
            for entry in hass.config_entries.async_entries(DOMAIN):
                runtime = getattr(entry, "runtime_data", None)
                coordinator = getattr(runtime, "coordinator", None) if runtime else None
                if not coordinator or not getattr(coordinator, "data", None):
                    continue
                if ident_value in coordinator.data:
                    entry_ids.add(entry.entry_id)

    # Offer the fetch_data action for each discovered config entry
    for entry_id in entry_ids:
        actions.append(
            {
                "domain": DOMAIN,
                "type": ACTION_FETCH_DATA,
                "device_id": device_id,
                "entry_id": entry_id,
            }
        )

    return actions


async def async_get_action_capabilities(hass: HomeAssistant, config: Dict[str, Any]) -> Dict[str, Any]:
    """Return action capabilities (no extra fields required)."""
    return {"extra_fields": vol.Schema({})}


async def async_call_action(hass: HomeAssistant, config: Dict[str, Any], variables: Dict[str, Any]) -> None:
    """Execute the action by calling the integration service."""
    device_id = config.get("device_id")
    # Device actions should call the integration service; the service
    # already supports a `device_id` target.
    await hass.services.async_call(
        DOMAIN,
        ACTION_FETCH_DATA,
        {"device_id": device_id},
        blocking=True,
    )
