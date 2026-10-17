# Project scratchpad

## Atom Tags

| Tag | Meaning |
| --- | --- |
| goal | Intended outcome |
| constraint | Requirement or boundary |
| proposal | Recommendation awaiting agreement |
| evidence | Existing evidence and its limits |
| question | Choice or uncertainty to resolve |

## Atoms

- A001 [goal] A repeatable workflow produces printable plaster-casting forms from supported STL inputs, using a Python package and one operator skill.
- A002 [constraint] Preserve accepted teapot V7 and exact approval provenance. Plaster appearance was approved; casting forms and final exports remain pending.
- A003 [constraint] Review gates: input → plaster design → casting forms → final export. Bind human decisions to exact revisions/hashes; invalidate affected downstream approvals after changes.
- A004 [constraint] Test before implementation. Keep appearance approval separate from engineering evidence and physical validation.
- A005 [evidence] 45 tests pass on a fresh uv install from the lock file (Python 3.12.13, macOS arm64, 2026-09-24) in `baseline/`. Generic reuse, Blender scripts and slicer remain unverified.
- A006 [constraint] The teapot's strictly-below-0.5-mm finishing allowance is specific to that experiment. Sampled depth bounds do not prove continuous release or identify required sanding.
- A007 [constraint] User accepts starting with a two-part mould. Proposed initial algorithm remains bounded planar partitions with explicit unsupported outcomes; precise input classes and permitted repairs still need definition.
- A008 [proposal] Sequence: preserve/reproduce baseline → scope and acceptance contract → resumable orchestration → geometry and form checks → review/export automation → second-input reuse → operator skill evaluation.
- A009 [constraint] Check object-from-plaster release, plaster-from-form release and ordered tooling assembly/removal separately.
- A010 [question] Agree initial input classes, partition scope, target runtime, second STL fixture and operating model/environment before their dependent implementation or evaluation.
- A011 [proposal] Prioritize validated release semantics over adding more geometry options. Return inconclusive when evidence cannot establish the required condition.
- A012 [goal] User wants the workflow to expand to more complex moulds in the future.
- A013 [proposal] Represent named parts, per-part release directions, ordered removal steps and part relationships generically. Keep the initial two-part partition generator separate from validation, review, casting-form generation and exports. General data structures do not establish multipart geometry support.

- **A014 External clamping lips** `[constraint]`
  Printed form parts need extended mating lips for external bulldog clips or small clamps.
- **A015 Removable casting walls** `[constraint]`
  Release clips after plaster sets, then withdraw walls to free the plaster.
- **A016 Clamping and release checks** `[proposal]`
  Validate clamp access, lip strength, joint sealing and wall withdrawal without trapping the plaster.
- **A017 Plaster appearance accepted** `[evidence]`
  User confirms visual satisfaction with plaster pieces; revised printed forms still require review.
- **A018 Configurable lip extension** `[constraint]`
  Default outward lip extension is 20 mm; workflow accepts a custom value. No particular clamp is prescribed.

- **A019 Lip thickness = wall thickness** `[constraint]`
  Lip thickness always matches wall thickness. Default 3 mm (existing prototype walls); 1.5 mm was the fallback had none been defined.
- **A020 Tongue-and-groove seams** `[constraint]`
  Form seams use printed grooves that parts slot into, locked with external bulldog-style clips. Clip design/selection is out of scope.
- **A021 Wall height clearance** `[constraint]`
  Walls default to 30 mm above the top of the plaster mould block; configurable.
- **A022 Plaster fill-level mark** `[goal]`
  Shallow debossed line (~0.6 mm) on the inner face of every wall at the top-of-plaster-block height.

- **A023 Evaluate on two operator models** `[constraint]`
  Benchmark the packaged skill on both Sonnet 5 and Haiku 4.5 to map how far capability extends.
- **A024 Release 2: complex moulds** `[goal]`
  Non-planar partitions and 3+ part moulds are the Release 2 target; v1 is single planar split, two parts.
- **A025 Default finishing allowance 0.1 mm** `[constraint]`
  New jobs default to 0.1 mm; configurable per job. Teapot's 0.5 mm stays demo-specific.

- **A026 Groove coupon print pending** `[question]`
  User to print `prints/groove-coupon/` (groove block + tongue) and report which slot (1–5 dots = 0.15–0.35 mm/side) gives a snug slide-in fit, and whether the 0.6 mm fill line is legible. Result sets the Stage 7 default clearance.

- **A027 Cloud sessions for middle stages** `[proposal]`
  Once Stage 0 lands, run Stages 1–4 and 6–8 as Claude Code on the web sessions that open PRs; Stage 9 (Blender) stays local.
- **A028 Anthropic credit for review and evaluation** `[evidence]`
  User has Anthropic cloud credit and Claude connected to GitHub. Candidate uses: `/code-review ultra` on geometry-heavy PRs (Stages 2, 4, 7) and the 36-run Stage 11 evaluation.
