"""Generate a standalone launcher from the authoritative recovery modules."""
import base64
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

from src.package_format.envelope import decode_frame
from src.package_format.publication import write_private


class KeyInjector:
    def create_python_decryptor(self, recovery_bytes, output_path):
        decode_frame(recovery_bytes, secret=True)
        root = Path(__file__).resolve().parents[2]
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as bundle:
            # Minimal package initializers avoid importing encryption/GUI dependencies.
            for name in ('src', 'src/decryptor', 'src/package_format', 'src/crypto'):
                bundle.writestr(name + '/__init__.py', '')
            files = list((root/'src/exceptions').glob('*.py'))
            files += [root/'src/crypto/twofish_backend.py', root/'src/crypto/TWOFISH-LICENSE.txt']
            files += list((root/'src/package_format').glob('*.py'))
            files += [root/'src/decryptor'/name for name in
                      ('base_decryptor.py', 'cpu_decryptor.py', 'algorithm_registry.py')]
            for path in files:
                if path.parent.name == 'package_format' and path.name == '__init__.py':
                    continue
                bundle.writestr(path.relative_to(root).as_posix(), path.read_bytes())
        runtime = base64.b64encode(buffer.getvalue()).decode('ascii')
        secret = base64.b64encode(recovery_bytes).decode('ascii')
        script = '''#!/usr/bin/env python3
"""PRIVATE recovery program. Contains keys; do not share this file.
Requires cryptography, PyNaCl, pycryptodome, and twofish for applicable profiles.
"""
import argparse, base64, pathlib, sys, tempfile

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', help='data.jmi or its package directory')
    parser.add_argument('output', nargs='?', help='new output path; existing paths are never overwritten')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='jiami-runtime-') as directory:
        runtime = pathlib.Path(directory) / 'runtime.zip'
        runtime.write_bytes(base64.b64decode(RUNTIME))
        sys.path.insert(0, str(runtime))
        from src.decryptor.cpu_decryptor import CPUDecryptor
        decryptor = CPUDecryptor(recovery_bytes=base64.b64decode(RECOVERY))
        try:
            path = decryptor.decrypt_file(args.input, args.output)
            print(path)
            if decryptor.last_publication.warning:
                print(decryptor.last_publication.warning, file=sys.stderr)
        except Exception as exc:
            print('Recovery failed: ' + str(exc), file=sys.stderr)
            return 1
    return 0

'''
        script += 'RUNTIME = ' + repr(runtime) + '\nRECOVERY = ' + repr(secret) + '\n'
        script += "if __name__ == '__main__':\n    raise SystemExit(main())\n"
        write_private(output_path, script.encode('utf-8'))
        return str(output_path)

    def create_executable_decryptor(self, recovery_bytes, output_path):
        """Explicit optional PyInstaller build; failures never masquerade as an exe."""
        destination = Path(output_path).absolute()
        if sys.platform != 'win32':
            raise RuntimeError('Build Windows recovery executables on Windows')
        if destination.exists():
            raise FileExistsError(destination)
        import importlib.util
        native = importlib.util.find_spec('_twofish')
        if native is None or not native.origin:
            raise RuntimeError('Install the native twofish dependency before building the executable')
        with tempfile.TemporaryDirectory(prefix='.jiami-build-', dir=destination.parent) as directory:
            work = Path(directory)
            script = work/'recover.py'
            self.create_python_decryptor(recovery_bytes, script)
            subprocess.run([sys.executable, '-m', 'PyInstaller', '--onefile', '--clean',
                            '--distpath', str(work/'dist'), '--workpath', str(work/'build'),
                            '--specpath', str(work), '--collect-all', 'cryptography',
                            '--collect-all', 'nacl', '--collect-all', 'Crypto',
                            '--add-binary', native.origin + ';.', str(script)], check=True)
            from src.package_format.publication import publish_file
            publish_file((work/'dist/recover.exe').read_bytes(), destination)
        return str(destination)
