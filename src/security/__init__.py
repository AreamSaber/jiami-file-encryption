"""File-integrity helpers; verification is explicit, not automatic."""

from .anti_reverse import AntiReverse, verify_file_integrity

__all__ = ["AntiReverse", "verify_file_integrity"]
