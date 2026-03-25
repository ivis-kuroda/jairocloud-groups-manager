import re
import typing as t

from server.clients import utils


if t.TYPE_CHECKING:
    import pytest


def test_get_time_stamp_returns_int_timestamp_string(monkeypatch: pytest.MonkeyPatch):
    """A fixed input should always make a fixed output"""

    fixed_time = 1700000000.987654
    expecter_timestamp = "1700000000"
    monkeypatch.setattr(utils.time, "time", lambda: fixed_time)
    result = utils.get_time_stamp()
    assert result == expecter_timestamp


def test_compute_signature_matches_expected_hash():
    """A known input should make a known SHA-256 hash"""
    cs = "secret"
    at = "token"
    ts = "1700000000"
    expected = utils.hashlib.sha256(f"{cs}{at}{ts}".encode()).hexdigest()
    result = utils.compute_signature(cs, at, ts)
    assert result == expected


def test_compute_signature_returns_sha256_hex_format():
    """The return value should be a SHA-256 hash"""
    expected_length = 64
    out = utils.compute_signature("a", "b", "c")
    assert isinstance(out, str)
    assert len(out) == expected_length
    assert re.fullmatch(r"[0-9a-f]{64}", out)


def test__compute_signature_changes_when_input_changes():
    """If one character in the input changes, the output hash should also change"""
    base = utils.compute_signature("s", "t", "1")
    changed = utils.compute_signature("s", "t", "2")
    assert base != changed
