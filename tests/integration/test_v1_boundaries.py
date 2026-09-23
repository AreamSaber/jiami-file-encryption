"""Failure boundaries exercised through real readers and entry points."""
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from src.decryptor.base_decryptor import BaseDecryptor, load_package
from src.decryptor.cpu_decryptor import CPUDecryptor
from src.encryptor.main import FileEncryptor
from src.exceptions import InvalidMetadataError, IntegrityVerificationError
from src.package_format.envelope import decode_frame, encode_frame, parse_json
from src.package_format.archive import unpack_folder
from src.package_format.schema import validate_headers, create_headers


@pytest.fixture
def package(tmp_path):
    source = tmp_path / 'input.bin'
    source.write_bytes(b'synthetic boundary test' * 20)
    enc = FileEncryptor(max_threads=1)
    try:
        result = enc.encrypt_file(source, tmp_path / 'packages', 'high')
        assert result['success'], result
        return result
    finally:
        enc.hybrid_engine.shutdown()


def forbidden(*args, **kwargs):
    pytest.fail('Cipher must not be constructed for this input')


def test_other_package_recovery_never_decrypts(package, tmp_path, monkeypatch):
    source = tmp_path / 'other.bin'
    source.write_bytes(b'other')
    enc = FileEncryptor(max_threads=1)
    try:
        other = enc.encrypt_file(source, tmp_path / 'other', 'basic')
        assert other['success'], other
    finally:
        enc.hybrid_engine.shutdown()
    monkeypatch.setattr(BaseDecryptor, 'decrypt_layer', forbidden)
    with pytest.raises(IntegrityVerificationError):
        CPUDecryptor(recovery_path=other['recovery_file']).decrypt_file(package['encrypted_file'], tmp_path/'restored')
    assert not (tmp_path/'restored').exists()


def test_nested_rsa_secret_mutation_fails_before_decryption(package, tmp_path, monkeypatch):
    path = Path(package['recovery_file'])
    original = path.read_bytes()
    header, _, key = decode_frame(original, secret=True)
    rsa = header['layers'][0]['params']
    assert 'aes_metadata' in rsa
    rsa['aes_metadata']['key'] = 'AAAA'
    modified = encode_frame(header, b'', key, secret=True)
    path.write_bytes(modified[:-32] + original[-32:])
    monkeypatch.setattr(BaseDecryptor, 'decrypt_layer', forbidden)
    with pytest.raises(IntegrityVerificationError):
        CPUDecryptor().decrypt_file(package['encrypted_file'], tmp_path/'restored')
    assert not (tmp_path/'restored').exists()


@pytest.mark.parametrize('bad', [None, [], 5, 'unexpected'])
def test_malformed_authenticated_structure_is_typed_failure(package, bad):
    public, secret, body = load_package(package['encrypted_file'])
    public['layers'][0]['params'] = bad
    with pytest.raises(InvalidMetadataError):
        validate_headers(public, secret, len(body))


def test_digest_failure_publishes_no_plaintext(package, tmp_path):
    path = Path(package['recovery_file'])
    header, _, key = decode_frame(path.read_bytes(), secret=True)
    header['plaintext_sha256'] = '0' * 64
    path.write_bytes(encode_frame(header, b'', key, secret=True))
    with pytest.raises(IntegrityVerificationError):
        CPUDecryptor().decrypt_file(package['encrypted_file'], tmp_path/'restored')
    assert not (tmp_path/'restored').exists()


@pytest.mark.parametrize('members', [
    ['../outside'], ['/absolute'], ['C:/drive'], ['a\\escape'],
    ['a', 'a/x'], ['A/x', 'a/y'], ['same', 'SAME'], ['bad:name'], ['CON.txt'],
])
def test_archive_validation_precedes_any_write(tmp_path, members):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        for name in members:
            info = zipfile.ZipInfo()
            info.filename = name  # Preserve raw hostile bytes on Windows too.
            archive.writestr(info, b'no write')
    stage = tmp_path/'stage'; stage.mkdir()
    with pytest.raises(InvalidMetadataError):
        unpack_folder(buffer.getvalue(), stage)
    assert not list(stage.iterdir())


def test_json_overflow_is_rejected():
    with pytest.raises(InvalidMetadataError):
        parse_json(b'{"number":1e9999}')


