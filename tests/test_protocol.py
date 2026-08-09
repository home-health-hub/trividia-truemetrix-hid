from __future__ import annotations

import datetime

from trividia_truemetrix_hid.protocol import (
    build_packet,
    download_checksum,
    extract_messages,
    filter_by_type,
    frame_checksum,
    model_name,
    parse_device_id,
    parse_download_checksum,
    parse_reading,
    remove_duplicates,
    verify_download_checksum,
)

# Tidepool's driver hardcodes eight command strings, each a
# parenthesized command plus its own 2-character frame checksum. These
# are the device's real accepted commands, so they double as known-good
# test vectors for frame_checksum -- no synthetic data needed here.
_KNOWN_COMMANDS = {
    "^": "AF",  # WAKEUP
    "I": "9A",  # IDENTIFY
    "Z1": "DC",  # GET_SERIAL
    "*": "7B",  # ACK
    "G": "98",  # GET_RESULTS
    "_": "B0",  # POWER_OFF
    "V": "A7",  # GET_FIRMWARE_VERSION
    "T": "A5",  # GET_METER_TIME
}


def test_frame_checksum_matches_known_device_commands():
    for content, expected in _KNOWN_COMMANDS.items():
        assert frame_checksum(content) == expected


def test_build_packet_matches_known_wakeup_command():
    assert build_packet("(^)AF") == bytes([0xA0, 5]) + b"(^)AF"


def test_build_packet_length_byte_is_command_length():
    command = "(Z1)DC"
    packet = build_packet(command)
    assert packet[0] == 0xA0
    assert packet[1] == len(command)
    assert packet[2:] == command.encode("ascii")


def test_extract_messages_accepts_valid_frame():
    raw = "(^)AF".encode("latin-1")
    assert extract_messages(raw) == ["^"]


def test_extract_messages_rejects_bad_checksum():
    raw = "(^)00".encode("latin-1")
    assert extract_messages(raw) == []


def test_extract_messages_finds_multiple_frames_in_one_stream():
    bad_checksums = "(iBLU)00(z112345678)00"
    assert extract_messages(bad_checksums.encode("latin-1")) == []

    valid = f"(iBLU){frame_checksum('iBLU')}(z112345678){frame_checksum('z112345678')}"
    assert extract_messages(valid.encode("latin-1")) == ["iBLU", "z112345678"]


def test_filter_by_type_strips_prefix():
    assert filter_by_type(["iBLU", "z112345678", "g5xyz"], "i") == ["BLU"]
    assert filter_by_type(["iBLU", "z112345678", "g5xyz"], "z1") == ["12345678"]


def test_remove_duplicates_keeps_first_occurrence_order():
    assert remove_duplicates(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]


def test_parse_device_id_combines_identify_and_serial_responses():
    messages = ["iBLU", "z112345678"]
    assert parse_device_id(messages) == ("BLU", "12345678")


def test_parse_device_id_returns_none_when_incomplete():
    assert parse_device_id(["iBLU"]) is None


def test_model_name_looks_up_known_codes():
    assert model_name("BLU") == "TRUE METRIX AIR"
    assert model_name("MR2") == "TRUE METRIX"
    assert model_name("RC2") == "TRUE METRIX GO"


def test_model_name_falls_back_to_raw_code():
    assert model_name("ZZZ") == "ZZZ"


def test_download_checksum_is_zero_padded_to_four_digits():
    # Sum of an empty payload is 0; the source zero-pads this case, unlike
    # frame_checksum which does not.
    assert download_checksum("") == "0000"


def test_download_checksum_round_trips_with_verify():
    payload = "65F659D07800" + "65F659D07801"
    checksum = download_checksum(payload)
    assert verify_download_checksum(payload, checksum)
    assert not verify_download_checksum(payload + "x", checksum)


def test_parse_download_checksum_drops_extra_leading_character():
    # See parse_download_checksum's docstring: after the "x" type prefix is
    # stripped, one more leading character is dropped, per the source.
    assert parse_download_checksum(["xQABCD"]) == "ABCD"


def test_parse_download_checksum_returns_none_when_absent():
    assert parse_download_checksum(["iBLU"]) is None


def test_parse_reading_decodes_a_normal_value():
    # Encodes month=6, day=15, year=2026, hour=14, minute=37, value=120
    # mg/dL (three_bits=0, low byte 0x78), not a control solution.
    nibbles = "65F659D07800"
    reading = parse_reading(nibbles)

    assert reading is not None
    assert reading.value_mg_dl == 120
    assert reading.out_of_range is None
    assert reading.is_control_solution is False
    assert reading.device_time == datetime.datetime(2026, 6, 15, 14, 37, 0)
    assert reading.raw == nibbles


def test_parse_reading_clamps_high_value():
    # Same date/time fields as above; three_bits=2, low byte 0xBC -> 700.
    nibbles = "65F659D2BC00"
    reading = parse_reading(nibbles)
    assert reading is not None
    assert reading.value_mg_dl == 601
    assert reading.out_of_range == "high"


def test_parse_reading_clamps_low_value():
    # three_bits=0, low byte 0x0A -> 10.
    nibbles = "65F659D00A00"
    reading = parse_reading(nibbles)
    assert reading is not None
    assert reading.value_mg_dl == 19
    assert reading.out_of_range == "low"


def test_parse_reading_flags_control_solution():
    # Same as the normal-value case, but with the control-solution flag
    # (index 11) set to '1' instead of '0'.
    nibbles = "65F659D07801"
    assert len(nibbles) == 12
    reading = parse_reading(nibbles)
    assert reading is not None
    assert reading.is_control_solution is True


def test_parse_reading_returns_none_when_too_short():
    assert parse_reading("65F659D0780") is None
