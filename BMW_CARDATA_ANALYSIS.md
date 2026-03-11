# BMW CarData Home Assistant Integration - Fetch Actions Analysis

## Directory Structure

```
custom_components/cardata/
├── __init__.py                    # Main entry point
├── manifest.json                  # Component metadata
├── services.yaml                  # Service declarations
├── services.py                    # Service handlers (24.5 KB)
├── lifecycle.py                   # Setup/unload/config entry lifecycle
├── coordinator.py                 # Data coordination (39.5 KB)
├── api_parsing.py                 # API response parsing
├── auth.py                        # Authentication & token management
├── bootstrap.py                   # Initial data fetch
├── config_flow.py                 # Configuration UI
├── options_flow.py                # Options/settings UI
├── const.py                       # Constants & configurations
├── container.py                   # Container management
├── coordinator_housekeeping.py    # Maintenance tasks
├── telematics.py                  # Telemetry data fetching
├── metadata.py                    # Metadata storage & retrieval
├── device_tracker.py              # Device tracking platform
├── sensor.py                      # Sensor platform (23.5 KB)
├── binary_sensor.py               # Binary sensor platform
├── button.py                      # Button platform (for services)
├── image.py                       # Image platform
├── number.py                      # Number platform
├── entity.py                      # Base entity class
├── device_info.py                 # Device information
├── soc_learning.py                # State of charge learning
├── soc_prediction.py              # SoC prediction
├── motion_detection.py            # Motion detection
├── magic_soc.py                   # SOC calculations
├── runtime.py                     # Runtime data container
├── device_flow.py                 # Device config flow
├── ratelimit.py                   # Rate limiting
├── http_retry.py                  # HTTP retry logic
├── migrations.py                  # Entity ID migrations
├── debug.py                       # Debug utilities
├── message_utils.py               # Message utilities
├── sensor_helpers.py              # Sensor helpers
├── sensor_diagnostics.py          # Diagnostics for sensors
└── geo_utils.py                   # Geographic utilities
```

## Services Declaration (services.yaml)

The services are declared in YAML format with the following `fetch_*` actions:

### 1. **fetch_telematic_data**
- **Name**: Fetch Telematic Data
- **Description**: Fetch telematic data for a VIN using the stored container and log the response
- **Fields**:
  - `entry_id` (Optional): Config entry ID (required if multiple entries configured)
  - `vin` (Optional): VIN to query (defaults to first VIN on stream)

### 2. **fetch_vehicle_mappings**
- **Name**: Fetch Vehicle Mappings
- **Description**: Fetch mapping information for the configured account and log the response
- **Fields**:
  - `entry_id` (Optional): Config entry ID

### 3. **fetch_basic_data**
- **Name**: Fetch Basic Vehicle Data
- **Description**: Fetch static vehicle metadata (model name, series, etc.)
- **Fields**:
  - `entry_id` (Optional): Config entry ID
  - `vin` (Optional): VIN to query (defaults to stored VIN in config entry)

### 4. **fetch_vehicle_images**
- **Name**: Fetch Vehicle Images
- **Description**: Manually fetch vehicle images for all configured vehicles
- **Fields**: None (no parameters)

### 5. **fetch_charging_history**
- **Name**: Fetch Charging History
- **Description**: Fetch charging session history for a VIN (last 30 days)
- **Fields**:
  - `entry_id` (Optional): Config entry ID
  - `vin` (Optional): VIN to query (fetches all if omitted)

### 6. **fetch_tyre_diagnosis**
- **Name**: Fetch Tyre Diagnosis
- **Description**: Fetch tyre health and wear data for a VIN
- **Fields**:
  - `entry_id` (Optional): Config entry ID
  - `vin` (Optional): VIN to query (fetches all if omitted)

## Implementation Pattern in services.py

### Service Schema Definition (Voluptuous)

