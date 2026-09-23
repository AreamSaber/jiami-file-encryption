"""Real profile roundtrips, standalone recovery, and publication rejection."""
import builtins
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from src.encryptor.main import FileEncryptor
from src.decryptor.cpu_decryptor import CPUDecryptor
from src.decryptor.base_decryptor import load_package
from src.encryptor.hybrid_engine import HybridEncryptionEngine

PROFILES = tuple(json.loads((Path(__file__).resolve().parents[2]/'config/encryption_profiles.json').read_text(encoding='utf8'))['encryption_profiles'])


@pytest.fixture
def encryptor():
    engine = FileEncryptor(max_threads=2)
    yield engine
    engine.hybrid_engine.shutdown()


@pytest.mark.parametrize('profile', PROFILES)
@pytest.mark.parametrize('size', [0, 1, 32, 511])
def test_all_profiles_roundtrip(tmp_path, encryptor, profile, size):
    original = bytes((i * 37) % 256 for i in range(size))
    source = tmp_path/'input.bin'
    source.write_bytes(original)
    result = encryptor.encrypt_file(source, tmp_path/'packages', profile)
    assert result['success'], result
    public, secret, body = load_package(result['encrypted_file'])
    assert public['profile'] == profile
    assert public['topology'] == ('parallel_chunks' if profile == 'parallel_fast' else 'sequential')
    output = tmp_path/'restored.bin'
    CPUDecryptor().decrypt_file(result['encrypted_file'], output)
    assert output.read_bytes() == original
    assert hashlib.sha256(output.read_bytes()).hexdigest() == hashlib.sha256(original).hexdigest()
    # The shareable header contains only explicitly allowed fields, never keys.
    def no_secrets(value):
        if isinstance(value, dict):
            assert not ({'key', 'private_key_pem', 'obfuscation_key', 'mac_key', 'seed', 'transform_matrix', 'operations', 'applied_operations'} & value.keys())
            for item in value.values(): no_secrets(item)
        elif isinstance(value, list):
            for item in value: no_secrets(item)
    no_secrets(public)
    assert b'PRIVATE KEY' not in Path(result['encrypted_file']).read_bytes()


