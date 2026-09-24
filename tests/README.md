# Supported verification entry points

Run `python -B scripts/run_isolated_tests.py` from a prepared `.venv-test`, or use standalone `compose.test.yml`. Browser contracts run through `npm test --prefix tests/frontend`. See [test setup and evidence](../docs/testing_baseline.md).

Do not run blanket test discovery on this directory against application data. Top-level historical scripts can initialize models/databases, write data, delete alerts or use obsolete mocks. Their disposition and maintained replacements are listed in the [feature coverage map](../docs/feature_contract_coverage.md). They are not part of the CI regression allowlist.

Integration scripts under `tests/integration` are intended for their documented disposable Docker profiles. Live-model quality is a separate measured experiment, not a unit-test side effect.
