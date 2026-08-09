"""Data types for the TRUE METRIX HID protocol."""

from __future__ import annotations

import dataclasses
import datetime


@dataclasses.dataclass
class Reading:
    """A single decoded blood-glucose record from CMD_GET_RESULTS.

    Attributes:
        value_mg_dl: Blood glucose value, mg/dL. Clamped to 601 or 19 when
            out_of_range is set -- see out_of_range.
        out_of_range: "high" if the meter reported this as "HI" (raw value
            over 600, per the user manual), "low" if reported as "LO" (raw
            value under 20), otherwise None.
        device_time: Timestamp as read from the meter's own clock, decoded
            from the record's embedded month/day/year/hour/minute fields.
            Not timezone-aware -- the meter has no timezone concept, only
            common.checkDeviceTime()-style drift detection against the
            host clock (not implemented by this package).
        is_control_solution: True if the meter flagged this as a control
            solution test rather than a real reading. TrueMetrixClient
            excludes these from get_readings() by default -- see its
            include_control_solution parameter -- matching Tidepool's own
            checklist, which says these should be discarded until a data
            model for them exists.
        raw: The undecoded nibble string this reading was parsed from.
    """

    value_mg_dl: int
    out_of_range: str | None
    device_time: datetime.datetime
    is_control_solution: bool
    raw: str


@dataclasses.dataclass
class DeviceInfo:
    """Device identity and clock, from CMD_IDENTIFY/GET_SERIAL/GET_FIRMWARE_VERSION/GET_METER_TIME.

    Attributes:
        model: Full model name (e.g. "TRUE METRIX AIR"), looked up from
            model_code via const.MODELS.
        model_code: Raw 3-character model code reported by the meter
            (e.g. "BLU").
        serial_number: Device serial number.
        device_id: Synthesized identifier in the same
            "Trividia-<code>-<serial>" form Tidepool's uploader used, for
            anyone matching records against previously-uploaded Tidepool
            data.
        firmware_version: Firmware version string, as reported verbatim.
        meter_time: The meter's own clock at the time of the request,
            decoded from CMD_GET_METER_TIME. Not timezone-aware. None if
            the meter didn't respond to the request.
    """

    model: str
    model_code: str
    serial_number: str
    device_id: str
    firmware_version: str
    meter_time: datetime.datetime | None
