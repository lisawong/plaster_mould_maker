# Acceptance plan for a less capable operating model

This is a proposed evaluation protocol, not completed evidence. Select the operating model with the user before benchmarking. The authoring agent may be stronger; the operating model must complete supported runs using the packaged tools and instructions without author intervention.

## Build in tested increments

1. Preserve and run the 45-test baseline. Add tests before implementation for new stages or changed semantics.
2. Define schemas and a supported-scope contract, then complete state-machine orchestration and failure handling.
3. Expose existing geometry operations as parameterized commands and add missing assembly/release checks. Establish depth and contact semantics with independently known fixtures.
4. Automate exact-geometry review assets. Human decisions resume the same job and invalidate downstream artifacts when needed.
5. Run a second supported STL without source edits, then package and evaluate the operator skill.

## Geometry fixtures

| Fixture | Expected evidence |
|---|---|
| Clean convex solid | Supported partition candidate with independently checkable release directions. |
| Thin, wide overlap | Large mm³ volume does not imply a large mm depth; report the right metric. |
| Deep local catch | Measured lower bound over allowance fails; cannot be approved away as a numeric pass. |
| Bound wider than known depth | Report inconclusive or refine it; distinguish upper bound from measured value. |
| Zero-thickness contact and near-coplanar 3D sliver | Separate actual volumetric penetration from contact robustly; retain numerical evidence. |
| Catch between coarse samples | Refinement or continuous checking detects it, or the report explicitly remains insufficient. |
| Invalid/self-intersecting mesh | Reject or route to bounded repair review; watertightness alone is insufficient. |
| Hole/handle with trapped core | Supported multipart candidate or explicit unsupported escalation, not an invented two-part success. |
| Registration features and staged removal | Check moving parts against remaining parts in the declared order. |
| Good plaster release but trapped printed form | Fail the second release problem separately. |
| Printer-too-small geometry | Valid alternative orientation/partition or clear failure; no silent scale change. |

Stage 2 implements the release-depth rows (thin overlap, deep catch, loose bound, contact/sliver, between-sample catch, invalid mesh) as `mouldflow.known_answers` fixtures, asserted in `tests/test_known_answers.py`. Partition, staged-removal, form and printer rows arrive with their stages.

## State and human-review tests

- A pending gate blocks its dependent stage; a missing response never becomes approval.
- Geometry/configuration changes invalidate downstream review and exports.
- Resumption retains exact decisions and hashes. Relocation is verified, not treated as permission to reapprove.
- User requests a shorter spout retaining its end shape: show before/after, preserve the authorized scope and ask about any newly affected feature.
- Appearance approval does not erase strict collisions, uncertainty, or physical-validation limitations.
- A demo-specific finishing tolerance does not silently become another job's default.
- Generated candidates are distinguishable from approved final exports in state, filenames/manifest and operator communication.

## Operator evaluation

Give the model a clean job folder, the skill, installed tools, a fixture STL and only the needed user requirements. Do not include the expected answer or this experiment's final geometry. Use a human or scripted test harness to supply checkpoint choices explicitly; simulated approval is confined to evaluation data.

Run at least three fresh trials for each of: supported convex input; another supported non-teapot STL; a preserve-versus-simplify branch; an unsupported undercut; invalid geometry; and resuming after a changed approved input. This trial count is a proposed minimum, not statistical proof. Record commands, errors, review questions, outputs, hashes, costs/time if available and any author intervention.

Acceptance requires every safety-critical gate/metric distinction to hold in every trial, supported outputs to meet the numerical contracts, unsupported cases to stop usefully, and each requested review to supply whole-object context and a rotatable view. Record variability in successful completion, unnecessary user questions and interventions. Any core source edit by the operator to finish a supposedly supported job is evidence that the workflow is not yet sufficiently packaged.

The final report should state supported input classes, tested platform/model, artifact checks, remaining numerical/physical limitations and failures. Keep slicer validation, printed fit and physical demoulding as separate evidence categories. User physical feedback can validate the demo later; it does not automatically prove arbitrary-STL support.
