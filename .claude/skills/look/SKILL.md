---
name: look
description: Render and inspect mould geometry (STL files, plaster halves, release-check catches) with `mouldflow view`, then look at the pictures. Use after any change that produces or alters geometry, when a release check reports a location, or when the user says "show me", "look at", "what does it look like".
argument-hint: [mesh files or what to look at]
---

Look at geometry, don't just read metrics. What to look at: $ARGUMENTS
If that is empty, look at whatever geometry this session last produced or changed; ask only if there is none.

1. Pick a short name for the look (e.g. `teapot-halves`, `stage4-cube-catch`). Output goes to `look/<name>/` (git-ignored).
2. Render:
   ```bash
   uv run mouldflow view PATH=LABEL ... --out look/<name> [--up z] [--explode AXIS=MM] [--section AXIS=MM ...] [--marks-from RECORD.json] [--mark X0,Y0,Z0,X1,Y1,Z1]
   ```
   - Label every mesh (`object`, `half_1`, …). Mould halves: `--explode` along the withdrawal axis so the parting faces separate.
   - Release record with a `worst_location`: pass it with `--marks-from`, and add a `--section` through the middle of the marked box on the axis that cuts across the catch.
   - Default sections cut through the scene centre on x, y and z.
   - The command prints a `mouldflow.result/1` record. `status: error` → fix the reported input and rerun.
3. Read `look/<name>/views.png` and `look/<name>/sections.png` with the Read tool and actually look at them.
4. Tell the user, briefly: what each part is, anything surprising (gaps, slivers, open cavities, keys missing, catch location), and what the pictures can't settle. Pictures never change a release outcome. Numbers come from the checks.
5. Offer the rotatable view. Start the `look` server (preview_start name `look`, serves `look/` on port 8765) and open `http://localhost:8765/<name>/viewer.html` in the browser pane. It can toggle parts, change opacity, slide a section plane and zoom to marks.

For several angles, sections or rounds of looking (e.g. hunting a catch), hand off to the `mould-inspector` agent instead of iterating here.
