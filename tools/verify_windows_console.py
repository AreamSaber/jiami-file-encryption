"""Accept real Windows CTRL_C_EVENT delivery in an isolated hidden console.

Application logic is unchanged; a test-only probe holds the real publication
gate and observes the real Python handler. Output artifacts contain metrics only.
"""
import argparse
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / 'tools/windows_console_probe.py'
sys.path.insert(0, str(ROOT))


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def wait_marker(path, process=None, seconds=30):
    deadline = time.monotonic() + seconds
    while not path.exists():
        if process is not None and process.poll() is not None:
            raise RuntimeError(f'Process exited {process.returncode} before {path.name}')
        if time.monotonic() >= deadline:
            raise TimeoutError('Missing console handshake: ' + path.name)
        time.sleep(0.01)


def send_console_event(pid, marker):
    # This helper starts detached from the host's console, then attaches only
    # to the new console belonging to the Popen PID supplied by this tool.
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    # CREATE_NO_WINDOW can still provide a console association on Windows.
    # Detach this helper only; never detach the acceptance runner or target.
    kernel.FreeConsole()
    require(kernel.AttachConsole(pid), 'AttachConsole failed: ' + str(ctypes.get_last_error()))
    try:
        require(kernel.SetConsoleCtrlHandler(None, True), 'Cannot protect the signal helper')
        require(kernel.GenerateConsoleCtrlEvent(0, 0), 'GenerateConsoleCtrlEvent failed')
        wait_marker(marker, seconds=10)
    finally:
        kernel.FreeConsole()


def instrumented_exe(recovery, destination):
    from src.encryptor.key_injector import KeyInjector
    actual = subprocess.run

    def build(command, **kwargs):
        require(command[1:3] == ['-m', 'PyInstaller'], 'Unexpected packager command')
        return actual([*command, '--runtime-hook', str(PROBE)], **kwargs)

    # The real generator/build/publication path runs. Only this acceptance
    # build receives an extra runtime hook; production builds never include it.
    with patch('src.encryptor.key_injector.subprocess.run', side_effect=build):
        KeyInjector().create_executable_decryptor(recovery, destination)


