#!/usr/bin/env python3
"""Custom types for integration_keba_rest_api."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .api import KebaRestIntegrationApiClient
    from .coordinator import KebaDataUpdateCoordinator


type KebaRestIntegrationConfigEntry = ConfigEntry[KebaRestIntegrationData]


@dataclass
class KebaRestIntegrationData:
    """Data for the Keba integration."""

    client: KebaRestIntegrationApiClient
    coordinator: KebaDataUpdateCoordinator
    integration: Integration
