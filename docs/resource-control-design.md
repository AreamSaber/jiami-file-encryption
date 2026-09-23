# Resource admission and cooperative cancellation — design for Claude review

Status: Claude approved the design with refinements after reviewing
`5701e428a42f537d380a2fb063f995fa678bccd7`. Phase 1 (producer admission and
reservations) was approved at `b10b75a45178a624c0d41525c42bca6f59c3a9c1` with
no blockers; see [implementation and limits](resource-admission.md). Phase 2
(cooperative cancellation) was approved with no blockers at
`e3f5a646f345d0ca3960b2be2a9e52577ea4271e`; see
[cancellation contract](resource-cancellation.md). The authenticated v1 format, cipher variants and
publication contract remain unchanged.

## Recorded architecture decisions

Implement admission first; cancellation requires its own subsequent range.
Size relations must have one source in schema.py, shared with validation, rather
than a second set of padding/expansion formulas. Exact ciphertext and collection
sizes are required for the 11 shipped profiles and actual topology. Custom or
unrecognized configurations must explicitly report no admission guarantee and
keep post-hoc behavior. Memory reservations must use profile-aware estimates;
256 MiB budget/reserve defaults remain provisional and unvalidated.

For Phase 2, PublicationGate.request_cancel() and enter_publishing() must share
one lock and transition once from pending to cancelled or publishing. Retain
private staging under the existing contract. Counts stay distinct; exit
precedence is error 1, otherwise cancellation 130, otherwise success 0. A request
that loses to publishing must not count as cancellation; report that it arrived
too late. A publication failure remains a real failure. Both race orderings need
deterministic barrier tests and a real Qt worker test for pending cancellation.

The proposal below is retained as design context, with these decisions governing
implementation. Recovery admission, cancellation, GUI wiring and exit-code
changes are outside Phase 1.

## Evidence and first objective

On the two-core, approximately 2 GiB Linux host, a traced 64 KiB paranoid file
completed encryption in 11.149 s and recovery in 12.572 s. Its final-obfuscation
layer consumed 8.5977 s of encryption. The steganography layer expanded 65,536
bytes to 524,288 bytes; final obfuscation expanded that to 576,716 bytes.

A 128 KiB input generated 104,857 insertion positions and then failed the existing
100,000-item metadata collection limit. The expensive layers had already run.
A 1 MiB sample reached final obfuscation with 8 MiB of input and was stopped at
the experiment's 40-second timeout. These are small, single-run observations,
not a universal file-size limit or an isolated-machine benchmark.

A separate instrumented 120 KiB run completed and matched SHA-256. Within its
16.6188-second final-obfuscation layer, cProfile recorded 98,304 bytearray.insert
calls consuming 6.0652 seconds of self time, and 9.4515 seconds in the Python
function itself. Instrumentation and random operation choices affect timings.
An earlier uninstrumented 120 KiB run completed publication but exceeded its
40-second total budget during recovery. Do not interpret the later pass as a
speed comparison or conceal the earlier timeout.

The first objective is early refusal of predictably invalid or over-budget work,
plus safe cancellation. Optimizing the transforms is a separate proposal. Do not
raise metadata limits, replace a cipher, change randomness, omit layers, or change
the format to make the measurements pass.

## Proposed admission contract

Introduce an operation-owned ResourcePolicy and a per-batch reservation ledger.
Keep existing FileEncryptor/CPUDecryptor call signatures compatible through
optional keyword arguments. Thread settings and the ledger have distinct roles.

1. Before reading a whole plaintext input, check its size and the selected trusted
   profile. Derive conservative output and recovery-metadata bounds for the actual
   chosen topology. Reuse strategy selection rather than assuming all paranoid
   inputs have one sequential plan. Account for padding, chunk counts, matrix
   rounding, LSB expansion, final insertion counts and encoded JSON overhead.
2. For a supported profile, reject a plan that necessarily violates an existing
   frame, JSON or collection limit before running expensive transforms. If exact
   bounds are unavailable, distinguish an estimate from a guarantee. Unknown
   custom configurations must not be silently substituted with another profile.
3. Recheck sizes at stage boundaries. File growth and directory changes between
   preflight and reads remain possible: use bounded reads and enforce the limits
   while accumulating, not only a prior stat. Folder checks include archive
   overhead, entry counts and aggregate bytes, not just the largest member.