@pytest.mark.parametrize('profile', PROFILES)
def test_generated_program_outside_checkout(tmp_path, encryptor, profile):
    source = tmp_path/'original.bin'
    source.write_bytes(bytes(range(256)))
    result = encryptor.encrypt_file(source, tmp_path/'packages', profile)
    assert result['success'], result
    output = tmp_path/'standalone.bin'
    env = os.environ.copy()
    env.pop('PYTHONPATH', None)
    proc = subprocess.run([sys.executable, result['decryptor_file'], result['encrypted_file'], str(output)],
                          cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert output.read_bytes() == source.read_bytes()


def test_folder_roundtrip_and_no_overwrite(tmp_path, encryptor):
    folder = tmp_path/'folder'
    (folder/'empty').mkdir(parents=True)
    (folder/'nested').mkdir()
    (folder/'nested/a.txt').write_text('你好\n', encoding='utf8')
    (folder/'b.bin').write_bytes(bytes(range(256)))
    result = encryptor.encrypt_folder(folder, tmp_path/'packages', 'standard')
    assert result['success'], result
    output = tmp_path/'restored'
    CPUDecryptor().decrypt_file(result['encrypted_file'], output)
    assert (output/'empty').is_dir()
    assert (output/'nested/a.txt').read_bytes() == (folder/'nested/a.txt').read_bytes()
    assert (output/'b.bin').read_bytes() == (folder/'b.bin').read_bytes()
    with pytest.raises(FileExistsError):
        CPUDecryptor().decrypt_file(result['encrypted_file'], output)
    original = Path(result['encrypted_file']).read_bytes()
    again = encryptor.encrypt_folder(folder, tmp_path/'packages', 'standard')
    assert not again['success']
    assert Path(result['encrypted_file']).read_bytes() == original


@pytest.mark.parametrize('profile,dependency', [('twofish_strong','src.crypto.twofish_backend'), ('multi_algorithm','src.crypto.twofish_backend'), ('paranoid_gpu','src.crypto.twofish_backend'), ('salsa20_stream','nacl.secret')])
def test_missing_dependency_fails_without_output(tmp_path, encryptor, monkeypatch, profile, dependency):
    source = tmp_path/'input.bin'
    source.write_bytes(b'sensitive')
    real_import = builtins.__import__
    def unavailable(name, *args, **kwargs):
        if name == dependency: raise ImportError('deliberately unavailable')
        return real_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', unavailable)
    result = encryptor.encrypt_file(source, tmp_path/'output', profile)
    assert not result['success']
    assert not (tmp_path/'output').exists()


def test_actual_threaded_layer_chunks(tmp_path, encryptor, monkeypatch):
    # Force real chunking, including different keys and padded ciphertext lengths.
    engine = encryptor.hybrid_engine
    monkeypatch.setattr(engine.thread_manager, 'get_parallel_threshold', lambda: 16)
    monkeypatch.setattr(engine, 'get_optimal_thread_count', lambda *args: 2)
    monkeypatch.setattr(engine, 'get_optimal_chunk_size', lambda *args: 4096)
    source = tmp_path/'input.bin'
    source.write_bytes(os.urandom(8193))
    config = {'strategy':'threaded_layered', 'layers':[{'method':'aes256','mode':'CBC'}, {'method':'chacha20'}]}
    result = encryptor.encrypt_file(source, tmp_path/'packages', custom_config=config)
    assert result['success'], result
    public, secret, _ = load_package(result['encrypted_file'])
    assert any('chunks' in layer for layer in public['layers'])
    chunks = secret['layers'][0]['chunks']
    assert len(chunks) >= 2
    assert len({chunk['params']['key'] for chunk in chunks}) == len(chunks)
    assert CPUDecryptor().decrypt_bytes(result['encrypted_file'])[0] == source.read_bytes()


def test_aes_ctr_nist_vector():
    engine = HybridEncryptionEngine(max_threads=1)
    # NIST SP 800-38A F.5.5 AES-256 CTR, first block.
    key = bytes.fromhex('603deb1015ca71be2b73aef0857d77811f352c073b6108d72d9810a30914dff4')
    counter = bytes.fromhex('f0f1f2f3f4f5f6f7f8f9fafbfcfdfeff')
    plaintext = bytes.fromhex('6bc1bee22e409f96e93d7e117393172a')
    encrypted, _ = engine._encrypt_aes256_cpu(plaintext, {'mode':'CTR','key':key,'initial_counter':counter})
    assert encrypted.hex() == '601ec313775789a5b7a7f504bbf3d228'
    engine.shutdown()


def test_failed_thread_chunk_does_not_retry_sequentially(tmp_path, encryptor, monkeypatch):
    engine = encryptor.hybrid_engine
    monkeypatch.setattr(engine.thread_manager, 'get_parallel_threshold', lambda: 16)
    monkeypatch.setattr(engine, 'get_optimal_thread_count', lambda *args: 2)
    monkeypatch.setattr(engine, 'get_optimal_chunk_size', lambda *args: 4096)
    source = tmp_path/'input.bin'; source.write_bytes(b'x' * 8193)
    actual = engine.encryption_methods['aes256']
    def fail_chunk(data, config):
        if len(data) < 8193:
            raise RuntimeError('injected chunk failure')
        pytest.fail('Must not retry the whole layer after a failed chunk')
    monkeypatch.setitem(engine.encryption_methods, 'aes256', fail_chunk)
    result = encryptor.encrypt_file(source, tmp_path/'packages', custom_config={
        'strategy':'threaded_layered', 'layers':[{'method':'aes256','mode':'CBC'}]})
    assert not result['success'] and 'injected chunk failure' in result['error']
    assert not (tmp_path/'packages').exists()


@pytest.mark.parametrize('key,plain,cipher', [
    ('9F589F5CF6122C32B6BFEC2F2AE8C35A','D491DB16E7B1C39E86CB086B789F5419','019F9809DE1711858FAAC3A3BA20FBC3'),
    ('88B2B2706B105E36B446BB6D731A1E88EFA71F788965BD44','39DA69D6BA4997D585B6DC073CA341B2','182B02D81497EA45F9DAACDC29193A65'),
    ('D43BB7556EA32E46F2A282B7D45B4E0D57FF739D4DC92C1BD7FC01700CC8216F','90AFE91BB288544F2C32DC239B2635E6','6CB4561C40BF0A9705931CB6D408E7FA'),
])
def test_real_twofish_known_answers(key,plain,cipher):
    from src.crypto.twofish_backend import Twofish
    tf=Twofish(bytes.fromhex(key))
    assert tf.encrypt(bytes.fromhex(plain))==bytes.fromhex(cipher)
    assert tf.decrypt(bytes.fromhex(cipher))==bytes.fromhex(plain)