```python
# Schema definitions using voluptuous library
TELEMATIC_SERVICE_SCHEMA = vol.Schema({
    vol.Optional("entry_id"): str,
    vol.Optional("vin"): str,
})

BASIC_DATA_SERVICE_SCHEMA = vol.Schema({
    vol.Optional("entry_id"): str,
    vol.Optional("vin"): str,
})

MAPPING_SERVICE_SCHEMA = vol.Schema({vol.Optional("entry_id"): str})

DAILY_FETCH_SERVICE_SCHEMA = vol.Schema({
    vol.Optional("entry_id"): str,
    vol.Optional("vin"): str,
})
```

### Helper Function: _resolve_target()

A critical utility function that handles multi-entry scenarios:

```python
def _resolve_target(
    hass: HomeAssistant,
    call_data: dict,
) -> tuple[str, ConfigEntry, CardataRuntimeData] | None:
    """Resolve target entry from service call data (for fetch_* services).
    
    Returns: (entry_id, ConfigEntry, runtime_data) or None if error
    """
    entries = {k: v for k, v in hass.data.get(DOMAIN, {}).items() if not k.startswith("_")}
    
    # If entry_id specified, use it
    target_entry_id = call_data.get("entry_id")
    if target_entry_id:
        runtime = entries.get(target_entry_id)
        target_entry = hass.config_entries.async_get_entry(target_entry_id)
        if runtime is None or target_entry is None:
            _LOGGER.error("Cardata service: unknown entry_id %s", target_entry_id)
            return None
        return target_entry_id, target_entry, runtime
    
    # If no entry_id specified, must have exactly one entry
    if len(entries) != 1:
        _LOGGER.error("Cardata service: multiple entries configured; specify entry_id")
        return None
    
    target_entry_id, runtime = next(iter(entries.items()))
    target_entry = hass.config_entries.async_get_entry(target_entry_id)
    if target_entry is None:
        _LOGGER.error("Cardata service: unable to resolve entry %s", target_entry_id)
        return None
    
    return target_entry_id, target_entry, runtime
```

### Handler Pattern: async_handle_fetch_* Functions

**Generic Pattern:**
1. Extract hass and call data
2. Resolve target entry using _resolve_target()
3. Refresh access token if needed
4. Make HTTP request with proper headers
5. Parse and log response
6. Update local state (if applicable)
7. Handle errors appropriately

**Example: fetch_telematic_data Handler**

```python
async def async_handle_fetch_telematic(call: ServiceCall) -> None:
    """Handle fetch_telematic_data service call."""
    hass = call.hass
    resolved = _resolve_target(hass, call.data)
    if not resolved:
        return
    
    target_entry_id, target_entry, runtime = resolved
    
    from .telematics import (
        async_perform_telematic_fetch,
        async_update_last_telematic_poll,
    )
    
    # Perform the actual fetch
    result = await async_perform_telematic_fetch(
        hass,
        target_entry,
        runtime,
        vin_override=call.data.get("vin"),
    )
    
    # Handle result status
    if result.status is None:
        # Fatal error
        _LOGGER.error(
            "Cardata fetch_telematic_data: fatal error for entry %s (reason=%s)",
            target_entry_id,
            result.reason or "unknown",
        )
        return
    
    if result.status is True:
        # Success - update timestamp
        await async_update_last_telematic_poll(hass, target_entry, time.time())
        _LOGGER.info(
            "Cardata fetch_telematic_data: successfully fetched data for entry %s",
            target_entry_id,
        )
    else:
        # Temporary failure
        _LOGGER.warning(
            "Cardata fetch_telematic_data: failed to fetch data for entry %s (temporary failure)",
            target_entry_id,
        )
```

**Example: fetch_basic_data Handler**

