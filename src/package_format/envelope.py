"""Bounded v1 frames. Authentication always covers the original wire bytes."""
import hmac
import json
import math
import os
import struct

from src.exceptions.decryption_errors import CorruptedDataError, InvalidMetadataError, IntegrityVerificationError

MAX_HEADER = 1 << 20
MAX_BODY = 1 << 30  # Current engines operate in memory; reject before allocating.
MAX_DEPTH = 16
MAX_COLLECTION = 100000


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidMetadataError('Duplicate JSON key')
        result[key] = value
    return result


def _reject_constant(value):
    raise InvalidMetadataError('Non-finite JSON number')


def check_tree(value, depth=0):
    if depth > MAX_DEPTH:
        raise InvalidMetadataError('Metadata nesting limit exceeded')
    if type(value) is float and not math.isfinite(value):
        raise InvalidMetadataError('Non-finite JSON number')
    if isinstance(value, (list, dict)):
        limit = 10000 if isinstance(value, dict) else MAX_COLLECTION
        if len(value) > limit:
            raise InvalidMetadataError('Metadata collection limit exceeded')
        for item in value.values() if isinstance(value, dict) else value:
            check_tree(item, depth + 1)


def json_bytes(value):
    check_tree(value)
    try:
        raw = json.dumps(value, ensure_ascii=True, sort_keys=True,
                         separators=(',', ':'), allow_nan=False).encode('utf-8')
    except (TypeError, ValueError) as exc:
        raise InvalidMetadataError('Metadata is not JSON data') from exc
    if len(raw) > MAX_HEADER:
        raise InvalidMetadataError('Metadata exceeds 1 MiB')
    return raw


def parse_json(raw):
    if len(raw) > MAX_HEADER:
        raise InvalidMetadataError('Metadata exceeds 1 MiB')
    # Bound nesting before json.loads allocates a recursive object graph.
    depth, quoted, escaped = 0, False, False
    for byte in raw:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted = True
        elif byte in (91, 123):
            depth += 1
            if depth > MAX_DEPTH:
                raise InvalidMetadataError('Metadata nesting limit exceeded')
        elif byte in (93, 125):
            depth -= 1
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_object,
                           parse_constant=_reject_constant)
        check_tree(value)
        return value
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise InvalidMetadataError('Invalid JSON metadata') from exc


def _subkey(key, secret):
    if type(key) is not bytes or len(key) != 32:
        raise InvalidMetadataError('MAC key must be 32 bytes')
    from cryptography.hazmat.primitives.kdf.hkdf import HKDFExpand
    from cryptography.hazmat.primitives import hashes
    return HKDFExpand(algorithm=hashes.SHA256(), length=32,
                      info=b'jiami/v1/secret' if secret else b'jiami/v1/outer').derive(key)


def encode_frame(header, body, key, *, secret=False):
    if type(body) is not bytes or len(body) > MAX_BODY or (secret and body):
        raise CorruptedDataError('Invalid frame body size')
    raw = json_bytes(header)
    prefix = (b'JMIS' if secret else b'JMI1') + b'\x01\x00'
    if secret:
        prefix += key
    frame = prefix + struct.pack('>I', len(raw)) + raw + struct.pack('>Q', len(body)) + body
    return frame + hmac.digest(_subkey(key, secret), frame, 'sha256')


def decode_frame(frame, key=None, *, secret=False):
    start = 42 if secret else 10
    if len(frame) < start + 8 + 32:
        raise CorruptedDataError('Truncated frame; legacy formats are not supported')
    if frame[:6] != (b'JMIS' if secret else b'JMI1') + b'\x01\x00':
        raise CorruptedDataError('Unsupported format/version/flags; legacy pickle is rejected')
    if secret:
        key = frame[6:38]
    size = struct.unpack('>I', frame[start-4:start])[0]
    if size > MAX_HEADER or len(frame) < start + size + 8 + 32:
        raise CorruptedDataError('Invalid header length')
    body_size = struct.unpack('>Q', frame[start+size:start+size+8])[0]
    if body_size > MAX_BODY or (secret and body_size != 0):
        raise CorruptedDataError('Invalid body length')
    if len(frame) != start + size + 8 + body_size + 32:
        raise CorruptedDataError('Truncated frame or trailing bytes')
    expected = hmac.digest(_subkey(key, secret), frame[:-32], 'sha256')
    if not hmac.compare_digest(expected, frame[-32:]):
        raise IntegrityVerificationError('Package authentication failed')
    header = parse_json(frame[start:start+size])
    return header, frame[start+size+8:-32], key


def read_frame(path, *, secret=False):
    maximum = MAX_HEADER + (82 if secret else MAX_BODY + 50)
    with open(path, 'rb') as stream:
        size = os.fstat(stream.fileno()).st_size
        if size > maximum:
            raise CorruptedDataError('File exceeds supported frame size')
        # Immutable snapshot: decrypt the bytes authenticated, not a later reread.
        result = stream.read(size + 1)
        if len(result) != size:
            raise CorruptedDataError('File changed while reading')
        return result
