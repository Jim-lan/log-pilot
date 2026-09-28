# Controlled model comparison harness

Design checkpoint: 2026-09-28. Extends Q04–Q06; does not mark the live Q07
experiment or release thresholds complete.

## Model control

An opt-in server catalog (`LOGPILOT_MODEL_PROFILES_PATH`) defines named Ollama
profiles with independent generation and validation settings. HTTP clients select
only an allowed profile ID, never a provider URL or credentials. Profiles are
validated, frozen per request and fingerprinted. A pinned expected fingerprint
fails closed if configuration changes. Selection requires stateless query mode;
ordinary chat retains its existing configuration. The registry is never mutated.

Each role controls model tag, temperature, top-p, seed, output token cap and
optional reasoning effort. Requested settings, returned model, available usage,
profile fingerprint and template hashes enter existing request provenance.
Model tags/provider-returned names are not verified weight digests. Context size
is controlled at the Ollama server, not through this chat-completions profile;
record server version/context settings in the experiment's data revision notes.
The existing input-token estimate and request/provider budgets still apply.
Unsupported models/settings fail visibly rather than silently changing profiles.

Runtime context/answer validation uses the validation role. Answer validation
receives SQL or retrieved/web evidence and must check support, not just fluency.
Unknown citation checks and restricted SQL remain deterministic. Runtime judge
approval is not the offline correctness score and never promotes a model alone.

## Comparisons

`POST /evaluate/compare` selects 2–4 unique profiles, 1–5 repetitions, an optional
case limit and a required data revision label. Both services load the same
catalog. The orchestrator must declare the same revision through
`LOGPILOT_EVALUATION_DATA_REVISION`. This label is an operator assertion: use a
frozen disposable fixture environment with ingestion stopped; the harness does
not snapshot or authenticate live SQL/vector data.

The validator settings must be identical across candidates. All candidate/run
rosters persist atomically before any provider request. Only one batch/comparison job is admitted per evaluator; overlapping submissions return 409. Runs execute sequentially,
rotating candidate order between repetitions. Each candidate/repetition has its
own ephemeral conversation context. Cases, scorer identity, data revision, profile
settings/fingerprints and execution order are recorded. A changed profile or data
revision is an error; interrupted runs follow Q06 and are never silently replayed.
At most 5,000 case executions are admitted per comparison.

`GET /evaluate/comparisons/{id}` reports persisted per-run and candidate totals,
pass/error/unscored rates, latency p50/p95, citation dimensions, runtime validator
acceptance and token availability separately. Failures stay in denominators;
missing token/latency values remain unavailable. A recommendation requires a
complete, scored comparison with matching observed profile/data/template/scorer
provenance and caller-supplied acceptance gates. Otherwise the report explains
why no recommendation is available. The report never switches the default model. Comparison cases default to requiring a validated outcome; expected abstention must be specified explicitly with `expected_outcome`. Correct SQL rows paired with an unexpected abstention do not count as task success. Each report records its reporter code fingerprint.

## Use

Copy `config/model_profiles.example.json` to a server-owned configuration file
and set `LOGPILOT_MODEL_PROFILES_PATH` to that file in both services. Set the
orchestrator's `LOGPILOT_EVALUATION_DATA_REVISION` to your frozen fixture label.
Use an endpoint reachable from those services; host Ollama and Docker have
separate hostnames. Profile activation does not start Ollama or download models.

```sh
python3 scripts/compare_models.py --api-url http://localhost:8002 \
  --profiles qwen-4b qwen-9b gemma-e4b --repeats 3 \
  --data-revision synthetic-fixture-v1 --output /tmp/logpilot-comparison.json
```

The command prints the persisted comparison ID and writes the initial status.
Use `--comparison-id ID` to fetch a current report without starting new work.
Optional gates are explicit experiment choices, not invented enterprise release
criteria. The example profiles share one validator to avoid changing the judge
while testing the generator. No cloud credentials or external search are needed.

Storage remains additive JSON in existing v1 run records; no destructive schema
migration. Rollback removes the new endpoints/profile selection together and
retains recorded runs. Existing history, ingestion and SQL protections remain.


The Ollama adapter forwards the supported chat-completions settings documented
in [Ollama compatibility](https://docs.ollama.com/api/openai-compatibility).
Reasoning effort support is model-dependent; leaving it null preserves the
server/model default and records that choice. Inspect `/api/show` before choosing
a non-default effort. Current example profiles are candidates, not quality
rankings or verified installations.
