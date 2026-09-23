# Cooperative cancellation and publication ordering

Phase 2 implements the design approved by Claude, following the separately
approved admission baseline `b10b75a45178a624c0d41525c42bca6f59c3a9c1`.
This implementation range is pending manual review. It changes no v1 cipher,
key model, authentication order, schema bounds or no-overwrite rule.

## Interfaces and gate

`src/package_format/cancellation.py` defines `CancellationToken`,
`CancellationGroup`, `OperationCancelled`, `PublicationGate` and CLI helpers.
Use one token for one attempted output. Optional keyword `cancellation=` is
accepted by FileEncryptor file/folder operations, HybridEncryptionEngine,
BaseDecryptor load/bytes/file operations, archive helpers, reservations and
publishers. Existing callers can omit it. A publishing token cannot be reused.

The gate owns a lock and three private states. `request_cancel()` transitions
pending to cancelled (repeated requests are idempotent). `enter_publishing()`
transitions pending to publishing once, under the same lock. A request in
publishing returns false and records a late request. A checkpoint in cancelled
raises `OperationCancelled` with error code `CANCELLED`.

Before the final no-replace rename, the publisher enters this gate after private
staging, validation and the existing pre-rename synchronization. If cancellation
wins, rename is never called. If publication wins, there are no further
cancellation checkpoints: finish rename, durability reporting and cleanup.
Entering publishing is not itself successful publication. A collision or other
rename failure is still a real error. After successful publication, a late
request is a warning on success, never a cancellation. Post-rename directory
fsync failure remains published with durability unconfirmed. No output is removed.

Owned private staging is retained on cancellation or failure after creation.
Results include the exact path and a warning about keys/recovery secrets or
verified plaintext. An incomplete private file may remain there. No matching
directory cleanup, automatic retry, overwrite or secure-erasure claim is added.
Exception notes also survive on Python 3.10 via the `__notes__` attribute.

## Checkpoints and resource lifetime

Check before producer reads, between 64 KiB plaintext read/write blocks,
between folder members and cipher layers/chunks, and at reservation waits.
Maintained Python transforms check at most every 4,096 iterator items, including
the existing final-obfuscation insertion/removal loops. An item is not a fixed
amount of CPU time. Context-local tokens are explicitly bound inside each
inner cipher worker and each authenticated recovery layer; independent tasks
do not share a mutable token context.

Native cipher/RSA calls, random sampling/sorting, bulk allocations/copies,
authentication/JSON processing, bounded frame reads, archive member reads,
filesystem calls and program generation may finish before a checkpoint is
reached. There is no guaranteed cancellation latency. The pipeline remains
in-memory, not streaming, and the admission budget remains soft and uncalibrated.

Reservation waits check cancellation at intervals of at most 100 ms while
waiting, subject to scheduler delays; they do not busy-spin. The claim is
released only after the operation and all already-running inner workers have
ended. On an inner cancellation, the engine drains its pool and preserves any
real error from another submitted future instead of hiding it behind cancellation.
No thread termination, process kill, hard memory isolation or forced second Ctrl+C
is used. An engine remains operation-owned, not safe for concurrent reuse.

## Batch, CLI and Qt behavior

`BatchProcessor.process_directory` and `process_file_list` accept a
`CancellationGroup`. The group registers an individual token per attempt and
requests cancellation of active tokens. Already queued futures resolve as
cancelled before creating another engine or reading file contents. Directory
enumeration and scheduling are not preempted; resolving a large cancelled queue
can take time. A discovered empty/invalid batch remains an input error.
Published successes remain valid. Counts are distinct and progress counts every
resolved attempt. Final status has precedence: real error **1**, otherwise any
cancelled attempt **130**, otherwise success **0**. A late request alone exits 0.

`main.py --cli`, enhanced CLI encrypt/batch, and newly generated `recover.py`
install SIGINT handling around the operation. Actual work runs in one outer
thread, leaving the main thread to request cancellation without interrupting
worker locks or rename. A reentrancy guard makes repeated SIGINT a no-op while
the first handler acquires controller locks. The prior handler is restored on
exit. Calls from a non-main thread cannot install a signal handler; their owner
must request cancellation on the supplied controller. Signals before/after the
operation wrapper retain the entry point's ordinary behavior.

The primary `main.py --gui` window has Cancel Encryption and Cancel Decryption
buttons. Pending text explicitly says the worker must finish. A late request
shows publication has already started. Terminal outcome signals disable cancel
controls; only real `QThread.finished` releases worker references and restores
start controls. Close remains blocked while a worker exists. No percentage is
claimed for decryption. Errors and retained-stage paths remain visible.

The historical GUI selected by plain `main.py`, legacy entry points and standalone
experimental GPU adapters are not new cancellation acceptance surfaces. A custom
GPU backend may inherit boundary checks but can remain nonpreemptible. Hardware
execution is not validated here. Existing recovery scripts/EXEs do not update
themselves; new ones embed the authoritative cancellation module. New recovery
EXEs retain their ordinary round-trip acceptance workflow; real Windows console
Ctrl+C delivery needs separate native-console acceptance.

## Verification contract

`test_cancellation.py` covers barrier-controlled gate ordering, real file/folder
encryption and recovery in both orderings, pre-read cancellation, private partial
writes, unchanged unrelated staging, a controlled native-call boundary, waiting
reservations, surviving inner workers and real-error precedence, periodic recovery
loops, batch counts, late publication/collision/durability outcomes, and actual
POSIX SIGINT through both CLIs and the generated embedded recovery runtime.

`test_gui_decryption.py` adds actual offscreen Qt clicks with a real held worker
for both operations and both gate orderings. It verifies pending wording, close
deferral, locked controls and final outputs/status. Existing 11-profile,
authentication, standalone recovery, publication and platform tests remain
regression gates. No test result here substitutes for real desktop interaction,
Windows console signal delivery, GPU hardware or physical power-loss acceptance.
