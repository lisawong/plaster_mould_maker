# Implementation plan — mouldflow Release 1

Approved 2026-09-24. Implements [PRD.md](PRD.md). Every stage is test-first and ends with a green suite and a commit.

Fixed decisions: `src/` layout, `uv`, `pytest` (runs the ported unittest suite as-is), **pydantic v2** for settings/result schemas, `argparse` CLI.

## Stage 0 — Scaffold, port baseline, CI
- **Status:** done — PR #1 merged 2026-09-26 (53 tests green in CI).
- **Build:** `pyproject.toml` (Python 3.12, deps pinned `==` to `baseline/work/requirements.lock.txt`), `uv.lock`, `src/mouldflow/` ported verbatim from `baseline/work/mouldflow`, 45 tests ported to `tests/`, `make test`. Coupon tool stays in `tools/` and runs in the project venv. Teapot-specific scripts are not ported.
- **Fixtures:** `tests/fixtures/historical/` (older three-part scene manifest + `.blend` used by `test_scene_artifact`, labelled historical); `tests/fixtures/teapot-v7/` (accepted source, prepared object, reference plaster halves, settings, reports) with a provenance file of snapshot hashes — needed by Stage 5 and by cloud sessions that can't see `baseline/`.
- **CI:** GitHub Actions (ubuntu, uv) runs the full suite on push and PR. Confirms the macOS-captured pins install on Linux.
- **Tests:** the 45 baseline tests + 8 coupon tests pass locally and in CI.

## Working mode
From Stage 1 on, stages may run as Claude Code on the web sessions that open one PR per stage; CI must be green before merge. Use `/code-review ultra` on Stages 2, 4 and 7. Stage 9 (Blender) and physical prints stay local.

**Docs before every PR.** Update the documentation in the same branch *before* opening the PR, so each merge leaves `main` current and no follow-up docs PR is needed:
- `SESSION_LOG.md` — dated entry: work done, test count, notes for later stages, open todos (with the PR link once opened).
- `PLAN.md` — the stage's **Status** line (mark done on merge in the next stage's PR if not known yet).
- `README.md` — progress line, new commands, new modules/files in Structure.
- `SCRATCHPAD.md` — new decisions (dated) and any new or resolved atoms.
- `TECHNICAL-REFERENCE.md` / `PRD.md` / `EVALUATION-PLAN.md` — only where behaviour, contracts or scope changed.
The PR template (`.github/pull_request_template.md`) carries this checklist.

## Stage 1 — Job folder, schemas, state machine (no geometry)
- **Status:** done — PR #2 merged 2026-09-26 (116 tests green in CI). Added `mouldflow job decide` beyond the planned `init|status`.
- **Build:** `mouldflow job init|status`; pydantic settings (units, target, printer, allowance 0.1 mm, wall/lip 3 mm, lip 20 mm, groove clearance 0.25 mm/side, wall clearance 30 mm); versioned result record (status, metrics, limitations, `next_action`, evidence paths); four hash-bound gates; generic part/release-direction/removal-order model.
- **Tests (first):** pending gate blocks; missing answer ≠ approval; upstream change invalidates downstream; relocation reverifies, never reapproves; per-job allowance doesn't leak.

## Stage 2 — Known-answer fixtures & depth-semantics audit
- **Build:** fixture library for each EVALUATION-PLAN row (thin-wide overlap, deep catch, zero-thickness contact, near-coplanar sliver, between-sample catch, self-intersecting mesh). Audit `release_depth`; add adaptive sample refinement near the allowance; add `inconclusive`. Investigate the trimesh divide-by-zero warnings seen in the baseline run.
- **Trade-off:** adaptive sampling (Release 1) vs continuous collision detection (research). Unresolvable → `inconclusive`.
- **Tests (first):** each fixture asserts metric unit (mm vs mm³), bound-vs-measured and outcome.

## Stage 3 — Intake & prepare
- **Build:** `mouldflow intake`, `mouldflow prepare`: hash source, require units, validate mesh, apply scale/orientation as a new revision, simple PNG previews for the input gate.
- **Tests (first):** invalid meshes rejected with reasons; scale never guessed; repairs create revisions and invalidate downstream.

## Stage 4 — Plaster mould for a given plane
- **Build:** parameterize `pipeline.py` for any plane (not hard-coded Y=0): cavity, gate, keys, blocks. Ordered release checks (plaster/object, half/half). Classify strict / conditional (< 0.1 mm) / inconclusive / fail.
- **Tests (first):** cube on a good plane passes; known undercut fails; just-under/just-over allowance labelled correctly; appearance approval never changes technical status.

## Stage 5 — Teapot regression (plaster)
- **Build:** run the teapot through the new CLI with recorded V7 settings; compare to accepted V7 plaster (geometry within tolerance + same outcome labels). Do not migrate approvals.
- **Tests:** parity test; any divergence is documented and explained, never silently accepted. Extended to forms after Stage 7.

## Stage 6 — Partition proposals & feature resolution
- **Build:** bounded planar candidate search (axis-aligned + principal axes × offsets), ranked by obstruction count → max depth → edit area; obstruction locator; `unsupported` when none work. Wire simplify operations into the CLI with per-region authorization.
- **Tests (first):** convex solid → supported candidate; trapped core → `unsupported`; authorization is region-scoped; every edit reruns checks.

## Stage 7 — Casting forms
- **7a geometry:** positive patterns; 3 mm walls + 20 mm lips; tongue-and-groove seams at the clearance confirmed by the coupon print (default 0.25 mm/side); walls 30 mm above plaster; 0.6 mm fill line on inner wall faces.
- **7b checks:** plaster-from-pattern release; wall withdrawal after unclipping; groove engagement/alignment; clip-access envelope around lips; fill line above release obstructions.
- **Human, in parallel:** print `prints/groove-coupon/` and report which slot fits best (see SCRATCHPAD A026).
- **Tests (first):** known-answer dimensions (lip width, groove clearance, wall height, fill-line height); trapped pattern caught even when object release passes; wrong-side groove fails withdrawal. Extend Stage 5 regression to forms.

## Stage 8 — Export
- **Build:** print orientation (walls inner-face-up), export → reimport → solidity/dimension/MK3 bed checks; manifest with quantities, hashes, transforms, unperformed checks; candidate vs `approved/` separation; optional PrusaSlicer check.
- **Tests (first):** oversize → clear fail, no silent rescale; nothing reaches `approved/` without the export gate; unperformed checks always listed.

## Stage 9 — Review packages
- **Build:** locator / marked close-up / before-after / Blender scene script generator. Short, time-boxed headless Blender spike (`--gpu-backend`, factory startup) first; fall back to UI-console scripts.
- **Interim:** Stages 3–8 use simple PNG previews until this lands.
- **Tests (first):** every geometry review has all required views; annotation meshes never reach printable STLs; scene meshes match hashed artifacts.

## Stage 10 — Second STL & unsupported cases
- **Blocked on:** user's second STL choice.
- **Build:** fresh job on the second STL with zero source edits; end-to-end invalid / undercut / trapped-core runs.

## Stage 11 — Skill packaging & evaluation
- **Build:** `stl-to-plaster-mould` skill (per `writing-for-agents`); scripted checkpoint harness.
- **Evaluate:** 6 scenarios × 3 trials × {Sonnet 5, Haiku 4.5} = 36 runs. Record where each model's capability ends.
