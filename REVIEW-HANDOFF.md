# Stage 2.5 review fixes

Status: **all three findings resolved** on `claude/stage-2-5-view` (see Resolution at the end).

Review scope: `git diff main...HEAD`, through `f138aa7`; base `main` was `20bb26b`. The review made no implementation changes. Relevant requirements: [PLAN.md](PLAN.md), Stage 2.5; [PRD.md](PRD.md), R9.1/R9.2; [TECHNICAL-REFERENCE.md](TECHNICAL-REFERENCE.md), Visual inspection.

## Workflow and completion

1. Read each finding below and add its failing regression tests in `tests/test_view.py` **before** changing implementation. Confirm each fails for the reported reason.
2. Fix `src/mouldflow/view.py` and, if needed, `src/mouldflow/cli.py`. Keep section summaries, renderer behavior, and operator documentation consistent.
3. Run `.venv/bin/python -m pytest tests/test_view.py -q`, then `.venv/bin/python -m pytest -q`. Use `uv run` if the existing venv is unavailable.
4. Use the project's `look` skill to render and visually inspect the changed section output: open box, closed box, annulus, and a plane missing the mesh. Confirm open paths remain visible, closed material is filled, and holes remain open.
5. Update this note with resolution/test evidence and record the work in `SESSION_LOG.md`. Completion means all three regressions pass, the full suite passes, and the relevant operator instructions describe the resulting behavior.

Review baseline: **166 tests passed, 72 subtests passed**, with one existing trimesh divide warning in `test_local_insert.py`. These tests did not cover the findings below. Browser interactions were not exercised during this review.

## 1. P2 — Malformed release records bypass JSON errors

Location: `src/mouldflow/view.py`, `marks_from_record` (reviewed lines 94–100); CLI error handling in `cli.run`.

Reproduction: create a valid box STL and a JSON file containing `[]`, then run:

```sh
mouldflow view box.stl --out look/review-invalid-record --marks-from invalid.json
```

Observed: exit 1, empty stdout, and `AttributeError: 'list' object has no attribute 'get'`. The exception bypasses the promised `mouldflow.result/1` error record. PRD R9.1/R9.2 require versioned JSON and actionable failures.

Fix direction: validate the top-level object, nested location object, and bounds structure before accessing them. Raise `ViewError` with an actionable message for invalid records. Preserve legitimate records with no catch location.

Acceptance tests:

- A JSON array produces exit 2 and a parseable error result with `error` and `next_action`.
- Malformed nested location/bounds also produce structured errors; validate finite, ordered 2-by-3 bounds.
- Both supported record shapes still work; valid records without a location still produce no marks.

## 2. P2 — Open sections are reported as empty

Location: `src/mouldflow/view.py`, `_cut` (reviewed lines 165–176), `section_loops`, and `render_sections` (empty-section label at lines 337–338).

Reproduce in Python:

```python
import trimesh
from mouldflow import view

mesh = trimesh.creation.box(extents=(10, 10, 10))
mesh.update_faces(mesh.face_normals[:, 0] < 0.5)  # remove the +X wall
section = mesh.section(plane_origin=[0, 0, 0], plane_normal=[0, 0, 1])
print(len(section.entities), len(section.discrete))  # 1, 0
print(view.section_loops([view.Item('open_box', mesh)], 'z', 0))
```

Observed: the intersection contains a U-shaped path, but the summary reports `loops=0`, `bounds_mm=None`; the renderer says “no material on this plane.” `_cut` uses only `section.discrete`, which excludes open paths. The viewer accepts non-watertight meshes, so damaged geometry can disappear from the evidence.

Fix direction: retain open intersection paths, draw them unfilled, and distinguish open sections from empty intersections in the summary. Keep closed-loop counts meaningful. Update the “0 loops means no material” interpretation in `TECHNICAL-REFERENCE.md` and `.claude/agents/mould-inspector.md` to match the new contract.

Acceptance tests:

