# Supported verification entry points

Run `python -B scripts/run_isolated_tests.py` from a prepared `.venv-test`, or use standalone `compose.test.yml`. Browser contracts run through `npm test --prefix tests/frontend`. See [test setup and evidence](../docs/testing_baseline.md).

Do not run blanket test discovery on this directory against application data. Top-level historical scripts can initialize models/databases, write data, delete alerts or use obsolete mocks. Their disposition and maintained replacements are listed in the [feature coverage map](../docs/feature_contract_coverage.md). They are not part of the CI regression allowlist.

Integration scripts under `tests/integration` are intended for their documented disposable Docker profiles. Live-model quality is a separate measured experiment, not a unit-test side effect.


Quality fixtures: `isolated/quality_cases_v1.json` is the original development SQL corpus; `isolated/quality_holdout_v2.json` is a separately versioned, published held-out regression partition. SQL expectations run against disposable rows with scripted generation; source/abstention cases validate the scorer and negative controls. Neither is a live-model quality result. Do not run the holdout against ordinary application data: its counts, fact IDs and sources require the documented synthetic fixture setup.
