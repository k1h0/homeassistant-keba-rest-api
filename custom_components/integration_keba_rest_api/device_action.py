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
    # Offer the action for each config entry the device belongs to
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
    device_id = config.get("device_id")
    # Device actions should call the integration service; the service
    # already supports a `device_id` target.
    await hass.services.async_call(
        DOMAIN,
        ACTION_FETCH_DATA,
        {"device_id": device_id},
        blocking=True,
    )
