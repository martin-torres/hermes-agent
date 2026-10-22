#!/usr/bin/env python3
"""Apply the model-picker pricing/spec edits to the fork clone, deterministically.

Each edit asserts its anchor appears exactly once, so a silent mis-apply is impossible.
"""
import pathlib
import sys

REPO = pathlib.Path.home() / "Projects" / "hermes-agent"


def edit(rel, old, new, *, count=1):
    path = REPO / rel
    text = path.read_text(encoding="utf-8")
    found = text.count(old)
    if found != count:
        sys.exit(f"ANCHOR FAIL {rel}: found {found} occurrences (expected {count})")
    path.write_text(text.replace(old, new), encoding="utf-8")
    print(f"edited {rel} (+{len(new.splitlines()) - len(old.splitlines())} lines)")


# ── 1. the spec module: split out a public suffix accessor ────────────────────────────────
edit(
    "hermes_cli/model_picker_specs.py",
    '''def decorate_model_label(
    model_id: str, provider_row: Optional[dict], *, config: Optional[dict] = None
) -> str:
    """``model_id`` with its price/context/capability suffix — what the picker row renders.

    The RAW id stays the first token so a row can never be mistaken for a different model, and
    resolution/commit still works off ``provider_row["models"]``, never off this label.
    """
    row = provider_row or {}
    slug = str(row.get("slug") or "")
    key = (slug, model_id)
    cached = _spec_cache.get(key)
    if cached is None:
        try:
            cached = _build_suffix(model_id, row, config=config)
        except Exception:
            cached = ""  # a metadata failure must never cost the user the row
        _spec_cache[key] = cached
    return f"{model_id}{cached}"''',
    '''def model_spec_suffix(
    model_id: str, provider_row: Optional[dict], *, config: Optional[dict] = None
) -> str:
    """The suffix alone (``" · $3/$15 · 1M ctx · reasoning"``, or "" when nothing is known).

    Memoized per (provider slug, model id) — the picker re-renders on every filter keystroke.
    Callers that build the row themselves use this: the CLI picker appends it AFTER the plan
    tags from ``model_picker_usage.annotate_window_plan_rows``, which resolve RAW model ids and
    therefore have to run first.
    """
    row = provider_row or {}
    key = (str(row.get("slug") or ""), model_id)
    cached = _spec_cache.get(key)
    if cached is None:
        try:
            cached = _build_suffix(model_id, row, config=config)
        except Exception:
            cached = ""  # a metadata failure must never cost the user the row
        _spec_cache[key] = cached
    return cached


def decorate_model_label(
    model_id: str, provider_row: Optional[dict] = None, *, config: Optional[dict] = None
) -> str:
    """``model_id`` with its price/context/capability suffix — a full row label.

    The RAW id stays the first token so a row can never be mistaken for a different model, and
    resolution/commit still works off ``provider_row["models"]``, never off this label.
    """
    return f"{model_id}{model_spec_suffix(model_id, provider_row, config=config)}"''',
)

# ── 2. the picker must actually ask inventory for pricing ─────────────────────────────────
edit(
    "hermes_cli/cli_model_switch_mixin.py",
    "            capabilities=True,  # the effort step hides itself on reasoning-free routes\n",
    "            capabilities=True,  # the effort step hides itself on reasoning-free routes\n"
    "            # Row suffixes carry price + context + capabilities, with FREE where it applies.\n"
    "            # cache-only pricing keeps the picker non-blocking: a cold endpoint is warmed by\n"
    "            # the background worker and its prices appear on the next open, not by stalling.\n"
    "            pricing=True,\n"
    "            pricing_cache_only=True,\n",
)

# ── 3. the model stage: decorate rows, keeping upstream's plan tags intact ────────────────
edit(
    "hermes_cli/cli_tui_mixin.py",
    '''            model_labels = [e for (_i, e) in filtered_pairs]
            from hermes_cli.model_picker_usage import annotate_window_plan_rows
            row_labels, limit_line = annotate_window_plan_rows(provider_data, model_labels)
            choices = row_labels + [t("cli.shared.back"), t("cli.shared.cancel")]''',
    '''            model_labels = [e for (_i, e) in filtered_pairs]
            from hermes_cli.model_picker_specs import model_spec_suffix, rows_have_pricing
            from hermes_cli.model_picker_usage import annotate_window_plan_rows
            # Plan tags resolve the RAW ids, so annotate first and append this row's
            # price/context/capability suffix by position afterwards (both keep order + length).
            # ``_filtered_pairs`` itself stays raw, so filtering and the commit are unaffected.
            row_labels, limit_line = annotate_window_plan_rows(provider_data, model_labels)
            if len(row_labels) == len(filtered_pairs):
                row_labels = [
                    f"{label}{model_spec_suffix(_candidate, provider_data)}"
                    for label, (_i, _candidate) in zip(row_labels, filtered_pairs)
                ]
            choices = row_labels + [t("cli.shared.back"), t("cli.shared.cancel")]''',
)

edit(
    "hermes_cli/cli_tui_mixin.py",
    '''            else:
                hint = t("cli.tui.picker_empty")
            # Window plan past an allowance: say once what happens next (pay as you go or wait), above the hint.''',
    '''            else:
                hint = t("cli.tui.picker_empty")
            if rows_have_pricing(row_labels):
                legend = t("cli.tui.picker_pricing_legend")
                hint = f"{hint}{' · ' if hint else ''}{legend}"
            # Window plan past an allowance: say once what happens next (pay as you go or wait), above the hint.''',
)

# ── 4. the legend string ──────────────────────────────────────────────────────────────────
edit(
    "locales/en.yaml",
    '    picker_select_hint: "Select a model ({count} available) — type to filter"\n',
    '    picker_select_hint: "Select a model ({count} available) — type to filter"\n'
    '    picker_pricing_legend: "price = $ per 1M tokens (in/out), FREE = no charge"\n',
)

print("\nall edits applied")
