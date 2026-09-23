#!/usr/bin/env python3
"""Build and execute private synthetic recovery EXEs; publish metrics only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def tree_hashes(path):
    return {str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in path.rglob('*') if p.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    require(sys.platform == 'win32', 'Run this acceptance tool on Windows')
    require(sys.version_info >= (3, 12, 4), 'Private staging requires Python 3.12.4+')
    from src.encryptor.main import FileEncryptor
    from src.encryptor.key_injector import KeyInjector
    from src.crypto.twofish_backend import Twofish
    import PyInstaller
    require(Twofish(bytes(16)).encrypt(bytes(16)).hex() == '9f589f5cf6122c32b6bfec2f2ae8c35a',
            'Native Twofish known-answer mismatch')
    rows = []
    report = {'python': sys.version.split()[0], 'pyinstaller': PyInstaller.__version__,
              'platform': sys.platform, 'results': rows}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix='jiami-exe-acceptance-') as directory:
            work = Path(directory)
            env = dict(os.environ, PYTHONUTF8='1')
            env.pop('PYTHONPATH', None)
            env.pop('PYTHONHOME', None)
            packages, executables = [], []
            for profile, kind in [('multi_algorithm', 'file'), ('paranoid', 'file'), ('standard', 'folder')]:
                row = {'profile': profile, 'kind': kind, 'status': 'running'}
                rows.append(row)
                source = work / (profile + '-input')
                content = bytes(range(256)) + b'\x00\xff'
                if kind == 'folder':
                    (source / 'empty').mkdir(parents=True)
                    (source / 'nested').mkdir()
                    (source / 'nested' / 'sample.bin').write_bytes(content)
                else:
                    source.write_bytes(content)
                engine = FileEncryptor(max_threads=2)
                try:
                    operation = engine.encrypt_folder if kind == 'folder' else engine.encrypt_file
                    result = operation(source, work / 'packages', profile)
                    require(result['success'], str(result))
                finally:
                    engine.hybrid_engine.shutdown()
                package = Path(result['package_dir'])
                packages.append(package)
                exe = work / (profile + '-private-recovery.exe')
                KeyInjector().create_executable_decryptor((package / 'recovery.jmis').read_bytes(), exe)
                require(exe.is_file() and exe.read_bytes()[:2] == b'MZ', 'Missing PE executable')
                executables.append(exe)

                def invoke(data, destination):
                    return subprocess.run([str(exe), str(data), str(destination)], cwd=work,
                                          env=env, capture_output=True, text=True,
                                          encoding='utf-8', errors='replace', timeout=90)

                restored = work / (profile + '-restored')
                recovered = invoke(package / 'data.jmi', restored)
                require(recovered.returncode == 0, 'EXE recovery failed: ' + recovered.stderr)
                if kind == 'folder':
                    require(tree_hashes(restored) == tree_hashes(source), 'Folder content mismatch')
                    require((restored / 'empty').is_dir(), 'Empty folder was lost')
                else:
                    require(restored.read_bytes() == content, 'File content mismatch')
                require('Windows directory durability is not guaranteed' in recovered.stderr,
                        'Windows durability warning missing')
                before = tree_hashes(restored) if kind == 'folder' else restored.read_bytes()
                conflict = invoke(package / 'data.jmi', restored)
                require(conflict.returncode == 1, 'EXE did not report no-overwrite failure')
                after = tree_hashes(restored) if kind == 'folder' else restored.read_bytes()
                require(before == after, 'Existing output was changed')
                corrupt = work / (profile + '-damaged.jmi')
                encoded = (package / 'data.jmi').read_bytes()
                corrupt.write_bytes(encoded[:-1] + bytes([encoded[-1] ^ 1]))
                invalid_output = work / (profile + '-must-not-exist')
                rejected = invoke(corrupt, invalid_output)
                require(rejected.returncode == 1 and not invalid_output.exists(),
                        'Tampered ciphertext published output or wrong exit code')
                legacy = work / (profile + '-legacy.pickle')
                legacy.write_bytes(b'\x80\x04N.')
                rejected = invoke(legacy, invalid_output)
                require(rejected.returncode == 1 and not invalid_output.exists(), 'Legacy input was accepted')
                row.update(status='passed', roundtrip=True, preserves_existing=True,
                           rejects_tampering=True, rejects_legacy=True, durability_warning=True,
                           exe_bytes=exe.stat().st_size)
                print(json.dumps(row), flush=True)
            mismatch = work / 'wrong-recovery-output'
            proc = subprocess.run([str(executables[0]), str(packages[1] / 'data.jmi'), str(mismatch)],
                                  cwd=work, env=env, capture_output=True, timeout=90)
            require(proc.returncode == 1 and not mismatch.exists(), 'Mismatched embedded keys were accepted')
            report['mismatched_embedded_keys_rejected'] = True
            report['status'] = 'passed'
    except Exception as exc:
        report['status'] = 'failed'
        report['error'] = str(exc)
        raise
    finally:
        # No generated EXE, input, ciphertext or recovery secret is uploaded.
        args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
