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

## Decisions

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