- **A029 CI gates every PR** `[constraint]`
  GitHub Actions runs the full test suite on push/PR so cloud or `@claude` work shows green/red before merge.

- **A030 Two-sided release depth** `[evidence]`
  Depth below the fixed surface alone is ≤ half the fixed feature's thickness, so it misses parts sweeping through thin fixed walls. Stage 2 uses max(depth below fixed, depth below moving).
- **A031 Whole-motion depth bound** `[evidence]`
  Releases are covered from 0 to the clearance distance. Between samples, Minkowski sweeps give the exact union of overlaps over the travel interval; erosion certificates prove "below r deep" for thin/shell overlaps. The 1-Lipschitz bound remains as a second interval bound.
- **A032 strict_pass wording** `[evidence]`
  Resolved by the swept intervals: `strict_pass` now means contact only (≤ contact tolerance) over the whole motion, not just at samples.
- **A033 Teapot assessment cost** `[question]`
  Sweeps and erosions remove the dense-sampling requirement (a clean 60 mm withdrawal at 0.1 mm now takes 2 samples). V7 cost: half A conditional_finishing in 187 s (measured 0.066 mm, certified < 0.4995 mm), half B conditional_finishing in 174 s (measured 0.097 mm, certified < 0.4995 mm) at the demo's 0.5 mm allowance, 2 samples each (0 and clearance). Stage 5 should confirm this is practical for the regression.
- **A034 Visual inspection while building** `[decision]`
  (2026-10-17, user) Be able to look at the geometry at each step, not only read metrics. Combine standard commands/skills with an agent that iterates (render → look → adjust). Candidate pieces: a `mouldflow view` command (PNG contact sheets + rotatable HTML), a `/look` project skill, a `mould-inspector` subagent, and possibly pulling the Stage 9 headless-Blender spike forward (Blender 5.2.2 is installed locally). Overlaps Stage 3 previews and Stage 9 review packages. Built as Stage 2.5 (matplotlib PNGs + three.js HTML first; Blender stays in Stage 9).
- **A035 Pictures never decide outcomes** `[constraint]`
  `mouldflow view` output, `/look` and `mould-inspector` describe what they see; release outcomes come only from `release_check`. Numbers are quoted from result records, never estimated from pixels.

## Decisions

- 2026-10-18: Stage 3 (intake & prepare) design, agreed with the user:
  - **Scale:** `--units mm|cm|m|in` is always required at intake (never guessed). `--target-mm`/`--target-axis` optionally rescale so the prepared extent on that axis matches. Every factor is recorded.
  - **Orientation:** `mouldflow prepare --rotate AXIS=DEG` (repeatable, applied in order about fixed axes) is stored in `settings.source`, so changing it invalidates the input gate. The canonical frame is Z-up. Order: units → repairs → rotations → target scale → centre at origin.
  - **Repairs:** only when requested (`--repair drop-degenerate|fix-winding|stitch=TOL`). Invalid meshes are rejected with reasons and suggested repairs, and nothing is auto-fixed. A requested repair that matches no reported problem is an error. Multiple components, self-intersections, zero volume and non-finite vertices cannot be repaired (`unsupported`).
  - **Degenerate faces:** zero-area faces reject a *source* STL (PRD R2.1). Generated Boolean meshes keep the Stage 2 warning behaviour.
  - Each successful prepare writes a new revision folder `candidates/input/rNNN/` (never overwritten) and submits the input gate, which invalidates anything downstream. A rejected prepare writes nothing. One job has one source STL; a different file needs a new job.

- 2026-10-18: The workflow now has a separate **review agent** alongside the **dev agent**. They communicate through files in `review-notes/` (git-ignored, local only): the review agent writes findings/handoffs there, the dev agent works from them and records resolutions back in the same file. First file: `review-notes/REVIEW-HANDOFF.md` (Stage 2.5 review, moved from the repo root).

- 2026-10-17: Codex is used as a review agent for now. The Codex copies of `/look` and `mould-inspector` (`.agents/`, `.codex/`) are committed. The Claude files are the source of truth, and a test keeps the copies identical.

- 2026-10-17: Stage 2.5 review fixes (review-notes/REVIEW-HANDOFF.md, local only).
  - Malformed `--marks-from` records now give JSON errors.
  - Open section paths are kept: `open_paths`, drawn dashed and unfilled, with per-plane `empty`.
  - Colours are now a pure function of the label (fixed for object/half_1/half_2, otherwise hashed hue clear of mark red). Stability between renders wins over guaranteed distinctness within one render.

- 2026-10-17: First `mould-inspector` run (teapot V7 halves). The answer was correct: closed cavity, intended gate, male/female keys, no fragments. Applied its feedback:
  - sections, bounds and marks stay in the assembled pose under `--explode`;
  - `pieces` per mesh;
  - label-stable colours;
  - `--views` with documented directions;
  - the agent returns findings as text and the caller saves FINDINGS.md, because subagents can't write report files.

