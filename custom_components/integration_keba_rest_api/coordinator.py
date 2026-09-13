#!/usr/bin/env python3
"""DataUpdateCoordinator for integration_keba_rest_api."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    KebaRestIntegrationApiClientAuthenticationError,
    KebaRestIntegrationApiClientError,
)
from .data import KebaUpdateState

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

        # Persist the refresh token if it changed (e.g. after an automatic re-login)
        new_rt = self.config_entry.runtime_data.client.get_refresh_token()
        if new_rt and new_rt != self.config_entry.data.get("refreshToken"):
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**self.config_entry.data, "refreshToken": new_rt},
            )

        return data


class KebaUpdateCoordinator(DataUpdateCoordinator[KebaUpdateState]):
    """Class to manage firmware update information."""

    config_entry: KebaRestIntegrationConfigEntry

    async def _async_update_data(self) -> KebaUpdateState:
        """Return the current package version and cached portal information."""
        client = self.config_entry.runtime_data.client
        installed_version = await client.async_get_package_version()
        state = KebaUpdateState(installed_version=installed_version)

        try:
            portal = await client.async_get_update_portal()
        except KebaRestIntegrationApiClientError as exc:
            self.logger.debug("No cached KEBA update information: %s", exc)
            return state

        if not isinstance(portal, dict):
            return state

        description = portal.get("description")
        state.location = portal.get("location")
        state.retrieve_date = portal.get("retrieveDate")
        state.install_date = portal.get("installDate")
        state.check_date = portal.get("checkDate")
        state.retries = portal.get("retries")
        state.retry_interval = portal.get("retryInterval")
        state.signing_certificate = portal.get("signingCertificate")
        state.signature = portal.get("signature")
        state.description = description if isinstance(description, str) else None
        state.latest_version = _extract_version(state.description, installed_version)
        return state

    async def async_check_for_updates(self) -> None:
        """Request a fresh portal check and refresh the cached update state."""
        await self.config_entry.runtime_data.client.async_check_update_portal()
        await self.async_request_refresh()


_VERSION_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])v?(\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)(?![A-Za-z0-9])"
)
_TARGET_VERSION_PATTERN = re.compile(
    r"(?:nach\s+der\s+installation.*?softwareversion|"
    r"(?:aktualisiert|aktualisierung|update).*?auf)\s+v?"
    r"(\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)",
    re.IGNORECASE | re.DOTALL,
)


def _extract_version(
    description: str | None, installed_version: str | None = None
) -> str | None:
    """Extract the target version from a strictly delimited description."""
    if not description:
        return None

    target_matches = _TARGET_VERSION_PATTERN.findall(description)
    candidates = target_matches or _VERSION_PATTERN.findall(description)
    if not candidates:
        return None

    if installed_version:
        installed_key = _version_key(installed_version)
        newer = [
            version for version in candidates if _version_key(version) > installed_key
        ]
        if newer:
            return max(newer, key=_version_key)

    return candidates[-1]


def _version_key(version: str) -> tuple[int, int, int]:
    """Return the numeric part used to compare firmware versions."""
    major, minor, patch = version.lstrip("v").split(".", maxsplit=2)
    patch = re.match(r"\d+", patch)
    return int(major), int(minor), int(patch.group()) if patch else 0
