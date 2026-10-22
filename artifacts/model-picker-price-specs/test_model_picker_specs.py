"""``/model`` picker row specs: price, context window, capabilities, and the FREE badge.

The picker rendered bare model ids, so nothing on screen said what a model costs and free
models (``beam-free``, ``ring-2.6-1t-free``, ``big-pickle``) were indistinguishable from paid
ones. ``hermes_cli.model_picker_specs`` builds the row suffix from the provider's own pricing
feed when it publishes one, and from models.dev otherwise — which is the only source covering
opencode-go/opencode-zen, whose ``/v1/models`` endpoints publish no prices at all.

These tests also pin the property that makes the decoration safe: the row label must still
START with the raw model id, and the picker must keep resolving/committing on raw ids.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import hermes_cli.model_picker_specs as specs


def _info(**over):
    """models.dev ModelInfo stand-in with the fields the suffix builder reads."""
    base = dict(
        cost_input=0.0, cost_output=0.0, context_window=200_000, max_output=64_000,
        reasoning=True, status="")
    base.update(over)
    info = SimpleNamespace(**base)
    info.supports_vision = lambda: over.get("vision", False)
    info.supports_pdf = lambda: over.get("pdf", False)
    info.supports_audio_input = lambda: over.get("audio", False)
    return info


def _row(**over):
    row = {"slug": "opencode-zen", "models": [], "capabilities": {}, "pricing": {}}
    row.update(over)
    return row


def setup_function(_func=None):
    specs.clear_spec_cache()


def test_paid_model_shows_price_context_and_capabilities():
    """A paid model with catalog metadata renders price, context, output and capability flags."""
    with patch.object(specs, "_lookup_models_dev",
                      lambda slug, mid, cfg: _info(cost_input=3.0, cost_output=15.0,
                                                   context_window=1_000_000, max_output=64_000,
                                                   vision=True)):
        label = specs.decorate_model_label("claude-sonnet-4-5", _row(slug="opencode-zen"))

    assert label.startswith("claude-sonnet-4-5 ")
    assert "$3/$15" in label
    assert "1M ctx" in label
    assert "64K out" in label
    assert "reasoning" in label and "vision" in label
    assert "FREE" not in label


def test_free_model_is_labeled_free():
    """A zero-cost catalog entry is the free tier — this is the label that was missing."""
    with patch.object(specs, "_lookup_models_dev",
                      lambda slug, mid, cfg: _info(cost_input=0.0, cost_output=0.0,
                                                   context_window=1_048_576, max_output=128_000)):
        label = specs.decorate_model_label("beam-free", _row(slug="opencode-go"))

    assert "FREE" in label, "a zero-cost model must be labeled FREE"
    assert "$" not in label, "no price pair on a free row"
    assert "1M ctx" in label


def test_free_suffix_labels_even_without_metadata():
    """The provider's own naming (``-free`` / ``:free``) is enough to label a row FREE."""
    with patch.object(specs, "_lookup_models_dev", lambda slug, mid, cfg: None):
        go_label = specs.decorate_model_label("ring-2.6-1t-free", _row(slug="opencode-zen"))
        or_label = specs.decorate_model_label("z-ai/glm-5.2:free", _row(slug="openrouter"))
        paid_label = specs.decorate_model_label("z-ai/glm-5.2", _row(slug="openrouter"))

    assert "FREE" in go_label and "FREE" in or_label
    assert paid_label == "z-ai/glm-5.2", "no metadata and no free naming: no fabricated suffix"


def test_provider_pricing_feed_wins_over_models_dev():
    """Live provider pricing is what the account is billed — it beats catalog cost data."""
    row = _row(slug="openrouter", pricing={"z-ai/glm-5.2": {"input": "$0.03", "output": "$7.00",
                                                            "cache": None, "free": False}})
    with patch.object(specs, "_lookup_models_dev",
                      lambda slug, mid, cfg: _info(cost_input=9.0, cost_output=9.0)):
        label = specs.decorate_model_label("z-ai/glm-5.2", row)

    assert "$0.03/$7.00" in label and "9" not in label.split("ctx")[0]