- The open box above has visible intersection paths and nonempty bounds, without an empty-material message or invented closing edge/fill.
- A closed box remains filled; an annulus retains its hole.
- A plane missing the mesh remains genuinely empty.

## 3. P2 — Colour collisions break stability between rounds

Location: `src/mouldflow/view.py`, `colours` (reviewed lines 211–222).

Reproduction:

```python
from mouldflow.view import colours
print(colours(['wall', 'pattern']))
# wall: #8c8c8c, pattern: #7f6a5a
print(colours(['pattern', 'wall']))
# pattern: #8c8c8c, wall: #7f6a5a
print(colours(['pattern']))
# pattern: #8c8c8c
```

Observed: collision handling depends on argument order and membership. This violates the documented promise that a part keeps its colour between renders, including the explicitly recommended workflow of viewing one part alone.

Fix direction: choose a deterministic per-label assignment independent of the current list, or persist an explicit palette across rounds. Sorting the current list alone does not solve subset instability. Resolve the tradeoff with the existing test requiring unique colours for eight selected labels; preserve the documented stability contract rather than merely testing non-colliding labels.

Acceptance tests: colliding labels retain their colours when reordered, viewed alone, or rendered with additional labels. Inspect the legend and mesh colours for consistency.

## Resolution (2026-10-17, Claude Code)

The tests were written first. Each failed for the reported reason before the fix: empty stdout and `AttributeError` or opaque numpy errors; missing `open_paths`; `{'wall': '#7f6a5a'} != {'wall': '#8c8c8c'}`.

| # | Fix | Regression tests (`tests/test_view.py`) |
|---|---|---|
| 1 | `marks_from_record` checks the top level, `details`, `worst_location` and `bounds_mm` (numeric, 2 × 3, finite, min ≤ max). On failure it raises `ViewError` naming the file, and the CLI returns exit 2 with a JSON `error` and `next_action`. No location and null bounds still give no marks. | `test_malformed_release_records_give_json_errors` (7 cases), `test_record_with_null_bounds_gives_no_marks`, plus the existing two-shape and no-location tests |
| 2 | `_cut` keeps `section.dangling` open paths. Summaries report `loops` (closed), `open_paths` and bounds over both, and each plane reports `empty`. Open paths are drawn dashed and never closed or filled, with a note on the panel. | `test_open_section_paths_are_kept_not_reported_empty`, `test_closed_and_missed_sections_count_no_open_paths`, `test_open_paths_are_drawn_unfilled`, plus the existing annulus and miss tests |
| 3 | `label_colour` depends only on the label. `object`, `half_1` and `half_2` have fixed colours; other labels get a crc32 hue in 30–330° (clear of mark red) and adler32 lightness. On the tradeoff: render-to-render stability wins. The old "8 labels → 8 unique palette slots" test is replaced; distinct labels still give distinct hex colours in practice (42-label check), but similar shades are possible. | `test_colour_is_a_pure_function_of_label` (5 cases, including the `wall`/`pattern` reproduction), `test_hashed_colours_differ_and_stay_clear_of_mark_red`, `test_colours_follow_labels_not_argument_order` |

**Evidence**
- `uv run pytest tests/test_view.py -q` gives 40 passed.
- `uv run pytest -q` gives 183 passed and 72 subtests, with the one existing trimesh warning.
- Visual check with `/look`, in `look/review-sections/` (git-ignored). The meshes were a closed box, an open box (+X wall removed) and an annulus, cut at Z=0.5 and Z=20:
  - open box: dashed U, unfilled, no invented closing edge;
  - closed box: filled;
  - annulus: hole open;
  - Z=20: "nothing intersects this plane" with `empty: true`.
  The legend and mesh colours agree.

Docs updated: TECHNICAL-REFERENCE (Visual inspection contract), `.claude/agents/mould-inspector.md` (loop/open-path rule, colour wording), PLAN status, SCRATCHPAD decision, SESSION_LOG. Browser interactions in `viewer.html` were not re-exercised; these fixes don't touch the viewer.
