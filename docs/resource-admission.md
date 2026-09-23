# Producer admission and memory reservations — Phase 1

This implements the admission-first slice approved by Claude at baseline
`5701e428a42f537d380a2fb063f995fa678bccd7`. Cancellation is a separate future
review range. No cipher, wire limit, publication rule, GUI lifecycle or CLI exit
precedence changes here.

## What runs before plaintext is read

FileEncryptor resolves the profile and captures operation-owned thread settings
and configuration. It stats a file, or builds a stat-only ZIP_STORED folder plan
that includes directories, UTF-8 filenames, local/central headers and ZIP64
entry-count footer overhead. It then forecasts the exact selected topology,
ciphertext lengths and final-obfuscation insertion counts. The estimator uses
the same strategy/chunk helpers as the engine and simulates thread recommendations
on a separate settings snapshot, without starting a cipher or inner pool.

The 11 shipped configurations are identified by canonical-JSON fingerprints in
src/resources/admission.py. A modified configuration, unknown profile/variant,
or explicit custom_config returns `no_guarantee`, emits a warning and retains
post-hoc behavior. It is not silently approved as safe or rejected as unsupported.
Even passing an unchanged shipped configuration explicitly as custom_config has
this status. Profile edits require reviewing size behavior and updating the
fingerprints, not just retaining the same profile name.

Known plans that violate MAX_BODY, a chunk-count bound or MAX_COLLECTION fail with
ADMISSION_FORMAT. A lower bound on the combined insertion-list JSON length also
rejects certain MAX_HEADER violations. For example, sequential paranoid at
131,072 bytes predicts 104,857 positions and fails before the reader/engine run.
Matrix rounding matters: with the sequential shipped configuration, 124,928
bytes predicts 99,942 positions; 124,929 predicts 100,147 and is rejected.
These are not universal limits across all possible threading topologies.

schema.py owns the forward size relations used by both admission and validation.
The RSA SHA-256 OAEP boundary and final-obfuscation producer count are shared
with the engine. There is one compatibility subtlety: the existing reader checks
final-obfuscation length against recorded operations, not a mandatory sequence
implied by the level label. Validation therefore calls the common output-size
relation with the recorded insertion count. It does not introduce a new reader
restriction while adding producer preflight.

## Exact sizes versus soft memory estimates

`AdmissionEstimate.guaranteed` means the recognized configuration has an exact
ciphertext/collection size model. It does **not** guarantee that all metadata,
available memory, execution, or publication will succeed. Random operation
choices, integer encodings and RSA PEM lengths prevent exact JSON-size forecasts.
The estimator records a conservative header upper estimate for reservation
arithmetic, while format rejection uses only proven bounds. Normal frame/schema
validation still runs after encryption and MAC-before-JSON recovery is unchanged.

The provisional allocation model includes retained input/output, per-stage or
parallel working buffers, extra LSB bit-string allocations, insertion-position
objects, metadata/JSON copies and 8 MiB fixed slack. It is topology/profile aware;
it is not a measured peak-RSS theorem. Folder entries add 4 KiB per entry. The
stat-only folder plan itself is created before reservation and is capped at
100,000 entries; filesystem traversal and other process overhead are not hard
bounded by the reservation ledger.

Defaults are a **provisional, unvalidated 256 MiB reservation budget and 256 MiB
available-memory reserve**, with at most 30 seconds waiting for occupied claims.
These came from the reference-host proposal, not a calibration study. A claim
that cannot fit alone fails immediately with ADMISSION_RESOURCE. Insufficient
available memory with no active claim also fails immediately. Contending tasks
wait on a condition variable outside cipher pools, then recheck both bounds.
Available memory is conservatively reduced by outstanding claims, even though
some claims may already have actual allocations reflected in the OS sample.

All default FileEncryptor/BatchProcessor instances share one ledger in the current
process. Explicitly supplied ledgers define separate accounting domains; callers
must share one when they want a joint budget. Custom configurations bypass the
new claims with the explicit no-guarantee status. Another process, a low-level
engine caller, custom configuration or allocator transient can exceed real
memory. This is **not an OS-enforced limit or OOM protection guarantee**.

```python
from src.encryptor.main import FileEncryptor
from src.resources.reservations import ResourcePolicy, ReservationLedger
from cli.batch_processor import BatchProcessor

policy = ResourcePolicy(budget_bytes=256 * 1024**2,
                        available_reserve_bytes=256 * 1024**2,
                        wait_seconds=30)
ledger = ReservationLedger(policy)
encryptor = FileEncryptor(resource_ledger=ledger)
batch = BatchProcessor(resource_ledger=ledger)
```

Supplying resource_policy instead creates a private ledger; do not supply both
keywords. CLI/GUI callers inherit defaults through FileEncryptor; this phase
does not add UI controls or CLI flags. Successful result dictionaries include
an `admission` status and estimate; policy/format refusals remain ordinary failure
results under existing exit behavior.

## Read bounds and lifetimes

Known-profile file reads are capped at the stat size plus one detection byte.
Growth or shrinkage fails. Folder members are read in bounded chunks, constrained
by each planned size; the ZIP buffer cannot grow beyond the admitted archive
size. A final stat-only scan checks for added/deleted/resized entries. These checks
do not promise a filesystem snapshot: same-size concurrent edits can remain
undetectable, and hostile filesystem replacement races are not eliminated.

A reservation covers the read, encryption and verified publication. It releases
in finally on arbitrary exceptions as well as success. Failed encryption drains
already-running inner futures before propagating failure and releasing its claim.
No forced thread termination or cancellation protocol is introduced. Existing
owned-staging retention and no-overwrite behavior remain in effect.

Direct HybridEncryptionEngine.encrypt_data calls get deterministic format
preflight for recognizable configs, but do not acquire whole-file reservations:
the caller already owns its plaintext allocation. GPUFileEncryptor's separate
adapter and CPUDecryptor do not gain memory admission in this phase. Recovery
authentication and all existing limits continue to apply.

## Regression evidence required for this range

- Actual sequential, parallel-chunk and threaded-layer output sizes/counts match
  predictions; all 11 shipped profiles retain small-fixture round trips.
- A real nearby valid paranoid input recovers, and the invalid case fails before
  an instrumented reader or engine can run.
- Custom/modified configurations explicitly have no guarantee.
- File/folder growth remains bounded, including ZIP overhead and ZIP64 footer.
- Single-task budget/system-memory refusals do not wait indefinitely. Concurrent
  reservations stay within budget and release after atypical reader exceptions.
- A blocked real cipher task retains its claim while another worker fails; the
  claim is released only after that remaining work ends.
- Full supported Linux/Windows CI, offscreen Qt and recovery EXE checks retain
  their established acceptance limits; native desktop/GPU/power loss remain separate.
