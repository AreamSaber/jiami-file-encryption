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


def child(directory, profile, size):
    from src.encryptor.main import FileEncryptor
    from src.decryptor.cpu_decryptor import CPUDecryptor
    from src.thread_pool.thread_manager import thread_manager
    source = Path(directory) / 'sample.bin'
    with source.open('wb') as stream:
        for _ in range(size):
            stream.write(os.urandom(MIB))
    settings = thread_manager.snapshot()
    settings.set_gui_config(max_threads=2)
    engine = FileEncryptor(thread_settings=settings)
    start = time.perf_counter()
    try:
        result = engine.encrypt_file(source, Path(directory) / 'packages', profile)
        if not result['success']:
            raise RuntimeError(result['error'])
        encrypt_seconds = time.perf_counter() - start
        start = time.perf_counter()
        restored = Path(CPUDecryptor().decrypt_file(result['encrypted_file'], Path(directory) / 'restored'))
        decrypt_seconds = time.perf_counter() - start
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


def measure(profile, size, timeout, rss_limit):
    row = {'profile': profile, 'input_mib': size, 'status': 'failed'}
    # All artifacts, including recovery secrets, are synthetic and private.
    with tempfile.TemporaryDirectory(prefix='jiami-memory-') as directory:
        log = Path(directory) / 'worker.log'
        with log.open('wb') as stream:
            proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
                                     '--child', directory, '--profiles', profile,
                                     '--sizes-mib', str(size)], cwd=ROOT,
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
    parser.add_argument('--sizes-mib', nargs='+', type=int, default=[8, 32])
    parser.add_argument('--timeout', type=float, default=60)
    parser.add_argument('--rss-limit-mib', type=int, default=768)
    parser.add_argument('--child', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if any(size < 1 or size > 128 for size in args.sizes_mib):
        parser.error('Synthetic samples must be between 1 and 128 MiB')
    if not 0 < args.timeout <= 300 or not 128 <= args.rss_limit_mib <= 1024:
        parser.error('Use timeout <= 300 seconds and RSS limit between 128 and 1024 MiB')
    if args.child:
        child(args.child, args.profiles[0], args.sizes_mib[0])
        return 0
    report = {'python': sys.version.split()[0], 'platform': sys.platform,
              'rss_limit_mib': args.rss_limit_mib, 'timeout_seconds': args.timeout,
              'threads_per_engine': 2, 'results': []}
    for profile in args.profiles:
        for size in args.sizes_mib:
            report['results'].append(measure(profile, size, args.timeout, args.rss_limit_mib))
    print(json.dumps(report, indent=2))
    return int(any(row['status'] != 'passed' for row in report['results']))


if __name__ == '__main__':
    raise SystemExit(main())