def run_case(work, entry, ordering, package, exe):
    from src.decryptor.cpu_decryptor import CPUDecryptor
    case = work / f'{entry}-{ordering}'
    case.mkdir()
    probe = case / 'probe'; probe.mkdir()
    inputs = case / 'inputs'; inputs.mkdir()
    source = inputs / 'source.bin'; source.write_bytes(b'native console acceptance\x00\xff')
    output = case / 'output'
    recovering = entry.startswith('recover')
    destination = output if recovering else output / 'source.bin.jiami'
    if ordering == 'conflict':
        if recovering:
            destination.write_bytes(b'preserve existing')
        else:
            destination.mkdir(parents=True)
            (destination / 'keep').write_bytes(b'preserve existing')
    env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8',
               JIAMI_CONSOLE_PROBE=str(probe), JIAMI_CONSOLE_ORDERING=ordering)
    env.pop('PYTHONHOME', None)
    env.pop('PYTHONPATH', None)
    if entry == 'recover-exe':
        command = [str(exe), str(package / 'data.jmi'), str(output)]
    elif entry == 'recover-python':
        command = [sys.executable, str(PROBE), str(package / 'recover.py'), str(package / 'data.jmi'), str(output)]
    else:
        env['PYTHONPATH'] = str(ROOT)
        script = ROOT / ('main.py' if entry == 'primary' else 'cli/enhanced_cli.py')
        if entry == 'primary':
            args = ['--cli', '-i', str(source)]
        elif entry == 'enhanced':
            args = ['encrypt', '-i', str(source)]
        else:
            # EnhancedCLI's relative imports need module execution for batch.
            script = case / 'batch.py'
            script.write_text("from cli.enhanced_cli import EnhancedCLI\nraise SystemExit(EnhancedCLI().run())\n", encoding='utf-8')
            args = ['batch', '-d', str(inputs), '--parallel', '2']
        command = [sys.executable, str(PROBE), str(script), *args, '-o', str(output), '-p', 'basic']
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    stdout, stderr = case / 'stdout.log', case / 'stderr.log'
    failure = None
    with stdout.open('wb') as out, stderr.open('wb') as err:
        process = subprocess.Popen(command, cwd=case, env=env, stdout=out, stderr=err,
                                   startupinfo=startup, creationflags=subprocess.CREATE_NEW_CONSOLE)
        try:
            wait_marker(probe / 'ready.json', process)
            ready = json.loads((probe / 'ready.json').read_text(encoding='utf-8'))
            if recovering:
                require('runtime.zip' in ready['runtime'], 'Recovery did not use embedded runtime')
            # Both events are generated externally through the real console.
            # The signal-2 marker proves the second Python handler invocation
            # returned before work is released; it is not a timing assumption.
            for number in (1, 2):
                helper = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--signal',
                                         str(process.pid), str(probe / f'signal-{number}.json')],
                                        capture_output=True, text=True, encoding='utf-8', env=env,
                                        creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
                require(helper.returncode == 0, helper.stdout + helper.stderr)
            request = json.loads((probe / 'request.json').read_text(encoding='utf-8'))
            require(request == {'accepted': ordering == 'cancel', 'count': 1}, 'Wrong request result: ' + str(request))
            require(process.poll() is None, 'Cancellation returned before held work ended')
            if ordering != 'conflict':
                require(not destination.exists(), 'Published before releasing the gate')
        except Exception as exc:
            failure = exc
        finally:
            (probe / 'release').touch()
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                # Only this private synthetic acceptance process tree, on a
                # harness failure. The application never force-kills its workers.
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                               capture_output=True, timeout=15)
                process.wait(timeout=10)
                failure = failure or TimeoutError('Console target did not exit after release')
    captured = stdout.read_text(encoding='utf-8') + stderr.read_text(encoding='utf-8')
    if failure:
        raise RuntimeError(f'{entry}/{ordering}: {failure}\n{captured}') from failure
    def check(condition, message):
        require(condition, f'{entry}/{ordering}: {message}\n{captured}')

    expected = {'cancel': 130, 'publish': 0, 'conflict': 1}[ordering]
    check(process.returncode == expected, f'exit {process.returncode}, wanted {expected}')
    stage_path_canonicalized = False
    if ordering == 'cancel':
        check(not destination.exists(), 'Cancelled operation published output')
        parent = case if recovering else output
        stages = list(parent.glob('.jiami-stage-*'))
        # Publishers report canonical paths. Windows TEMP may use an 8.3 alias
        # (e.g. RUNNER~1), so compare the same canonical representation.
        check(len(stages) == 1 and str(stages[0].resolve()) in captured,
              'Retained stage not reported: ' + repr([str(p) for p in stages]))
        stage_path_canonicalized = str(stages[0]) != str(stages[0].resolve())
    elif ordering == 'publish':
        content = destination.read_bytes() if recovering else CPUDecryptor().decrypt_bytes(destination)[0]
        check(content == b'native console acceptance\x00\xff', 'Completed plaintext mismatch')
        check('too late' in captured, 'Late request warning missing')
        check('Windows directory durability is not guaranteed' in captured, 'Durability warning missing')
    else:
        existing = destination if recovering else destination / 'keep'
        check(existing.read_bytes() == b'preserve existing', 'Existing destination changed')
    return {'entry': entry, 'ordering': ordering, 'status': 'passed', 'exit_code': process.returncode,
            'console_events_observed': 2, 'cancellation_requests': request['count'],
            'embedded_runtime': recovering, 'instrumented_gate': True,
            'stage_path_canonicalized': stage_path_canonicalized}


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--signal':
        send_console_event(int(sys.argv[2]), Path(sys.argv[3]))
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--skip-exe', action='store_true', help='Supplementary source-only run; not full acceptance')
    args = parser.parse_args()
    require(sys.platform == 'win32', 'Windows console acceptance requires Windows')
    require(sys.version_info >= (3, 12, 4), 'Private staging requires Python 3.12.4+')
    rows = []
    report = {'python': sys.version.split()[0], 'platform': sys.platform, 'results': rows,
              'signal': 'GenerateConsoleCtrlEvent(CTRL_C_EVENT, 0)',
              'isolated_hidden_console': True, 'test_only_probe': True, 'exe_included': not args.skip_exe}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    try:
        from src.encryptor.main import FileEncryptor
        with tempfile.TemporaryDirectory(prefix='jiami-console-acceptance-') as directory:
            work = Path(directory)
            source = work / 'source.bin'; source.write_bytes(b'native console acceptance\x00\xff')
            engine = FileEncryptor(max_threads=2)
            try:
                result = engine.encrypt_file(source, work / 'packages', 'basic')
                require(result['success'], str(result))
            finally:
                engine.hybrid_engine.shutdown()
            package, exe = Path(result['package_dir']), work / 'private-recovery.exe'
            entries = ['primary', 'enhanced', 'batch', 'recover-python']
            if not args.skip_exe:
                instrumented_exe((package / 'recovery.jmis').read_bytes(), exe)
                entries.append('recover-exe')
            for entry in entries:
                for ordering in ('cancel', 'publish', 'conflict'):
                    row = {'entry': entry, 'ordering': ordering, 'status': 'running'}
                    rows.append(row)
                    row.update(run_case(work, entry, ordering, package, exe))
                    print(json.dumps(row), flush=True)
            report['status'] = 'passed'
    except Exception as exc:
        report['status'], report['error'] = 'failed', str(exc)
        raise
    finally:
        args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
