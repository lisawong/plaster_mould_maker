# Plaster mould maker

## Purpose

Build a repeatable STL → plaster mould → printable plaster-casting-form workflow, operated through a Python package (`mouldflow`) and one workflow skill (`stl-to-plaster-mould`). The deliverables are STL files for printing the forms used to cast plaster. Physical casting and finishing remain human operations.

Release 1 supports two-part plaster moulds from a single planar split, with deterministic checks, resumable jobs and hash-bound human review gates (input → plaster → forms → export). Release 2 targets more complex moulds. Printed casting forms use 3 mm walls with 20 mm outward lips, printed tongue-and-groove seams locked by external bulldog-style clips, walls 30 mm above the plaster block and a debossed fill line. The default finishing allowance is 0.1 mm per job. The finished skill will be evaluated on Sonnet 5 and Haiku 4.5.

The accepted teapot demo is prototype evidence, not proof of general applicability. Its casting forms remain awaiting human review. See [PRD.md](PRD.md) for requirements and [PLAN.md](PLAN.md) for the staged build (next: Stage 0).

## Structure

- `PRD.md` — approved requirements (2026-09-24).
- `PLAN.md` — approved staged, test-first implementation plan.
- `HANDOFF.md` — original assignment, preserved demo decisions and priorities.
- `TECHNICAL-REFERENCE.md` — prototype modules, geometry semantics and known limitations.
- `EVALUATION-PLAN.md` — geometry, workflow and operator acceptance criteria.
- `SCRATCHPAD.md` — idea atoms and dated decisions.
- `SESSION_LOG.md` — session work and outstanding tasks.
- `tools/groove_coupon.py` — generator for the groove-clearance test print (`python -m tools.groove_coupon`).
- `tests/` — tests for project code (currently the coupon).
- `prints/groove-coupon/` — test-print STLs: groove block (5 clearances) and tongue.
- `snapshot-manifest.json`, `handoff-verification.json` — snapshot hashes and predecessor verification.
- `prototype-snapshot.zip` *(git-ignored)* — prototype source, tests and evidence.
- `baseline/` *(git-ignored)* — hash-verified extraction of the snapshot with its own venv (`baseline/work/.venv`); read-only reference. Run its tests with `cd baseline && PYTHONPATH=work MPLCONFIGDIR=work/mpl-cache work/.venv/bin/python -m unittest discover -s work/tests`.

Until Stage 0 creates a project venv, run coupon tests with `baseline/work/.venv/bin/python -m unittest tests.test_groove_coupon`.

The original workspace at `/Users/lisawong/Documents/Codex/2026-09-18/i` remains authoritative for the current demo.
