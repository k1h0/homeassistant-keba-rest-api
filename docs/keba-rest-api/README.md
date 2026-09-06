# OpenAPI source

This directory is the Copilot-facing API reference for the integration.

The live contract is synchronized from `KEBA_OPENAPI_URL` in `.env` or the environment.

Generated files:
- `openapi_orig.json`: synchronized source snapshot
- `openapi_pretty.json`: readable equivalent of the snapshot
- `endpoint_index.md`: complete method/path/response inventory

The generated files must be refreshed with:
```text
python3 docs/keba-rest-api/sync_openapi.py
```

The synchronizer uses the existing snapshot only with `--offline`.
It writes files atomically so a failed download cannot replace a valid snapshot.

Current contract: OpenAPI `3.0.3`, API version `2.4.1`, `255` paths, `136` schemas.