def test_producer_does_not_drop_unknown_secret_field():
    enc = FileEncryptor(max_threads=1)
    try:
        result = enc.hybrid_engine.encrypt_data(b'x', {'layers':[{'method':'aes256','mode':'GCM'}]})
    finally:
        enc.hybrid_engine.shutdown()
    result['metadata']['new_secret_field'] = b'key'
    with pytest.raises(InvalidMetadataError):
        create_headers(result, b'x', 'custom', 'name', 'file', '0'*32)


def test_gui_reader_adapter_uses_authenticated_runtime(package, tmp_path):
    # No window or display is needed to test the GUI's adapter.
    from src.decryptor.hybrid_decryptor_gui import HybridDecryptor
    result = HybridDecryptor().decrypt_file(package['encrypted_file'], tmp_path/'gui-output')
    assert result['success'], result
    assert Path(result['output_file']).read_bytes() == b'synthetic boundary test' * 20


def test_gpu_adapter_requires_explicit_fallback(package):
    from src.decryptor.gpu_decryptor import GPUDecryptor
    with pytest.raises(RuntimeError, match='backend'):
        GPUDecryptor()
    recovery = GPUDecryptor(allow_fallback=True)
    plain, _ = recovery.decrypt_bytes(package['encrypted_file'])
    assert plain == b'synthetic boundary test' * 20
    assert recovery.backend_used == {'cpu'}


@pytest.mark.parametrize('level', [1, 2, 3, 4, 5])
def test_desktop_engine_adapter_roundtrip(tmp_path, level):
    from src.encryptor.gpu_file_encryptor import GPUFileEncryptor
    source = tmp_path/'source.bin'; source.write_bytes(b'desktop synthetic' * 40)
    result = GPUFileEncryptor(allow_fallback=True).encrypt_file(source, tmp_path/'out', level)
    assert result['success'], result
    assert result['using_fallback'] and not result['gpu_only']
    assert CPUDecryptor().decrypt_bytes(result['encrypted_file'])[0] == source.read_bytes()


def test_cli_roundtrip_and_collision_exit_status(tmp_path):
    root = Path(__file__).resolve().parents[2]
    source = tmp_path/'input.bin'; source.write_bytes(b'CLI synthetic test')
    env = dict(os.environ, PYTHONUTF8='1')
    command = [sys.executable, str(root/'main.py'), '--cli', '-i', str(source), '-o', str(tmp_path/'out'), '-p', 'basic']
    first = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, timeout=60)
    assert first.returncode == 0, first.stdout + first.stderr
    data = tmp_path/'out/input.bin.jiami/data.jmi'
    original = data.read_bytes()
    again = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, timeout=60)
    assert again.returncode != 0
    assert data.read_bytes() == original
    assert CPUDecryptor().decrypt_bytes(data)[0] == source.read_bytes()


@pytest.mark.parametrize('when', ['before', 'after'])
def test_process_exit_at_rename_boundary(tmp_path, when):
    # Process interruption is distinct from a filesystem/hardware power-loss test.
    root = Path(__file__).resolve().parents[2]
    program = '''
import os, sys
from pathlib import Path
from src.package_format import publication as p
dest = Path(sys.argv[1]) / 'final'
stage = p.make_stage(dest)
p.write_private(stage/'data', b'complete')
p.write_private(stage/'secret', b'private')
actual = p.rename_noreplace
def interrupted(source, destination):
    if sys.argv[2] == 'before': os._exit(23)
    actual(source, destination)
    os._exit(23)
p.rename_noreplace = interrupted
p.publish_directory(stage, dest, lambda _: None)
'''
    result = subprocess.run([sys.executable, '-c', program, str(tmp_path), when], cwd=root, capture_output=True, timeout=30)
    assert result.returncode == 23, result.stderr
    if when == 'before':
        assert not (tmp_path/'final').exists()
        stages = list(tmp_path.glob('.jiami-stage-*'))
        assert len(stages) == 1
        assert (stages[0]/'secret').read_bytes() == b'private'
    else:
        assert (tmp_path/'final/data').read_bytes() == b'complete'
        assert (tmp_path/'final/secret').read_bytes() == b'private'
