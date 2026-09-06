# Repository guidance for AI agents

## KEBA REST API reference

Before implementing or changing an API endpoint, consult the generated
reference under `./docs/keba-rest-api/`:

- `README.md` explains the synchronized artifacts and refresh commands.
- `integration_mapping.md` maps API payloads and operations to the Home
  Assistant integration.
- `endpoint_index.md` lists every available API operation.
- `openapi_pretty.json` contains the readable contract details.
- `openapi_orig.json` is the local source snapshot and offline fallback.

Use the exact operation and schema from the OpenAPI files instead of inferring
request fields, response envelopes, status codes, or units from an endpoint
name. Prioritize the v2 wallbox, session, charging-action, and meter
operations when they satisfy the feature request.

## Refreshing the reference

The live API URL is configured through `KEBA_OPENAPI_URL` in the ignored
`./docs/keba-rest-api/.env` file or through the environment. Do not commit the
`.env` file, credentials, tokens, or live wallbox payloads.

Refresh from the live API with:

```text
python3 docs/keba-rest-api/sync_openapi.py
```

Use the committed snapshot when the live API is unavailable:

```text
python3 docs/keba-rest-api/sync_openapi.py --offline
```

## Integration conventions

- Extend the existing client in `custom_components/integration_keba_rest_api/api.py`.
- Reuse `_api_wrapper` for authentication, timeout, communication errors, and SSL fallback.
- Preserve the coordinator's `wallboxes` envelope and per-wallbox detail flow.
- Preserve Home Assistant device targeting and coordinator refresh behavior for actions.
- Verify units and scaling against the OpenAPI schema before adding sensors.
- Handle non-JSON, CSV, binary, and 204 responses explicitly; do not assume every successful response is JSON.