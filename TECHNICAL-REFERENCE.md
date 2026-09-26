# Technical reference and prototype limits

Read this when implementing geometry or auditing the demo. Paths below are relative to the original workspace or the extracted snapshot unless stated otherwise.

## Artifact map

| Path | Meaning |
|---|---|
| `outputs/base-repair-review-v7/input.stl` | Accepted source V7; preserve it. |
| `work/base-diagnostic-v7/prepared_object.stl` | Pipeline-normalized V7 used to generate current tooling; minor centering difference from raw accepted input. |
| `work/base-diagnostic-v7/reference_plaster/` | Exact two reviewed plaster STL solids. |
| `work/base-diagnostic-v7/print_candidates/` | Assembly-coordinate patterns and four walls. |
| `outputs/casting-forms-review-v7/` | Print-oriented candidate STLs, quantities, transforms, image and manifest. Forms approval pending. |
| `outputs/exploded-design-v7/exploded-design.blend` | Three rotatable scenes: actual withdrawal directions, cavity-up plaster, exploded patterns/walls. Geometry is real STL geometry. |
| `outputs/exploded-design-v7/plaster-appearance-acceptance.json` | User visual approval bound to part hashes. |
| `outputs/sanding-assessment-v7-final/summary.json` | Current depth report, hashes, samples and limitations. Individual reports contain component bounds/locations. |
| `outputs/source-review-v2/review-state.json` | Canonical state, despite old directory name. Current input is V7; plaster conditionally approved; forms pending. |
| `outputs/base-repair-review-v7/teapot-context-review.blend` | Accepted source repair context. Preserve approved artifact hashes. |

Older exploded-scene annotations say depth has not been measured. They predate the final depth report; the report is current. `outputs/sanding-assessment-v7/` is superseded debug output. `outputs/mouldflow-prototype.zip` is an older package and is not the handoff snapshot. Earlier rejected lid inserts, top caps and contour seams are experiments, not fallback production designs.

## Code map and tool use

| Module/script | Current capability and boundary |
|---|---|
| `work/mouldflow/pipeline.py` | STL preparation/inspection, Manifold Boolean wrapper, Y=0 two-part tooling, sampled overlap-volume checks; top-cap/local-insert experiments. |
| `intersections.py` | Strict edge-through-face crossing detection. Does not establish absence of all coplanar overlaps or endpoint contacts. |
| `release_depth.py` | Conservative spatial penetration bound on collision components at specified translations. Review limitations below. |
| `print_layout.py` | Rigid print orientation, centering, bed placement and transform provenance. |
| `workflow.py` | Artifact hashes, revisions, approval invalidation, feature choices and history. |
| `review.py` | Prepare/status/approve/changes/feature operations. Modification CLI supports only local directional fill; other edits are API operations. |
| `simplify.py` | Local fill, frustum, trim, smooth spout lowering and local smoothing. Operations still need unified CLI/config integration. |
| `review_context.py`, `preview.py` | Hash/change-location context and previews. Full Blender review generation remains demo scripting. |
| `contour_seam.py` | Experimental height-field partition; passing a sphere fixture did not yield a valid teapot partition. |
| `work/assess_v7_depth.py` | Demo-specific assessment. Rebuilds tooling, reads cached solids, samples four release pairs. Not a generic command. |
| `work/export_forms_review_v7.py` | Demo-specific export and reimport checks. Explicit quantities, transformations and review ZIP. |
| `work/record_forms_review_v7.py` | Historical recording script containing this user's approvals. Do not reuse to approve another object. |
| `work/build_exploded_v7.py` | Blender UI-executed scene/render generator. Uses demo paths and historical pending-depth annotations. |

Python libraries in use: trimesh, manifold3d, NumPy, SciPy, rtree, networkx, matplotlib, Pillow, scikit-image and fast_simplification. Inspect the lock file for versions. Use Blender for inspectable scenes and renders, not AI-generated illustrations as geometric evidence. A slicer still needs to be supplied and integrated; no slicer validation has been performed.

Blender installed at `/Applications/Blender.app/Contents/MacOS/Blender` (5.2.2 LTS observed in this session). Background execution crashed at Metal detection on this machine. UI Python-console execution worked. This is an environment observation, not a universal Blender limitation. Preserve user scenes; save review artifacts to new filenames. In the console, clear the input before pasting a command; stale input previously caused concatenation errors. Scripts should select a useful review scene and viewport before saving. Scene 03 of the exploded file shows casting forms.

## Geometry conventions in this demonstration

Units are millimetres; scale is based on Y extent 50 mm. The accepted object's overall X extent is about 80.49 mm. Mould split plane is Y=0; halves withdraw along +Y and -Y. Object stays fixed. Base gate radius is 5 mm; X/Z margin and backing settings are 12 mm. These are demo parameters, not validated defaults for arbitrary ceramic objects.

