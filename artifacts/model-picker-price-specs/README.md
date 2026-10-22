# /model picker price + spec artifacts

Scratch artifacts for the change shipped in this fork's `feat/model-picker-price-specs`
branch (PR #1). Not part of the product — delete this branch once it stops being useful.

- `model-picker-price-specs.patch` — the same change as a patch, taken from the local install
  before it was reverted there (useful for re-applying to another checkout).
- `apply_to_fork.py` — deterministic applier: edits the branch's five files, asserting each
  anchor appears exactly once, so a partial/mis-applied edit is impossible.
- `model_picker_specs.py`, `test_model_picker_specs.py` — the two new files, for dropping into
  an install that needs the feature before the branch is merged.
- `commit-message.txt`, `pr-body.md` — the commit message and PR description as authored.
