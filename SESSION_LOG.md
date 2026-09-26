# Session log

## 2026-09-21 20:28 NZST — Initialization and work-plan recommendation

- Session state: fresh start in this successor folder. No prior local session log existed; historical session notes remain in the prototype snapshot. This is a continuation of an existing prototype, not an abandoned-session recovery.
- Agent: Codex.
- Goal: initialize this folder, understand HANDOFF.md and recommend a work plan.
- Completed: read the init skill, HANDOFF.md, TECHNICAL-REFERENCE.md, EVALUATION-PLAN.md, predecessor verification and manifest metadata; inspected folder and Git status; created README.md, SCRATCHPAD.md and SESSION_LOG.md.
- Findings: folder holds handoff materials only and is not a Git repository. Original demo workspace remains authoritative. Forms approval is pending. Baseline tests and hashes are predecessor-reported and were not rerun this session.
- Recommended stages: baseline preservation/reproduction; agreed supported-scope contract; resumable state machine; validated release/assembly checks and parameterized geometry; automated review/export; second-input reuse; packaged operator evaluation.

### Open todos

- [ ] Define detailed supported input/partition scope and turn it into a PRD and staged implementation plan. User accepts two-part moulds initially and wants future expansion to more complex moulds.
- [ ] Verify snapshot hashes, preserve a separate baseline and reproduce the 45 tests; check fresh dependency installation.
- [ ] Audit depth/contact semantics and motion sampling using independently known fixtures.
- [ ] Implement tested orchestration, approval invalidation and verified path relocation.
- [ ] Parameterize tooling generation and implement ordered release/assembly checks for both release problems.
- [ ] Design removable casting walls with configurable 20 mm default clamping lips; define thickness, alignment, sealing and clamp access, then test before implementation.
- [ ] Automate contextual Blender review assets, casting-form review and gated export validation.
- [ ] Demonstrate a second supported STL without source edits and useful unsupported/failure handling.
- [ ] Select the operating model/environment and package/evaluate the workflow skill.

No geometry, approval state, prototype code or original-workspace files changed.

### Scope follow-up — 2026-09-21

- User agreed to start with two-part moulds, with future expansion to more complex moulds as a project goal.
- Captured the decision and proposed extensibility boundaries in SCRATCHPAD.md: generic part records and removal sequences, with a separately bounded two-part generator. No multipart capability is claimed or implemented.

### Casting-form requirement follow-up — 2026-09-21

- Used dump skill to capture five atoms: external clamping lips, removable walls, proposed engineering checks, plaster appearance acceptance and clamp sizing question. No new tags.
- User requires printed parts joined using extended lips and external bulldog clips/small clamps, with walls removable after plaster sets.
- User reconfirmed visual satisfaction with plaster mould pieces. Exact canonical approval records remain untouched; revised forms remain pending review.
- No active PRD.md, PLAN.md or tests exist in this successor folder. Future requirements, implementation stages and tests must cover mating lips, clamp access, sealing and ordered wall release. Archived prototype documents were not changed.
- User resolved clamp-sizing question: use 20 mm default lip extension and allow a custom workflow value. Updated A018; lip thickness remains a separate design parameter. Requirement recorded, not yet implemented.

### Wrap — 2026-09-21 20:41:08 NZST — session closed

- Agent: Codex.
- [x] Initialized successor project notes and reviewed handoff materials.
- [x] Recorded two-part first release, future multipart goal, configurable 20 mm external clamping lips and removable walls.
- [x] Recorded user confirmation of plaster appearance acceptance separately from pending revised-form approval.
- [x] Updated README and synchronized open todos; checked scratchpad for missing decisions.

Recommended next-session order:

1. Verify archive/per-file hashes, extract into a separate baseline directory, inspect source instructions and reproduce the reported 45-test baseline. Record environment and any installation failures.
2. Draft a PRD defining supported input classes and two-part partition scope, unsupported outcomes, review gates and future multipart extension boundaries. Include configurable 20 mm clamping lips and removable walls.
3. Resolve remaining form design parameters: lip thickness, joint alignment/sealing and accessible clamp placement. Preserve accepted plaster geometry unless a change is separately authorized.
4. After PRD approval, prepare a staged test-first implementation plan covering geometry metric fixtures, state transitions, both release problems, clamping forms and export checks.
5. Start implementation only after plan review; keep second-STL reuse and operating-model evaluation as later acceptance milestones.

No implementation or test execution occurred this session. No changes committed or pushed: this folder has no Git repository; repository/remote setup remains optional future work. Original workspace and canonical approval records remain unchanged.

## 2026-09-24 11:16 NZST — Session start

- Session state: clean start (previous session closed with /wrap on 2026-09-21 20:41). Open todos carried forward.
- Agent: Claude Code.
- Goal: re-read HANDOFF.md and outline the steps to turn the teapot prototype into a repeatable workflow.
- Noted: original workspace `/Users/lisawong/Documents/Codex/2026-09-18/i` still present (has its own PRD.md/PLAN.md — prototype-era, not the successor PRD).

### Step 1 — baseline reproduced

