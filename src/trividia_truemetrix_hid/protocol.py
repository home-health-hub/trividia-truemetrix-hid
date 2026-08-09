"""Packet framing and message decoding for the TRUE METRIX HID protocol.

Every packet sent to the device is `HEADER(1) | length(1) | command(var,
ASCII)`, where `command` is one of the fixed strings in `const` (each
already carrying its own frame checksum, e.g. `"(^)AF"`). The device
answers with one or more 64-byte HID input reports; report byte 0 is how
many of the remaining bytes are valid payload, and reports keep coming
until an empty one is read (see client.py). Concatenating and decoding
those payload bytes as one Latin-1 string (matching the original driver's
`String.fromCharCode` over raw byte values) yields a stream of
`(content)XX` messages, where `XX` is a 2-character uppercase hex frame
checksum over `content`.

Ported from Tidepool's uploader driver
(lib/drivers/trividia/trueMetrix.js, BSD-2-Clause) -- see const.py's module
docstring for source/verification caveats.
"""

from __future__ import annotations

import datetime
import re

from .const import (
    GLUCOSE_RECORD_MIN_LEN,
    HEADER,
    HIGH_CLAMPED_VALUE,
    HIGH_THRESHOLD,
    LOW_CLAMPED_VALUE,
    LOW_THRESHOLD,
    MODELS,
    TYPE_CHECKSUM,
    TYPE_MODEL,
    TYPE_SERIAL,
)
from .data import Reading

_MESSAGE_RE = re.compile(r"\(([^)]*)\)(\w{2})")


def build_packet(command: str) -> bytes:
    """Build the raw bytes for one request packet."""
    return bytes([HEADER, len(command)]) + command.encode("ascii")


def frame_checksum(frame: str) -> str:
    """Compute a message's frame checksum (the `XX` after its `(...)`).

    Sum of the ASCII codes of `frame`'s characters, plus the codes for the
    `(` and `)` frame delimiters, rendered as hex and truncated to the last
    2 characters -- *not* zero-padded if that leaves fewer than 2, matching
    the source exactly. In practice the summed value is always well above
    0x10 (it includes the fixed +0x51 for the delimiters), so this only
    matters for pathologically short/empty frames.
    """
    checksum = sum(ord(c) for c in frame) + 0x29 + 0x28
    return f"{checksum:X}"[-2:]


def download_checksum(payload: str) -> str:
    """Compute the checksum covering all glucose-record payloads together.

    Sum of the ASCII codes of every character in `payload`, rendered as
    4-character hex, zero-padded on the left if needed. Unlike
    `frame_checksum`, this one *is* zero-padded, matching the source.
    """
    checksum = sum(ord(c) for c in payload)
    return f"{checksum:X}"[-4:].rjust(4, "0")


def extract_messages(raw: bytes) -> list[str]:
    """Decode a raw response byte stream into checksum-verified messages.

    Bytes are decoded 1:1 as character codes (Latin-1), matching the
    source's `String.fromCharCode`. Messages whose frame checksum doesn't
    verify are silently dropped, same as the source.
    """
    text = raw.decode("latin-1")
    messages = []
    for match in _MESSAGE_RE.finditer(text):
        content, checksum = match.group(1), match.group(2)
        if frame_checksum(content).upper() == checksum.upper():
            messages.append(content)
    return messages


def filter_by_type(messages: list[str], type_prefix: str) -> list[str]:
    """Return the payloads of messages starting with `type_prefix`, prefix stripped."""
    return [m[len(type_prefix):] for m in messages if m.startswith(type_prefix)]


def remove_duplicates(values: list[str]) -> list[str]:
    """Return `values` with later duplicates of an earlier entry dropped."""
    seen: list[str] = []
    for value in values:
        if value not in seen:
            seen.append(value)
    return seen


def _safe_digit(char: str) -> int:
    """Decimal value of one digit character, or 0 if it isn't a digit.

    Mirrors JS's `ToNumber` coercion of a non-numeric string to `NaN`,
    which bitwise/arithmetic ops on the source then silently treat as 0.
    """
    return int(char) if char.isdigit() else 0


def parse_device_id(messages: list[str]) -> tuple[str, str] | None:
    """Extract (model_code, serial_number) from CMD_IDENTIFY + CMD_GET_SERIAL responses.

    `messages` should be the concatenated results of both commands. Returns
    None if either a model or serial message isn't present.
    """
    model_codes = remove_duplicates(filter_by_type(messages, TYPE_MODEL))
    serials = remove_duplicates(filter_by_type(messages, TYPE_SERIAL))
    if not model_codes or not serials:
        return None
    return model_codes[0], serials[0]


def parse_download_checksum(messages: list[str]) -> str | None:
    """Extract the download checksum value from CMD_GET_RESULTS response messages.

    Ported verbatim from the source, including one unexplained detail: after
    stripping the "x" type prefix, the source drops one further leading
    character before comparing against `download_checksum`'s 4-hex-digit
    output. Kept unchanged pending real-hardware confirmation of the exact
    checksum-record wire format.
    """
    checksums = remove_duplicates(filter_by_type(messages, TYPE_CHECKSUM))
    if not checksums or len(checksums[0]) < 2:
        return None
    return checksums[0][1:]


def verify_download_checksum(payload: str, expected: str) -> bool:
    """Check `payload` (concatenated glucose-record nibble strings) against `expected`."""
    return download_checksum(payload).upper() == expected.upper()


def parse_reading(nibbles: str) -> Reading | None:
    """Decode one CMD_GET_RESULTS glucose ("g5") message into a Reading.

    Returns None if `nibbles` is too short to contain the fields this
    package decodes. See the Reading and const.py docstrings for field
    semantics and the source of the day/year/time decoding's fragility --
    it's ported as-is from Tidepool's driver.
    """
    if len(nibbles) < GLUCOSE_RECORD_MIN_LEN:
        return None

    month = int(nibbles[0], 16)
    day_year = str(int(nibbles[1:4], 16))
    timestamp = str(int(nibbles[4:7], 16))
    year = int(day_year[-2:]) + 2000
    day = int(day_year[:-2]) if len(day_year) > 2 else 0
    hours = int(timestamp[:-2]) if len(timestamp) > 2 else 0
    minutes = int(timestamp[-2:])
    device_time = datetime.datetime(year, month, day, hours, minutes, 0)

    three_bits = _safe_digit(nibbles[7]) & 0x07
    value = (three_bits << 8) + int(nibbles[8:10], 16)

    out_of_range = None
    if value > HIGH_THRESHOLD:
        value = HIGH_CLAMPED_VALUE
        out_of_range = "high"
    elif value < LOW_THRESHOLD:
        value = LOW_CLAMPED_VALUE
        out_of_range = "low"

    is_control_solution = _safe_digit(nibbles[11]) != 0

    return Reading(
        value_mg_dl=value,
        out_of_range=out_of_range,
        device_time=device_time,
        is_control_solution=is_control_solution,
        raw=nibbles,
    )


def model_name(model_code: str) -> str:
    """Full model name for a model code, or the raw code if unrecognized."""
    return MODELS.get(model_code, model_code)
