"""USB HID client for Trividia Health TRUE METRIX blood glucose meters.

The meter is a request/response device on one USB HID interface: every
operation is a single packet write followed by one or more input reports,
concatenated and decoded by `protocol.extract_messages`. There's no
persistent "connection" beyond having the HID handle open -- see
protocol.py's module docstring for the framing/message details this class
builds on.

Uses the `hidapi` package (`import hid`) for USB HID access. On Linux,
reading/writing the device as a non-root user typically requires a udev
rule granting access to Trividia's vendor ID -- see the README.
"""

from __future__ import annotations

import datetime
import logging

import hid

from . import protocol
from .const import (
    CMD_GET_FIRMWARE_VERSION,
    CMD_GET_METER_TIME,
    CMD_GET_RESULTS,
    CMD_GET_SERIAL,
    CMD_IDENTIFY,
    CMD_POWER_OFF,
    CMD_WAKEUP,
    METER_TIME_STRPTIME_FORMAT,
    PRODUCT_IDS,
    READ_TIMEOUT_SECONDS,
    TYPE_GLUCOSE,
    VENDOR_ID,
)
from .data import DeviceInfo, Reading

_LOGGER = logging.getLogger(__name__)

#: HID input reports are read in 64-byte chunks; report byte 0 says how many
#: of the rest are valid, matching the source's `length < 64` sanity check.
_REPORT_SIZE = 64


def discover() -> list[dict]:
    """Return `hid.enumerate()` entries for connected TRUE METRIX meters."""
    found = []
    for product_id in PRODUCT_IDS:
        found.extend(hid.enumerate(VENDOR_ID, product_id))
    return found


class TrueMetrixError(RuntimeError):
    """Raised for meter communication failures not covered by a more specific error."""


class ChecksumError(TrueMetrixError):
    """Raised when a downloaded batch of readings fails its checksum."""


class TrueMetrixClient:
    """Client for one TRUE METRIX meter over USB HID.

    Usage:

        with TrueMetrixClient() as client:
            info = client.get_device_info()
            readings = client.get_readings()

    If more than one meter is connected, pass `path` (from `discover()`)
    to pick a specific one; otherwise the first discovered device is used.
    """

    def __init__(self, path: bytes | None = None) -> None:
        self._path = path
        self._device: hid.Device | None = None

    def __enter__(self) -> TrueMetrixClient:
        self.open()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def open(self) -> None:
        """Open the HID connection, powering the meter off first.

        Tidepool's driver notes that on Windows, the device only accepts a
        connection on a second attempt unless powered off first and woken
        up later -- `get_device_info()` sends the wakeup, so callers should
        follow `open()` with it rather than assuming the meter is ready
        immediately after `open()` returns.
        """
        if self._device is not None:
            return
        if self._path is not None:
            device = hid.Device(path=self._path)
        else:
            devices = discover()
            if not devices:
                raise TrueMetrixError("No TRUE METRIX meter found. Is it in the cradle?")
            device = hid.Device(path=devices[0]["path"])
        self._device = device
        self._command_response(CMD_POWER_OFF)

    def close(self) -> None:
        """Power off and close the HID connection, if open.

        Unlike `open()`'s power-off (part of the connect handshake, which
        waits for a response), this is a fire-and-forget write -- the
        source does the same on disconnect, since the meter isn't expected
        to answer once told to power off, and waiting here would just
        block for the full read timeout every time.
        """
        if self._device is None:
            return
        try:
            self._device.write(protocol.build_packet(CMD_POWER_OFF))
        finally:
            self._device.close()
            self._device = None

    def _command_response(self, command: str) -> list[str]:
        if self._device is None:
            raise TrueMetrixError("Not connected")

        self._device.write(protocol.build_packet(command))

        raw = bytearray()
        while True:
            report = self._device.read(_REPORT_SIZE, timeout=int(READ_TIMEOUT_SECONDS * 1000))
            if not report:
                break
            length = report[0]
            if length < _REPORT_SIZE:
                raw.extend(report[1:length + 1])

        if not raw:
            return []
        messages = protocol.extract_messages(bytes(raw))
        _LOGGER.debug("%s -> %s", command, messages)
        return messages

    def get_device_info(self) -> DeviceInfo:
        """Wake the meter and read its model, serial, firmware, and clock."""
        self._command_response(CMD_WAKEUP)

        id_messages = self._command_response(CMD_IDENTIFY)
        id_messages += self._command_response(CMD_GET_SERIAL)
        parsed_id = protocol.parse_device_id(id_messages)
        if parsed_id is None:
            raise TrueMetrixError(
                "Could not read model/serial. Is a supported meter in the cradle?"
            )
        model_code, serial_number = parsed_id

        firmware_messages = self._command_response(CMD_GET_FIRMWARE_VERSION)
        firmware_version = firmware_messages[0] if firmware_messages else ""

        time_messages = self._command_response(CMD_GET_METER_TIME)
        meter_time = None
        if time_messages:
            meter_time = datetime.datetime.strptime(
                time_messages[0], METER_TIME_STRPTIME_FORMAT
            )

        return DeviceInfo(
            model=protocol.model_name(model_code),
            model_code=model_code,
            serial_number=serial_number,
            device_id=f"Trividia-{model_code}-{serial_number}",
            firmware_version=firmware_version,
            meter_time=meter_time,
        )

    def get_readings(self, *, include_control_solution: bool = False) -> list[Reading]:
        """Download and decode stored readings, verified against the meter's checksum.

        Raises ChecksumError if the batch's download checksum doesn't
        match -- per Tidepool's driver, this indicates possible data
        corruption and the batch should not be trusted.
        """
        messages = self._command_response(CMD_GET_RESULTS)
        glucose_messages = protocol.filter_by_type(messages, TYPE_GLUCOSE)
        checksum = protocol.parse_download_checksum(messages)

        if checksum is not None:
            payload = "".join(glucose_messages)
            if not protocol.verify_download_checksum(payload, checksum):
                raise ChecksumError("Downloaded readings failed checksum verification")

        readings = []
        for nibbles in glucose_messages:
            reading = protocol.parse_reading(nibbles)
            if reading is None:
                continue
            if reading.is_control_solution and not include_control_solution:
                continue
            readings.append(reading)
        return readings
