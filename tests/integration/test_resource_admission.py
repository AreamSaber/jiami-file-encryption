"""Real topology predictions, pre-read rejection and bounded reservation lifetimes."""
from concurrent.futures import ThreadPoolExecutor
import io
from pathlib import Path
import threading

import pytest

from cli.batch_processor import BatchProcessor
from src.decryptor.base_decryptor import load_package
from src.decryptor.cpu_decryptor import CPUDecryptor
from src.encryptor.main import FileEncryptor
from src.package_format.archive import pack_folder, plan_folder
from src.package_format.schema import predicted_collection_sizes, predicted_output_size, validate_params
from src.resources.admission import AdmissionEstimate, MIB, _position_list_minimum
from src.resources.reservations import ReservationLedger, ResourcePolicy, ResourceRefusal
from src.thread_pool.thread_manager import thread_manager


@pytest.fixture
def encryptor():
    settings = thread_manager.snapshot()
    settings.cpu_count = 4
    settings.set_gui_config(max_threads=4, enable_threading=True, parallel_threshold_mb=16 / MIB)
    ledger = ReservationLedger(available_memory=lambda: 2 * 1024 * MIB)
    result = FileEncryptor(thread_settings=settings, resource_ledger=ledger)
    yield result
    result.hybrid_engine.shutdown()
    assert ledger.reserved_bytes == 0


def assert_sizes(estimate, public, secret, body):
    assert estimate.guaranteed
    assert estimate.output_size == len(body)
    field = 'chunk_layers' if estimate.strategy == 'parallel' else 'layers'
    for stage, node, private in zip(estimate.stages, public[field], secret[field]):
        nodes = node.get('chunks', [node])
        secrets = private.get('chunks', [private])
        assert len(stage) == len(nodes)
        for prediction, actual, recovery in zip(stage, nodes, secrets):
            assert (prediction.algorithm, prediction.input_size, prediction.output_size) == (
                actual['algorithm'], actual['input_size'], actual['output_size'])
            count = sum(len(op[1]) for op in recovery['params'].get('applied_operations', [])
                        if op[0] == 'frequency_analysis_resistance')
            assert prediction.insertion_count == count
    assert len(estimate.stages) == len(public[field])


