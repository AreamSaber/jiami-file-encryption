# Bounded memory measurements

## Method and source

Measured on 2026-09-23 UTC, Debian Linux x86-64, Python 3.12.14, NumPy 1.26.4, two CPU cores, 1,985 MiB RAM and no swap. The host had about 525 MiB available at the start; other services were running. These are single observations, not isolated or statistically stable benchmarks.

Measured staged tree: `b5412e8c8fbbb612d65cc25b1e13f80e06dd35cc`, based on `0fdad67664adbd0acbbe7056c5eacac341c73180`. Later changes in this optimization branch add documentation, delete an unused benchmark stub and strengthen a GUI warning assertion; the measured producer/reader/profiler code is unchanged.

`tools/profile_memory.py` creates private synthetic random files and runs each case in a fresh subprocess. It measures FileEncryptor encryption (including publication verification), then CPUDecryptor file recovery and an independent SHA-256 comparison. Each engine is restricted to two inner threads, with cases run sequentially. This is file profiling; folder-archive peaks and concurrent batch peaks were not measured.

```bash
.venv/bin/python tools/profile_memory.py --profiles basic parallel_fast --sizes-mib 8 32
.venv/bin/python tools/profile_memory.py --profiles paranoid --sizes-mib 1 4
```

Default limits are 60 seconds per case and a 768 MiB sampled-RSS termination threshold. The parent samples every 20 ms; this is not a hard OS memory limit and cannot guarantee prevention of a transient spike or OOM. The child reports Linux `ru_maxrss` after successful completion. For interrupted cases, only the sampled peak up to termination is available. Synthetic inputs, outputs, recovery secrets and logs are deleted with the private temporary directory. The JSON report contains only metrics and a bounded diagnostic tail on failure.

## Observations

| Profile | Input MiB | Result | Peak RSS MiB | Encryption seconds | Recovery seconds |
|---|---:|---|---:|---:|---:|
| basic | 8 | SHA-256 matched | 91.9 | 0.336 | 0.189 |
| basic | 32 | SHA-256 matched | 209.9 | 1.577 | 0.742 |
| parallel_fast | 8 | SHA-256 matched | 101.6 | 0.333 | 0.167 |
| parallel_fast | 32 | SHA-256 matched | 243.9 | 1.403 | 0.809 |
| paranoid | 1 | Stopped at 60-second timeout | at least 148.2 sampled | incomplete | not reached |
| paranoid | 4 | Stopped at 60-second timeout | at least 446.6 sampled | incomplete | not reached |

For the four completed rows, sampled peaks and Linux maximum RSS agreed to one decimal place. `paranoid` processes were deliberately killed by the profiling parent (exit -9), not reported as successful round trips. The full CPU suite checks all 11 profiles with small fixtures, but that does not establish practical large-file throughput.

## Operational consequence

The pipeline still buffers whole inputs and transformed outputs. The 1 GiB frame/archive cap is a format bound, not a safe input size or a RAM promise. Even 32 MiB inputs consumed over 200 MiB in these completed cases; the heavy profile's 4 MiB case had already reached about 447 MiB when stopped.

For this host, begin with one batch worker and small representative samples. Check currently available memory; these observations are not a universal size recommendation. Thread budgeting prevents unbounded worker multiplication but does not limit total batch RAM. Do not extrapolate these rows linearly to 1 GiB. No runtime input-size policy, hard memory admission control, streaming format, or new cipher variant was introduced here.

Further work should separately investigate the heavy transforms and their metadata expansion, then propose a reviewed policy or streaming format if larger workloads are required. GPU hardware, packaged Windows EXEs and folder-memory scaling remain separate validations.

## Follow-up: tracing paranoid layers

The subsequent resource-diagnostics branch adds `--sizes-kib`, `--trace-layers`
and optional `--profile-calls` to the same bounded tool. Instrumentation wraps
the real layer dispatcher only in the disposable profiling child. It records
sizes, timings, RSS snapshots and aggregate function statistics; it never exports
keys, insertion positions, ciphertext or recovery metadata.

```bash
.venv/bin/python tools/profile_memory.py --profiles paranoid --sizes-kib 64 120 128 1024 --trace-layers --timeout 40 --rss-limit-mib 256
.venv/bin/python tools/profile_memory.py --profiles paranoid --sizes-kib 120 --trace-layers --profile-calls --timeout 60 --rss-limit-mib 256
```

Measured source tree: `3ed74838201a186feefad47fc622fbbe08461d91`, with the same
producer/reader algorithms as approved commit `e417f53960423fc88667c0adfc37ef96204dae65`.
The host still had 1,985 MiB RAM, no swap and two CPU cores; about 527 MiB was
available at the start. Results are single observations with random operation
choices and other services running.

| Input | Observation | Peak sampled RSS |
|---|---|---:|
| 64 KiB | SHA-256 matched; encryption 11.149 s, recovery 12.572 s | 63.8 MiB |
| 120 KiB | Publication completed; total 40 s limit reached during recovery | 98.1 MiB |
| 128 KiB | Failed before publication: metadata collection limit exceeded | 96.4 MiB |
| 1 MiB | Reached final obfuscation; total 40 s limit reached | 147.4 MiB |
| 120 KiB with cProfile | SHA-256 matched; encryption 21.903 s, recovery 17.946 s | 98.9 MiB |

The 64 KiB case spent 8.5977 s in final obfuscation, versus 0.4164 s in
steganography. The latter expanded 65,536 bytes into 524,288 bytes. The final
layer produced 576,716 bytes and 52,428 insertion positions.

At 128 KiB, LSB expanded 131,072 bytes into 1,048,576 bytes; final obfuscation
recorded 104,857 insertion positions. That list exceeds the existing
`MAX_COLLECTION = 100000` limit, so recovery-metadata serialization failed after
the expensive work. This is an observed constraint of the measured topology,
not a newly imposed universal file-size cap. Chunk topology and other profiles
require their own bounds.

In the cProfile case, the 16.6188-second final layer spent 9.4515 seconds in its
Python function and 6.0652 seconds in 98,304 `bytearray.insert` calls. Repeated
middle insertions and Python byte/bit loops are concrete optimization targets.
The LSB intermediate buffers and expanded operation-position lists also explain
why source bytes alone are a poor working-memory estimate. These measurements
do not attribute every RSS peak to one allocation: RSS is process-wide,
allocators retain memory, and tracing/profiling adds overhead.

No operation choice or random seed was fixed to make a case pass. The later
120 KiB success does not erase the earlier timeout and is not a controlled speed
comparison. Frame, JSON and collection limits were not relaxed. The proposal in
[resource-control-design.md](resource-control-design.md) addresses early refusal
and cancellation first; transform optimization requires a separate review.
