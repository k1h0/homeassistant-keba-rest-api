# BMW CarData Implementation - Complete Code Examples

## 1. services.yaml - Service Declaration

```yaml
fetch_telematic_data:
  name: Fetch Telematic Data
  description: Fetch telematic data for a VIN using the stored container and log the response.
  fields:
    entry_id:
      description: Optional config entry id to target. Required if multiple entries are configured.
      example: 01K65NKFESKBQZ78PBW6V9BCCX
    vin:
      description: Optional VIN to query. Defaults to the first VIN seen on the stream.
      example: WBY31AW090FP15359

fetch_vehicle_mappings:
  name: Fetch Vehicle Mappings
  description: Fetch mapping information for the configured account and log the response.
  fields:
    entry_id:
      description: Optional config entry id to target. Required if multiple entries are configured.
      example: 01K65NKFESKBQZ78PBW6V9BCCX

fetch_basic_data:
  name: Fetch Basic Vehicle Data
  description: Fetch static vehicle metadata (model name, series, etc.) for a VIN and log the response.
  fields:
    entry_id:
      description: Optional config entry id to target. Required if multiple entries are configured.
      example: 01K65NKFESKBQZ78PBW6V9BCCX
    vin:
      description: Optional VIN to query. Defaults to the VIN stored in the config entry.
      example: WBY31AW090FP15359

fetch_vehicle_images:
  name: Fetch Vehicle Images
  description: Manually fetch vehicle images for all configured vehicles.

fetch_charging_history:
  name: Fetch Charging History
  description: Fetch charging session history for a VIN (last 30 days). Uses 1 API call per vehicle.
  fields:
    entry_id:
      description: Optional config entry id to target. Required if multiple entries are configured.
      example: 01K65NKFESKBQZ78PBW6V9BCCX
    vin:
      description: Optional VIN to query. If omitted, fetches for all known VINs.
      example: WBY31AW090FP15359

fetch_tyre_diagnosis:
  name: Fetch Tyre Diagnosis
  description: Fetch tyre health and wear data for a VIN. Uses 1 API call per vehicle.
  fields:
    entry_id:
      description: Optional config entry id to target. Required if multiple entries are configured.
      example: 01K65NKFESKBQZ78PBW6V9BCCX
    vin:
      description: Optional VIN to query. If omitted, fetches for all known VINs.
      example: WBY31AW090FP15359
```

## 2. services.py - Schema Definitions

```python
# Schema definitions using voluptuous validation library
TELEMATIC_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): str,
        vol.Optional("vin"): str,
    }
)

MAPPING_SERVICE_SCHEMA = vol.Schema({vol.Optional("entry_id"): str})

BASIC_DATA_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): str,
        vol.Optional("vin"): str,
    }
)

DAILY_FETCH_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): str,
        vol.Optional("vin"): str,
    }
)

MIGRATE_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): str,
        vol.Optional("force", default=False): vol.Boolean(),
        vol.Optional("dry_run", default=False): vol.Boolean(),
    }
)

CLEAN_CONTAINERS_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): str,
        vol.Optional("action", default="list"): vol.In(["list", "delete", "delete_all_matching"]),
        vol.Optional("container_id"): str,
    }
)
```

## 3. services.py - Target Resolution Helper

```python
def _resolve_target(
    hass: HomeAssistant,
    call_data: dict,
) -> tuple[str, ConfigEntry, CardataRuntimeData] | None:
    """Resolve target entry from service call data (for fetch_* services).
    
    Handles:
    - Multi-entry scenarios (requires entry_id)
    - Single-entry mode (uses default entry)
    - Invalid/unknown entry IDs
    
    Returns:
        (entry_id, ConfigEntry, runtime_data) tuple on success, None on error
    """
    # Get all non-internal domain entries
    entries = {k: v for k, v in hass.data.get(DOMAIN, {}).items() if not k.startswith("_")}

    # If entry_id specified in service call, use it
    target_entry_id = call_data.get("entry_id")
    if target_entry_id:
        runtime = entries.get(target_entry_id)
        target_entry = hass.config_entries.async_get_entry(target_entry_id)
        if runtime is None or target_entry is None:
            _LOGGER.error("Cardata service: unknown entry_id %s", target_entry_id)
            return None
        return target_entry_id, target_entry, runtime

    # No entry_id specified: must have exactly 1 entry configured
    if len(entries) != 1:
        _LOGGER.error("Cardata service: multiple entries configured; specify entry_id")
        return None

    # Use the single entry
    target_entry_id, runtime = next(iter(entries.items()))
    target_entry = hass.config_entries.async_get_entry(target_entry_id)
    if target_entry is None:
        _LOGGER.error("Cardata service: unable to resolve entry %s", target_entry_id)
        return None

    return target_entry_id, target_entry, runtime
```

