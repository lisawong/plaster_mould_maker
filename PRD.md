# PRD: STL → plaster mould → printable casting forms

Approved 2026-09-24. Supersedes the prototype-era `baseline/PRD.md` for successor work.

## Overview

`mouldflow` is a Python package plus one operator skill (`stl-to-plaster-mould`). It turns a supported STL into print-ready STLs for the forms plaster is poured into, producing a two-part plaster slip-casting mould. Work runs in a resumable job folder. Deterministic geometry tools do the design work; the human approves each stage. A less capable model can drive it without improvising.

Physical plaster casting, slip casting and sanding are human operations. The tool designs for them but never claims physical success from digital checks.

## Goals & Non-Goals

### Goals
- G1: One parameterized workflow runs on any *supported* STL without source edits.
- G2: Release 1 — two-part plaster moulds from a single planar split. The data model (named parts, per-part release directions, ordered removal) is general so Release 2 can add complex moulds.
- G3: Check three release problems separately: plaster off the object, plaster out of its printed form, and form disassembly order.
- G4: Honest outcomes: `strict_pass`, `conditional_finishing`, `inconclusive`, `fail`, `unsupported`.
- G5: Review gates input → plaster → forms → export, bound to exact hashes; upstream changes invalidate downstream approvals.
- G6: Packaged skill passes the operator evaluation in `EVALUATION-PLAN.md` on both Sonnet 5 and Haiku 4.5.

### Non-goals (Release 1)
- Non-planar partitions, 3+ part moulds, or any minimal-part-count claim (Release 2 target).
- Ceramic shrinkage compensation or fired-dimension promises.
- Clip/clamp design or selection; forms use off-the-shelf bulldog-style clips.
- Physical validation of casting, print fit or demoulding (recorded as separate evidence later).
- Migrating or re-approving the teapot demo; the original workspace stays authoritative.

## Requirements

### R1 Job & intake
- R1.1 `mouldflow job init <dir>` creates a job folder with settings, state and artifact folders; all paths inside are relative.
- R1.2 Intake records source STL (copied and hashed), declared units, target dimension + axis, object purpose, printer envelope and finishing allowance. STL has no units — scale is never guessed.
- R1.3 Relocating a job is detected and hashes reverified; never auto-reapproved.

### R2 Prepare
- R2.1 Validate: closed, consistently wound, single component, no self-intersections, no degenerate faces. Unsupported input stops with a reason.
- R2.2 Apply declared scale/orientation; any repair creates a new revision.
- R2.3 **Gate: input review** — whole-object locator, marked close-up, before/after for every change.

### R3 Partition proposals
- R3.1 Evaluate a bounded set of planar split candidates (axis-aligned + principal axes, with offsets) and per-half release directions.
- R3.2 Each candidate reports actual geometry, obstructing regions, complexity explanation and check results.
- R3.3 No working candidate → `unsupported` with obstructing regions marked. Never invent a two-part success.

### R4 Feature resolution
- R4.1 Present one obstructing region at a time: simplify the object, or preserve it (escalate — unsupported in Release 1).
- R4.2 Edits only via tested local operations (fill, frustum, trim, spout lowering, smoothing), each recorded with authorization, parameters and before/after.
- R4.3 Authorization is scoped per region. Every edit reruns checks and invalidates downstream approvals.

### R5 Plaster mould
- R5.1 Generate cavity, pour gate, registration keys and two plaster blocks from settings. Defaults from the demo (12 mm margin/backing, 5 mm gate, 2.5 mm keys), all overridable.
- R5.2 Check plaster vs object and half vs half along the removal order. Report penetration depth in **mm** with method, samples and bound-vs-measurement. Never compare mm³ volume to a depth.
- R5.3 Finishing allowance defaults to **0.1 mm**, configurable per job. `conditional_finishing` only when a proven bound is strictly below the job's allowance; an unproven bound is `inconclusive`. The teapot's 0.5 mm allowance is demo-specific.
- R5.4 **Gate: plaster review** — visual approval recorded separately from technical status.

### R6 Casting forms
- R6.1 Per plaster half: a positive pattern plus removable walls.
- R6.2 Wall thickness = lip thickness, **default 3 mm**. Outward lips **default 20 mm**, configurable.
- R6.3 Seams are **printed tongue-and-groove** joints; parts slot together and are locked by external bulldog-style clips on the lips. Groove clearance **default 0.25 mm per side**, configurable; to be confirmed with a physical test print.
- R6.4 Walls **default to 30 mm above the plaster block top**, configurable.
- R6.5 **Fill line**: ~0.6 mm debossed line on every wall's inner face at plaster-block-top height. Walls print inner-face-up.
- R6.6 Checks: plaster release from pattern; wall withdrawal after unclipping without trapping plaster; groove engagement and alignment; clamp access to lips; fill line clear of any feature the plaster releases past.
- R6.7 **Gate: forms review** — contextual assembled and exploded views.

### R7 Export
- R7.1 Orient, export, reimport; check dimensions, solidity and bed fit against the configured printer (default Prusa MK3, 250 × 210 × 210 mm).
- R7.2 Manifest lists files, quantities, hashes, transforms, check results and **unperformed checks** (e.g. slicer).
- R7.3 **Gate: final export** — candidates and approved exports are distinguishable in directory, manifest and operator output.

### R8 Review packages
- R8.1 Every geometry review has a whole-object locator, marked close-up, before/after and a rotatable Blender scene built from exact meshes. Annotations never enter printable STLs.

### R9 Operator interface
- R9.1 Small documented CLI; each command returns versioned JSON: hashes, stage, status, metrics, limitations, `next_action`, evidence paths.
- R9.2 Nonzero exit + actionable error on failure. The model explains results and asks the tool-provided question; it never moves thresholds or improvises repairs.
- R9.3 Skill: short entry point, progressive references, demonstrated capability only.

### R10 Quality
- R10.1 Tests before implementation. Known-answer geometry fixtures (per `EVALUATION-PLAN.md`) and state-transition tests.
- R10.2 The 45-test baseline keeps passing, or retirements are explicitly recorded.

## Assumptions
- A-1 Release 1 supports a single closed solid with a single planar split. Non-planar/multipart deferred to Release 2.
- A-3 Prusa MK3 is the default printer profile; overridable.
- A-4 Plaster block defaults come from the teapot demo.
- A-5 PrusaSlicer check optional; reported as "not performed" if absent.
- A-6 Blender review generation may need the UI console if headless keeps crashing on this Mac; headless to be investigated.
- A-7 Operator skill is a Claude Code skill; package installed in a local venv.
- A-8 New code lives at this project root (`src/mouldflow`, `tests/`), ported from `baseline/`, which stays untouched as reference.

## Open Questions
- Second STL for the reuse test — to be chosen later (simple, non-teapot).
