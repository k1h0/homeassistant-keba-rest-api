#!/usr/bin/env python3
"""
Custom integration to integrate integration_keba_rest_api with Home Assistant.

For more details about this integration, please refer to
https://github.com/ludeeus/integration_keba_rest_api
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME, Platform
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_loaded_integration

from .api import (
    KebaRestIntegrationApiClient,
    KebaRestIntegrationApiClientAuthenticationError,
    KebaRestIntegrationApiClientError,
)
from .const import DOMAIN, LOGGER
from .coordinator import KebaDataUpdateCoordinator
from .data import KebaRestIntegrationData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall

    from .data import KebaRestIntegrationConfigEntry

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
]

SERVICE_FETCH_DATA = "fetch_data"


async def _async_fetch_data(hass: HomeAssistant, _call: ServiceCall) -> None:
    """Refresh data for all loaded KEBA config entries concurrently."""
    await asyncio.gather(
        *(
            entry.runtime_data.coordinator.async_request_refresh()
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.runtime_data and entry.runtime_data.coordinator
        )
    )


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(
    hass: HomeAssistant,
    entry: KebaRestIntegrationConfigEntry,
) -> bool:
    """Set up this integration using UI."""
    coordinator = KebaDataUpdateCoordinator(
        hass=hass,
        logger=LOGGER,
        name=DOMAIN,
        config_entry=entry,
        update_interval=timedelta(
            seconds=max(5, int(entry.options.get("coordinator_poll_interval", 60)))
        ),
        always_update=True,
    )
    entry.runtime_data = KebaRestIntegrationData(
        client=KebaRestIntegrationApiClient(
            url=entry.data[CONF_URL],
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
            session=async_get_clientsession(hass),
        ),
        integration=async_get_loaded_integration(hass, entry.domain),
        coordinator=coordinator,
    )

    # If we previously persisted a refresh token, use it and attempt to refresh
    rt = entry.data.get("refreshToken")
    if rt:
        entry.runtime_data.client.set_refresh_token(rt)
        try:
            await entry.runtime_data.client.async_refresh_jwt()
        except KebaRestIntegrationApiClientAuthenticationError as exc:
            # Refresh token is invalid -> require reauth
            raise ConfigEntryAuthFailed(exc) from exc
        except KebaRestIntegrationApiClientError as exc:
            LOGGER.exception("Error while refreshing token during setup: %s", exc)
            return False
    else:
        # No persisted refresh token; perform a fresh login and
        # persist the refresh token
        try:
            tokens = await entry.runtime_data.client.async_login_jwt()
        except KebaRestIntegrationApiClientAuthenticationError as exc:
            raise ConfigEntryAuthFailed(exc) from exc
        except KebaRestIntegrationApiClientError as exc:
            LOGGER.exception("Error while logging in during setup: %s", exc)
            return False

        # Persist refreshToken in the config entry data for future restarts
        if tokens.get("refreshToken"):
            hass.config_entries.async_update_entry(
                entry, data={**entry.data, "refreshToken": tokens.get("refreshToken")}
            )

    # https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Register the fetch_data service once (shared across all config entries)
    if not hass.services.has_service(DOMAIN, SERVICE_FETCH_DATA):

        async def _handle_fetch_data(call: ServiceCall) -> None:
            await _async_fetch_data(hass, call)

        hass.services.async_register(DOMAIN, SERVICE_FETCH_DATA, _handle_fetch_data)

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: KebaRestIntegrationConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Unregister the service when the last config entry is removed
    if unload_ok and not hass.config_entries.async_entries(DOMAIN):
        hass.services.async_remove(DOMAIN, SERVICE_FETCH_DATA)

    return unload_ok


async def async_reload_entry(
    hass: HomeAssistant,
    entry: KebaRestIntegrationConfigEntry,
) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
