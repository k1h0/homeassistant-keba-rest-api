"""Custom types for integration_keba_rest-api."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .api import KebaRestIntegrationApiClient
    from .coordinator import BlueprintDataUpdateCoordinator


type KebaRestIntegrationConfigEntry = ConfigEntry[KebaRestIntegrationData]


@dataclass
class KebaRestIntegrationData:
    """Data for the Blueprint integration."""

    client: KebaRestIntegrationApiClient
    coordinator: BlueprintDataUpdateCoordinator
    integration: Integration
