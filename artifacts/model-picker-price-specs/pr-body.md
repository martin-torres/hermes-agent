## Why

The `/model` picker listed bare model ids, so nothing on screen said what a model costs, and
free models were indistinguishable from paid ones.

This bites hardest on `opencode-go` and `opencode-zen`: their own `/v1/models` endpoints publish
**no prices at all** (verified — `get_pricing_for_provider("opencode-go")` returns 0 entries), so
every row for either provider rendered with no price, and the free SKUs (`beam-free`,
`ring-2.6-1t-free`, `big-pickle`) carried no label.

## What changed

Rows now carry a compact spec suffix, built from the provider's own pricing feed when it
publishes one and from models.dev otherwise:

```
claude-sonnet-4-5 · $3/$15 · 1M ctx · 64K out · reasoning, vision
beam-free · FREE · 1M ctx · 131K out · reasoning
big-pickle · FREE · 200K ctx · 32K out · reasoning
```

- `hermes_cli/model_picker_specs.py` (new) builds the suffix and memoizes it per
  `(provider slug, model id)` — the picker re-renders on every filter keystroke. The raw id
  stays the row's first token, and a metadata failure drops the suffix rather than the row.
- `_show_model_picker` requests `pricing=True` with `pricing_cache_only=True`, so a cold
  endpoint's prices arrive on a later open instead of stalling the REPL.
- The model stage decorates labels only: `_filtered_pairs` keeps the raw ids, so filtering and
  the commit resolve exactly as before. The suffix is appended *after*
  `model_picker_usage.annotate_window_plan_rows`, which resolves raw ids for its plan tags.
- The stage hint gains a one-line legend (`price = $ per 1M tokens (in/out), FREE = no charge`)
  only when a row actually carries one.

## Tests

- 12 new tests in `tests/hermes_cli/test_model_picker_specs.py` (paid, free-by-catalog,
  free-by-suffix, provider-feed precedence, deprecated marker, unknown metadata, capability-map
  override, memoization, legend gate, and the two properties that keep selection safe).
- 32 passed across the new file plus the existing picker suites
  (`test_show_model_picker_exhausted_pool`, `test_user_providers_model_switch`,
  `test_model_picker_expensive_confirm`) with an isolated `HERMES_HOME`.
- Render against the real catalogs: 44 of 45 `opencode-go` rows priced; 13 free models labeled
  on `opencode-zen`.

## Follow-ups (not in this PR)

- Instance-start prewarm + a freshness stamp, so this metadata is canonical and current on every
  new instance rather than cache-only.
- An alias for `deepseek-flash`, which has no models.dev entry and therefore renders with only
  its capability flags.