@pytest.mark.parametrize('profile,size,strategy', [
    ('paranoid', 511, 'layered'), ('parallel_fast', 8193, 'parallel'),
    ('standard', 524289, 'threaded_layered'),
])
def test_estimates_equal_real_topologies(tmp_path, encryptor, profile, size, strategy):
    if profile == 'paranoid':
        encryptor.thread_manager.set_gui_config(enable_threading=False)
    source = tmp_path / 'input.bin'
    data = bytes(range(251)) * (size // 251) + bytes(range(size % 251))
    source.write_bytes(data)
    config = encryptor._get_encryption_config(profile)
    before = encryptor.thread_manager.get_config()
    estimate = encryptor.hybrid_engine.estimate_admission(size, config, profile=profile)
    assert encryptor.thread_manager.get_config() == before
    assert estimate.strategy == strategy
    if strategy == 'threaded_layered':
        assert any(len(stage) > 1 for stage in estimate.stages)
    result = encryptor.encrypt_file(source, tmp_path / 'out', profile)
    assert result['success'], result
    assert_sizes(estimate, *load_package(result['package_dir']))
    assert CPUDecryptor().decrypt_bytes(result['package_dir'])[0] == data


def test_paranoid_collision_rejected_before_reader_or_engine(tmp_path, encryptor, monkeypatch):
    source = tmp_path / 'input.bin'
    source.write_bytes(b'x' * 131072)
    encryptor.thread_manager.set_gui_config(enable_threading=False)
    calls = []
    monkeypatch.setattr(encryptor.file_processor, 'read_file', lambda *a, **kw: calls.append('read'))
    monkeypatch.setattr(encryptor.hybrid_engine, 'encrypt_data', lambda *a, **kw: calls.append('encrypt'))
    result = encryptor.encrypt_file(source, tmp_path / 'out', 'paranoid')
    assert not result['success'] and result['error_code'] == 'ADMISSION_FORMAT'
    assert '104857' in result['error'] and 'MAX_COLLECTION=100000' in result['error']
    assert calls == [] and not (tmp_path / 'out').exists()


def test_nearby_paranoid_bound_respects_matrix_rounding(encryptor):
    encryptor.thread_manager.set_gui_config(enable_threading=False)
    config = encryptor._get_encryption_config('paranoid')
    near = encryptor.hybrid_engine.estimate_admission(124928, config, profile='paranoid')
    assert near.guaranteed and not near.violations
    assert near.stages[-1][0].insertion_count == 99942
    over = encryptor.hybrid_engine.estimate_admission(124929, config, profile='paranoid')
    assert over.stages[-1][0].insertion_count == 100147 and over.violations


def test_nearby_valid_paranoid_roundtrip(tmp_path, encryptor):
    encryptor.thread_manager.set_gui_config(enable_threading=False)
    source = tmp_path / 'input'; source.write_bytes(b'x' * 124928)
    result = encryptor.encrypt_file(source, tmp_path / 'out', 'paranoid')
    assert result['success'], result
    assert CPUDecryptor().decrypt_bytes(result['package_dir'])[0] == source.read_bytes()


@pytest.mark.parametrize('custom', [True, False])
def test_unknown_config_reports_no_guarantee_and_still_roundtrips(tmp_path, encryptor, custom):
    config = {'layers': [{'method': 'aes256', 'mode': 'CBC'}]}
    estimate = encryptor.hybrid_engine.estimate_admission(19, config, profile='custom', custom=custom)
    assert not estimate.guaranteed and estimate.summary()['status'] == 'no_guarantee'
    source = tmp_path / 'input'; source.write_bytes(b'custom input')
    result = encryptor.encrypt_file(source, tmp_path / 'out', custom_config=config)
    assert result['success'] and result['admission']['status'] == 'no_guarantee', result
    assert CPUDecryptor().decrypt_bytes(result['package_dir'])[0] == source.read_bytes()


def test_explicit_shipped_custom_config_keeps_no_guarantee(encryptor):
    config = encryptor._get_encryption_config('basic')
    assert not encryptor.hybrid_engine.estimate_admission(4, config, profile='basic', custom=True).guaranteed


def test_modified_shipped_name_cannot_claim_a_guarantee(encryptor):
    import copy
    config = copy.deepcopy(encryptor._get_encryption_config('basic'))
    config['layers'][0]['mode'] = 'CBC'
    estimate = encryptor.hybrid_engine.estimate_admission(4, config, profile='basic')
    assert not estimate.guaranteed and estimate.summary()['status'] == 'no_guarantee'


def test_file_growth_read_is_bounded(tmp_path, encryptor, monkeypatch):
    source = tmp_path / 'input'; source.write_bytes(b'four')
    stream = io.BytesIO(b'x' * 10000)
    sizes = []
    class Reader(io.BytesIO):
        def read(self, n=-1):
            sizes.append(n)
            return super().read(n)
    actual = Path.open
    def open_path(path, *a, **kw):
        return Reader(stream.getvalue()) if path == source else actual(path, *a, **kw)
    monkeypatch.setattr(Path, 'open', open_path)
    result = encryptor.encrypt_file(source, tmp_path / 'out', 'basic')
    assert not result['success'] and sizes == [5]
    assert not (tmp_path / 'out').exists()


def test_settings_change_during_read_cannot_change_admitted_topology(tmp_path, encryptor, monkeypatch):
    source = tmp_path / 'input'; source.write_bytes(b'x' * 8193)
    settings = encryptor.thread_manager
    actual = encryptor.file_processor.read_file
    def read(path, **kw):
        settings.set_gui_config(max_threads=1)
        return actual(path, **kw)
    monkeypatch.setattr(encryptor.file_processor, 'read_file', read)
    result = encryptor.encrypt_file(source, tmp_path / 'out', 'parallel_fast')
    assert result['success'], result
    public, _, _ = load_package(result['package_dir'])
    assert len(public['chunk_layers']) == 4
    assert encryptor.hybrid_engine.thread_manager is settings and settings.get_max_threads() == 1


def test_folder_plan_counts_overhead_and_changes(tmp_path):
    folder = tmp_path / 'folder'; folder.mkdir()
    (folder / 'empty').mkdir()
    (folder / '中文.txt').write_bytes(b'abc')
    (folder / 'skip.tmp').write_bytes(b'ignored')
    plan = plan_folder(folder, ('*.tmp',))
    assert len(pack_folder(folder, ('*.tmp',), plan=plan)) == plan.archive_size > 3
    (folder / '中文.txt').write_bytes(b'grew')
    with pytest.raises(Exception, match='changed'):
        pack_folder(folder, ('*.tmp',), plan=plan)


def test_folder_zip64_entry_count_overhead(tmp_path, monkeypatch):
    import zipfile
    monkeypatch.setattr(zipfile, 'ZIP_FILECOUNT_LIMIT', 2)
    folder = tmp_path / 'folder'; folder.mkdir()
    for name in ('a', 'b', 'c'):
        (folder / name).write_bytes(b'')
    plan = plan_folder(folder)
    archive = pack_folder(folder, plan=plan)
    assert plan.archive_size == len(archive) == 22 + 3 * 78 + 76
    with zipfile.ZipFile(io.BytesIO(archive)) as result:
        assert result.namelist() == ['a', 'b', 'c']


def test_folder_member_growth_read_is_bounded(tmp_path, monkeypatch):
    folder = tmp_path / 'folder'; folder.mkdir()
    source = folder / 'input'; source.write_bytes(b'four')
    plan = plan_folder(folder)
    sizes = []
    class Reader(io.BytesIO):
        def read(self, n=-1):
            sizes.append(n)
            return super().read(n)
    actual = Path.open
    monkeypatch.setattr(Path, 'open', lambda path, *a, **kw:
                        Reader(b'x' * 10000) if path == source else actual(path, *a, **kw))
    with pytest.raises(Exception, match='grew'):
        pack_folder(folder, plan=plan)
    assert sizes == [5]


def test_folder_overhead_can_trigger_pre_read_refusal(tmp_path, encryptor, monkeypatch):
    folder = tmp_path / 'folder'; folder.mkdir()
    (folder / 'data').write_bytes(b'x' * 124900)
    encryptor.thread_manager.set_gui_config(enable_threading=False)
    calls = []
    monkeypatch.setattr(encryptor.file_processor, 'process_folder', lambda *a, **k: calls.append(1))
    result = encryptor.encrypt_folder(folder, tmp_path / 'out', 'paranoid')
    assert not result['success'] and result['error_code'] == 'ADMISSION_FORMAT'
    assert calls == [] and not (tmp_path / 'out').exists()


def test_profile_aware_memory_and_cannot_fit_alone(tmp_path, encryptor, monkeypatch):
    estimates = {profile: encryptor.hybrid_engine.estimate_admission(
        65536, encryptor._get_encryption_config(profile), profile=profile)
        for profile in ('basic', 'stealth')}
    assert estimates['stealth'].estimated_peak_bytes > estimates['basic'].estimated_peak_bytes
    encryptor.resource_ledger = ReservationLedger(ResourcePolicy(budget_bytes=1), available_memory=lambda: 10**12)
    source = tmp_path / 'input'; source.write_bytes(b'data')
    monkeypatch.setattr(encryptor.file_processor, 'read_file', lambda *a, **k: pytest.fail('read before refusal'))
    result = encryptor.encrypt_file(source, tmp_path / 'out', 'basic')
    assert not result['success'] and result['error_code'] == 'ADMISSION_RESOURCE'
    assert 'cannot fit even alone' in result['error']


def test_available_memory_refusal_without_waiting():
    ledger = ReservationLedger(ResourcePolicy(100, 50), available_memory=lambda: 55)
    with pytest.raises(ResourceRefusal, match='available=55'):
        with ledger.reserve(AdmissionEstimate(True, '', 1, estimated_peak_bytes=10)):
            pytest.fail('must refuse')
    assert ledger.reserved_bytes == 0


def test_reservation_wait_and_release_after_atypical_failure():
    ledger = ReservationLedger(ResourcePolicy(100, 0), available_memory=lambda: 1000)
    estimate = AdmissionEstimate(True, '', 1, estimated_peak_bytes=75)
    waiting = threading.Event()
    actual_wait = ledger._condition.wait
    def observed_wait(*a, **kw):
        waiting.set()
        return actual_wait(*a, **kw)
    ledger._condition.wait = observed_wait
    def next_task():
        with ledger.reserve(estimate):
            assert ledger.reserved_bytes == 75
            return True
    with ThreadPoolExecutor(max_workers=1) as pool:
        with pytest.raises(LookupError, match='unusual'):
            with ledger.reserve(estimate):
                future = pool.submit(next_task)
                assert waiting.wait(5)
                assert not future.done()
                raise LookupError('unusual non-cipher failure')
        assert future.result(timeout=5)
    assert ledger.peak_reserved_bytes == 75 and ledger.reserved_bytes == 0


def test_batch_reservation_serializes_real_work_and_releases_reader_error(tmp_path, monkeypatch):
    ledger = ReservationLedger(ResourcePolicy(9 * MIB, 0), available_memory=lambda: 2**40)
    batch = BatchProcessor(resource_ledger=ledger)
    source = tmp_path / 'in'; source.mkdir()
    for i in range(3):
        (source / str(i)).write_bytes(b'x' * 8193)
    from src.encryptor.file_processor import FileProcessor
    read = FileProcessor.read_file
    def injected(processor, path, **kw):
        assert ledger.reserved_bytes > 0
        if path.name == '1':
            raise LookupError('atypical reader error')
        return read(processor, path, **kw)
    monkeypatch.setattr(FileProcessor, 'read_file', injected)
    result = batch.process_directory(str(source), str(tmp_path / 'out'), {'parallel': 2, 'profile': 'basic'})
    assert result['successful'] == 2 and result['failed'] == 1, result
    assert ledger.reserved_bytes == 0 and 0 < ledger.peak_reserved_bytes <= 9 * MIB
    for i in (0, 2):
        assert CPUDecryptor().decrypt_bytes(tmp_path / 'out' / f'{i}.jiami')[0] == b'x' * 8193


def test_inner_failure_drains_running_work_before_releasing_reservation(tmp_path, encryptor, monkeypatch):
    source = tmp_path / 'input'; source.write_bytes(b'x' * 8193)
    encryptor.thread_manager.set_gui_config(max_threads=2)
    barrier = threading.Barrier(2, timeout=5)
    running, release = threading.Event(), threading.Event()
    engine = encryptor.hybrid_engine
    actual = engine._run_layer
    def run(data, layer, method):
        barrier.wait()
        if method == 'aes256':
            raise RuntimeError('injected inner-worker failure')
        running.set()
        assert release.wait(5)
        return actual(data, layer, method)
    monkeypatch.setattr(engine, '_run_layer', run)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(encryptor.encrypt_file, source, tmp_path / 'out', 'parallel_fast')
        try:
            assert running.wait(5)
            assert not future.done() and encryptor.resource_ledger.reserved_bytes > 0
        finally:
            release.set()
        result = future.result(timeout=5)
    assert not result['success'] and 'inner-worker failure' in result['error']
    assert engine.thread_pool is None and encryptor.resource_ledger.reserved_bytes == 0
    assert not (tmp_path / 'out').exists()


@pytest.mark.parametrize('size', [0, 1, 10, 11, 99, 100, 1001])
def test_obfuscation_size_threshold_and_reader_compatibility(size):
    count = predicted_collection_sizes('Final_Obfuscation', {'obfuscation_level': 'high'}, size)['insertion_positions']
    assert count == (size // 10 if size > 10 else 0)
    assert predicted_output_size('Final_Obfuscation', {'obfuscation_level': 'high'}, size) == size + count
    # The reader has always accepted a well-formed empty operation list. Do not
    # introduce a new format restriction while extracting producer formulas.
    params = dict(obfuscation_key=bytes(32), original_length=size, obfuscation_level='high',
                  applied_operations=[], operations_count=0)
    validate_params('Final_Obfuscation', params, size, size)


@pytest.mark.parametrize('count', [0, 1, 9, 10, 11, 100])
def test_position_json_lower_bound(count):
    import json
    assert _position_list_minimum(count) == len(json.dumps(list(range(count)), separators=(',', ':')))
