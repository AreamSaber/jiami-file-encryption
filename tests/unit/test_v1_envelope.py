import base64
import copy
import hashlib
import hmac
import json
import os
from pathlib import Path
import pickle
import struct

import pytest

from src.package_format import envelope
from src.package_format.envelope import encode_frame, decode_frame
from src.package_format.schema import validate_headers
from src.encryptor.main import FileEncryptor
from src.decryptor.base_decryptor import BaseDecryptor, load_package
from src.decryptor.cpu_decryptor import CPUDecryptor
from src.exceptions.decryption_errors import DecryptionError, InvalidMetadataError, CorruptedDataError, IntegrityVerificationError


@pytest.mark.parametrize('secret', [False, True])
def test_frame_exact_coverage_and_lengths(secret):
    key = os.urandom(32)
    frame = encode_frame({'message':'x'}, b'' if secret else b'ciphertext', key, secret=secret)
    assert decode_frame(frame, key, secret=secret)[0] == {'message':'x'}
    # Every individual byte, including bootstrap key, lengths and trailing MAC.
    for i in range(len(frame)):
        changed = bytearray(frame); changed[i] ^= 1
        with pytest.raises(DecryptionError):
            decode_frame(bytes(changed), key, secret=secret)
    for changed in (frame[:-1], frame+b'\x00', frame[:5]):
        with pytest.raises(CorruptedDataError): decode_frame(changed, key, secret=secret)


@pytest.mark.parametrize('secret', [False, True])
def test_reader_accepts_exact_limit_and_rejects_extra_byte_before_read(tmp_path, monkeypatch, secret):
    key = b'k' * 32
    header, body = {'a': 1}, b'' if secret else b'payload'
    frame = encode_frame(header, body, key, secret=secret)
    # Use a small real frame to exercise the exact maximum without allocating GiB.
    monkeypatch.setattr(envelope, 'MAX_HEADER', len(envelope.json_bytes(header)))
    monkeypatch.setattr(envelope, 'MAX_BODY', len(body))
    path = tmp_path/'frame'
    path.write_bytes(frame)
    assert envelope.read_frame(path, secret=secret) == frame
    assert decode_frame(frame, key, secret=secret)[:2] == (header, body)
    path.write_bytes(frame + b'x')
    actual_open = open
    class GuardedFile:
        def __enter__(self):
            self.stream = actual_open(path, 'rb')
            return self
        def __exit__(self, *args):
            self.stream.close()
        def fileno(self):
            return self.stream.fileno()
        def read(self, *args):
            pytest.fail('Oversize input must be rejected by fstat before reading')
    monkeypatch.setattr(envelope, 'open', lambda *a, **k: GuardedFile(), raising=False)
    with pytest.raises(CorruptedDataError, match='exceeds supported frame size'):
        envelope.read_frame(path, secret=secret)


@pytest.mark.parametrize('raw', [b'{"a":1,"a":2}', b'['*17 + b'0' + b']'*17, b'{"a":NaN}', b'{"a":'])
def test_authenticated_invalid_json_is_rejected(raw):
    key = b'k'*32
    prefix = b'JMIS\x01\x00' + key + struct.pack('>I',len(raw)) + raw + b'\x00'*8
    frame = prefix + hmac.digest(envelope._subkey(key,True),prefix,'sha256')
    with pytest.raises(InvalidMetadataError): decode_frame(frame,secret=True)


def test_hmac_failure_never_invokes_json(monkeypatch):
    frame = bytearray(encode_frame({'key':'value'},b'',b'k'*32,secret=True)); frame[-1] ^= 1
    def forbidden(*args,**kwargs): raise AssertionError('JSON must not run')
    monkeypatch.setattr(envelope,'parse_json',forbidden)
    with pytest.raises(IntegrityVerificationError): decode_frame(bytes(frame),secret=True)


def test_value_codec_has_no_tag_collision():
    original = {'__type__':'bytes','v':'YQ==','nested':{0:(b'abc','x'),1:[True,1,1.0,None]}}
    assert BaseDecryptor.deserialize_metadata(BaseDecryptor.serialize_metadata(original)) == original


@pytest.fixture
def package(tmp_path):
    source=tmp_path/'input';source.write_bytes(b'secret sample'*5)
    enc=FileEncryptor(max_threads=1)
    result=enc.encrypt_file(source,tmp_path/'packages','standard')
    enc.hybrid_engine.shutdown()
    assert result['success'], result
    return result


def test_bad_recovery_and_ciphertext_never_decrypt_or_publish(package,tmp_path,monkeypatch):
    def forbidden(*args,**kwargs): raise AssertionError('Cipher operation must not run')
    monkeypatch.setattr(BaseDecryptor,'decrypt_layer',forbidden)
    data=Path(package['encrypted_file']); recovery=Path(package['recovery_file'])
    original=data.read_bytes()
    changed=bytearray(original);changed[-33]^=1;data.write_bytes(changed)
    with pytest.raises(IntegrityVerificationError): CPUDecryptor().decrypt_file(data,tmp_path/'output')
    assert not (tmp_path/'output').exists()
    data.write_bytes(original)
    changed=bytearray(recovery.read_bytes());changed[6]^=1;recovery.write_bytes(changed)
    with pytest.raises(IntegrityVerificationError): CPUDecryptor().decrypt_file(data,tmp_path/'output')
    assert not (tmp_path/'output').exists()


def test_each_secret_field_mutation_is_rejected(package,tmp_path,monkeypatch):
    recovery=Path(package['recovery_file']);original=recovery.read_bytes()
    header,_,_=decode_frame(original,secret=True)
    raw=json.loads(original[42:42+int.from_bytes(original[38:42],'big')])
    def forbidden(*args,**kwargs): raise AssertionError('Cipher operation must not run')
    monkeypatch.setattr(BaseDecryptor,'decrypt_layer',forbidden)
    for i,layer in enumerate(raw['layers']):
        for field in layer['params']:
            modified=copy.deepcopy(raw)
            value=modified['layers'][i]['params'][field]
            modified['layers'][i]['params'][field]=('A' if value[0]!='A' else 'B')+value[1:]
            encoded=envelope.json_bytes(modified)
            # Keep the original tag, deliberately unauthenticated modified header.
            tampered=original[:38]+struct.pack('>I',len(encoded))+encoded+b'\x00'*8+original[-32:]
            recovery.write_bytes(tampered)
            with pytest.raises(IntegrityVerificationError): CPUDecryptor().decrypt_file(package['encrypted_file'],tmp_path/'output')
    assert not (tmp_path/'output').exists()


def test_authenticated_missing_or_public_secret_fields_rejected(package):
    public,secret,body=load_package(package['encrypted_file'])
    bad=copy.deepcopy(secret);del bad['layers'][0]['params']['key']
    with pytest.raises(InvalidMetadataError):validate_headers(public,bad,len(body))
    bad=copy.deepcopy(public);bad['layers'][0]['params']['key']='AAAA'
    with pytest.raises(InvalidMetadataError):validate_headers(bad,secret,len(body))


def test_legacy_pickle_never_executes(package,tmp_path):
    marker=tmp_path/'EXECUTED'
    class Gadget:
        def __reduce__(self):return (eval,("__import__('pathlib').Path("+repr(str(marker))+").write_text('bad')",))
    data=Path(package['encrypted_file']);data.write_bytes(pickle.dumps(Gadget()))
    with pytest.raises(CorruptedDataError):CPUDecryptor().decrypt_file(data,tmp_path/'output')
    assert not marker.exists() and not (tmp_path/'output').exists()
