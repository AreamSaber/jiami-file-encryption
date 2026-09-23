"""Test-only gate/signal observation, also usable as a PyInstaller runtime hook.

Never included by the production KeyInjector. Enabled only by the acceptance
tool's private environment. No replacement cipher, gate or cancellation handler.
"""
import builtins
import json
import os
from pathlib import Path
import runpy
import signal
import sys
import time


def record(directory, name, value):
    path = directory / name
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value), encoding='utf-8')
    temporary.replace(path)


def install_probe(module, directory, ordering):
    enter = module.PublicationGate.enter_publishing
    request = module.CancellationToken.request_cancel
    original_signal = signal.signal
    counts = {'requests': 0, 'signals': 0}

    def held_gate(gate):
        result = enter(gate) if ordering != 'cancel' else None
        record(directory, 'ready.json', {'pid': os.getpid(), 'runtime': module.__file__})
        deadline = time.monotonic() + 45
        while not (directory / 'release').exists():
            if time.monotonic() >= deadline:
                raise TimeoutError('Acceptance gate release missing')
            time.sleep(0.01)
        return enter(gate) if ordering == 'cancel' else result

    def observed_request(token):
        accepted = request(token)
        counts['requests'] += 1
        record(directory, 'request.json', {'accepted': accepted, 'count': counts['requests']})
        return accepted

    def observed_signal(number, handler):
        if number == signal.SIGINT and getattr(handler, '__name__', '') == 'request_once':
            def observe(*args):
                handler(*args)  # Always execute the real installed handler.
                counts['signals'] += 1
                record(directory, f'signal-{counts["signals"]}.json', {'handled': True})
            return original_signal(number, observe)
        return original_signal(number, handler)

    module.PublicationGate.enter_publishing = held_gate
    module.CancellationToken.request_cancel = observed_request
    signal.signal = observed_signal


def arm_import_probe():
    directory = os.environ.get('JIAMI_CONSOLE_PROBE')
    if not directory:
        return
    directory = Path(directory)
    ordering = os.environ['JIAMI_CONSOLE_ORDERING']
    original_import = builtins.__import__

    def imported(name, *args, **kwargs):
        result = original_import(name, *args, **kwargs)
        if name == 'src.package_format.cancellation':
            module = sys.modules[name]
            if hasattr(module, 'PublicationGate'):
                builtins.__import__ = original_import
                install_probe(module, directory, ordering)
        return result

    builtins.__import__ = imported


arm_import_probe()
if __name__ == '__main__' and not getattr(sys, 'frozen', False):
    sys.argv = sys.argv[1:]
    runpy.run_path(sys.argv[0], run_name='__main__')
