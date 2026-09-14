# Rendering and outbound content safeguards

Step 1.3 is an incremental protection layer, not enterprise certification.

## Decision and trust boundaries

User messages, SQL, query results, retrieved context, alert fields and model status are plain text. Model answers and stored AI replies support Markdown but pass through a restricted DOMPurify allowlist before insertion. Links retain safe URL protocols; images, scripts, SVG, frames, forms, inline events and inline styles are excluded. Markdown tables, lists, code and expandable references remain usable. Alert dismissal uses an event listener and an encoded identifier rather than generated JavaScript. API error messages render as escaped text, including query deadlines.

The browser ships Marked 18.0.13 and DOMPurify 3.4.15 locally under `services/frontend/src/vendor`, with upstream licenses. Exact npm dependencies and integrity metadata live in `tests/frontend/package-lock.json`. To update, change pinned test dependencies, install them, copy Marked's `lib/marked.umd.js`, DOMPurify's `dist/purify.min.js` and both licenses into vendor, then rerun browser contracts. Google Fonts remain external presentation requests; rendering libraries no longer depend on a CDN.

`shared/privacy.py` redacts supported email/IP/card/SSN patterns, private-key blocks, URL credentials, bearer tokens and common credential assignments. The shared LLM completion adapter applies it to prompt content for both registry and legacy providers, including local inference. Search applies it to query content even when explicitly enabled. Provider authentication configuration is unchanged. Nested PII masking handles dictionaries within lists without mutating the input.

All application Compose host port mappings bind to IPv4 loopback. This preserves access from the same Mac while removing default LAN exposure. It is not authentication; local processes still have access. Running containers need recreation before this configuration takes effect.

## Experiment and learning

Synthetic attack strings previously became browser elements or executable handlers. Four browser regression tests now pass while preserving Markdown/code and showing literal evidence. Backend tests prove supported secrets are absent from SDK request bodies and search queries. The learning point is to enforce policy at the final sink: the DOM insertion and outbound adapter, rather than relying on upstream callers to remember it.

## Limits and rollout

Pattern matching can miss unknown/encoded secrets and can remove useful IP evidence. It is not comprehensive DLP or a defense against prompt injection. Raw storage, history, debug output, embedding traffic, dependency telemetry and other network clients are not covered by this policy. Host allowlists, retention controls, authentication/authorization and an approved cloud-data policy remain future work. No live AI quality or whole-stack deployment test is claimed.

Deploy only after isolated tests pass, then smoke-test a disposable deployment before applying to valuable data. No schema migration is involved. Do not roll back to unsafe HTML rendering to restore images or styling; repair the allowlist/CSS while retaining sanitization. Broader LAN use needs a separate authentication and transport design.
