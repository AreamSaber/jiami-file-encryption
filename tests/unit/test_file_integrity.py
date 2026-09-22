"""Integrity checks must never report unverified or altered files as valid."""

import hashlib

import pytest

from src.security import AntiReverse, verify_file_integrity


@pytest.mark.parametrize(
    "contents", [b"", b"example", b"x" * (2 * 1024 * 1024 + 17)],
    ids=["empty", "small", "multiple-chunks"],
)
def test_known_digest_verifies_file(tmp_path, contents):
    path = tmp_path / "data.bin"
    path.write_bytes(contents)
    expected = hashlib.sha256(contents).hexdigest()
    assert verify_file_integrity(path, expected)
    assert AntiReverse().check_file_integrity(path, expected.upper())


def test_altered_file_fails_verification(tmp_path):
    path = tmp_path / "data.bin"
    path.write_bytes(b"original")
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    path.write_bytes(b"modified")
    assert not verify_file_integrity(path, expected)


@pytest.mark.parametrize("expected", [None, "", "0" * 63, "g" * 64, " " * 64, 123])
def test_missing_or_invalid_digest_never_passes(tmp_path, expected):
    path = tmp_path / "data.bin"
    path.write_bytes(b"original")
    assert not AntiReverse().check_file_integrity(path, expected)


def test_missing_file_or_directory_never_passes(tmp_path):
    expected = hashlib.sha256(b"").hexdigest()
    assert not verify_file_integrity(tmp_path / "missing", expected)
    assert not verify_file_integrity(tmp_path, expected)


def test_read_failure_never_passes(tmp_path, monkeypatch):
    path = tmp_path / "data.bin"
    path.write_bytes(b"original")

    def inaccessible(*args, **kwargs):
        raise PermissionError("Access denied")

    monkeypatch.setattr("builtins.open", inaccessible)
    assert not verify_file_integrity(path, hashlib.sha256(b"original").hexdigest())