def test_provider_pricing_free_flag_labels_free():
    row = _row(slug="nous", pricing={"mystery-model": {"input": "free", "output": "free",
                                                       "cache": None, "free": True}})
    with patch.object(specs, "_lookup_models_dev", lambda slug, mid, cfg: None):
        label = specs.decorate_model_label("mystery-model", row)

    assert "FREE" in label


def test_deprecated_status_is_surfaced():
    with patch.object(specs, "_lookup_models_dev",
                      lambda slug, mid, cfg: _info(status="deprecated")):
        label = specs.decorate_model_label("ring-2.6-1t-free", _row(slug="opencode-zen"))

    assert "deprecated" in label


def test_unknown_metadata_renders_bare_id_and_spec_errors_never_raise():
    """No metadata → bare id; a metadata explosion must cost a suffix, never the row."""
    with patch.object(specs, "_lookup_models_dev", lambda slug, mid, cfg: None):
        assert specs.decorate_model_label("some-model", _row()) == "some-model"

    def _boom(*_a, **_k):
        raise RuntimeError("catalog exploded")

    with patch.object(specs, "_lookup_models_dev", _boom):
        assert specs.decorate_model_label("some-model", _row()) == "some-model"


def test_capability_map_from_inventory_is_honoured():
    """The inventory's own capability map (the same one that gates the effort step) wins."""
    row = _row(capabilities={"glm-5.2": {"fast": False, "reasoning": False}})
    with patch.object(specs, "_lookup_models_dev",
                      lambda slug, mid, cfg: _info(reasoning=True, cost_input=0.2, cost_output=1.2)):
        label = specs.decorate_model_label("glm-5.2", row)

    assert "reasoning" not in label, "inventory says no reasoning control; do not claim it"


def test_legend_gate():
    assert specs.rows_have_pricing(["beam-free · FREE · 1M ctx", "x · 1M ctx"]) is True
    assert specs.rows_have_pricing(["a · $3/$15", "b"]) is True
    assert specs.rows_have_pricing(["a", "b"]) is False


def test_suffixes_are_memoized_per_provider_and_model():
    calls = []

    def _count(slug, mid, cfg):
        calls.append((slug, mid))
        return _info(cost_input=1.0, cost_output=2.0)

    with patch.object(specs, "_lookup_models_dev", _count):
        row = _row(slug="opencode-zen")
        specs.decorate_model_label("m", row)
        specs.decorate_model_label("m", row)
        specs.decorate_model_label("m", _row(slug="other"))

    assert len(calls) == 2, "same provider+model must not re-resolve metadata per keystroke"


def test_show_model_picker_requests_pricing_for_the_rows():
    """``_show_model_picker`` must ask inventory for pricing or no row can be priced/labeled."""
    from hermes_cli.cli_model_switch_mixin import _show_model_picker

    captured: dict = {}

    def _fake_build(_ctx, **kwargs):
        captured.update(kwargs)
        return {"providers": [{"slug": "opencode-go", "models": ["beam-free"]}]}

    cli = SimpleNamespace(model="deepseek-flash", provider="opencode-go",
                          _open_model_picker=MagicMock())
    ctx = SimpleNamespace(user_providers={}, custom_providers=[])
    with patch("hermes_cli.inventory.build_models_payload", side_effect=_fake_build):
        _show_model_picker(cli, ctx, force_refresh=False)

    assert captured.get("pricing") is True
    assert captured.get("pricing_cache_only") is True, (
        "the picker must not block the REPL on a cold endpoint's pricing fetch")


def test_picker_rows_still_resolve_on_raw_ids_after_decoration():
    """Filtering stays raw-id based, so a decorated label can never change the committed model."""
    from hermes_cli.cli_model_switch_mixin import CLIModelSwitchMixin

    raw = ["beam-free", "claude-sonnet-4-5", "glm-5.2"]
    with patch.object(specs, "_lookup_models_dev",
                      lambda slug, mid, cfg: _info(cost_input=0.0, cost_output=0.0)):
        labels = [specs.decorate_model_label(m, _row()) for m in raw]

    filtered = CLIModelSwitchMixin._filter_model_picker_entries(raw, "claude")
    assert [e for (_i, e) in filtered] == ["claude-sonnet-4-5"]
    assert labels[1].startswith("claude-sonnet-4-5"), "label keeps the raw id as its first token"
