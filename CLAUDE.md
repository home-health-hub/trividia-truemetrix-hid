# Project notes for trividia-truemetrix-hid

## Upstream source to watch

This library's entire protocol implementation (packet framing, checksum
algorithm, command set, glucose-record decoding) is ported from a single
external source -- unlike sibling libraries in this family (e.g.
viatom-o2ring-ble), which had multiple independent sources to cross-check
against, this one has only ever had one. A fix, a new device variant, or a
corrected protocol detail landing upstream could mean this port needs
updating too, with no independent way to notice except watching the
source directly.

- **Tidepool's uploader repo**: https://github.com/tidepool-org/uploader
  - Driver source: `lib/drivers/trividia/trueMetrix.js` (BSD-2-Clause) --
    the sole reference for everything this library implements.
  - USB vendor/product IDs + transport mode:
    `lib/core/driverManifests.js` (the `TrueMetrix` entry).
  - Default branch is `develop`, not `main`.
  - Last commit touching the driver as of this writing (2026-08-10):
    `9c451a5`, 2024-08-05, "improve messaging when there are no records on
    device". Check
    `git log --oneline -- lib/drivers/trividia/trueMetrix.js` on that
    branch periodically for anything newer, and diff against what's
    ported here if so.

- **glucometerutils**: https://github.com/glucometers-tech/glucometerutils
  Checked once (2026-08); no TRUE METRIX support as of then. If they add
  one later, it becomes a second independent source to cross-check this
  port against, the way viatom-o2ring-ble had five instead of one --
  worth another look periodically.

## Verification status

Protocol-correct-on-paper, not yet confirmed against real hardware -- see
the README's warning banner. Once tested against a real TRUE METRIX AIR
(a docking station has been ordered as of this writing), update or remove
that banner and this note.
