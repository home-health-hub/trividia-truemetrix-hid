"""Constants for the Trividia Health TRUE METRIX USB HID protocol.

Ported from Tidepool's open-source uploader driver
(lib/drivers/trividia/trueMetrix.js, BSD-2-Clause), the only known public
implementation of this protocol -- unlike viatom-o2ring-ble's five
cross-checked sources, everything here traces back to that one file, so
treat any detail not exercised by this package's tests as unverified until
confirmed against real hardware.

Covers all three models Tidepool's driver recognizes on one shared USB HID
protocol and vendor/product ID pair: TRUE METRIX (MR2), TRUE METRIX GO
(RC2), and TRUE METRIX AIR (BLU). Only TRUE METRIX AIR has been acquired
for real-hardware testing so far.
"""

MANUFACTURER = "Trividia Health"

#: USB HID vendor/product IDs, from Tidepool's driverManifests.js. Two
#: product IDs are listed there for the "TrueMetrix" entry with no
#: per-model breakdown, so both are treated as valid for any of the three
#: models below.
VENDOR_ID = 0x1F41  # 8001
PRODUCT_IDS = (0x0000, 0x0003)

#: Leading byte of every packet sent to the device.
HEADER = 0xA0

#: Seconds to wait for each HID input report while reading a response.
READ_TIMEOUT_SECONDS = 2.0

#: Command strings sent inside a packet body. Each is a parenthesized
#: command followed by a 2-character uppercase hex frame checksum (see
#: protocol.frame_checksum) -- these are the device's own fixed, checksummed
#: command strings, not something this package computes.
CMD_WAKEUP = "(^)AF"
CMD_IDENTIFY = "(I)9A"
CMD_GET_SERIAL = "(Z1)DC"
CMD_ACK = "(*)7B"
CMD_GET_RESULTS = "(G)98"
CMD_POWER_OFF = "(_)B0"
CMD_GET_FIRMWARE_VERSION = "(V)A7"
CMD_GET_METER_TIME = "(T)A5"

#: Type prefixes on decoded response messages, used to pick out which kind
#: of record a given "(...)" message contains.
TYPE_MODEL = "i"
TYPE_SERIAL = "z1"
TYPE_GLUCOSE = "g5"
TYPE_TIME = "t"
TYPE_CHECKSUM = "x"

#: Model code (as returned by CMD_IDENTIFY, TYPE_MODEL) to full model name.
MODELS = {
    "MR2": "TRUE METRIX",
    "RC2": "TRUE METRIX GO",
    "BLU": "TRUE METRIX AIR",
}

#: Per the TRUE METRIX user manual: readings above this are reported as
#: "HI" rather than a number, and vice versa for LOW_THRESHOLD. Tidepool's
#: driver clamps the stored value to one past the threshold rather than
#: keeping the raw decoded value, and this package does the same.
HIGH_THRESHOLD = 600
HIGH_CLAMPED_VALUE = 601
LOW_THRESHOLD = 20
LOW_CLAMPED_VALUE = 19

#: Minimum length of a decoded glucose ("g5") message's nibble string for
#: all fields this package parses to be present.
GLUCOSE_RECORD_MIN_LEN = 12

#: sundial.js format string for CMD_GET_METER_TIME's raw response, as used
#: by Tidepool's driver: two digits each of seconds, minutes, hours (24h),
#: day, month, and 2-digit year, with no separators. Equivalent Python
#: strptime format: "%S%M%H%d%m%y".
METER_TIME_STRPTIME_FORMAT = "%S%M%H%d%m%y"
