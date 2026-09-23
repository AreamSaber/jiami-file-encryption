# Developing authenticated v1

Read [architecture](architecture.md), [security design](security-redesign.md), and [remote development](remote-development.md) before modifying the protocol or recovery path. Claude provides architecture and review; Codex implements and validates. Claude is invoked manually by the user with an English report tied to an exact commit range.

## Validation

Use the repository virtual environment:

```bash
.venv/bin/python tools/dev.py test -- -rs
.venv/bin/python -m pytest tests/integration/test_batch_processing.py -q
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/integration/test_gui_decryption.py -q
.venv/bin/python -m flake8 src/ cli/ gui/ tools/ main.py --select=E9,F63,F7,F82
```

Windows uses `.venv\Scripts\python.exe` and can set `QT_QPA_PLATFORM=offscreen` in its environment. CI installs Qt and native Twofish explicitly before running the full suite. A CPU-only remote environment legitimately skips the Qt module; that skip is not desktop acceptance. GPU-device tests explain their skips. No fake ciphers or broad dependency skips should hide missing CPU functionality. `tools/dev.py test-core` remains only a configuration/exception subset.

The supported CI matrix is Linux 3.10, 3.11 and 3.12, plus Windows 3.12 (latest patch, at least 3.12.4). Offscreen Qt widget tests exercise real workers and crypto but do not validate native file dialogs, display scaling, packaging or a physical GPU.

## Ownership and cleanup

BatchProcessor owns a configuration template; it never uses that template to encrypt concurrently. Each task snapshots its settings, creates one FileEncryptor, and closes its pool in `finally`. Changes to the task's settings must not mutate global or sibling settings. Avoid concurrently mutating a template while taking snapshots. The global manager remains the compatibility default for other entry points; it is not generally made thread safe by this change.

The main Qt window allows one operation at a time, holds worker references until the real `QThread.finished` signal, and delegates decryption to CPUDecryptor. Authentication, complete-plan validation, hash checking and publication remain centralized. Never implement another GUI-specific cipher or execute an untrusted recovery script to fill a UI feature gap.

The unused LargeFileProcessor, MemoryManager, ProgressTracker, interrupt-controller module, and FileUtils temporary-file/directory helpers have been removed after checking repository callers. Their old exports are intentionally removed too; unknown external imports will need migration. They were not a streaming v1 implementation. The unused Benchmark stub was also removed: its timed block never invoked encryption, so its throughput numbers were not measurements. Use [the bounded profiling tool](memory-profile.md) for current pipeline measurements.

## Review boundaries

Do not change wire format, cipher variants, key placement, authentication order, publication/no-overwrite semantics, or GPU fallback policy as an incidental optimization. Those changes require a separate design review. Preserve failure evidence and never describe a Linux pass as Windows, GUI, EXE or GPU validation. Keep real data, generated recovery secrets, credentials and runtime logs out of commits.