```python
async def async_handle_fetch_basic_data(call: ServiceCall) -> None:
    """Handle fetch_basic_data service call."""
    from homeassistant.helpers import device_registry as dr
    from .const import BASIC_DATA_ENDPOINT
    
    hass = call.hass
    resolved = _resolve_target(hass, call.data)
    if not resolved:
        return
    
    target_entry_id, target_entry, runtime = resolved
    
    # Get VIN from parameter or config
    vin = call.data.get("vin") or target_entry.data.get("vin")
    if not vin:
        _LOGGER.error("Cardata fetch_basic_data: no VIN available; provide vin parameter")
        return
    
    # Validate VIN format (security)
    if not is_valid_vin(vin):
        _LOGGER.error("Cardata fetch_basic_data: invalid VIN format provided")
        return
    
    redacted_vin = redact_vin(vin)
    
    # Refresh token
    try:
        from .auth import refresh_tokens_for_entry
        await refresh_tokens_for_entry(
            target_entry,
            runtime.session,
            runtime.stream,
            runtime.container_manager,
        )
    except Exception as err:
        _LOGGER.error(
            "Cardata fetch_basic_data: token refresh failed for entry %s: %s",
            target_entry_id,
            err,
        )
        return
    
    access_token = target_entry.data.get("access_token")
    if not access_token:
        _LOGGER.error("Cardata fetch_basic_data: access token missing after refresh")
        return
    
    # Make API request
    headers = {
        "Authorization": f"Bearer {access_token}",
        "x-version": API_VERSION,
        "Accept": "application/json",
    }
    url = f"{API_BASE_URL}{BASIC_DATA_ENDPOINT.format(vin=vin)}"
    
    try:
        timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
        async with runtime.session.get(url, headers=headers, timeout=timeout) as response:
            text = await response.text()
            log_text = redact_vin_in_text(text)
            
            if response.status != 200:
                _LOGGER.error(
                    "Cardata fetch_basic_data: request failed (status=%s) for %s: %s",
                    response.status,
                    redacted_vin,
                    log_text,
                )
                return
            
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                payload = text
            
            _LOGGER.info(
                "Cardata basic data for %s: %s",
                redacted_vin,
                redact_vin_payload(payload),
            )
            
            # Process and store metadata
            if isinstance(payload, dict):
                metadata = await runtime.coordinator.async_apply_basic_data(vin, payload)
                if metadata:
                    from .metadata import async_store_vehicle_metadata
                    
                    await async_store_vehicle_metadata(
                        hass,
                        target_entry,
                        vin,
                        metadata.get("raw_data") or payload,
                    )
                    
                    # Update device registry
                    device_registry = dr.async_get(hass)
                    device_registry.async_get_or_create(
                        config_entry_id=target_entry.entry_id,
                        identifiers={(DOMAIN, vin)},
                        manufacturer=metadata.get("manufacturer", "BMW"),
                        name=metadata.get("name", vin),
                        model=metadata.get("model"),
                        sw_version=metadata.get("sw_version"),
                        hw_version=metadata.get("hw_version"),
                        serial_number=metadata.get("serial_number"),
                    )
    except (aiohttp.ClientError, TimeoutError) as err:
        _LOGGER.error(
            "Cardata fetch_basic_data: network error for %s: %s",
            redacted_vin,
            redact_sensitive_data(str(err)),
        )
```

### Service Registration (async_register_services)

```python
def async_register_services(hass: HomeAssistant) -> None:
    """Register all Cardata services."""
    hass.services.async_register(
        DOMAIN,                              # Domain: "cardata"
        "fetch_telematic_data",             # Service name
        async_handle_fetch_telematic,       # Handler function
        schema=TELEMATIC_SERVICE_SCHEMA,    # Validation schema
    )
    hass.services.async_register(
        DOMAIN,
        "fetch_vehicle_mappings",
        async_handle_fetch_mappings,
        schema=MAPPING_SERVICE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "fetch_basic_data",
        async_handle_fetch_basic_data,
        schema=BASIC_DATA_SERVICE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "fetch_vehicle_images",
        async_fetch_vehicle_images_service,
        schema=vol.Schema({}),
    )
    hass.services.async_register(
        DOMAIN,
        "fetch_charging_history",
        async_handle_fetch_charging_history,
        schema=DAILY_FETCH_SERVICE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "fetch_tyre_diagnosis",
        async_handle_fetch_tyre_diagnosis,
        schema=DAILY_FETCH_SERVICE_SCHEMA,
    )
    
    # Developer services
    if not hass.services.has_service(DOMAIN, "migrate_entity_ids"):
        hass.services.async_register(
            DOMAIN,
            "migrate_entity_ids",
            async_handle_migrate,
            schema=MIGRATE_SERVICE_SCHEMA,
        )
    
    if not hass.services.has_service(DOMAIN, "clean_hv_containers"):
        hass.services.async_register(
            DOMAIN,
            "clean_hv_containers",
            async_handle_clean_containers,
            schema=CLEAN_CONTAINERS_SCHEMA,
        )
```

