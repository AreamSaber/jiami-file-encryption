#!/usr/bin/env python3
"""Bounded synthetic CPU round trips; JSON measurements, not capacity guarantees."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MIB = 1024 * 1024


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(MIB), b''):
            value.update(block)
    return value.hexdigest()


def child(directory, profile, size, unit='mib', trace=False, calls=False):
    from src.encryptor.main import FileEncryptor
    from src.decryptor.cpu_decryptor import CPUDecryptor
    from src.thread_pool.thread_manager import thread_manager
    source = Path(directory) / 'sample.bin'
    remaining = size * (1024 if unit == 'kib' else MIB)
    with source.open('wb') as stream:
        while remaining:
            block = min(remaining, MIB)
            stream.write(os.urandom(block))
            remaining -= block
    settings = thread_manager.snapshot()
    settings.set_gui_config(max_threads=2)
    engine = FileEncryptor(thread_settings=settings)
    if trace:
        observe_layers(engine.hybrid_engine, calls)
    start = time.perf_counter()
    try:
        result = engine.encrypt_file(source, Path(directory) / 'packages', profile)
        if not result['success']:
            raise RuntimeError(result['error'])
        encrypt_seconds = time.perf_counter() - start
        if trace:
            print('LAYER ' + json.dumps({'event': 'publication_complete'}), flush=True)
        start = time.perf_counter()
        restored = Path(CPUDecryptor().decrypt_file(result['encrypted_file'], Path(directory) / 'restored'))
        decrypt_seconds = time.perf_counter() - start
        if trace:
            print('LAYER ' + json.dumps({'event': 'recovery_complete'}), flush=True)
        if digest(restored) != digest(source):
            raise RuntimeError('Restored SHA-256 mismatch')
        peak = 0
        if sys.platform.startswith('linux'):
            import resource
            peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        print('MEASUREMENT ' + json.dumps({
            'encrypt_seconds': round(encrypt_seconds, 3),
            'decrypt_seconds': round(decrypt_seconds, 3),
            'ciphertext_mib': round(Path(result['encrypted_file']).stat().st_size / MIB, 3),
            'os_peak_rss_mib': round(peak, 1), 'sha256_match': True,
        }), flush=True)
    finally:
        engine.hybrid_engine.shutdown()


def observe_layers(engine, calls=False):
    """Wrap the real layer dispatcher in this disposable process, without keys.

    RSS observations are process-wide snapshots, not per-layer allocation peaks.
    Optional cProfile timings include instrumentation overhead.
    """
    import cProfile
    import pstats
    import threading
    process = psutil.Process()
    output_lock = threading.Lock()
    actual = engine._run_layer

    def emit(value):
        with output_lock:
            print('LAYER ' + json.dumps(value), flush=True)

    def observed(data, layer, method):
        name = layer.get('algorithm', method)
        emit({'event': 'start', 'layer': name, 'input_bytes': len(data),
              'rss_mib': round(process.memory_info().rss / MIB, 1)})
        profiler = cProfile.Profile() if calls else None
        start = time.perf_counter()
        if profiler:
            profiler.enable()
        try:
            encrypted, metadata = actual(data, layer, method)
        finally:
            if profiler:
                profiler.disable()
        value = {'event': 'end', 'layer': name, 'output_bytes': len(encrypted),
                 'seconds': round(time.perf_counter() - start, 4),
                 'rss_mib': round(process.memory_info().rss / MIB, 1)}
        if name == 'final_obfuscation':
            value['insertion_count'] = sum(len(op[1]) for op in metadata.get('applied_operations', [])
                                           if op[0] == 'frequency_analysis_resistance')
        if profiler:
            stats = pstats.Stats(profiler).stats
            value['top_self_time'] = [
                {'function': key[2], 'calls': record[1], 'self_seconds': round(record[2], 4)}
                for key, record in sorted(stats.items(), key=lambda pair: pair[1][2], reverse=True)[:6]
            ]
        emit(value)
        return encrypted, metadata

    engine._run_layer = observed


def measure(profile, size, timeout, rss_limit, unit='mib', trace=False, calls=False):
    row = {'profile': profile, 'input_' + unit: size, 'status': 'failed'}
    # All artifacts, including recovery secrets, are synthetic and private.
    with tempfile.TemporaryDirectory(prefix='jiami-memory-') as directory:
        log = Path(directory) / 'worker.log'
        with log.open('wb') as stream:
            command = [sys.executable, str(Path(__file__).resolve()),
                       '--child', directory, '--profiles', profile, '--sizes-' + unit, str(size)]
            if trace:
                command.append('--trace-layers')
            if calls:
                command.append('--profile-calls')
            proc = subprocess.Popen(command, cwd=ROOT,
                                    stdout=stream, stderr=subprocess.STDOUT)
            process = psutil.Process(proc.pid)
            peak, start = 0, time.monotonic()
            try:
                while proc.poll() is None:
                    try:
                        peak = max(peak, process.memory_info().rss / MIB)
                    except psutil.NoSuchProcess:
                        break
                    if peak > rss_limit:
                        row['status'] = 'rss_limit'
                        proc.kill()
                        break
                    if time.monotonic() - start > timeout:
                        row['status'] = 'timeout'
                        proc.kill()
                        break
                    time.sleep(0.02)
                proc.wait(timeout=10)
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
        row['sampled_peak_rss_mib'] = round(peak, 1)
        row['exit_code'] = proc.returncode
        output = log.read_text(encoding='utf-8', errors='replace')
        if trace:
            row['layers'] = [json.loads(line[6:]) for line in output.splitlines() if line.startswith('LAYER ')]
        measurements = [line[12:] for line in output.splitlines() if line.startswith('MEASUREMENT ')]
        if proc.returncode == 0 and measurements:
            row.update(json.loads(measurements[-1]))
            row['status'] = 'passed'
        else:
            row['diagnostic_tail'] = output[-2000:]
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profiles', nargs='+', default=['basic', 'parallel_fast'])
    sizes = parser.add_mutually_exclusive_group()
    sizes.add_argument('--sizes-mib', nargs='+', type=int)
    sizes.add_argument('--sizes-kib', nargs='+', type=int)
    parser.add_argument('--trace-layers', action='store_true', help='Record real layer timing and RSS snapshots, without secrets')
    parser.add_argument('--profile-calls', action='store_true', help='Include cProfile self-time summaries; adds overhead')
    parser.add_argument('--timeout', type=float, default=60)
    parser.add_argument('--rss-limit-mib', type=int, default=768)
    parser.add_argument('--child', help=argparse.SUPPRESS)
    args = parser.parse_args()
    unit = 'kib' if args.sizes_kib is not None else 'mib'
    selected_sizes = args.sizes_kib if unit == 'kib' else (args.sizes_mib or [8, 32])
    if any(size < 1 or size > (128 * 1024 if unit == 'kib' else 128) for size in selected_sizes):
        parser.error('Synthetic samples must be positive and at most 128 MiB')
    if args.profile_calls and not args.trace_layers:
        parser.error('--profile-calls requires --trace-layers')
    if not 0 < args.timeout <= 300 or not 128 <= args.rss_limit_mib <= 1024:
        parser.error('Use timeout <= 300 seconds and RSS limit between 128 and 1024 MiB')
    if args.child:
        child(args.child, args.profiles[0], selected_sizes[0], unit, args.trace_layers, args.profile_calls)
        return 0
    report = {'python': sys.version.split()[0], 'platform': sys.platform,
              'rss_limit_mib': args.rss_limit_mib, 'timeout_seconds': args.timeout,
              'threads_per_engine': 2, 'layer_trace': args.trace_layers,
              'cprofile_enabled': args.profile_calls, 'results': []}
    for profile in args.profiles:
        for size in selected_sizes:
            report['results'].append(measure(profile, size, args.timeout, args.rss_limit_mib,
                                              unit, args.trace_layers, args.profile_calls))
    print(json.dumps(report, indent=2))
    return int(any(row['status'] != 'passed' for row in report['results']))


if __name__ == '__main__':
    raise SystemExit(main())