- 2026-10-17: Stage 2 merged (PR #4). Stage 2.5 added: visual inspection toolkit. `mouldflow view` (PNG views, filled sections, self-contained three.js `viewer.html` pinned to three@0.160.0 on jsDelivr), project skill `/look`, agent `mould-inspector`, `look/` output folder (git-ignored) served by `.claude/launch.json` → `look` on port 8765. Section planes that pass exactly through vertex rings are nudged by 1e-6 × extent and the nudge is recorded.

- 2026-10-17: Code review of PR #4 fixed. Swept intervals (Minkowski sums) replace dense sampling between poses; erosion certificates (Minkowski differences) prove depth below the allowance and contact-only; zero-area faces are input warnings, not `unsupported`; the reported catch location is the deepest component; per-side bounds only tighten, so records are self-consistent.

- 2026-09-26: Stage 2 depth audit. New release checks go through `release_check.assess_release` (two-sided depth, Lipschitz whole-motion bound, adaptive spatial/temporal refinement, `inconclusive` when unresolved, `unsupported` for invalid solids). Prototype `check_release` / `check_release_depth` keep their behaviour for the baseline. Contact tolerance 1e-3 mm. trimesh divide-by-zero warnings traced to mass-property volume on zero-volume Booleans; fixed with `solid_volume` / `is_solid`.

- 2026-09-26: Workflow change: documentation (SESSION_LOG, PLAN status, README, SCRATCHPAD, and reference docs where affected) is updated in each stage branch before its PR is opened; checklist in `.github/pull_request_template.md`. No separate docs PRs after merge.

- 2026-09-26: Stage 1 delivered as PR #2 and merged (CI green). Stage 2 is next and gets `/code-review ultra`.

- 2026-09-26: Stage 1 gate design: gates bind to one settings section each (input↔source, plaster↔plaster, forms↔forms, export↔printer) plus the upstream approved revision, so e.g. a lip change invalidates forms/export only. Stale is sticky until resubmission. Only `strict_pass`/`conditional_finishing` outcomes are approvable. `mouldflow job decide` added alongside `init|status` so gates can be answered from the CLI.

- 2026-09-26: One PR per stage, merged by the user after CI is green. Stage 0 delivered as PR #1.

- 2026-09-26: Stage 0 expanded: add GitHub Actions CI (Linux) and commit the V7 teapot fixtures (`tests/fixtures/teapot-v7/`) plus the historical scene fixtures, so the repo is self-sufficient for cloud sessions. Dependencies pinned `==` to baseline versions for reproduction; loosen deliberately later.

- 2026-09-24: PLAN.md approved and saved (12 stages, 0–11). Teapot plaster regression moved directly after the plaster-generation stage (now Stage 5). pydantic v2 chosen for schemas. Groove test coupon generated ahead of Stage 7 for an early physical fit test.
- 2026-09-24: Git repo initialized (`main`). `baseline/` and `prototype-snapshot.zip` are git-ignored; the tracked `snapshot-manifest.json` records their hashes.

- 2026-09-24: PRD.md approved and saved. v1 = single planar split, two-part moulds; Release 2 = complex/multipart. Default finishing allowance 0.1 mm. Groove clearance 0.25 mm/side (needs a physical test print). Operator evaluation on Sonnet 5 and Haiku 4.5. Second STL chosen later.

- 2026-09-24: Forms design parameters agreed during PRD review: wall = lip thickness, 3 mm default; printed tongue-and-groove seams locked with external bulldog-style clips (clip design out of scope); walls clear the plaster block top by 30 mm (configurable); ~0.6 mm debossed fill line on inner wall faces at plaster-block top.

- 2026-09-24: Snapshot extracted to `baseline/` (hash-verified, read-only reference). Fresh venv at `baseline/work/.venv` via uv reproduces 45/45 tests. Original workspace remains authoritative for the demo.

- 2026-09-21: User specified a default lip of 2 cm and workflow support for a custom value. Record as 20 mm outward lip extension; lip thickness is a separate design parameter. No specific clips or clamps selected.

- 2026-09-21: User requires extended lips for external clips or small clamps joining the printed casting-form parts. Walls must withdraw after unclipping once plaster has set. This is external clamp retention, not a request for integral printed snap clips.
- 2026-09-21: User said, "Otherwise I have visually inspected the design and happy with the plaster mould pieces." Recorded as confirmation of plaster appearance acceptance in conversation; no canonical hash-bound approval record changed, and no revised casting-form approval inferred.

- 2026-09-21: User approved starting with a two-part mould and requested future expansion to more complex moulds. Build and validate two-part support first; preserve architectural room for additional parts without implementing an arbitrary multipart solver in the first release.

- 2026-09-21: Initialized successor notes in this folder using `/init`. Read the handoff, technical reference and evaluation plan. Work plan is a recommendation only; no implementation scope has been approved or code changed.
- 2026-09-21: Keep the original workspace authoritative for the existing demo, as required by HANDOFF.md. No archive extraction, workspace migration or Git initialization performed.
