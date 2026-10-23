# Keeping this change across `hermes update`

The change lives in two places, and they survive updates differently:

| Copy | Where | Survives an update? |
|---|---|---|
| Canonical | `martin-torres/hermes-agent` `main` (commit `7dd6c030`, PR #1) | Yes — it is a normal commit; nothing to do |
| Running install | `~/.hermes/hermes-agent` (working-tree edit, not committed) | Usually, via autostash — but see the failure mode below |

## What `hermes update` actually does to it

`hermes update` on a git install pulls with **autostash**: local working-tree changes are stashed,
upstream commits are pulled, then the changes are restored on top ("Local changes were restored
on top of the updated codebase").

That restore is best-effort. If upstream edited the *same lines* — `cli_tui_mixin.py` and
`cli_model_switch_mixin.py` are both actively developed — the restore conflicts, and the change is
left in a stash instead of the working tree. That is exactly what happened four times before:
`git stash list` in the install still holds `hermes-update-autostash-20260704…20260929`.

A local **commit** in the install does not solve it either: the updater treats local commits on
the target branch as *diverged* and parks them in a rescue ref
(`refs/hermes-update-backups/diverged-<branch>-<ts>-<sha>`) before moving HEAD. Backed up, not
re-applied.

## The procedure after every update

One command, idempotent — it says "already applied" when nothing is needed:

```bash
~/.hermes/patches/reapply-model-picker-specs.sh                 # the install
~/.hermes/patches/reapply-model-picker-specs.sh /some/checkout  # any other checkout
```

Exit codes: `0` applied or already present, `1` the patch no longer applies (upstream moved —
the script prints the rebase recipe), `2` not a Hermes checkout, `3` applied but verification
failed.

Verify by hand if you prefer:

```bash
cd ~/.hermes/hermes-agent
grep -c pricing_cache_only hermes_cli/cli_model_switch_mixin.py   # 1 = present
ls hermes_cli/model_picker_specs.py                               # exists = present
```

Then start a new session (`hermes`) and open `/model`. A completed update restarts the gateway
and dashboard itself, so Telegram picks the change up at the same time — no separate step, and
never restart those by hand.

## When the patch stops applying

That means upstream rewrote one of the five files. Rebase at the source, then come back:

```bash
cd ~/Projects/hermes-agent
git fetch origin
git checkout -B feat/model-picker-price-specs origin/main
git apply --3way ~/.hermes/patches/model-picker-price-specs.patch   # resolve conflicts
# re-run the suites, then commit + push and merge to main
~/.hermes/patches/reapply-model-picker-specs.sh                     # now applies to the install
```

## The five files

```
hermes_cli/model_picker_specs.py            (new)  suffix builder: price, ctx, caps, FREE
hermes_cli/cli_tui_mixin.py                        model-stage rows + hint legend
hermes_cli/cli_model_switch_mixin.py               pricing=True, pricing_cache_only=True
locales/en.yaml                                    picker_pricing_legend
tests/hermes_cli/test_model_picker_specs.py (new)  12 tests
```

## Permanent alternatives to re-applying

- **Track the fork instead of upstream.** Point the install's `origin` at
  `martin-torres/hermes-agent` (whose `main` already contains the change) and keep that main
  synced by merging upstream in. Updates then carry the change with them and nothing needs
  re-applying. Cost: upstream updates arrive only after you merge them into the fork.
- **Land it upstream.** Open a PR to `NousResearch/hermes-agent`; once merged, the change is in
  every future update and this document becomes obsolete.
