# Handoff: build a repeatable STL → plaster mould → printed casting-form workflow

Prepared 21 September 2026 for human review and a successor agent.

## Assignment and starting point

Build a reliable workflow that a less capable model can operate on another STL. Use deterministic geometry tools, a resumable state machine and explicit human choices. The current teapot experiment is a useful prototype, not a generic mould designer or a physically validated process. Your first deliverable should be a supported-scope implementation and evaluation plan, followed by tested orchestration and a skill package. Preserve the approved demo while doing this work.

The user’s deliverable is STL files for printing the forms into which they pour plaster. Physical plaster casting, slip casting and sanding are human operations. Their geometry and release constraints still matter. A custom agent is optional; start with one workflow skill backed by a Python package.

Read this document first. Read [TECHNICAL-REFERENCE.md](TECHNICAL-REFERENCE.md) when inspecting or changing geometry, and [EVALUATION-PLAN.md](EVALUATION-PLAN.md) before claiming repeatability. The accompanying `prototype-snapshot.zip` contains selected current code, tests, accepted geometry and review evidence. `snapshot-manifest.json` records their hashes and original relative paths.

## Current demo: preserve these decisions

- Decorative Utah teapot, approximately 50 mm body diameter, not 50 mm overall span. Prusa MK3 access. No validated ceramic shrinkage compensation; do not promise 50 mm fired dimensions.
- Accepted V7 object: simplified lid rim; shortened spout with original-looking flared end and smooth transition; filled inner spout recess; local upper-handle smoothing; two-vertex underside repair. The user rejected an abrupt vertical spout cut.
- Two plaster halves. The user explicitly approved their appearance on 21 September.
- User accepts interference **strictly below 0.5 mm depth** for manual finishing in this experiment. This is not a universal tolerance for future inputs.
- Sampled conservative penetration bounds: half A/object 0.234223 mm, A/printed pattern 0.234587 mm; B/object 0.482567 mm, B/pattern 0.482569 mm. B is close to the allowance. These bounds are neither a continuous-motion proof nor a map of exact material that must be sanded away.
- Casting-form candidates: two positive patterns, one each; long wall, two copies; short wall, two copies. Six printed pieces with one reusable wall set. Loose walls require external retention and joint sealing. Slicer checks, physical release, strength and sealing are unvalidated.
- Forms are **awaiting human review**. The wrap/handoff request is not approval of the forms or final exports. The reusable skill has not been built or tested with a less capable model.

## Required human interaction

Review gates are input → plaster design → casting forms → final export. A changed input, setting or artifact invalidates relevant downstream approvals. Bind approval to exact hashes and revision identifiers; save the human’s actual decision and any authorized edit scope.

For each complex region, present the choice to simplify the object or preserve it with more complex tooling. Explain the region and consequence before asking. Every geometry-change review needs a whole-object locator, marked close-up, before/after and a rotatable Blender view. An isolated triangle image is inadequate. Human appearance approval and engineering check results are separate records.

For a less capable model, the tool should report the next action and evidence paths. The model explains the result and asks the applicable question; it should not invent repairs, move the acceptance threshold or decide that a failed check is harmless. If a tool cannot prove a condition, report `inconclusive` rather than calling the geometry good or bad without evidence.

## Proposed workflow and completion criteria

| Step | Tool/action | Completion criterion |
|---|---|---|
| 1. Intake | Collect STL, units, target dimension/reference axis, object purpose, printer envelope and any finishing allowance. Preserve original and hash it. | Explicit settings; uncertainties about scale resolved. STL carries no reliable units. |
| 2. Prepare | Inspect solid topology, winding, components and intersections; apply declared scale/orientation. Repairs produce a new revision. | Valid supported mesh, saved report and approved source/repair views. Unsupported input stops here. |
| 3. Propose partitions | Evaluate a bounded library of candidate parting directions/surfaces and removal orders. Locate obstructing regions. | Each candidate has actual geometry, release directions, sequence, checks and a complexity explanation. No claim of globally minimal part count. |
| 4. Resolve features | Show one complex region at a time. Ask simplify versus preserve/more parts. Apply only an authorized edit; revalidate and regenerate downstream. | All blocking regions have recorded decisions and reviewed results, or an explicit unsupported escalation. |
| 5. Review plaster | Generate cavity, opening, keys and mould blocks. Check part coverage, mutual interference and release in the proposed order. | Exact plaster revision accepted visually; technical result separately classified as strict pass, conditional finishing, inconclusive or fail. |
| 6. Build forms | Construct positive patterns/complement tooling, walls and retention/sealing arrangement for each plaster part. Check assembly and plaster-from-form release. | Both release problems addressed; contextual assembled/exploded views available; user approves exact forms revision. |
| 7. Prepare print exports | Orient real geometry, reimport STLs, check dimensions/solidness/bed fit. Inspect slicer support and toolpath issues when available. | Exact file manifest, quantities and validation results; explicit final export approval. State any unperformed checks. |
| 8. Validate reuse | Run another supported STL from clean configuration and exercise unsupported/failure cases. | Same commands work without source edits; review gates and resumptions behave correctly. |
| 9. Package/evaluate | Package skill, tools, schemas and targeted references. Evaluate on an agreed less capable model. | Meets the acceptance criteria in EVALUATION-PLAN.md; limitations retained in operator output. |

