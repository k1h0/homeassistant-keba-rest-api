# BMW CarData Reference Repository Analysis - Summary

## Repository Analyzed
- **URL**: https://github.com/kvanbiesen/bmw-cardata-ha
- **Component**: Home Assistant custom integration for BMW vehicle data
- **Domain**: `cardata`

## Deliverables

Three comprehensive documents have been created:

### 1. **BMW_CARDATA_ANALYSIS.md** - Complete Architecture
- Full directory structure (40+ files)
- All 6 fetch services detailed
- Schema definitions with Voluptuous library
- Helper functions and patterns
- Integration with lifecycle
- Security features and best practices

### 2. **BMW_CARDATA_QUICK_REFERENCE.md** - Cheat Sheet
- File organization table
- Service list
- Implementation patterns with code snippets
- Multi-entry resolution logic
- Error handling patterns
- Testing and usage examples

### 3. **BMW_CARDATA_CODE_EXAMPLES.md** - Production Code
- Complete YAML service declarations
- Full Python handler implementations
- Schema definitions
- Registration/unregistration functions
- Real automation examples
- Commented code with explanations

## Key Findings

### Architecture Pattern

```
services.yaml (YAML declarations)
    ↓
services.py (Python implementation)
    ├─ Schemas (voluptuous)
    ├─ _resolve_target() (multi-entry helper)
    ├─ async_handle_fetch_xxx() (handlers)
    └─ async_register_services() (registration)
    ↓
lifecycle.py (component lifecycle)
    ├─ async_setup_cardata() → calls async_register_services()
    └─ async_unload_cardata() → calls async_unregister_services()
```

### Six Fetch Services

| Service | Purpose | Parameters |
|---------|---------|-----------|
| `fetch_telematic_data` | Real-time vehicle telemetry | entry_id, vin |
| `fetch_vehicle_mappings` | Account vehicle mappings | entry_id |
| `fetch_basic_data` | Static vehicle metadata | entry_id, vin |
| `fetch_vehicle_images` | Vehicle photos | (none) |
| `fetch_charging_history` | Last 30 days charging | entry_id, vin |
| `fetch_tyre_diagnosis` | Tire health & wear | entry_id, vin |

### Implementation Pattern Summary

**1. Service Declaration (services.yaml)**
- Human-readable names and descriptions
- Clear field documentation with examples
- Type hints via schema definitions

**2. Schema Validation (services.py)**
```python
SERVICE_SCHEMA = vol.Schema({
    vol.Optional("entry_id"): str,
    vol.Optional("vin"): str,
})
```

**3. Handler Implementation (services.py)**
- Resolve target entry (handles multi-entry)
- Validate inputs (VIN format)
- Refresh auth token
- Make API request with proper headers
- Parse response
- Handle errors (fatal vs temporary)
- Update state/metadata
- Log with sensitive data redacted

**4. Registration/Unregistration (services.py)**
```python
def async_register_services(hass):
    hass.services.async_register(
        DOMAIN,
        "service_name",
        async_handler_function,
        schema=SERVICE_SCHEMA,
    )
```

**5. Lifecycle Integration (lifecycle.py)**
- Register services during component setup
- Unregister services during component unload
- Only register once, even with multiple config entries

### Security Best Practices

1. **VIN Validation**: Uses `is_valid_vin()` before using in URLs
2. **Sensitive Data Redaction**:
   - `redact_vin()` - Hide VINs in logs
   - `redact_vin_in_text()` - Hide in response text
   - `redact_vin_payload()` - Hide in JSON data
3. **Token Management**: Refresh tokens before API calls
4. **Authorization**: Bearer tokens in headers
5. **Timeout Handling**: Configurable HTTP timeouts

### Error Handling Pattern

Three-state result status:
- `None` → Fatal error (don't update state)
- `True` → Success (update state/timestamps)
- `False` → Temporary failure (may retry)

### Multi-Entry Support

The `_resolve_target()` helper function:
- Accepts optional `entry_id` parameter
- If specified: validates and uses it
- If not specified: requires exactly 1 entry (error otherwise)
- Returns: (entry_id, ConfigEntry, runtime_data) tuple

## Key File Breakdown

| File | Size | Purpose |
|------|------|---------|
| `services.yaml` | 3.5 KB | YAML service declarations |
| `services.py` | 24.5 KB | Service handlers & registration |
| `__init__.py` | 2.4 KB | Component entry point |
| `lifecycle.py` | 31.4 KB | Setup/unload logic (calls services registration) |
| `coordinator.py` | 39.5 KB | Data coordination |
| `auth.py` | 28.3 KB | Token management |
| `bootstrap.py` | 22 KB | Initial data fetch |
| `telematics.py` | N/A | Telemetry fetching |
| `metadata.py` | 28.6 KB | Metadata storage |

## Patterns Applicable to KEBA REST API

### 1. Service Declaration
Use YAML for clear, human-readable service definitions with examples.

### 2. Schema Validation
Use Voluptuous for parameter validation before handler execution.

### 3. Helper Resolution Function
Create helper function to resolve target device/entry when multiple devices possible.

### 4. Handler Pattern
Follow consistent pattern: resolve → validate → fetch → parse → store → log

### 5. Multi-Device Support
Use `_resolve_target()`-style pattern for optional device_id parameter.

### 6. Error Handling
Implement three-level error status (None=fatal, True=success, False=temporary).

### 7. Lifecycle Integration
Register services in async_setup_entry, unregister in async_unload_entry.

### 8. Security
- Validate all parameters before use
- Redact sensitive data in logs
- Use proper authentication headers
- Implement timeouts for network requests

### 9. Logging
Use different log levels appropriately:
- ERROR: Failures, missing parameters
- WARNING: Temporary issues
- INFO: Successful operations
- DEBUG: Detailed flow

### 10. Device Registry
Update Home Assistant's device registry with device metadata.

## Testing Pattern

Services can be called from:
1. **Automations**: `service: cardata.fetch_xxx`
2. **Scripts**: Service calls in script editor
3. **Developer Tools**: Services tab in Home Assistant settings
4. **API**: Direct HTTP calls to `/api/services/cardata/fetch_xxx`

## Manifest Structure

```json
{
  "domain": "cardata",
  "name": "BMW Cardata",
  "config_flow": true,
  "integration_type": "device",
  "iot_class": "cloud_push",
  "version": "5.0.2"
}
```

## Lessons Learned

1. **Modularity**: Separate concerns (yaml, schemas, handlers, lifecycle)
2. **Clarity**: Clear naming conventions (`async_handle_fetch_xxx`)
3. **Robustness**: Comprehensive error handling at each step
4. **Security**: Default to safe practices (validation, redaction, tokens)
5. **Flexibility**: Support optional parameters and multi-entry scenarios
6. **Observability**: Detailed logging with redacted sensitive info
7. **Testability**: Services can be triggered from UI/automations
8. **Documentation**: Clear descriptions in YAML
9. **Maintainability**: Consistent patterns across all services
10. **Extensibility**: Easy to add new services following same pattern

## Conclusion

The BMW CarData integration provides an excellent reference for implementing Home Assistant services. It demonstrates production-grade code with:
- Clear architecture and separation of concerns
- Comprehensive error handling
- Security best practices
- Multi-entry support
- Extensive logging and debugging
- Professional documentation
- Extensible patterns

This pattern can be directly applied to the KEBA REST API integration for fetch/update actions, adapting the payload types and validation rules to suit KEBA's API specifics.
