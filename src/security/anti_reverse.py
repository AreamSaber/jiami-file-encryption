"""Explicit SHA-256 file verification; no environment or process inspection.

The expected digest must come from a trusted source. Comparing an attacker-supplied
file with an attacker-supplied digest does not establish authenticity.
"""

import hashlib
import hmac
from typing import Optional


def verify_file_integrity(file_path: str, expected_hash: Optional[str]) -> bool:
    """Return True only for a readable file matching a valid SHA-256 digest.

    Missing/invalid digests and unreadable files fail closed. Hashing is streamed
    to avoid loading an entire file into memory.
    """
    if not isinstance(expected_hash, str) or len(expected_hash) != 64:
        return False
    normalized = expected_hash.lower()
    if any(char not in "0123456789abcdef" for char in normalized):
        return False
    digest = hashlib.sha256()
    try:
        with open(file_path, "rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except (OSError, ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hexdigest(), normalized)


class AntiReverse:
    """Compatibility name for the remaining file-integrity operation only."""

    def check_file_integrity(self, file_path: str,
                             expected_hash: Optional[str] = None) -> bool:
        return verify_file_integrity(file_path, expected_hash)