Steps 3, 6 and 7 need substantive work. The present CLI is not an end-to-end implementation of this table.

## Skills: recommended division of responsibilities

| Capability | Recommendation | Reason |
|---|---|---|
| Main workflow | Create one `stl-to-plaster-mould` skill after supported scope and tools are validated. | One entry point, saved state, clear routing and review gates reduce model improvisation. |
| Overlap/release checking | Put calculations in a tested Python command/API; document interpretation in a supporting reference. A separate skill is optional only if reused independently. | A skill cannot establish geometric correctness. The model should consume numeric results, uncertainty and marked geometry, not calculate collision depth from a picture. |
| Choosing number of parts | Build a bounded partition-planning tool plus decision reference. Split into a specialist skill only if it becomes a substantial independently invoked workflow. | No generic automatic part-count solver exists here. Start with explicitly supported candidates and escalate when none work. Minimum part count alone is not sufficient: release order, castability and printability matter. |
| Blender review | A reusable scripted review generator; a separate Blender skill only if application-specific procedures are needed across projects. | Consistent locator, labels, before/after and scene names must come from exact meshes. |
| Source simplification | Tested, parameterized local operations with authorization bounds and before/after artifacts. | Preserve unrelated shape; leave changes reviewable and reversible. |
| Skill authoring | Use the available `skill-creator` and `mattpocock-skills:writing-for-agents` guidance when constructing the package. | Keep the entry point short; disclose technical branches only when needed; make completion criteria explicit. |
| Implementation | Use `mattpocock-skills:tdd` when building/refactoring tools. User requires tests before implementation. | Known geometry fixtures and state-transition tests matter more than prose conformity. |
| Investigation | Use `mattpocock-skills:diagnosing-bugs` for unresolved geometry failures; research official technical sources when new algorithms are introduced. | Preserve failures as fixtures; avoid treating one successful visual review as validation. |

These are architectural recommendations, not a list of skills that are already installed in the handoff. Avoid making the finished operator skill depend on authoring/debugging skills just to run a normal job.

## Next implementation priorities

1. Reproduce the 45-test baseline and verify snapshot hashes. Audit current depth semantics before making conditional finishing a generic pass: quantify what the bound does and does not imply about material removal.
2. Define the supported input/partition scope. A two-part mode with honest unsupported outcomes is a reasonable first release; arbitrary multipart automatic design is not established.
3. Replace teapot-specific scripts with one parameterized runner and explicit result schemas. Wire forms and export gates into it. Preserve strict collision findings alongside any user-specific finishing policy.
4. Add partition/removal-sequence and casting-form assembly checks. Strengthen temporal sampling or continuous checks, especially near the 0.5 mm threshold. Validate numerical contacts and degenerate Boolean fragments.
5. Build review packages automatically, then test a second STL and evaluate a less capable model. Ask the user which model/environment to benchmark if it has not been selected.
6. Package only the demonstrated capability. Physical feedback can later expand confidence; report digital and physical evidence separately.

## Practical starting instructions

Original project: `/Users/lisawong/Documents/Codex/2026-09-18/i`.
Handoff destination: `/Users/lisawong/Projects/plaster_mould_maker`.
The original workspace remains authoritative for the current run. This handoff does not move it or initialize Git.

From the original project directory:

```sh
PYTHONPATH=work MPLCONFIGDIR=work/mpl-cache work/.venv/bin/python -m unittest discover -s work/tests -v
PYTHONPATH=work work/.venv/bin/python -m mouldflow.review status outputs/source-review-v2/review-state.json
PYTHONPATH=work work/.venv/bin/python -m mouldflow --help
PYTHONPATH=work work/.venv/bin/python -m mouldflow.review --help
```

After extracting the snapshot elsewhere, recreate a Python 3.12 virtual environment using `work/requirements.lock.txt`; the virtual environment itself is not copied. The lock file is a snapshot of this environment, not a cross-platform compatibility promise. Historical review state contains absolute paths: preserve it as provenance and implement explicit path relocation/reverification before reuse. Never rewrite hashes or manufacture replacement approvals to make relocated state pass.