### Service Unregistration (async_unregister_services)

```python
def async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister all Cardata services."""
    for service in (
        "fetch_telematic_data",
        "fetch_vehicle_mappings",
        "fetch_basic_data",
        "migrate_entity_ids",
        "clean_hv_containers",
        "fetch_vehicle_images",
        "fetch_charging_history",
        "fetch_tyre_diagnosis",
    ):
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)
            _LOGGER.debug("Unregistered service %s.%s", DOMAIN, service)
```

## Integration with Lifecycle (lifecycle.py)

Services are registered during component setup:

```python
from .services import async_register_services, async_unregister_services

async def async_setup_cardata(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up CarData from a config entry."""
    # ... setup code ...
    
    if not domain_data.get("_service_registered"):
        async_register_services(hass)
        domain_data["_service_registered"] = True
    
    # ... rest of setup ...
```

## Key Implementation Patterns

### 1. **Multi-Entry Support**
- Services work with multiple config entries
- `_resolve_target()` function determines which entry to operate on
- If no `entry_id` specified and multiple entries exist, service fails with error

### 2. **Security & Validation**
- VIN validation using `is_valid_vin()` before using in URLs
- Sensitive data redaction in logs (`redact_vin`, `redact_vin_in_text`, `redact_vin_payload`)
- Authorization headers use Bearer token from config entry data

### 3. **Token Management**
- Services refresh access tokens before making API calls
- Uses `refresh_tokens_for_entry()` from auth module
- Proper error handling if token refresh fails

### 4. **HTTP Communication**
- Uses aiohttp for async HTTP requests
- Configurable timeouts (HTTP_TIMEOUT constant)
- Proper error handling for network failures and timeouts

### 5. **Data Processing**
- Responses are parsed and logged
- Structured metadata is stored and updated
- Device registry is updated with vehicle information

### 6. **Result Handling**
- Three-state result status: None (fatal), True (success), False (temporary failure)
- Timestamps are updated on successful fetches
- Different logging levels for different outcomes

### 7. **Developer Tools**
- `migrate_entity_ids`: Supports dry_run and force parameters
- `clean_hv_containers`: Supports list/delete/delete_all_matching actions
- Optional registration (only if not already present)

## Manifest (manifest.json)

```json
{
  "domain": "cardata",
  "name": "BMW Cardata",
  "codeowners": ["@kvanbiesen"],
  "config_flow": true,
  "documentation": "https://github.com/kvanbiesen/bmw-cardata-ha/",
  "integration_type": "device",
  "iot_class": "cloud_push",
  "issue_tracker": "https://github.com/kvanbiesen/bmw-cardata-ha/issues",
  "loggers": ["custom_components.cardata", "paho.mqtt", "paho.mqtt.client"],
  "requirements": ["paho-mqtt>=1.6.1"],
  "version": "5.0.2"
}
```

## Dependencies & Imports

**Key imports in services.py:**
- `voluptuous` - Schema validation
- `aiohttp` - Async HTTP client
- `HomeAssistant` - Core framework
- `ConfigEntry` - Configuration management
- `ServiceCall` - Service call data
- Custom modules: auth, api_parsing, utils, telematics, metadata, etc.

## Summary

The BMW CarData integration implements fetch services following these key principles:

1. **Declarative** - Services defined in services.yaml with clear parameters
2. **Modular** - Schema definitions separate from handlers
3. **Robust** - Comprehensive error handling and validation
4. **Secure** - VIN validation, token refresh, sensitive data redaction
5. **Flexible** - Multi-entry support with fallback to single-entry mode
6. **Logged** - Detailed logging with redacted sensitive information
7. **Extensible** - Easy to add new fetch services following the same pattern
___BEGIN___COMMAND_DONE_MARKER___0
