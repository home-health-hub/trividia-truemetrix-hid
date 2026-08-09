# trividia-truemetrix-hid

A standalone Python USB HID client for Trividia Health TRUE METRIX blood
glucose meters: TRUE METRIX, TRUE METRIX GO, and TRUE METRIX AIR. It reads
device identity and stored glucose readings directly from the meter over
USB HID and keeps everything local -- there's no dependency on Tidepool's
cloud service or any other third party.

> [!WARNING]
> **Work in progress -- only TRUE METRIX AIR is confirmed on order for
> real-hardware testing, and even that hasn't happened yet.** Every
> protocol detail here is ported from one source (see
> [Acknowledgments](#acknowledgments)), not from testing against actual
> hardware. Treat this as protocol-correct-on-paper rather than
> field-verified until that's happened. This notice will be removed once
> confirmed against real hardware.

## Disclaimer

This is an unofficial, reverse-engineered client, ported from Tidepool's
open-source uploader driver. The author and contributors are not
affiliated with Trividia Health or Tidepool. **This is a personal-use tool
for reading data from your own meter, not a medical product.** Don't use
it to make treatment decisions -- read your meter's own display for that.

## Features

- Discovers connected TRUE METRIX meters over USB HID (no cable/dock
  driver installation beyond standard OS HID support).
- Reads device identity: model, serial number, firmware version, and the
  meter's own clock.
- Downloads stored glucose readings, verified against the meter's own
  checksum, with out-of-range ("HI"/"LO") flagging matching the device's
  own display logic.
- Excludes control-solution test strips from readings by default (they
  aren't real patient data), with an opt-in flag to include them.
- Ships a `trividia-truemetrix` CLI for one-off use without writing any code.
- Nothing here uploads anywhere -- reads stay local unless you choose to
  write them out yourself (e.g. via `--csv`).

## Requirements

- A Trividia Health TRUE METRIX meter and a USB cable or docking station
  (TRUE METRIX and TRUE METRIX AIR need the docking station; TRUE METRIX GO
  takes a direct Micro-USB cable).
- The [`hidapi`](https://pypi.org/project/hidapi/) Python package, which
  wraps the system `hidapi` library. On Debian/Ubuntu, install the
  system library first: `sudo apt install libhidapi-hidraw0`.
- On Linux, non-root USB HID access typically needs a udev rule. Create
  `/etc/udev/rules.d/99-truemetrix.rules` with:

  ```
  SUBSYSTEM=="hidraw", ATTRS{idVendor}=="1f41", MODE="0666"
  ```

  then `sudo udevadm control --reload-rules && sudo udevadm trigger`.

## Installation

```bash
pip install git+https://github.com/bonelifer/trividia-truemetrix-hid.git
```

## Library usage

```python
from trividia_truemetrix_hid import TrueMetrixClient

with TrueMetrixClient() as client:
    info = client.get_device_info()
    print(info.model, info.serial_number, info.firmware_version)

    for reading in client.get_readings():
        flag = f" ({reading.out_of_range})" if reading.out_of_range else ""
        print(f"{reading.device_time}  {reading.value_mg_dl} mg/dL{flag}")
```

### Discovering a specific meter

If more than one meter could be connected, pick one explicitly:

```python
from trividia_truemetrix_hid import TrueMetrixClient, discover

devices = discover()
with TrueMetrixClient(path=devices[0]["path"]) as client:
    ...
```

## CLI usage

```bash
# List connected meters
trividia-truemetrix --discover

# Print device info and exit
trividia-truemetrix --info

# Print device info + all readings as JSON
trividia-truemetrix

# Write readings to a CSV file instead
trividia-truemetrix --csv readings.csv

# Include control-solution test records too
trividia-truemetrix --csv readings.csv --include-control-solution
```

Run `trividia-truemetrix --help` for all options.

## Protocol notes

The meter is a USB HID device (vendor ID `0x1F41`, product ID `0x0000` or
`0x0003`) that speaks a simple request/response protocol: every packet is
`HEADER(0xA0) | length | command`, where `command` is one of eight fixed,
self-checksummed ASCII strings (e.g. `"(^)AF"` for wake-up). Responses
arrive as one or more 64-byte HID input reports (byte 0 = valid payload
length) that decode to a stream of `(content)XX` messages, each with its
own 2-character frame checksum.

Glucose readings come back as `g5`-prefixed messages, each a 12-character
hex/decimal nibble string encoding the record's date, time, value, and a
control-solution flag; a final `x`-prefixed message carries a checksum
over all of them together. See
[`protocol.py`](src/trividia_truemetrix_hid/protocol.py) and
[`const.py`](src/trividia_truemetrix_hid/const.py) for the exact framing,
checksum algorithms, and nibble layout, each documented at the point
they're used.

### Known quirks ported as-is

A few details in the source don't have an obvious explanation but are
kept exactly as written, pending real-hardware confirmation:

- The frame checksum (`protocol.frame_checksum`) is *not* zero-padded if
  it would otherwise be under 2 hex digits, while the download checksum
  (`protocol.download_checksum`) *is* zero-padded to 4 digits. This
  asymmetry is in the source, not a design choice made here.
- `protocol.parse_download_checksum` drops one extra leading character
  after stripping the `x` type prefix, before the result is compared
  against the computed download checksum.
- The date/time nibble decoding reinterprets a hex value as a decimal
  string and slices that string for day/year and hour/minute -- a
  two-step encoding that's fragile by construction (see
  `protocol.parse_reading`'s docstring) but is what the source does.

### Not yet implemented

Per Tidepool's own implementation checklist for this device, several
things aren't modeled here either: the unit reported by the meter (glucose
values are always mg/dL, matching the source, rather than read from the
device), date/time setting change logs, and ketone measurements (some
TRUE METRIX variants support ketone testing; this protocol's ketone
commands, if any, aren't in the source this package was ported from).

## Contributing

Contributions are welcome!

- **Bug reports**: [Open an issue](https://github.com/bonelifer/trividia-truemetrix-hid/issues).
- **Everything else** (questions, feature requests, ideas, general discussion): [Use Discussions](https://github.com/bonelifer/trividia-truemetrix-hid/discussions).
- Pull requests are welcome for bug fixes or discussed features.

## Acknowledgments

- Protocol ported from [tidepool-org/uploader](https://github.com/tidepool-org/uploader)'s
  `lib/drivers/trividia/trueMetrix.js` (BSD-2-Clause), the only known
  public implementation of this device's protocol. USB vendor/product IDs
  come from the same repository's `lib/core/driverManifests.js`.
- Code review, ported implementation, and documentation assisted by [Claude](https://www.anthropic.com/claude).

## License

This project is licensed under the **GNU General Public License v3.0**.

See [LICENSE](LICENSE) for more information.
