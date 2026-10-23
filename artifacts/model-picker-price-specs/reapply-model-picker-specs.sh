#!/bin/sh
# Re-apply the /model picker price+spec change to a Hermes checkout.
#
#   ./reapply-model-picker-specs.sh                 # default: ~/.hermes/hermes-agent
#   ./reapply-model-picker-specs.sh /path/to/checkout
#
# Idempotent: says "already applied" and exits 0 when the change is present, so it is safe to
# run after every `hermes update` (which autostashes local changes and restores them on top —
# the restore is skipped or left as a stray stash when upstream touched the same lines, and
# that is exactly the case this script exists for).
set -u

TARGET="${1:-$HOME/.hermes/hermes-agent}"
PATCH="${PICKER_PATCH:-$HOME/.hermes/patches/model-picker-price-specs.patch}"

# The two installs differ only in which helper they import (the fork's copy uses
# model_spec_suffix for the plan-tag composition, the older install copy uses
# decorate_model_label), so detect on the MODULE name, which both share.
present() {
    [ -f "$TARGET/hermes_cli/model_picker_specs.py" ] &&
        grep -q "model_picker_specs" "$TARGET/hermes_cli/cli_tui_mixin.py" 2>/dev/null &&
        grep -q "pricing_cache_only" "$TARGET/hermes_cli/cli_model_switch_mixin.py" 2>/dev/null &&
        grep -q "picker_pricing_legend" "$TARGET/locales/en.yaml" 2>/dev/null
}

if [ ! -d "$TARGET/hermes_cli" ]; then
    echo "not a Hermes checkout: $TARGET" >&2
    exit 2
fi

if present; then
    echo "already applied — nothing to do ($TARGET)"
    exit 0
fi

echo "change missing — applying $(basename "$PATCH") to $TARGET"
cd "$TARGET" || exit 2

if git apply --check "$PATCH" 2>/dev/null; then
    git apply "$PATCH" || exit 4
elif git apply --check --3way "$PATCH" 2>/dev/null; then
    git apply --3way "$PATCH" || exit 4
    echo "applied as a 3-way merge — check 'git status' for conflicts"
else
    cat >&2 <<'EOF'
the patch no longer applies cleanly: upstream has edited these files.

Fix it at the source (your fork), then re-copy:
  cd ~/Projects/hermes-agent
  git fetch origin && git checkout -B feat/model-picker-price-specs origin/main
  git apply --3way ~/.hermes/patches/model-picker-price-specs.patch   # resolve, commit, push
  # then re-run this script against ~/.hermes/hermes-agent

The five files involved:
  hermes_cli/model_picker_specs.py            (new)
  hermes_cli/cli_tui_mixin.py                 (row labels + legend)
  hermes_cli/cli_model_switch_mixin.py        (pricing=True, pricing_cache_only=True)
  locales/en.yaml                             (picker_pricing_legend)
  tests/hermes_cli/test_model_picker_specs.py (new)
EOF
    exit 1
fi

if present; then
    echo "verified: the change is in place"
    exit 0
fi
echo "applied, but verification failed — inspect $TARGET" >&2
exit 3
