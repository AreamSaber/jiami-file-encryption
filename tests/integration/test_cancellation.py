"""Cooperative cancellation uses real workers/publication and forced orderings."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys
import threading

import pytest

from cli.batch_processor import BatchProcessor
from src.decryptor.cpu_decryptor import CPUDecryptor
from src.encryptor.main import FileEncryptor
from src.package_format import publication
from src.package_format.cancellation import (PublicationGate, CancellationToken, CancellationGroup,
                                            OperationCancelled, iter_checked, exit_code)
from src.resources.admission import AdmissionEstimate
from src.resources.reservations import ReservationLedger, ResourcePolicy
from src.thread_pool.thread_manager import thread_manager


@pytest.fixture
def encryptor():
    settings = thread_manager.snapshot()
    settings.set_gui_config(max_threads=2)
    result = FileEncryptor(thread_settings=settings)
    yield result
    result.hybrid_engine.shutdown()
    assert result.resource_ledger.reserved_bytes == 0


@pytest.mark.parametrize('winner', ['cancel', 'publish'])
def test_gate_both_orderings_with_barriers(winner):
    gate = PublicationGate()
    ready, finish = threading.Barrier(2, timeout=5), threading.Barrier(2, timeout=5)
    def worker():
        first = gate.enter_publishing() if winner == 'publish' else None
        ready.wait(); finish.wait()
        return gate.enter_publishing() if winner == 'cancel' else first
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(worker)
        ready.wait()
        assert gate.request_cancel() is (winner == 'cancel')
        finish.wait()
        assert future.result(timeout=5) is (winner == 'publish')
    if winner == 'cancel':
        with pytest.raises(OperationCancelled): gate.checkpoint()
    else:
        gate.checkpoint()
        assert not gate.enter_publishing() and gate.late_request()


def hold_gate(token, monkeypatch, winner):
    ready, release = threading.Barrier(2, timeout=10), threading.Barrier(2, timeout=10)
    actual = token.gate.enter_publishing
    def enter():
        result = actual() if winner == 'publish' else None
        ready.wait(); release.wait()
        return actual() if winner == 'cancel' else result
    monkeypatch.setattr(token.gate, 'enter_publishing', enter)
    return ready, release


@pytest.mark.parametrize('folder', [False, True])
@pytest.mark.parametrize('winner', ['cancel', 'publish'])
def test_encryption_publication_order_and_private_stage(tmp_path, encryptor, monkeypatch, folder, winner):
    source = tmp_path / 'source'
    if folder:
        source.mkdir(); (source / 'data').write_bytes(b'real folder bytes')
    else:
        source.write_bytes(b'real file bytes')
    token = CancellationToken()
    ready, release = hold_gate(token, monkeypatch, winner)
    operation = encryptor.encrypt_folder if folder else encryptor.encrypt_file
    destination = tmp_path / 'out' / 'source.jiami'
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(operation, source, tmp_path / 'out', 'basic', cancellation=token)
        ready.wait()
        try:
            assert not destination.exists()
            assert token.request_cancel() is (winner == 'cancel')
            assert encryptor.resource_ledger.reserved_bytes > 0
        finally:
            release.wait()
        result = future.result(timeout=10)
    if winner == 'cancel':
        assert result['cancelled'] and not result['success'], result
        assert not destination.exists()
        stages = list((tmp_path / 'out').glob('.jiami-stage-*'))
        assert len(stages) == 1 and (stages[0] / 'recovery.jmis').exists()
        assert str(stages[0]) in '\n'.join(result['details'])
        assert 'secrets' in '\n'.join(result['details'])
    else:
        assert result['success'] and destination.is_dir(), result
        assert 'too late' in result['warning'] and exit_code(result) == 0
        assert CPUDecryptor().decrypt_bytes(destination)[0]
    assert encryptor.resource_ledger.reserved_bytes == 0


@pytest.mark.parametrize('folder', [False, True])
@pytest.mark.parametrize('winner', ['cancel', 'publish'])
def test_recovery_publication_order_and_retained_plaintext(tmp_path, encryptor, monkeypatch, folder, winner):
    source = tmp_path / 'source'
    if folder:
        source.mkdir(); (source / 'data').write_bytes(b'plaintext')
    else:
        source.write_bytes(b'plaintext')
    encrypted = (encryptor.encrypt_folder if folder else encryptor.encrypt_file)(source, tmp_path / 'out', 'basic')
    assert encrypted['success'], encrypted
    token, reader = CancellationToken(), CPUDecryptor()
    ready, release = hold_gate(token, monkeypatch, winner)
    target = tmp_path / 'restored'
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(reader.decrypt_file, encrypted['package_dir'], target, cancellation=token)
        ready.wait()
        assert token.request_cancel() is (winner == 'cancel')
        release.wait()
        if winner == 'cancel':
            with pytest.raises(OperationCancelled) as caught: future.result(timeout=10)
            assert reader.last_publication is None and not target.exists()
            stages = list(tmp_path.glob('.jiami-stage-*'))
            assert len(stages) == 1 and str(stages[0]) in '\n'.join(caught.value.__notes__)
            payload = stages[0] / ('data' if folder else 'payload')
            assert payload.read_bytes() == b'plaintext'
        else:
            assert future.result(timeout=10) == str(target)
            assert (target / 'data' if folder else target).read_bytes() == b'plaintext'
            assert 'too late' in token.completion_warning()


def test_late_cancel_does_not_mask_collision_failure(tmp_path, encryptor, monkeypatch):
    source = tmp_path / 'data'; source.write_bytes(b'plaintext')
    first = encryptor.encrypt_file(source, tmp_path / 'out', 'basic')
    old = Path(first['encrypted_file']).read_bytes()
    token = CancellationToken()
    actual = publication.rename_noreplace
    def conflict(stage, destination):
        assert not token.request_cancel()  # Publication has already won.
        return actual(stage, destination)
    monkeypatch.setattr(publication, 'rename_noreplace', conflict)
    result = encryptor.encrypt_file(source, tmp_path / 'out', 'basic', cancellation=token)
    assert not result['success'] and not result['cancelled'] and exit_code(result) == 1
    assert Path(first['encrypted_file']).read_bytes() == old


def test_cancel_before_work_never_reads(tmp_path, encryptor, monkeypatch):
    token = CancellationToken(); token.request_cancel()
    source = tmp_path / 'input'; source.write_bytes(b'x')
    monkeypatch.setattr(encryptor.file_processor, 'read_file', lambda *a, **k: pytest.fail('read after cancellation'))
    result = encryptor.encrypt_file(source, tmp_path / 'out', 'basic', cancellation=token)
    assert result['cancelled'] and exit_code(result) == 130 and not (tmp_path / 'out').exists()


def test_real_native_step_finishes_before_cancel_returns(tmp_path, encryptor, monkeypatch):
    source = tmp_path / 'input'; source.write_bytes(b'x' * 4096)
    token = CancellationToken()
    entered, release = threading.Barrier(2, timeout=5), threading.Barrier(2, timeout=5)
    actual = encryptor.hybrid_engine.encryption_methods['aes256']
    def native(data, params):
        entered.wait(); release.wait()
        return actual(data, params)
    monkeypatch.setitem(encryptor.hybrid_engine.encryption_methods, 'aes256', native)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(encryptor.encrypt_file, source, tmp_path / 'out', 'basic', cancellation=token)
        entered.wait()
        assert token.request_cancel() and not future.done()
        assert encryptor.resource_ledger.reserved_bytes > 0
        release.wait()
        result = future.result(timeout=5)
    assert result['cancelled'] and not (tmp_path / 'out').exists()


def test_cancellation_in_python_loop_is_periodic():
    token = CancellationToken()
    seen = []
    with pytest.raises(OperationCancelled):
        for i in iter_checked(range(100000), token):
            seen.append(i)
            if i == 100:
                token.request_cancel()
    assert len(seen) == 4096


def test_waiting_reservation_can_cancel_while_other_claim_is_held():
    ledger = ReservationLedger(ResourcePolicy(100, 0, 30), available_memory=lambda: 1000)
    estimate = AdmissionEstimate(True, '', 1, estimated_peak_bytes=75)
    token, waiting = CancellationToken(), threading.Event()
    wait = ledger._condition.wait
    def observe(*a, **kw):
        waiting.set(); return wait(*a, **kw)
    ledger._condition.wait = observe
    def task():
        with ledger.reserve(estimate, cancellation=token): pytest.fail('must cancel while waiting')
    with ThreadPoolExecutor(max_workers=1) as pool:
        with ledger.reserve(estimate):
            future = pool.submit(task)
            assert waiting.wait(5)
            token.request_cancel()
            with pytest.raises(OperationCancelled): future.result(timeout=5)
            assert ledger.reserved_bytes == 75
    assert ledger.reserved_bytes == 0


def test_batch_error_cancellation_success_counts_and_stop_admission(tmp_path, monkeypatch):
    from src.encryptor.file_processor import FileProcessor
    group = CancellationGroup()
    paths = []
    for i in range(4):
        path = tmp_path / str(i); path.write_bytes(b'content'); paths.append(str(path))
    actual, reads = FileProcessor.read_file, []
    def reader(self, path, **kw):
        reads.append(path.name)
        if path.name == '1': raise LookupError('real error before cancellation')
        if path.name == '2': group.request_cancel()
        return actual(self, path, **kw)
    monkeypatch.setattr(FileProcessor, 'read_file', reader)
    result = BatchProcessor().process_file_list(paths, str(tmp_path / 'out'), {'profile': 'basic'}, cancellation=group)
    assert (result['successful'], result['failed'], result['cancelled'], result['processed_count']) == (1, 1, 2, 4)
    assert reads == ['0', '1', '2'] and exit_code(result) == 1
    assert CPUDecryptor().decrypt_bytes(tmp_path / 'out/0.jiami')[0] == b'content'


@pytest.mark.parametrize('parallel', [1, 2])
def test_batch_cancelled_queue_counts_every_file(tmp_path, parallel):
    source = tmp_path / 'in'; source.mkdir()
    for i in range(3): (source / str(i)).write_bytes(b'data')
    group = CancellationGroup(); group.request_cancel()
    result = BatchProcessor().process_directory(str(source), str(tmp_path / 'out'), {'parallel': parallel}, cancellation=group)
    assert result['cancelled'] == result['processed_count'] == 3
    assert result['failed'] == result['successful'] == 0 and exit_code(result) == 130
    assert not list((tmp_path / 'out').glob('*.jiami'))


def test_late_batch_cancel_keeps_success_and_reports_warning(tmp_path, monkeypatch):
    source = tmp_path / 'input'; source.write_bytes(b'data')
    group, actual = CancellationGroup(), publication.rename_noreplace
    def rename(stage, target):
        group.request_cancel()
        return actual(stage, target)
    monkeypatch.setattr(publication, 'rename_noreplace', rename)
    result = BatchProcessor().process_file_list([str(source)], str(tmp_path / 'out'), {'profile': 'basic'}, cancellation=group)
    assert result['successful'] == 1 and result['cancelled'] == result['failed'] == 0
    assert exit_code(result) == 0 and any('too late' in x for x in result['warnings'])


def test_cancel_during_private_write_retains_only_owned_stage(tmp_path, encryptor, monkeypatch):
    source = tmp_path / 'input'; source.write_bytes(b'x' * 140000)
    out = tmp_path / 'out'; out.mkdir()
    other = out / '.jiami-stage-unrelated'; other.mkdir()
    (other / 'keep').write_bytes(b'not this attempt')
    token, actual = CancellationToken(), publication.os.fdopen
    class CancelAfterWrite:
        def __init__(self, stream): self.stream = stream
        def __enter__(self): return self
        def __exit__(self, *args): return self.stream.__exit__(*args)
        def write(self, data):
            count = self.stream.write(data)
            token.request_cancel()
            return count
        def __getattr__(self, name): return getattr(self.stream, name)
    monkeypatch.setattr(publication.os, 'fdopen', lambda *a, **k: CancelAfterWrite(actual(*a, **k)))
    result = encryptor.encrypt_file(source, out, 'basic', cancellation=token)
    assert result['cancelled'] and not result['success'] and not (out / 'input.jiami').exists()
    stage, = [p for p in out.glob('.jiami-stage-*') if p != other]
    assert (stage / 'data.jmi').stat().st_size == 65536
    assert str(stage) in '\n'.join(result['details'])
    assert (other / 'keep').read_bytes() == b'not this attempt'


@pytest.mark.skipif(os.name == 'nt', reason='Directory fsync warning is a POSIX publication path')
def test_late_cancel_keeps_post_rename_durability_warning(tmp_path, encryptor, monkeypatch):
    source = tmp_path / 'input'; source.write_bytes(b'plaintext')
    target = tmp_path / 'out/input.jiami'
    token, actual = CancellationToken(), publication.sync_directory
    def sync(path):
        if target.exists():
            assert not token.request_cancel()
            raise OSError('injected post-rename fsync failure')
        return actual(path)
    monkeypatch.setattr(publication, 'sync_directory', sync)
    result = encryptor.encrypt_file(source, target.parent, 'basic', cancellation=token)
    assert result['success'] and exit_code(result) == 0 and target.is_dir()
    assert result['durability'] == 'unconfirmed'
    assert 'too late' in result['warning'] and 'fsync failure' in result['warning']


def test_inner_error_outranks_cancellation_and_waits_for_survivor(tmp_path, encryptor, monkeypatch):
    source = tmp_path / 'input'; source.write_bytes(b'x' * 8193)
    token, engine = CancellationToken(), encryptor.hybrid_engine
    barrier = threading.Barrier(3, timeout=10)
    release, cancelling, draining = threading.Event(), threading.Event(), threading.Event()
    actual_shutdown = engine.shutdown
    def shutdown():
        draining.set()
        actual_shutdown()
    def run(data, layer, method):
        barrier.wait()
        if method == 'aes256':
            token.request_cancel()
            cancelling.set()
            token.checkpoint()
        assert release.wait(10)
        raise LookupError('real inner failure after cancellation')
    monkeypatch.setattr(engine, '_run_layer', run)
    monkeypatch.setattr(engine, 'shutdown', shutdown)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(encryptor.encrypt_file, source, tmp_path / 'out', 'parallel_fast', cancellation=token)
        try:
            barrier.wait()
            assert cancelling.wait(5) and draining.wait(5)
            assert not future.done() and encryptor.resource_ledger.reserved_bytes > 0
        finally:
            release.set()
        result = future.result(timeout=5)
    assert not result['success'] and not result['cancelled'] and exit_code(result) == 1
    assert 'real inner failure' in result['error'] and engine.thread_pool is None
    assert not (tmp_path / 'out').exists()


def test_real_recovery_python_loop_propagates_cancellation(tmp_path, encryptor, monkeypatch):
    from src.decryptor import algorithm_registry
    source = tmp_path / 'input'; source.write_bytes(b'x' * 9000)
    config = {'layers': [{'method': 'custom', 'algorithm': 'rotate_cipher', 'rotation': 13}], 'execution': 'sequential'}
    result = encryptor.encrypt_file(source, tmp_path / 'out', custom_config=config)
    assert result['success'], result
    token, checked, counts = CancellationToken(), algorithm_registry.iter_checked, []
    def cancel_inside(iterable):
        for index, item in enumerate(checked(iterable)):
            counts.append(index)
            if index == 100: token.request_cancel()
            yield item
    monkeypatch.setattr(algorithm_registry, 'iter_checked', cancel_inside)
    with pytest.raises(OperationCancelled):
        CPUDecryptor().decrypt_file(result['package_dir'], tmp_path / 'restored', cancellation=token)
    assert len(counts) == 4096 and not (tmp_path / 'restored').exists()


@pytest.mark.skipif(os.name == 'nt', reason='POSIX nested signal delivery; API/Qt coverage runs on Windows')
def test_repeated_sigint_does_not_reenter_controller_locks():
    script = r'''
import os, signal, threading
from src.package_format.cancellation import CancellationToken, run_with_sigint
class Controller(CancellationToken):
    def request_cancel(self):
        with self.gate._lock:
            os.kill(os.getpid(), signal.SIGINT)
        result = super().request_cancel()
        ack.set()
        return result
ack = threading.Event()
token = Controller()
def operation():
    os.kill(os.getpid(), signal.SIGINT)
    assert ack.wait(5)
    return 'done'
assert run_with_sigint(operation, token) == 'done'
'''
    proc = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True,
                          encoding='utf-8', env={**os.environ, 'PYTHONUTF8': '1'}, timeout=10)
    assert proc.returncode == 0, proc.stdout + proc.stderr


@pytest.mark.skipif(os.name == 'nt', reason='POSIX SIGINT delivery test; Windows token/Qt behavior is covered separately')
@pytest.mark.parametrize('entry', ['primary', 'enhanced', 'batch'])
def test_actual_cli_sigint_returns_130(tmp_path, entry):
    source = tmp_path / 'input'; source.write_bytes(b'data')
    script = r'''
import os, signal, threading, sys
from types import SimpleNamespace
from src.package_format.cancellation import CancellationToken
from src.encryptor.hybrid_engine import HybridEncryptionEngine
ack = threading.Event()
request = CancellationToken.request_cancel
def cancel(self):
    answer = request(self)
    ack.set()
    return answer
CancellationToken.request_cancel = cancel
actual = HybridEncryptionEngine._run_layer
def layer(self, *args):
    os.kill(os.getpid(), signal.SIGINT)
    assert ack.wait(5), 'main thread did not handle SIGINT'
    return actual(self, *args)
HybridEncryptionEngine._run_layer = layer
source, out, entry = sys.argv[1:]
if entry == 'primary':
    from main import run_cli_mode
    result = run_cli_mode(SimpleNamespace(input=source, output=out, profile='basic', list_profiles=False))
else:
    from cli.enhanced_cli import EnhancedCLI
    args = ['encrypt', '-i', source] if entry == 'enhanced' else ['batch', '-d', os.path.dirname(source), '--parallel', '2']
    result = EnhancedCLI().run(args + ['-o', out, '-p', 'basic'])
raise SystemExit(result)
'''
    output = tmp_path / 'out'
    proc = subprocess.run([sys.executable, '-c', script, str(source), str(output), entry],
                          cwd=Path(__file__).resolve().parents[2], capture_output=True,
                          text=True, encoding='utf8', env={**os.environ, 'PYTHONUTF8': '1'}, timeout=30)
    assert proc.returncode == 130, proc.stdout + proc.stderr
    assert not list(output.glob('*.jiami'))


@pytest.mark.skipif(os.name == 'nt', reason='POSIX SIGINT; generated recovery/EXE round trips run separately on Windows')
def test_generated_recovery_sigint_uses_embedded_runtime(tmp_path, encryptor):
    source = tmp_path / 'source'; source.write_bytes(b'recovery signal plaintext')
    result = encryptor.encrypt_file(source, tmp_path / 'out', 'basic')
    assert result['success'], result
    package = Path(result['package_dir'])
    # Instrument only the signal boundary in the real generated runtime. The
    # subprocess runs outside the repository and has no source-tree imports.
    wrapper = r'''
import builtins, os, runpy, signal, sys, threading
original_import, ack = builtins.__import__, threading.Event()
def instrument(name, *args, **kw):
    module = original_import(name, *args, **kw)
    if name == 'src.decryptor.cpu_decryptor':
        reader = sys.modules[name]
        assert 'runtime.zip' in reader.__file__, reader.__file__
        token = sys.modules['src.package_format.cancellation'].CancellationToken
        request, layer = token.request_cancel, reader.CPUDecryptor.decrypt_layer
        def cancel(self):
            value = request(self)
            ack.set()
            return value
        def decrypt(self, *a, **k):
            os.kill(os.getpid(), signal.SIGINT)
            assert ack.wait(5)
            return layer(self, *a, **k)
        token.request_cancel = cancel
        reader.CPUDecryptor.decrypt_layer = decrypt
        builtins.__import__ = original_import
    return module
builtins.__import__ = instrument
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name='__main__')
'''
    output = tmp_path / 'restored'
    proc = subprocess.run([sys.executable, '-c', wrapper, str(package / 'recover.py'),
                           str(package / 'data.jmi'), str(output)], cwd=tmp_path,
                          capture_output=True, text=True, encoding='utf-8',
                          env={**os.environ, 'PYTHONUTF8': '1'}, timeout=30)
    assert proc.returncode == 130, proc.stdout + proc.stderr
    assert 'Operation cancelled' in proc.stderr and not output.exists()
