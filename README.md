# Plaster mould maker

## Purpose

Build a repeatable STL → plaster mould → printable plaster-casting-form workflow, operated through a Python package (`mouldflow`) and one workflow skill (`stl-to-plaster-mould`). The deliverables are STL files for printing the forms used to cast plaster. Physical casting and finishing remain human operations.

Release 1 supports two-part plaster moulds from a single planar split, with deterministic checks, resumable jobs and hash-bound human review gates (input → plaster → forms → export). Release 2 targets more complex moulds. Printed casting forms use 3 mm walls with 20 mm outward lips, printed tongue-and-groove seams locked by external bulldog-style clips, walls 30 mm above the plaster block and a debossed fill line. The default finishing allowance is 0.1 mm per job. The finished skill will be evaluated on Sonnet 5 and Haiku 4.5.

The accepted teapot demo is prototype evidence, not proof of general applicability. Its casting forms remain awaiting human review. See [PRD.md](PRD.md) for requirements and [PLAN.md](PLAN.md) for the staged build. Progress: Stages 0–2 merged (scaffold + CI; job folder, schemas and review gates; known-answer fixtures, depth-semantics audit, `release_check`); Stage 2.5 (visual inspection: `mouldflow view`, `/look`, `mould-inspector`) in progress.

## Quick start

```sh
uv sync        # Python 3.12 env from uv.lock
make test      # full suite (uv run pytest)
make coupon    # regenerate the groove test print
uv run mouldflow --help
uv run mouldflow job init path/to/job      # new job folder (settings, gates, artifact folders)
uv run mouldflow job status path/to/job    # reverify hashes; gates + next_action as JSON
uv run mouldflow job decide path/to/job input --revision REV --answer approve --note "..."
uv run mouldflow view a.stl=object b.stl=half_1 --out look/demo --explode y=25 --marks-from release.json
```

## Looking at geometry

`mouldflow view` writes `views.png`, `sections.png` and a rotatable `viewer.html` into `look/<name>/` (git-ignored). In Claude Code:
- `/look [what]` renders, reads the pictures and reports what it sees, then offers the rotatable viewer (the `look` server in `.claude/launch.json` serves `look/` on http://localhost:8765).
- The `mould-inspector` agent repeats render → look → adjust sections/explode/marks until a question is answered, and writes `look/<name>/FINDINGS.md`.
Pictures are inspection aids. Outcomes always come from the release checks.

## Structure

- `PRD.md` — approved requirements (2026-09-24).
- `PLAN.md` — approved staged, test-first implementation plan.
- `HANDOFF.md` — original assignment, preserved demo decisions and priorities.
- `TECHNICAL-REFERENCE.md` — prototype modules, geometry semantics and known limitations.
- `EVALUATION-PLAN.md` — geometry, workflow and operator acceptance criteria.
- `SCRATCHPAD.md` — idea atoms and dated decisions.
- `SESSION_LOG.md` — session work and outstanding tasks.
- `src/mouldflow/` — the package. Prototype modules ported verbatim in Stage 0; Stage 1 added:
  - `settings.py` — pydantic per-job settings (source, plaster, forms, printer sections) with PRD defaults.
  - `result.py` — versioned JSON result record (`mouldflow.result/1`), outcomes and unit-tagged metrics.
  - `parts.py` — generic parts, release directions and removal order (`two_part_planar` for Release 1).
  - `job.py` — job folder and the four hash-bound review gates (input → plaster → forms → export).
  - `cli.py` — `mouldflow job init|status|decide`; other arguments fall through to the prototype generator.
  Stage 2 added:
  - `release_check.py` — `assess_release`: two-sided penetration depth (mm) over the whole motion (samples plus Minkowski-swept intervals, erosion certificates), adaptive refinement and `strict_pass` / `conditional_finishing` / `inconclusive` / `fail` / `unsupported`.
  - `known_answers.py` — known-answer release fixtures for the EVALUATION-PLAN geometry rows.
  Stage 2.5 added:
  - `view.py` — `mouldflow view`: PNG contact sheet, cross-sections and self-contained three.js viewer, with release-catch marks.
- `.claude/skills/look/`, `.claude/agents/mould-inspector.md`, `.claude/launch.json` — visual-inspection skill, iterating inspector agent and the `look` preview server.
- `.agents/skills/look/`, `.codex/agents/mould-inspector.toml` — the same skill and agent for Codex (used as a review agent). Edit the Claude versions and copy them across; `tests/test_view.py` fails if the copies differ.
- `review-notes/` — local only (git-ignored). The dev agent and the separate review agent hand work to each other through files here (e.g. `REVIEW-HANDOFF.md`).
- `tests/` — pytest suite: 45 ported baseline tests, coupon tests, Stage 1 job/schema tests, Stage 2 known-answer release tests and Stage 2.5 view tests.
  - `tests/fixtures/teapot-v7/` — accepted V7 source, prepared object and plaster halves for the Stage 5 regression; see its `PROVENANCE.md`.
  - `tests/fixtures/historical/` — older three-part study used only by `test_scene_artifact` (historical, not V7 evidence).
- `tools/groove_coupon.py` — generator for the groove-clearance test print.
- `prints/groove-coupon/` — test-print STLs: groove block (5 clearances) and tongue.
- `pyproject.toml`, `uv.lock`, `Makefile` — packaging, pinned environment, commands.
- `.github/workflows/tests.yml` — CI: full suite on every push/PR (Ubuntu).
- `.github/pull_request_template.md` — PR checklist, including the docs that must be updated before each PR.
- `snapshot-manifest.json`, `handoff-verification.json` — snapshot hashes and predecessor verification.
- `prototype-snapshot.zip` *(git-ignored)* — prototype source, tests and evidence.
- `baseline/` *(git-ignored)* — hash-verified extraction of the snapshot with its own venv; read-only reference.

The original workspace at `/Users/lisawong/Documents/Codex/2026-09-18/i` remains authoritative for the current demo.
