# Home Assistant integration mapping

This file is intentionally maintained separately from the generated OpenAPI
artifacts. It documents decisions made by this repository, not by the KEBA
API contract.

## Live contract

- Source: `KEBA_OPENAPI_URL` in `./docs/keba-rest-api/.env`
- Local source snapshot: `./docs/keba-rest-api/openapi_orig.json`
- Refresh command: `python3 docs/keba-rest-api/sync_openapi.py`
- Offline refresh: `python3 docs/keba-rest-api/sync_openapi.py --offline`
- The API uses OpenAPI 3.0.3 and currently reports version 2.4.1.
- The wallbox commonly exposes HTTPS on port 8443 and may use a self-signed certificate.

## Client conventions

The Home Assistant API client is in
`custom_components/integration_keba_rest_api/api.py`.

- Authenticated requests use `Authorization: Bearer <accessToken>`.
- `POST /v2/jwt/login` receives `username` and `password` and returns `accessToken` and `refreshToken`.
- `POST /v2/jwt/refresh` uses the refresh token as its Bearer token and returns a new `accessToken`.
- A 401 or 403 is treated as an authentication failure by the client wrapper.
- New methods should use the existing `_api_wrapper` instead of duplicating HTTP, timeout, SSL fallback, or token handling.
- Path parameters must be serialized safely. Do not concatenate untrusted values into URLs.
- Some API operations return CSV, binary data, or a 204 response instead of JSON. Do not assume every successful response supports `response.json()`.

## Existing wallbox data flow

`custom_components/integration_keba_rest_api/coordinator.py` performs the
regular update.

| API operation | Expected payload | Consumer |
| --- | --- | --- |
| `GET /v2/wallboxes` | Object with a `wallboxes` array | Coordinator discovers serial numbers |
| `GET /v2/wallboxes/{serialNumber}` | Wallbox object | Coordinator stores detail data by serial number |
| `POST /v2/wallboxes/{serialNumber}/start-charging` | Usually a wallbox/action response | Start service and button |
| `POST /v2/wallboxes/{serialNumber}/stop-charging` | Usually a wallbox/action response | Stop service and button |

The coordinator skips a wallbox when its detail request fails, then continues
with other discovered wallboxes. Preserve this behavior unless a new feature
explicitly requires a different failure policy.

## Wallbox fields used by entities

The wallbox detail object is the primary source for entities.

| JSON field | Usage | Notes |
| --- | --- | --- |
| `serialNumber` | Device identity | Required for coordinator and service targeting |
| `alias`, `model`, `firmwareVersion`, `macAddress`, `ipAddress`, `errorCode` | Entity attributes | Optional in API responses |
| `state` | Main charging state sensor | Enum is defined by the `v2Wbstate` schema |
| `vehiclePlugged` | Binary sensor | Missing values are treated as false by the current entity |
| `sessionActive` | Binary sensor | Missing values are treated as false by the current entity |
| `maxPhases`, `phasesUsed` or `phaseUsed` | Phase sensors | The integration supports the observed field variants |
| `maxCurrent` | Maximum-current sensor | API value is scaled by `0.001` by the current sensor implementation |
| `meter.meterValue` | Energy sensor | API unit is mWh; current implementation scales by `0.001` |
| `meter.totalActivePower` | Power sensor | API unit is mW; current implementation scales by `0.001` |
| `meter.currentOffered` | Current sensor | API unit is mA; current implementation scales by `0.001` |
| `meter.temperature` | Temperature sensor | API unit is hundredths of a degree Celsius; current implementation scales by `0.01` |

Confirm units in the generated OpenAPI schemas before adding a new sensor.
Do not infer a unit from a field name alone.

## Services and actions

`custom_components/integration_keba_rest_api/services.py` resolves a Home
Assistant device target to an integration entry and wallbox serial number.

- `integration_keba_rest_api.start_charging` calls the v2 start operation.
- `integration_keba_rest_api.stop_charging` calls the v2 stop operation.
- `integration_keba_rest_api.fetch_data` requests a coordinator refresh.
- Start and stop handlers refresh the coordinator after the command completes.
- New actions should follow the same device-target resolution and refresh pattern.

## Prioritized endpoint groups

When implementing additional endpoints, inspect the generated
`endpoint_index.md` first, then the exact operation in `openapi_pretty.json`.

1. Authentication: `/v2/jwt/login`, `/v2/jwt/refresh`, and fresh-login behavior.
2. Wallbox state: list, detail, state, dipswitch, and change-availability operations.
3. Charging actions: normal and synchronous start/stop, phase toggle, and session stop.
4. Sessions: list, detail, filters, statistics, and exports.
5. Meter/MVA: synchronization status, synchronization, and CSV exports.
6. Configuration: only add a configuration endpoint when it has a clear Home Assistant entity or service use case.

## Implementation checklist

- Confirm the exact v2 path, HTTP method, parameters, request content type, and response statuses in `openapi_pretty.json`.
- Resolve every response `$ref` before choosing a return type.
- Decide whether the response is JSON, empty, CSV, or binary.
- Add one focused client method using `_api_wrapper`.
- Add the smallest corresponding Home Assistant entity, button, or service surface.
- Preserve token refresh and SSL fallback behavior.
- Use a safe path-parameter builder or URL quoting for serial numbers and other identifiers.
- Add mocked HTTP coverage for success, authentication failure, malformed/optional payloads, and non-JSON responses where applicable.