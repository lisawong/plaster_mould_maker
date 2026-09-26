# Teapot V7 fixtures

Copied 2026-09-26 from the hash-verified prototype snapshot (`snapshot-manifest.json`). Every hash below matches the manifest.

These are **reference evidence for the Stage 5 regression**, not approval records. The user approved the plaster *appearance*; casting forms remain pending review. Do not treat these files as fabrication-ready, and do not reuse the demo's 0.5 mm finishing allowance for other jobs.

- `accepted-input.stl` — accepted source V7 as reviewed.
- `prepared_object.stl` — pipeline-normalized V7 used to generate the tooling (minor centering difference from the accepted input).
- `plaster_1.stl`, `plaster_2.stl` — the two reviewed plaster halves. Split plane Y=0; withdrawal ±Y.
- `settings.json` — tooling settings used (target 50 mm on Y, margin/backing 12 mm, gate 5 mm).
- `report.json` — prototype pipeline report.
- `depth-summary.json` — final sampled depth-bound summary (bounds, not continuous-motion proof).

| Fixture | Snapshot path | SHA-256 |
|---|---|---|
| `accepted-input.stl` | `outputs/base-repair-review-v7/input.stl` | `528a1b934cdb656a18287958a34bcf25bd0459205a52e72bd46cb80e85c3c730` |
| `prepared_object.stl` | `work/base-diagnostic-v7/prepared_object.stl` | `ec6375ecc43d696f230825966dc1730db0b5c0bb691602f109a620320499c729` |
| `plaster_1.stl` | `work/base-diagnostic-v7/reference_plaster/plaster_1.stl` | `8ad0f2e63d6ac409cf5142b469510e04f7384a8f89132044890f66f2d607e2c5` |
| `plaster_2.stl` | `work/base-diagnostic-v7/reference_plaster/plaster_2.stl` | `4a62b6be5fb6d347efe674dd8c2769033ee3a3d1611641d0dc56e50ae29383d7` |
| `settings.json` | `work/base-diagnostic-v7/settings.json` | `6308586a18ecf8bbd0d332791857e7cabd14d0f803d4721caa81afd54e8a20bc` |
| `report.json` | `work/base-diagnostic-v7/report.json` | `6a01d09c8b23c44a3960327b038188dc0a0e31b03352bbe8aec120c39979e10f` |
| `depth-summary.json` | `outputs/sanding-assessment-v7-final/summary.json` | `5edf0ce0a9cc21c403b23d038c71263a8235dccdaff492145239ba213b9028c0` |
