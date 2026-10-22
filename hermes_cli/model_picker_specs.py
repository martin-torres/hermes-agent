"""Per-model spec suffixes for the ``/model`` picker rows.

The picker listed bare model ids, which say nothing about price, context or capabilities —
and the one fact a user needs most, "this one is free", was invisible on every row. This
module builds the compact suffix appended to each model row::

    claude-sonnet-4-5 · $3/$15 · 1.0M ctx · 64K out · reasoning, vision
    beam-free · FREE · 1.0M ctx · 128K out · reasoning
    big-pickle · FREE · 200K ctx · 64K out · reasoning, tools

Two metadata sources, in priority order:

1. **The provider's own live pricing**, attached by ``inventory._apply_pricing`` as
   ``row["pricing"][model]`` for providers whose catalog publishes prices (OpenRouter, Nous,
   Vercel AI Gateway, Novita, Fireworks, DeepInfra, Kilo).
2. **models.dev** — cost per Mtok, context window, max output, capabilities. This is the ONLY
   source covering ``opencode-go`` / ``opencode-zen``: their ``/v1/models`` endpoints publish no
   prices at all (verified — ``get_pricing_for_provider("opencode-go")`` returns 0 entries), so
   without models.dev every opencode row renders with no price and free models (``beam-free``,
   ``ring-2.6-1t-free``, ``big-pickle``, …) never get labeled.

Missing metadata renders as NO suffix, never a guess: a wrong price is worse than no price.
Suffixes are memoized per (provider slug, model id) because the picker re-renders on every
filter keystroke.
"""

from __future__ import annotations

from typing import Any, Optional

# Label vocabulary, kept in one place so translating the row chrome is a one-file change.
FREE_LABEL = "FREE"
CTX_SUFFIX = "ctx"
OUT_SUFFIX = "out"
REASONING_LABEL = "reasoning"
VISION_LABEL = "vision"
PDF_LABEL = "PDF"
AUDIO_LABEL = "audio"
SEPARATOR = " · "

# models.dev ids differ from Hermes provider slugs; the opencode family is served from two
# models.dev providers, and a model present in one is often only priced in the other
# (deepseek-v4-flash resolves under "opencode" but not under "opencode-go").
_MODELS_DEV_CANDIDATES: dict[str, tuple[str, ...]] = {
    "opencode-go": ("opencode-go", "opencode"),
    "opencode-zen": ("opencode-zen", "opencode"),
    "opencode": ("opencode",),
}

# (provider slug, model id) -> rendered suffix. Populated on first render of a row.
_spec_cache: dict[tuple[str, str], str] = {}


def clear_spec_cache() -> None:
    """Drop memoized suffixes (tests, and after a catalog refresh changes the metadata)."""
    _spec_cache.clear()


def _fmt_tokens(count: Any) -> str:
    """Token count as ``1.0M`` / ``128K`` / ``512``. Non-numeric input yields ""."""
    try:
        value = int(count)
    except (TypeError, ValueError):
        return ""
    if value <= 0:
        return ""
    if value >= 1_000_000:
        text = f"{value / 1_000_000:.1f}".rstrip("0").rstrip(".")
        return f"{text}M"
    if value >= 1_000:
        return f"{value // 1_000}K"
    return str(value)


def _fmt_mtok(per_million: Any) -> str:
    """models.dev USD-per-million-token float as ``$3`` / ``$0.14`` / ``$0.0341``."""
    try:
        value = float(per_million)
    except (TypeError, ValueError):
        return ""
    if value == 0:
        return "$0"
    text = f"{value:.2f}" if value >= 0.01 else f"{value:.6f}".rstrip("0").rstrip(".")
    text = text.rstrip("0").rstrip(".") if "." in text else text
    return f"${text}"


def _id_says_free(model_id: str) -> bool:
    """The provider's own free-tier naming: ``-free`` (opencode) / ``:free`` (OpenRouter)."""
    return model_id.endswith("-free") or model_id.endswith(":free")


def _lookup_models_dev(slug: str, model_id: str, config: Optional[dict]) -> Any:
    """models.dev ``ModelInfo`` for provider+model, trying the family's candidate ids."""
    try:
        from agent.models_dev import get_model_info
    except Exception:
        return None
    for candidate in _MODELS_DEV_CANDIDATES.get(slug.lower(), (slug,) if slug else ()):
        try:
            info = get_model_info(candidate, model_id, config=config)
        except Exception:
            info = None
        if info is not None:
            return info
    return None


def _capability_flags(info: Any, caps: dict) -> list[str]:
    """Noteworthy capabilities, in row order. ``tools``/``structured output`` are omitted — they
    hold for nearly every model and would push the price off the row."""
    flags: list[str] = []
    reasoning = caps.get("reasoning") if isinstance(caps, dict) else None
    if reasoning is None and info is not None:
        reasoning = info.reasoning
    if reasoning:
        flags.append(REASONING_LABEL)
    vision = caps.get("vision") if isinstance(caps, dict) else None
    if vision is None and info is not None:
        try:
            vision = info.supports_vision()
        except Exception:
            vision = None
    if vision:
        flags.append(VISION_LABEL)
    if info is not None:
        try:
            if info.supports_pdf():
                flags.append(PDF_LABEL)
            if info.supports_audio_input():
                flags.append(AUDIO_LABEL)
        except Exception:
            pass
    return flags


def _build_suffix(model_id: str, provider_row: dict, *, config: Optional[dict] = None) -> str:
    """Rendered suffix for one row, or "" when nothing is known about the model."""
    pricing = (provider_row.get("pricing") or {}).get(model_id) or {}
    caps = (provider_row.get("capabilities") or {}).get(model_id) or {}
    slug = str(provider_row.get("slug") or "")
    info = _lookup_models_dev(slug, model_id, config)

    free = bool(pricing.get("free")) or _id_says_free(model_id)
    price_in = price_out = ""
    if pricing.get("input") or pricing.get("output"):
        # Provider's own feed wins: it is what this account will actually be billed.
        price_in, price_out = str(pricing.get("input") or "?"), str(pricing.get("output") or "?")
    elif info is not None and (info.cost_input or info.cost_output):
        price_in, price_out = _fmt_mtok(info.cost_input), _fmt_mtok(info.cost_output)
    elif info is not None:
        # A catalog entry whose both directions cost nothing IS the free tier (verified across
        # opencode-go/zen: every zero-cost entry is a free SKU, including unsuffixed ones).
        free = True

    parts: list[str] = []
    if free:
        parts.append(FREE_LABEL)
    elif price_in or price_out:
        parts.append(f"{price_in or '?'}/{price_out or '?'}")

    if info is not None:
        if ctx := _fmt_tokens(info.context_window):
            parts.append(f"{ctx} {CTX_SUFFIX}")
        if out := _fmt_tokens(info.max_output):
            parts.append(f"{out} {OUT_SUFFIX}")
    if flags := _capability_flags(info, caps if isinstance(caps, dict) else {}):
        parts.append(", ".join(flags))
    if info is not None and info.status:
        parts.append(info.status)

    return SEPARATOR + SEPARATOR.join(parts) if parts else ""


def model_spec_suffix(
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
    return f"{model_id}{model_spec_suffix(model_id, provider_row, config=config)}"


def rows_have_pricing(labels: list[str]) -> bool:
    """True when any decorated row carries a price or the FREE badge — gates the hint legend."""
    return any(("$" in label) or (FREE_LABEL in label) for label in labels)
