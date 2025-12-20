#!/usr/bin/env python3
"""
Custom integration to integrate integration_keba_rest-api with Home Assistant.

For more details about this integration, please refer to
https://github.com/ludeeus/integration_keba_rest-api
"""

from __future__ import annotations

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
    from homeassistant.core import HomeAssistant

    from .data import KebaRestIntegrationConfigEntry

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
]


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
        update_interval=timedelta(hours=1),
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
    rt = entry.data.get("refresh_token")
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

        # Persist refresh_token in the config entry data for future restarts
        if tokens.get("refresh_token"):
            hass.config_entries.async_update_entry(
                entry, data={**entry.data, "refresh_token": tokens.get("refresh_token")}
            )

    # https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: KebaRestIntegrationConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant,
    entry: KebaRestIntegrationConfigEntry,
) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
