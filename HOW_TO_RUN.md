# Running and verifying LogPilot

Run commands from the repository root. This guide distinguishes isolated verification from the application demo, which uses persistent project data. See [current architecture](docs/architecture.md) and [deployment limitations](docs/security_deployment.md).

## Inspect without changing application data

```sh
pwd
git status --short --branch
git remote -v
docker version
docker compose version
docker compose ps
```

Docker Desktop must be running for daemon operations; registry login alone does not establish daemon availability. Confirm ports 3000, 8000, 8001, 8002 and 11434 are available before application startup. Model resource needs depend on the chosen model and workload; no fixed RAM or speed guarantee is established.

## Isolated regression checks

For an existing prepared test environment:

```sh
.venv-test/bin/python -B scripts/run_isolated_tests.py
```

For initial setup, use a separate virtual environment:

```sh
python3 -m venv .venv-test
.venv-test/bin/python -m pip install --no-cache-dir -r tests/isolated/requirements.txt
```

The stronger OS boundary is the standalone test Compose profile:

```sh
docker compose -f compose.test.yml build baseline
docker compose -f compose.test.yml run --rm --no-deps baseline
docker compose -f compose.test.yml run --rm --no-deps --entrypoint python baseline -B /workspace/tests/integration/ingestion_crash_smoke.py
```

Do not combine this file with the application Compose file. The test container has no application data mounts or network. Building/installing dependencies requires network. Local audit hooks guard accidents but are not a complete sandbox for native code.

Browser contracts use synthetic responses:

```sh
npm ci --prefix tests/frontend --ignore-scripts --no-audit --no-fund
npm test --prefix tests/frontend
```

On macOS the browser runner defaults to `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`; use `LOGPILOT_CHROME_PATH` for another installed compatible executable. CI uses Playwright Chromium. See [test guide](docs/testing_baseline.md) for environment details and historical results.

## Start the local demo intentionally

Review `docker-compose.yml` and `config/llm_config.yaml` first. Starting main Compose pulls the configured model, generates demo logs, copies a catalog and allows services to write under `data/`. Preserve existing data and choose a disposable checkout/data directory when experimenting with a fresh demo. Do not use reset, forced process kills, volume deletion or Docker prune as routine startup steps.

```sh
docker compose up --build -d
docker compose ps
docker compose logs --tail=100 pilot-orchestrator ingestion-worker llm-service
```

Open the frontend at `http://localhost:3000`. API health is `http://localhost:8000/health`; evaluation health is `http://localhost:8002/health`. Health responses and running containers are not full readiness checks. Inspect failures before sending queries. Current configuration names `gemma4:e4b`; verify that identifier is available in your chosen provider rather than assuming startup succeeds.

Ordinary chat persists shared default history. To try a request without reading or writing normal chat history:

```sh
curl -sS http://localhost:8000/query -H 'Content-Type: application/json' -d '{"query":"How many ERROR logs are present?","persist_history":false}'
```

Check SQL/rows, evidence and outcome rather than judging only fluent answer text. A valid SQL result may be empty; insufficient evidence may produce abstention. Search defaults off. Explicit `LOGPILOT_ALLOW_WEB_SEARCH=true` enables provider egress for rewritten questions; review [redaction limits](docs/rendering_and_privacy.md) before opting in.

To stop application services without deleting data:

```sh
docker compose stop
```

## Ingest and recover

Publish completed immutable UTF-8 `.log` or `.md` files (maximum 8 MiB) by writing a temporary filename, closing it, then atomically renaming it into `data/source/landing_zone`. Do not append to files after publication. Check processed/quarantine state; a visible file alone is not proof of durable indexing.

Protocol-2 log replay and journaled Markdown replay are explicit maintenance operations with the normal worker stopped, using the same dependencies/configuration/data paths. Follow [ingestion recovery](docs/ingestion_recovery.md) for the exact replay command, failure windows and ordering constraints. Markdown replay uses its recorded document version ID when the file was renamed/quarantined. Do not blindly replay legacy interrupted inputs or newly changed bytes.

## Evaluate and change configuration

The evaluation service uses its configured dataset. POST `/evaluate/batch` with `{}` (or a valid `limit`) starts a persisted background run; it does not mean the run has passed. Requests use stateless query mode. Read API `/metrics` and the persisted run records using the [evaluation contract](docs/evaluation_contract.md); unavailable or unscored values are not zero or success.

Model and request settings are documented in [technical reference](docs/technical_reference.md). Recreate affected containers when applying environment/binding changes. Do not change models, data schemas and deployment topology in one experiment; retain a comparable baseline and a recovery plan.
