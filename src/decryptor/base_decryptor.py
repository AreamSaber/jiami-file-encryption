"""Shared authenticated reader, plan, and fail-closed recovery publication."""
import base64
import hashlib
import hmac
from src.package_format.cancellation import (CancellationToken, OperationCancelled, checkpoint, cancellation_scope, retain_stage)
from pathlib import Path

from src.exceptions.decryption_errors import IntegrityVerificationError, InvalidMetadataError, LayerDecryptionError
from src.package_format.envelope import decode_frame, read_frame, parse_json, json_bytes
from src.package_format.schema import validate_headers, _wire, require
from src.package_format.publication import make_stage, publish_directory, publish_file
from src.package_format.archive import unpack_folder
from .algorithm_registry import AlgorithmRegistry


def load_package(data_path, recovery_path=None, recovery_bytes=None, *, cancellation=None):
    checkpoint(cancellation)
    path = Path(data_path)
    if path.is_dir():
        path = path / 'data.jmi'
    if recovery_bytes is None:
        recovery_bytes = read_frame(recovery_path or path.with_name('recovery.jmis'), secret=True)
    checkpoint(cancellation)
    secret, _, key = decode_frame(recovery_bytes, secret=True)
    public, body, _ = decode_frame(read_frame(path), key)
    checkpoint(cancellation)
    validate_headers(public, secret, len(body))
    checkpoint(cancellation)
    return public, secret, body


class BaseDecryptor:
    """All file entry points authenticate both artifacts before constructing ciphers."""

    def __init__(self, recovery_path=None, recovery_bytes=None):
        self.recovery_path = recovery_path
        self.recovery_bytes = recovery_bytes
        self.registry = AlgorithmRegistry()
        self.last_publication = None

    def decrypt_layer(self, data, algorithm, params):
        return self.registry.get_handler(algorithm).decrypt(data, {**params, 'algorithm': algorithm})

    def _node(self, data, node, secret, cancellation=None):
        checkpoint(cancellation)
        require(len(data) == node['output_size'], 'Cipher chunk length mismatch')
        if node['algorithm'] == 'chunked':
            result, offset = [], 0
            for child, recovery in zip(node['chunks'], secret['chunks']):
                size = child['output_size']
                result.append(self._node(data[offset:offset+size], child, recovery, cancellation))
                offset += size
            plain = b''.join(result)
        else:
            params = _wire({**node['params'], **secret['params']}, False)
            try:
                with cancellation_scope(cancellation):
                    plain = self.decrypt_layer(data, node['algorithm'], params)
            except OperationCancelled:
                raise
            except Exception as exc:
                # Never return the original ciphertext or unverified padding on failure.
                raise LayerDecryptionError('Cipher operation failed', node['layer_index'], node['algorithm']) from exc
        require(len(plain) == node['input_size'], 'Recovered chunk length mismatch')
        return plain

    def decrypt_bytes(self, data_path, recovery_path=None, *, cancellation=None):
        checkpoint(cancellation)
        public, secret, body = load_package(data_path, recovery_path or self.recovery_path, self.recovery_bytes, cancellation=cancellation)
        field = 'layers' if public['topology'] == 'sequential' else 'chunk_layers'
        if field == 'layers':
            plain = body
            for node, recovery in reversed(list(zip(public[field], secret[field]))):
                plain = self._node(plain, node, recovery, cancellation)
        else:
            result, offset = [], 0
            for node, recovery in zip(public[field], secret[field]):
                size = node['output_size']
                result.append(self._node(body[offset:offset+size], node, recovery, cancellation))
                offset += size
            plain = b''.join(result)
        if len(plain) != public['original_size'] or not hmac.compare_digest(hashlib.sha256(plain).hexdigest(), secret['plaintext_sha256']):
            raise IntegrityVerificationError('Recovered plaintext does not match the original')
        checkpoint(cancellation)
        return plain, public

    def decrypt_file(self, encrypted_file, output_path=None, recovery_path=None, *, cancellation=None):
        cancellation = cancellation or CancellationToken()
        self.last_publication = None
        plain, public = self.decrypt_bytes(encrypted_file, recovery_path, cancellation=cancellation)
        source = Path(encrypted_file)
        parent = source if source.is_dir() else source.parent
        destination = Path(output_path) if output_path is not None else parent / ('restored-' + public['original_name'])
        if public['kind'] == 'folder':
            stage = make_stage(destination)
            try:
                unpack_folder(plain, stage, cancellation=cancellation)
                self.last_publication = publish_directory(stage, destination, lambda _: None, cancellation=cancellation)
            except BaseException as exc:
                retain_stage(exc, stage, 'verified plaintext')
                raise
        else:
            self.last_publication = publish_file(plain, destination, cancellation=cancellation)
        return str(self.last_publication.path)

    @staticmethod
    def serialize_metadata(metadata):
        """Compatibility value codec, separate from the closed wire schemas.

        Every value is tagged, so an ordinary user dictionary cannot impersonate
        a bytes marker. Integer keys and tuples are preserved without eval.
        """
        def encode(value):
            if value is None: return ['null', None]
            if type(value) in (str, int, float, bool): return [type(value).__name__, value]
            if type(value) is bytes: return ['bytes', base64.b64encode(value).decode('ascii')]
            if type(value) in (list, tuple): return [type(value).__name__, [encode(v) for v in value]]
            if type(value) is dict: return ['dict', [[encode(k), encode(v)] for k, v in value.items()]]
            raise InvalidMetadataError('Unsupported metadata value type')
        return base64.b64encode(json_bytes(encode(metadata))).decode('ascii')

    @staticmethod
    def deserialize_metadata(serialized):
        def decode(node):
            require(type(node) is list and len(node) == 2, 'Invalid typed value')
            tag, value = node
            scalars = {'str': str, 'int': int, 'float': float, 'bool': bool, 'null': type(None)}
            if tag in scalars:
                require(type(value) is scalars[tag], 'Invalid scalar value')
                return value
            if tag == 'bytes': return base64.b64decode(value, validate=True)
            if tag in ('list', 'tuple'):
                require(type(value) is list, 'Invalid sequence')
                result = [decode(v) for v in value]
                return tuple(result) if tag == 'tuple' else result
            if tag == 'dict':
                result = {}
                for pair in value:
                    require(type(pair) is list and len(pair) == 2, 'Invalid dictionary pair')
                    key = decode(pair[0])
                    require(key not in result, 'Duplicate dictionary key')
                    result[key] = decode(pair[1])
                return result
            raise InvalidMetadataError('Unknown value tag')
        try:
            require(type(serialized) is str and len(serialized) <= (1 << 21), 'Serialized metadata exceeds limit')
            return decode(parse_json(base64.b64decode(serialized, validate=True)))
        except (ValueError, TypeError, KeyError) as exc:
            raise InvalidMetadataError('Invalid serialized metadata') from exc
