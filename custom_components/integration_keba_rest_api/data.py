#!/usr/bin/env python3
"""Custom types for integration_keba_rest_api."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .api import KebaRestIntegrationApiClient
    from .coordinator import KebaDataUpdateCoordinator, KebaUpdateCoordinator


type KebaRestIntegrationConfigEntry = ConfigEntry[KebaRestIntegrationData]


@dataclass
class KebaRestIntegrationData:
    """Data for the Keba integration."""

    client: KebaRestIntegrationApiClient
    coordinator: KebaDataUpdateCoordinator
    integration: Integration
    options_at_setup: dict[str, Any] = field(default_factory=dict)
    update_coordinator: KebaUpdateCoordinator | None = None


@dataclass
class KebaUpdateState:
    """State returned by the KEBA firmware update coordinator."""

    installed_version: str | None = None
    latest_version: str | None = None
    location: str | None = None
    retrieve_date: int | None = None
    install_date: int | None = None
    check_date: int | None = None
    retries: int | None = None
    retry_interval: int | None = None
    signing_certificate: str | None = None
    signature: str | None = None
    description: str | None = None
    status: str | None = None
    update_percentage: int | None = None
    length: int | None = None
    size: int | None = None
    logs: str | None = None
    error: str | None = None
