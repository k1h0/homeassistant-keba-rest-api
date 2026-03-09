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
    # Only offer the action for config entries the device is actually
    # registered with by the device registry. Do not attempt fallbacks.
    actions: List[Dict[str, Any]] = []
    for entry_id in device.config_entries:
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
    # Prefer the provided config entry id. If missing, try to resolve from
    # the device registry entry. Do not use a global/integration-level
    # fallback — only update the coordinator for the related config entry.
    entry_id = config.get("entry_id")
    device_id = config.get("device_id")
    if not entry_id and device_id:
        device = dr.async_get(hass).async_get(device_id)
        if device and device.config_entries:
            entry_id = next(iter(device.config_entries))

    if not entry_id:
        return

    entry = hass.config_entries.async_get_entry(entry_id)
    if not entry:
        return

    runtime = getattr(entry, "runtime_data", None)
    coordinator = getattr(runtime, "coordinator", None) if runtime else None
    if coordinator:
        await coordinator.async_request_refresh()