- Archive SHA-256 matches manifest; extracted to `baseline/`; all 96 files match manifest size + SHA-256, no extras.
- Fresh venv: `uv venv --python 3.12` (pyenv 3.12.13, macOS arm64) + `uv pip install -r requirements.lock.txt` — installed cleanly.
- `PYTHONPATH=work MPLCONFIGDIR=work/mpl-cache work/.venv/bin/python -m unittest discover -s work/tests` → **45 tests OK** in ~15 s. trimesh emits divide-by-zero RuntimeWarnings in mass-property calculation (some zero-volume mesh in a test) — harmless for the baseline, worth a look during the depth/contact audit.
- `mouldflow --help` and `mouldflow.review status` both run; canonical state reports `next_action: review_forms`, matching the handoff.
- Hard-coded original-workspace paths found in 5 JSON state/manifest files under `baseline/outputs/` (18 in review-state.json) and in `work/build_exploded_v7.py`. Left untouched — provenance; relocation must be explicit and reverified.
- Not verified: Blender scripts, slicer, other hosts.

### Step 2 — PRD approved

- Drafted and iterated `PRD.md` with the user; saved on approval. Key calls: Release 1 = planar two-part (complex moulds → Release 2); 0.1 mm default finishing allowance; 3 mm wall = lip thickness; 20 mm lips; tongue-and-groove seams at 0.25 mm/side clearance; walls 30 mm above plaster; debossed fill line; evaluate on Sonnet 5 + Haiku 4.5. Second STL deferred.
### Step 3 — git, plan, groove coupon

- `git init -b main` with `.gitignore` (venvs, caches, `baseline/`, snapshot zip, `jobs/`). Later committed as `b9c3755` and pushed to https://github.com/lisawong/plaster_mould_maker.
- `PLAN.md` approved and saved: Stages 0–11; teapot regression moved to Stage 5 (after plaster generation); pydantic v2 confirmed.
- Groove test coupon (TDD): `tests/test_groove_coupon.py` (8 tests, red → green) + `tools/groove_coupon.py`; exported `prints/groove-coupon/groove-block.stl` (29.5 × 32 × 8 mm, 5 slots at 0.15–0.35 mm/side, dot-indexed) and `tongue.stl` (30 × 20 × 3 mm with 0.6 mm fill line). Reimported: both watertight. Currently run with the baseline venv until Stage 0 creates the project venv.

### Wrap — 2026-09-24 session closed

- Agent: Claude Code.
- [x] Initialized session; reviewed handoff and outlined the path to a repeatable workflow.
- [x] Reproduced baseline: hashes verified, fresh uv install, 45/45 tests.
- [x] PRD approved and saved.
- [x] Git initialized.
- [x] PLAN approved and saved.
- [x] Groove test coupon generated for early physical testing.

### Open todos

- [ ] **User:** print `prints/groove-coupon/` and report best-fitting slot + fill-line legibility (A026).
- [ ] **User:** choose second STL (blocks Stage 10).
- [ ] Stage 0 — scaffold `pyproject.toml`/`src/` layout, port baseline + 45 tests, move coupon tool in.
- [ ] Stage 1 — job folder, pydantic schemas, hash-bound gate state machine.
- [ ] Stage 2 — known-answer fixtures, depth-semantics audit, adaptive sampling, `inconclusive`; investigate trimesh divide-by-zero warnings.
- [ ] Stages 3–11 per PLAN.md.
- [ ] Optional: add a git remote (none configured).

## 2026-09-26 16:33 NZST — Session start

- Session state: clean start (previous session wrapped 2026-09-24; initial commit `b9c3755` pushed to GitHub).
- Agent: Claude Code.
- Goal: plan how to use GitHub + Anthropic cloud credit; implement Stage 0.
- Discussed: Claude Code on the web for cloud stage sessions, `/code-review ultra` on geometry-heavy PRs, `@claude` GitHub mentions, credits for the Stage 11 evaluation. Blender (Stage 9) stays local. Added CI + fixture commits to Stage 0 so cloud sessions can work from the repo alone.

### Open todos

- [x] Stage 0 — scaffold, port baseline + 45 tests, commit V7 + historical fixtures, GitHub Actions CI (local green; CI result below).
- [ ] **User:** print `prints/groove-coupon/` and report best slot + fill-line legibility (A026).
- [ ] **User:** choose second STL (blocks Stage 10).
- [ ] Stages 1–11 per PLAN.md.

### Stage 0 — work done (branch `stage-0-scaffold`)

- Tests + fixtures copied first → 19 collection errors (red); then `pyproject.toml` (hatchling, src layout, deps + transitive constraints pinned to baseline lock), `uv.lock`, `Makefile`, package ported → **53 passed** (45 baseline + 8 coupon).
- Port verified byte-identical to baseline (package and 44 tests); only `test_scene_artifact.py` changed (fixture path + HISTORICAL docstring).
- `uv sync` initially pulled a newer transitive `tifffile`; fixed with `[tool.uv] constraint-dependencies`.
- Fixtures: `tests/fixtures/teapot-v7/` (7 files, hashes match snapshot manifest, `PROVENANCE.md`), `tests/fixtures/historical/` (~9.9 MB total).
- CI: `.github/workflows/tests.yml` (ubuntu, setup-uv, `uv sync --locked`, pytest).
- Notes for Stage 1: `mouldflow` has no `__init__.py` (namespace package, kept verbatim); trimesh divide-by-zero warnings persist (Stage 2 item); user's shell exports `VIRTUAL_ENV` from pyenv, which makes uv print a harmless warning.
