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
