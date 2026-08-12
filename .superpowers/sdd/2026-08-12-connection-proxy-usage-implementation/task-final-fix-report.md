# Final Proxy Usage Review Fixes

## Changes

- Tagged the provider detail chat playground request with
  `X-9Router-Purpose: test-chat`.
- Routed connection model discovery through the connection's `upstream`
  proxy purpose and converted all remaining provider model fetch clients to
  `create_upstream_client`.
- Routed connection model testing through the `testModel` purpose and
  `create_upstream_client`.
- Added proxy usage controls to OAuth connection editing and persist the
  selected configuration on save.
- Routed create-time credential validation through the pending connection's
  `testConnection` proxy purpose. The standalone validate endpoint remains
  direct because its request schema has no connection or proxy pool.
- Avoided proxy-pool database lookups when the resolved usage mode does not
  use a proxy.

## Regression Coverage

- Added a test proving `/providers/{connection_id}/test-models` resolves
  `testModel` and creates its client with the resolved proxy.

## Verification

- `../.venv-test/bin/pytest tests/test_outbound_proxy.py
  tests/test_connection_proxy_usage_api.py tests/test_proxy_pool_usage.py
  tests/test_proxy_required_fallback.py -q` — 22 passed.
- `npm run build` in `frontend/` — passed.
