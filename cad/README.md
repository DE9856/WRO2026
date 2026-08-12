# cad/ — chassis design status (in fabrication)

## Current status

Sky Flyers' competition chassis is a **custom 3D-printed design** and is
**currently in fabrication**. It is not expected to be finished before
this documentation submission (WRO §7's final-commit deadline, ~2 weeks
/ ~15 days before competition), so this folder is mid-transition:

- `chassis_placeholder.stl` — the original **bounding-box reference**
  (two axis-aligned boxes: the WRO §11.1 max legal envelope,
  300×200×300 mm, and a rough plate placeholder inside it). This is
  **not** a design of the vehicle — it exists only as a correctly-scaled
  volume to design against.
- The **real chassis STL/source files** are being added directly by the
  team as they come off the printer/CAD software. Once added, they
  should replace or sit alongside `chassis_placeholder.stl` (delete the
  placeholder once the real files make it redundant, or keep it in a
  `reference/` subfolder if the envelope box is still useful).

See `ENGINEERING_JOURNAL.md` → *Criterion 1 → "Chassis manufacturing
status and submission timeline"* for the full, formal explanation of
why the physical chassis isn't finished yet, what's being submitted
in its place, and what happens between submission and competition day.

## Why this isn't a finished CAD deliverable yet

A finished CAD deliverable should let a judge or another team see
mounting-hole spacing, motor bracket geometry, camera-mount angle and
offset, and wheel/axle positions, and — ideally — reproduce the physical
part. The design intent for the new chassis exists, but final print
completion, fit-check, and any print-driven revisions are still
in progress. Rather than presenting an unfinished or unverified part as
final, this is documented as an open item — consistent with how this
whole repository has handled every other hardware-blocked gap (see
`CHANGELOG.md`'s note on removing an unverified "tested over 20+ runs"
claim): an honest in-progress status is worth more to a judge than a
part that looks finished but hasn't actually been validated.

## What happens next

1. **Team:** drop the real chassis STL (and source CAD file — Fusion
   360 / FreeCAD / SolidWorks / OnShape export, whichever was used) into
   this folder as soon as they're ready, even if that's after this
   GitHub submission's scored deadline — vehicle-check readiness matters
   regardless of the scoring cutoff.
2. Update this README's bullet list above to describe what each file
   actually is (chassis plate, sensor mount, motor bracket, etc.) —
   Appendix C, Criterion 1 (Mobility and Mechanical Design) specifically
   rewards diagrams and reasoning here, not just raw files sitting in a
   folder.
3. Once the finished chassis is weighed and measured, update the BOM
   weight figure in `docs/index.html` and the *Testing status* note in
   `ENGINEERING_JOURNAL.md` from "estimated" to "measured."
4. Delete `chassis_placeholder.stl` once it's no longer needed as a
   reference envelope.