Plaster is generated by subtracting the object-plus-gate cavity from enclosing half blocks. Spherical keys of radius 2.5 mm provide registration. The minus-side plaster is reflected in Y for the second printed pattern. Patterns are complementary solids with extended 4 mm bases; walls are separate 3 mm panels. Print placement rotates patterns about X by +90 degrees and places their bases at Z=0. Flat walls are oriented onto their broad faces.

Pattern A/B dimensions in print orientation: approximately 112.489 × 69.609 × 29 mm each. Long wall: 110.489 × 37 × 3 mm, quantity two. Short wall: 61.609 × 37 × 3 mm, quantity two. The wall set is reused for successive plaster halves; two wall sets permit parallel casting. The present design has no integrated fasteners or established sealing tolerance. All pieces individually fit the configured 250 × 210 × 210 mm envelope; build-volume fit alone does not establish printability or one-bed packing.

## Two separate release problems, plus assembly

1. Remove the plaster pieces from the ceramic/object geometry, following an ordered sequence and checking each moving piece against everything still present.
2. Remove each cast plaster piece from its printed pattern/form. The inverse geometry can trap even when the final object can leave the plaster mould.
3. Remove walls/inserts/fasteners in a feasible order and account for their own clearances, keys and access. Check plaster-part mutual interference as well as object interference.

Current numeric depth assessment covers each plaster half versus the object-plus-gate cavity and each half versus its pattern. Historical strict checks also tested first-half versus second-half. Generic multipart sequence verification and full form assembly checks remain unfinished. Appearance approval cannot substitute for these checks.

## What current collision results mean

`pipeline.check_release` computes intersection **volume in mm³** at discrete poses. Its strict numerical tolerance was 0.001 mm³. Residual V7 peaks were approximately 0.0702 and 0.1191 mm³. Those volumes must never be compared to a 0.5 **mm depth** allowance.

`release_depth.check_release_depth` instead bounds distance of overlapping material below the fixed solid's surface. For each collision component it bounds nearest-surface distance on its boundary, then adds half the smaller enclosing slab thickness (from oriented and axis-aligned boxes) to cover the interior via the distance function's Lipschitz property. The boundary routine subdivides triangles and retains a conservative upper bound if its resource limit is reached. Non-volume 3D fragments use a convex enclosure; this can overstate penetration. Lower-dimensional contacts are skipped using a 1e-10 mm rank threshold. Numerical degeneracy merits dedicated validation before broad reuse.

Current parameters: spatial tolerance 0.02 mm; translations 0.025, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.75, 1, 1.5, 2, 3, 4, 8, 16, 32 and 64 mm. Initial pose is excluded in this demo because assembled halves/patterns are constructed as complementary Boolean solids. That rationale is specific to this construction; a generic tool must validate initial assembly explicitly.

Both halves are below the demo's allowance at these samples. This does not establish the maximum between samples. A bound above the threshold is **inconclusive**, unless a trustworthy measured penetration already exceeds it. Even a bound below it does not tell the operator exactly how much/where to sand to establish an unobstructed directional path. Validate a material-removal interpretation before offering automatic sanding instructions. Zero sampled overlap is also not a continuous-motion certificate.

Early diagnostics produced much larger numbers from convex enclosures of zero-thickness contacts and loose oriented bounding boxes. Those were algorithmic overestimates, not evidence of multi-millimetre physical undercuts. The final implementation filters lower-dimensional contacts and takes the tighter enclosing slab. Preserve regression cases rather than silently discarding inconvenient collision solids.

## Required orchestration improvements

The main `python -m mouldflow` command with `--workflow` requires approved input but suppresses masters/walls and submits plaster based on strict sampled-volume checks. It does not implement the full finishing policy, forms or export stages. Demo scripts manually bridge these gaps. A successor should add explicit stages and structured results rather than instructing a weaker model to reproduce that manual bridge.

Proposed result fields (new contract, not implemented): schema/version, input and settings hashes, stage/revision, named parts and units, technical status, appearance-review status, metric/threshold, sampling/method, unresolved feature IDs, artifact paths, `next_action`, and limitations. Use separate outcomes for `strict_pass`, `conditional_finishing`, `inconclusive`, `fail`, and `unsupported`. Keep model-facing commands finite and documented; validate schemas and return useful nonzero errors. Diagnostic generation must not bypass approval-gated final delivery.

Portability needs deliberate work: replace hard-coded paths; support a job directory; keep provenance stable across relocation; pin and test dependencies on the intended host; preserve exact approvals without blindly changing path-bound state. The snapshot is evidence and starting code, not an installable skill.

## Baseline test caveat

`test_scene_artifact.py` checks an older three-part study manifest and Blender file, not the current two-part mould. Those historical artifacts are included so the 45-test baseline remains reproducible. Passing that test says nothing about current V7 release. Replace or extend artifact checks for the current supported workflow when implementing it; keep historical fixtures clearly labelled.
