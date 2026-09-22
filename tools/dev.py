#!/usr/bin/env python3
"""Repeatable CPU development commands; run from any working directory."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
CORE_TESTS = [
    'tests/unit/test_exceptions.py', 'tests/unit/test_config_manager.py',
    'tests/property/test_exception_properties.py', 'tests/property/test_config_properties.py',
]


def run(args):
    return subprocess.call([str(x) for x in args], cwd=ROOT)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['setup', 'lock', 'doctor', 'test-core', 'test', 'cli'])
    parser.add_argument('args', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    extra = args.args[1:] if args.args[:1] == ['--'] else args.args
    uv = shutil.which('uv') or str(Path.home() / '.local/bin/uv')
    if args.command in ('setup', 'lock') and not Path(uv).is_file():
        parser.error('uv is required. Install it from https://docs.astral.sh/uv/getting-started/installation/')
    if args.command == 'setup':
        if not PYTHON.exists():
            version = (ROOT / '.python-version').read_text(encoding='utf-8').strip()
            code = run([uv, 'venv', '--python', version, '.venv'])
            if code:
                return code
        return run([uv, 'pip', 'sync', '--python', PYTHON, '--no-binary', 'twofish',
                    'requirements-remote.lock'])
    if args.command == 'lock':
        # Keep requirements.txt as the dependency source; omit desktop bindings on the CPU host.
        lines = [line for line in (ROOT / 'requirements.txt').read_text(encoding='utf-8').splitlines()
                 if not line.strip().lower().startswith(('pyqt6', 'pyside6'))]
        with tempfile.TemporaryDirectory(prefix='jiami-lock-') as tmp:
            source = Path(tmp) / 'requirements.in'
            source.write_text('\n'.join(lines) + '\n', encoding='utf-8')
            return run([uv, 'pip', 'compile', '--python-version', '3.12', '--no-header', '--no-annotate',
                        '--no-binary', 'twofish', source, '-o', ROOT / 'requirements-remote.lock'])
    if args.command == 'doctor':
        missing = []
        for label, path in [('uv', Path(uv)), ('Python venv', PYTHON),
                            ('key injector', ROOT / 'src/encryptor/key_injector.py'),
                            ('base decryptor', ROOT / 'src/decryptor/base_decryptor.py')]:
            present = path.is_file()
            print(f'{"OK" if present else "MISSING"}: {label}: {path}', flush=True)
            if not present:
                missing.append(label)
        if PYTHON.exists():
            run([PYTHON, '--version'])
        print('GUI/GPU/Windows packaging require separate validation on a suitable machine.')
        return int(bool(missing))
    if not PYTHON.exists():
        parser.error('Run python tools/dev.py setup first (uv must be installed).')
    if args.command in ('test', 'test-core'):
        paths = CORE_TESTS if args.command == 'test-core' else ['tests']
        return run([PYTHON, '-m', 'pytest', *paths, '-q', '--tb=short', *extra])
    return run([PYTHON, 'main.py', '--cli', *extra])


if __name__ == '__main__':
    raise SystemExit(main())