4. Before authentication during recovery, trust only bounded file sizes and the
   framing checks already allowed by v1. Never interpret unauthenticated JSON to
   authorize a larger allocation or construct a cipher. Admission must preserve
   authentication-before-interpretation and full validation-before-publication.
5. A batch reserves an estimated peak allocation before starting each task and
   releases the reservation in finally on success, failure or cancellation.
   Waiting for memory must not occupy an inner cipher pool or spin indefinitely.
   If a task cannot fit even alone, fail clearly instead of waiting forever.
6. A candidate initial policy for this host is a configurable 256 MiB per-process
   budget plus a 256 MiB available-system-memory reserve. These values need review
   and calibration; the current observations do not prove them sufficient. Keep
   policy refusal separate from format rejection and report the relevant bound.

RSS sampling and available-memory checks are soft admission mechanisms. They do
not prevent another process consuming memory, allocator peaks, or OOM between
samples. A hard OS memory guarantee would require a separate process-isolation
design for Windows and Linux. Do not add RLIMIT/job-object/process changes as an
incidental implementation detail or advertise a hard cap in the UI.

## Proposed cancellation state machine

States: queued -> preflight -> running -> staging -> publishing -> completed.
Cancellation may lead to cancelled before publishing. Other errors lead to failed.

- Each operation receives a thread-safe cancellation token. Check it before
  reads, between layers/chunks, periodically within long Python loops and while
  waiting for resource reservations. Native cipher/RSA calls may need to finish
  before a request can take effect; the UI must say that cancellation is pending.
- Use an explicit publication gate shared by the token and publisher. Requesting
  cancellation and entering publishing must be ordered under the same lock; a
  last unsynchronized Boolean check before rename is insufficient.
- If cancellation wins the gate, do not perform the final rename. If publishing
  wins, finish the existing no-replace rename and durability reporting. Never
  return cancelled after a successful rename, remove a published output, or turn
  a durability warning into an unqualified failure.
- Keep owned private staging on cancellation once created, consistent with the
  current failure contract. Report its location and whether it can contain keys
  or verified plaintext. Do not delete arbitrary matching staging directories or
  promise secure erasure. Automatic cleanup would require a separate decision.
- Always close the task's engine pool and release its reservation. Do not use
  QThread.terminate, kill a shared process, or return the UI to idle while workers
  are still active. Window close remains deferred until genuine worker completion.
- Batch cancellation stops new admissions and requests cancellation of active
  tasks. Previously published successes remain valid. Results distinguish
  successful, failed and cancelled counts; progress counts all resolved tasks.
- Proposed CLI exit rule: 1 if any real failure occurred, otherwise 130 if any
  task was cancelled, otherwise 0. A late rejected cancellation after publication
  is reported as completed, with the existing durability state.

## Acceptance criteria

- Existing 11-profile small-fixture and standalone recovery regressions remain
  valid, including known-answer vectors, wrong keys, tampering and no-overwrite.
- A predictable oversized insertion-position list fails before heavy layers;
  nearby valid inputs still round-trip without relaxing the wire limits.
- Memory reservations stay bounded with multiple tasks; cancellation and failure
  cannot leak a reservation or leave another admissible task waiting forever.
- Real cancellation before work, during a controlled long step, during staging,
  and concurrently with the publication gate has deterministic outcomes. Verify
  both orderings of the race; use barriers rather than timing sleeps.
- Neither cancellation nor resource refusal publishes incomplete plaintext,
  overwrites existing files, deletes another attempt's staging, or changes a
  completed output into a reported cancellation.
- Test file and folder operations, serial and parallel batches, CLI exit status,
  actual Qt controls and pool lifetime. Preserve full failure output.
- Memory tests use bounded synthetic inputs; no OOM experiments on the shared
  residential host. GUI wording explicitly distinguishes requesting cancellation
  from cancellation having completed.

## Original review questions (answered; retained for context)

Respond entirely in English. Review this design before Codex implements it.
Approve or revise: (1) early bound checks and conservative handling of unknown
profiles; (2) the soft reservation model and initial configurable thresholds;
(3) the atomic cancellation/publication gate; (4) retained private staging;
(5) batch counts and exit-status precedence. Identify the smallest coherent
implementation slice, exact interfaces and missing race tests. Keep optimization
of existing transforms, a streaming format and hard process isolation separate.
