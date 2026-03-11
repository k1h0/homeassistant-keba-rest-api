# Quick Reference: BMW CarData Fetch Services Implementation

## File Organization

| File | Purpose |
|------|---------|
| `services.yaml` | YAML service declarations with schemas |
| `services.py` | Python service handlers and registration logic |
| `__init__.py` | Component entry point |
| `lifecycle.py` | Setup/teardown where services are registered |

## 6 Fetch Services Implemented

1. **fetch_telematic_data** - Real-time vehicle telemetry
2. **fetch_vehicle_mappings** - Account vehicle mappings
3. **fetch_basic_data** - Static vehicle metadata
4. **fetch_vehicle_images** - Vehicle images
5. **fetch_charging_history** - Charging session history
6. **fetch_tyre_diagnosis** - Tire health and wear

## Schema Definition Pattern

```python
SERVICE_SCHEMA = vol.Schema({
    vol.Optional("entry_id"): str,        # Optional: config entry ID
    vol.Optional("vin"): str,             # Optional: vehicle VIN
    # ... other optional fields
})
```

## Handler Implementation Pattern

```python
async def async_handle_fetch_xxx(call: ServiceCall) -> None:
    """Handle fetch_xxx service call."""
    hass = call.hass
    
    # 1. Resolve target entry (handles multi-entry case)
    resolved = _resolve_target(hass, call.data)
    if not resolved:
        return
    target_entry_id, target_entry, runtime = resolved
    
    # 2. Validate inputs (VIN format, etc.)
    vin = call.data.get("vin")
    if vin and not is_valid_vin(vin):
        _LOGGER.error("Invalid VIN format")
        return
    
    # 3. Refresh token if needed
    try:
        from .auth import refresh_tokens_for_entry
        await refresh_tokens_for_entry(target_entry, runtime.session, ...)
    except Exception as err:
        _LOGGER.error("Token refresh failed: %s", err)
        return
    
    # 4. Make API request
    headers = {
        "Authorization": f"Bearer {access_token}",
        "x-version": API_VERSION,
        "Accept": "application/json",
    }
    try:
        async with runtime.session.get(url, headers=headers, timeout=...) as response:
            if response.status != 200:
                _LOGGER.error("Request failed (status=%s): %s", response.status, ...)
                return
            data = await response.json()
    except (aiohttp.ClientError, TimeoutError) as err:
        _LOGGER.error("Network error: %s", err)
        return
    
    # 5. Process and store results
    _LOGGER.info("Fetch successful: %s", redact_vin_payload(data))
    # Update state, metadata, device registry, etc.
```

## Multi-Entry Resolution (_resolve_target)

```python
def _resolve_target(hass, call_data):
    """Returns (entry_id, ConfigEntry, runtime_data) or None"""
    entries = {k: v for k, v in hass.data.get(DOMAIN, {}).items() 
               if not k.startswith("_")}
    
    # If entry_id specified: use it (validate it exists)
    if call_data.get("entry_id"):
        target_id = call_data["entry_id"]
        if target_id not in entries:
            _LOGGER.error("Unknown entry_id: %s", target_id)
            return None
        return target_id, entry, runtime
    
    # If no entry_id: must have exactly 1 entry
    if len(entries) != 1:
        _LOGGER.error("Multiple entries configured; specify entry_id")
        return None
    
    target_id, runtime = next(iter(entries.items()))
    return target_id, entry, runtime
```

## Service Registration Pattern

```python
def async_register_services(hass: HomeAssistant) -> None:
    """Register all services."""
    hass.services.async_register(
        DOMAIN,              # "cardata"
        "fetch_xxx",         # Service name
        async_handle_fetch_xxx,  # Handler
        schema=SCHEMA,       # Validation schema
    )

def async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister all services."""
    for service_name in SERVICE_NAMES:
        if hass.services.has_service(DOMAIN, service_name):
            hass.services.async_remove(DOMAIN, service_name)
```

## Called From lifecycle.py

```python
# In async_setup_cardata():
if not domain_data.get("_service_registered"):
    async_register_services(hass)
    domain_data["_service_registered"] = True

# In async_unload_cardata():
async_unregister_services(hass)
```

## Security Features

1. **VIN Validation**: `is_valid_vin()` before using in URLs
2. **Sensitive Data Redaction**: 
   - `redact_vin()` - Hide VINs in logs
   - `redact_vin_in_text()` - Hide VINs in response text
   - `redact_vin_payload()` - Hide VINs in JSON payloads
3. **Token Management**: Refresh tokens before API calls
4. **Authorization Headers**: Bearer token from config entry

## Error Handling Pattern

```python
# Fatal error (result.status is None)
if result.status is None:
    _LOGGER.error("Fatal error: %s", result.reason)
    return  # Don't update state

# Temporary failure (result.status is False)
if result.status is False:
    _LOGGER.warning("Temporary failure, will retry")
    return

# Success (result.status is True)
if result.status is True:
    _LOGGER.info("Success!")
    # Update state, timestamps, etc.
```

## Key Constants (from const.py)

```python
API_BASE_URL = "https://..."              # BMW API base
API_VERSION = "v1"                        # API version
HTTP_TIMEOUT = 30                         # Request timeout
DOMAIN = "cardata"                        # Component domain
HV_BATTERY_CONTAINER_NAME = "..."         # Container name
HV_BATTERY_CONTAINER_PURPOSE = "..."      # Container purpose
BASIC_DATA_ENDPOINT = "/vehicles/{vin}/..."  # VIN-based endpoint
```

## Import Dependencies

```python
# Core
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry as dr

# Validation
import voluptuous as vol

# HTTP
import aiohttp

# Utilities
import logging
import time
import json
```

## Developer Services

1. **migrate_entity_ids** - Migrate old entity ID format
   - `entry_id` (optional): Target entry
   - `force` (bool): Force migration
   - `dry_run` (bool): Preview changes

2. **clean_hv_containers** - Manage HV battery containers
   - `entry_id` (optional): Target entry
   - `action` (list|delete|delete_all_matching): Action to perform
   - `container_id` (str): For delete action

## Testing Pattern

```python
# Call service from automation/script:
service: cardata.fetch_basic_data
data:
  entry_id: "config_entry_id"  # Optional if single entry
  vin: "WBY31AW090FP15359"

# Service logs response to Home Assistant logs
# Check: Settings > System > Logs > Cardata
```

## Summary

The BMW CarData integration demonstrates a clean, production-grade pattern for implementing Home Assistant services:
- **Declarative** YAML schemas with clear parameters
- **Modular** handler functions with consistent error handling
- **Flexible** multi-entry support with graceful fallbacks
- **Secure** with VIN validation and data redaction
- **Observable** with detailed logging
- **Maintainable** with clear separation of concerns