## 4. services.py - Complete fetch_telematic_data Handler

```python
async def async_handle_fetch_telematic(call: ServiceCall) -> None:
    """Handle fetch_telematic_data service call.
    
    This service fetches real-time telemetry data for a vehicle and logs the result.
    Uses the telematics module which handles the actual container communication.
    """
    hass = call.hass
    resolved = _resolve_target(hass, call.data)
    if not resolved:
        # Error already logged by _resolve_target
        return

    target_entry_id, target_entry, runtime = resolved

    # Import telemetry handlers
    from .telematics import (
        async_perform_telematic_fetch,
        async_update_last_telematic_poll,
    )

    # Perform the fetch with optional VIN override
    result = await async_perform_telematic_fetch(
        hass,
        target_entry,
        runtime,
        vin_override=call.data.get("vin"),
    )

    # Handle three result states
    if result.status is None:
        # Fatal error - don't update timestamp or state
        _LOGGER.error(
            "Cardata fetch_telematic_data: fatal error for entry %s (reason=%s)",
            target_entry_id,
            result.reason or "unknown",
        )
        return

    if result.status is True:
        # Data fetched successfully - update the last poll timestamp
        await async_update_last_telematic_poll(hass, target_entry, time.time())
        _LOGGER.info(
            "Cardata fetch_telematic_data: successfully fetched data for entry %s",
            target_entry_id,
        )
    else:
        # False: attempted but failed (temporary failure, may retry)
        _LOGGER.warning(
            "Cardata fetch_telematic_data: failed to fetch data for entry %s (temporary failure)",
            target_entry_id,
        )
```

## 5. services.py - Complete fetch_basic_data Handler

```python
async def async_handle_fetch_basic_data(call: ServiceCall) -> None:
    """Handle fetch_basic_data service call.
    
    This service fetches static metadata for a vehicle (model, series, etc.)
    and updates the device registry with the information.
    """
    from homeassistant.helpers import device_registry as dr
    from .const import BASIC_DATA_ENDPOINT

    hass = call.hass
    resolved = _resolve_target(hass, call.data)
    if not resolved:
        return

    target_entry_id, target_entry, runtime = resolved

    # Get VIN from parameter, or use stored VIN from config entry
    vin = call.data.get("vin") or target_entry.data.get("vin")
    if not vin:
        _LOGGER.error("Cardata fetch_basic_data: no VIN available; provide vin parameter")
        return
    
    # Validate VIN format before using in URL (security)
    if not is_valid_vin(vin):
        _LOGGER.error("Cardata fetch_basic_data: invalid VIN format provided")
        return
    redacted_vin = redact_vin(vin)

    # Ensure access token is fresh
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

    # Get access token after refresh
    access_token = target_entry.data.get("access_token")
    if not access_token:
        _LOGGER.error("Cardata fetch_basic_data: access token missing after refresh")
        return

    # Prepare API request headers
    headers = {
        "Authorization": f"Bearer {access_token}",
        "x-version": API_VERSION,
        "Accept": "application/json",
    }
    url = f"{API_BASE_URL}{BASIC_DATA_ENDPOINT.format(vin=vin)}"

    # Make the HTTP request
    try:
        timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
        async with runtime.session.get(url, headers=headers, timeout=timeout) as response:
            text = await response.text()
            log_text = redact_vin_in_text(text)
            
            # Check for errors
            if response.status != 200:
                _LOGGER.error(
                    "Cardata fetch_basic_data: request failed (status=%s) for %s: %s",
                    response.status,
                    redacted_vin,
                    log_text,
                )
                return
            
            # Parse JSON response
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                payload = text

            # Log the response (with VINs redacted)
            _LOGGER.info(
                "Cardata basic data for %s: %s",
                redacted_vin,
                redact_vin_payload(payload),
            )

            # Process and store metadata if we got a dict response
            if isinstance(payload, dict):
                # Apply basic data to coordinator
                metadata = await runtime.coordinator.async_apply_basic_data(vin, payload)
                
                if metadata:
                    from .metadata import async_store_vehicle_metadata

                    # Store metadata in Home Assistant storage
                    await async_store_vehicle_metadata(
                        hass,
                        target_entry,
                        vin,
                        metadata.get("raw_data") or payload,
                    )

                    # Update device registry with vehicle info
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

## 6. services.py - fetch_charging_history Handler (Multi-VIN Pattern)

```python
async def async_handle_fetch_charging_history(call: ServiceCall) -> None:
    """Handle fetch_charging_history service call.
    
    Demonstrates pattern for optional multi-VIN fetching.
    """
    from .telematics import async_fetch_charging_history

    hass = call.hass
    resolved = _resolve_target(hass, call.data)
    if not resolved:
        return

    _, target_entry, runtime = resolved
    vin = call.data.get("vin")

    # If specific VIN provided, validate and use only that
    if vin:
        if not is_valid_vin(vin):
            _LOGGER.error("Cardata fetch_charging_history: invalid VIN format")
            return
        vins = [vin]
    else:
        # If no VIN specified, fetch for all known VINs
        vins = list(runtime.coordinator.data.keys())

    if not vins:
        _LOGGER.error("Cardata fetch_charging_history: no VINs available")
        return

    # Fetch charging history for each VIN
    for v in vins:
        await async_fetch_charging_history(target_entry, runtime, v)
