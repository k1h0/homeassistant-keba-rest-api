#!/usr/bin/env python3
"""DataUpdateCoordinator for integration_keba_rest_api."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    KebaRestIntegrationApiClientAuthenticationError,
    KebaRestIntegrationApiClientError,
)

if TYPE_CHECKING:
    from .data import KebaRestIntegrationConfigEntry


# https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
class KebaDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    config_entry: KebaRestIntegrationConfigEntry

    async def _async_update_data(self) -> dict:
        """Return mapping serial -> wallbox payload dict."""
        data: dict[str, dict] = {}

        self.logger.debug(
            "Trying to update values. config_entry: %s", self.config_entry
        )

        self.logger.debug("Fetching wallbox data")
        try:
            resp = await self.config_entry.runtime_data.client.async_get_all_wallboxes()
        except KebaRestIntegrationApiClientAuthenticationError as exc:
            raise ConfigEntryAuthFailed(exc) from exc
        except KebaRestIntegrationApiClientError as exc:
            raise UpdateFailed(exc) from exc

        wallboxes = resp.get("wallboxes", []) if isinstance(resp, dict) else []

        for wb in wallboxes:
            serial = wb.get("serialNumber")
            if not serial:
                continue
            try:
                detail = await self.config_entry.runtime_data.client.async_get_wallbox(
                    serial
                )
                data[serial] = detail
            except KebaRestIntegrationApiClientError as exc:
                self.logger.debug("Error fetching wallbox %s: %s", serial, exc)
            except Exception:  # pylint: disable=broad-except
                # Log exception with stack trace; avoid passing exception object
                self.logger.exception(
                    "Unexpected error fetching wallbox %s",
                    serial,
                )
        self.logger.debug("Received updated values. data: %s", data)
        return data
