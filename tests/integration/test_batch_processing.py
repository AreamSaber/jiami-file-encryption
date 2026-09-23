"""Batch tasks own real engines, settings, bounded pools and publication results."""
import os
from pathlib import Path
import subprocess
import sys
import threading

import pytest

from cli.batch_processor import BatchProcessor
from src.decryptor.base_decryptor import load_package
from src.decryptor.cpu_decryptor import CPUDecryptor
from src.encryptor.hybrid_engine import HybridEncryptionEngine
from src.thread_pool.thread_manager import thread_manager


@pytest.fixture
def batch(monkeypatch):
    processor = BatchProcessor()
    # Keep the test bounded and independent of runner CPU count. The engine,
    # algorithms, publication, pools and recovery remain real.
    processor.encryptor.thread_manager.cpu_count = 4
    processor.encryptor.thread_manager.set_gui_config(max_threads=4)
    return processor


def files(tmp_path, count=4):
    source = tmp_path / 'inputs'
    source.mkdir()
    for index in range(count):
        (source / f'{index}.bin').write_bytes(bytes([index]) * 8193)
    return source


def test_parallel_roundtrips_isolation_and_shutdown(tmp_path, batch, monkeypatch):
    source = files(tmp_path)
    before = thread_manager.get_config()
    observed = []
    lock = threading.Lock()
    barrier = threading.Barrier(2, timeout=10)
    actual = HybridEncryptionEngine.encrypt_data

    def record(engine, *args, **kwargs):
        barrier.wait()  # Prove that distinct task engines actually overlap.
        result = actual(engine, *args, **kwargs)
        with lock:
            observed.append((engine, engine.thread_manager, engine.thread_pool))
        return result

    monkeypatch.setattr(HybridEncryptionEngine, 'encrypt_data', record)
    result = batch.process_directory(str(source), str(tmp_path / 'out'),
                                     {'parallel': 2, 'profile': 'parallel_fast'})
    assert result['success'] and result['successful'] == 4, result
    assert len({id(x[0]) for x in observed}) == 4
    assert len({id(x[1]) for x in observed}) == 4
    assert len({id(x[2]) for x in observed}) == 4
    for engine, settings, pool in observed:
        assert settings is not thread_manager and settings.get_max_threads() == 2
        assert pool._max_workers == 2 and pool._shutdown
        assert not any(t.is_alive() for t in pool._threads)
        assert engine.thread_pool is None
    assert thread_manager.get_config() == before
    for path in source.iterdir():
        package = tmp_path / 'out' / (path.name + '.jiami') / 'data.jmi'
        public, _, _ = load_package(package)
        assert len(public['chunk_layers']) == 2
        assert CPUDecryptor().decrypt_bytes(package)[0] == path.read_bytes()


@pytest.mark.parametrize('parallel', [1, 4])
def test_failure_closes_pools_and_preserves_existing_output(tmp_path, batch, monkeypatch, parallel):
    source = files(tmp_path, count=1)
    options = {'parallel': parallel, 'profile': 'parallel_fast'}
    output = tmp_path / 'out'
    assert batch.process_directory(str(source), str(output), options)['success']
    package = output / '0.bin.jiami' / 'data.jmi'
    original = package.read_bytes()
    closed = []
    actual = HybridEncryptionEngine.shutdown

    def shutdown(engine):
        pool = engine.thread_pool
        actual(engine)
        closed.append(pool)

    monkeypatch.setattr(HybridEncryptionEngine, 'shutdown', shutdown)
    result = batch.process_file_list([str(source / '0.bin')], str(output), options)
    assert not result['success'] and result['failed'] == 1 and result['successful'] == 0
    assert result['errors'] and package.read_bytes() == original
    assert len(closed) == 1 and closed[0]._shutdown
    assert not any(t.is_alive() for t in closed[0]._threads)


def test_snapshot_changes_never_change_global_or_siblings():
    before = thread_manager.get_config()
    first, second = thread_manager.snapshot(), thread_manager.snapshot()
    first.set_gui_config(max_threads=1)
    assert second.get_config() == before == thread_manager.get_config()
    assert first.thread_configs is not second.thread_configs


@pytest.mark.parametrize('parallel', [0, -1, True, '4'])
def test_reject_invalid_parallel_before_output(tmp_path, batch, parallel):
    source = files(tmp_path, count=1)
    result = batch.process_directory(str(source), str(tmp_path / 'out'), {'parallel': parallel})
    assert not result['success'] and 'positive integer' in result['error']
    assert not (tmp_path / 'out').exists()


def test_batch_cli_failure_exit_and_error_details(tmp_path):
    source = files(tmp_path, count=1)
    repo = Path(__file__).resolve().parents[2]
    command = [sys.executable, '-m', 'cli.enhanced_cli', 'batch', '-d', str(source),
               '-o', str(tmp_path / 'out'), '--parallel', '2', '-p', 'basic']
    env = dict(os.environ, PYTHONUTF8='1')
    first = subprocess.run(command, cwd=repo, env=env, capture_output=True, text=True, timeout=30)
    assert first.returncode == 0, first.stdout + first.stderr
    again = subprocess.run(command, cwd=repo, env=env, capture_output=True, text=True, timeout=30)
    assert again.returncode == 1, again.stdout + again.stderr
    assert '0.bin' in again.stdout and "'error'" not in again.stdout
