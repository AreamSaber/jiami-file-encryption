# Using authenticated v1

## Supported environments

The dependency set supports Linux with Python 3.10–3.12. Windows requires Python 3.12.4 or newer within the 3.12 series for the private staging-directory contract. NumPy is constrained below 2, so Python 3.13+ is outside this installation matrix. A C compiler is required to build the real `twofish==0.3.0` dependency. Windows CI uses Visual Studio build tools.

The locked remote CPU environment uses Python 3.12 and omits Qt. From the repository, run:

```bash
python3 tools/dev.py setup
.venv/bin/python tools/dev.py doctor
```

For a desktop environment, create `.venv`, then install `requirements.txt` using that virtual environment's Python. Windows commands use `.venv\Scripts\python.exe`; Linux commands below use `.venv/bin/python`.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install --no-binary=twofish -r requirements.txt
.venv/bin/python -m pip check
```

## Encrypt and recover

```bash
.venv/bin/python main.py --cli --list-profiles
.venv/bin/python main.py --cli -i example.txt -o ./encrypted -p basic
.venv/bin/python encrypted/example.txt.jiami/recover.py encrypted/example.txt.jiami/data.jmi ./restored.txt
```

A directory input uses the same encryption command. Choose an output directory outside the input tree. Recovery targets must not exist. Do not overwrite or delete the originals until you have independently checked a recovered copy.

Each `.jiami` package contains:

| Artifact | Meaning |
|---|---|
| `data.jmi` | Authenticated ciphertext and public metadata, including original name, size and profile |
| `recovery.jmis` | Private keys, authentication key and recovery metadata |
| `recover.py` | Private recovery program embedding recovery secrets |
| `PRIVATE-README.txt` | Handling instructions |

Share only `data.jmi`. The recovery material is not password protected; disclosure exposes the keys, and loss prevents recovery. Only execute a recovery program you trust. The generated program still requires Python and the relevant native dependencies; it is not a standalone EXE.

## Primary Qt interface

Run `.venv/bin/python main.py --gui` on a desktop with PyQt6 installed. Plain `main.py` still opens the historical separate-engine interface; the changes described here apply specifically to `--gui`.

On the encryption tab, choose the source, output directory and profile. On the decryption tab:

1. Select `data.jmi` or its `.jiami` package directory.
2. Select the matching `recovery.jmis`, or leave its field empty to discover it next to the ciphertext.
3. Enter the complete new destination path: a filename for file recovery or directory name for folder recovery. The save-location picker changes its parent directory; the field remains editable.
4. Start decryption and wait for the result. The busy indicator does not claim a percentage. Existing destinations are refused; authentication failures publish no plaintext.

This interface calls the shared authenticated reader and never executes a selected `recover.py`. Windows durability warnings remain visible after recovery. The Cancel Encryption and Cancel Decryption buttons request cooperative cancellation. The UI keeps controls locked and displays a pending state until the worker actually stops. Native cipher/RSA calls and some bounded operations must finish before responding. If publication has already won the gate, the request is reported as too late; a completed output remains successful. Close and overlapping operations remain blocked until the worker finishes.

## Batch operations

```bash
.venv/bin/python -m cli.enhanced_cli batch -d ./documents -o ./encrypted --profile basic --parallel 2
```

Use a separate output directory. `--parallel` must be a positive integer and is an upper request, not a promised number of simultaneous workers. Each file has its own engine and thread settings. The effective CPU thread budget caps outer workers and is divided among their inner pools. Outer orchestration threads are additional to that inner budget. All pools are closed after success, failure or cancellation. Ctrl+C stops new admissions and requests cancellation of active files. Successful, failed and cancelled totals are separate; processed count includes all resolved attempts. Exit status is 1 if any real failure occurred, otherwise 130 if any file was cancelled, otherwise 0. Completed packages remain available, including a publication that won the race against cancellation.

Ctrl+C uses the same cooperative behavior in `main.py --cli`, enhanced CLI encryption and newly generated recovery programs. Repeated Ctrl+C does not forcibly terminate native work. Existing recovery programs retain the code embedded when they were generated. Cancelled staging is retained and its path reported; it can contain keys or verified plaintext. See [cancellation scope and limits](resource-cancellation.md).

Thread limits do not bound memory. On a small host, start with one batch worker and representative small samples; see [memory measurements](memory-profile.md).

Recognized factory profiles now receive size preflight before plaintext reads and
share a soft allocation ledger. The default reservation budget and available-memory
reserve are each a provisional, unvalidated 256 MiB; they are not an OS memory cap.
An operation that cannot fit alone is refused immediately. Custom/modified profiles
explicitly report no admission guarantee and keep post-hoc validation. See
[resource admission](resource-admission.md) for Python configuration and scope.

## Limits and failures

All 11 factory profiles use the CPU baseline. `paranoid_gpu` is a retained name, not proof of GPU execution. Missing algorithm dependencies produce explicit errors, not substitute ciphers. RSA profiles retain their existing local recovery-key model. There is no PBKDF2/Argon2 password protection or recipient-key delivery.

v1 rejects legacy pickle artifacts. Migration requires a separate design and tool. The pipeline buffers complete data, and some transforms expand it. The 1 GiB frame/archive limit and 1 MiB JSON-header limit are format bounds, not safe working-memory limits. The measured `paranoid` topology rejected a 128 KiB input because its recovery-operation list exceeded the existing 100,000-item bound. Recognized plans now reject that predictable violation before reading plaintext or doing the expensive transforms; other metadata checks remain after encryption.

Publication uses private staging and a no-replace operation. Publication failures may retain private `.jiami-stage-*` directories for diagnosis; they can contain secrets or verified plaintext. Inspect the reported paths and remove only the failed operation's staging directory when no process is using it. There is no automatic overwrite, takeover or cross-filesystem copying. Windows does not promise power-loss durability.

## Development diagnostics

`main.py --help` focuses on user operations. `main.py --help-debug` exposes the historical diagnostic flags without changing their legacy behavior. Use `tools/dev.py test -- -rs` for the maintained suite; the older ad hoc `--test` mode is not an acceptance gate.