```

## 7. services.py - Service Registration

```python
def async_register_services(hass: HomeAssistant) -> None:
    """Register all Cardata services.
    
    Called during component setup. Services are only registered once,
    even if multiple config entries are created.
    """
    
    # Register main fetch services with their schemas
    hass.services.async_register(
        DOMAIN,
        "fetch_telematic_data",
        async_handle_fetch_telematic,
        schema=TELEMATIC_SERVICE_SCHEMA,
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

    # Developer/admin services (conditional registration)
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
        _LOGGER.debug("Registered service %s.%s", DOMAIN, "clean_hv_containers")


def async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister all Cardata services.
    
    Called during component unload. Safely checks if service exists
    before attempting to remove it.
    """
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

## 8. lifecycle.py - Service Registration Integration

```python
async def async_setup_cardata(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up CarData from a config entry.
    
    Services are registered once per domain, not per entry.
    """
    from .services import async_register_services, async_unregister_services
    
    domain_data = hass.data.setdefault(DOMAIN, {})
    
    # Register services only once, even if multiple entries exist
    if not domain_data.get("_service_registered"):
        async_register_services(hass)
        domain_data["_service_registered"] = True
    
    # ... rest of setup code ...


async def async_unload_cardata(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry.
    
    Unregisters services when last entry is unloaded.
    """
    from .services import async_unregister_services
    
    domain_data = hass.data.get(DOMAIN, {})
    
    # ... cleanup code ...
    
    # Unregister services when unloading
    async_unregister_services(hass)
    domain_data["_service_registered"] = False
    
    # ... rest of unload code ...
```

## 9. Usage Examples in Automations/Scripts

```yaml
# Example 1: Fetch telemetric data for specific vehicle
- service: cardata.fetch_telematic_data
  data:
    vin: "WBY31AW090FP15359"

# Example 2: Fetch telemetric data (auto-select if single entry)
- service: cardata.fetch_telematic_data
  data:

# Example 3: Fetch with explicit entry ID
- service: cardata.fetch_telematic_data
  data:
    entry_id: "01K65NKFESKBQZ78PBW6V9BCCX"
    vin: "WBY31AW090FP15359"

# Example 4: Fetch vehicle mappings
- service: cardata.fetch_vehicle_mappings
  data:
    entry_id: "01K65NKFESKBQZ78PBW6V9BCCX"

# Example 5: Fetch basic data (static metadata)
- service: cardata.fetch_basic_data
  data:
    vin: "WBY31AW090FP15359"

# Example 6: Fetch charging history for all vehicles
- service: cardata.fetch_charging_history
  data:

# Example 7: Fetch charging history for specific vehicle
- service: cardata.fetch_charging_history
  data:
    vin: "WBY31AW090FP15359"

# Example 8: Manually fetch vehicle images
- service: cardata.fetch_vehicle_images
  data:

# Example 9: Developer service - migrate entity IDs (dry run)
- service: cardata.migrate_entity_ids
  data:
    dry_run: true

# Example 10: Developer service - list containers
- service: cardata.clean_hv_containers
  data:
    action: "list"
```

