# Windows native console event acceptance

This is a separate acceptance range following Claude's approval of Phase 2 at
`e3f5a646f345d0ca3960b2be2a9e52577ea4271e`. The first supported Windows
Python 3.12 run exposed deferred signal handling while the main thread waited
indefinitely on a Future. The CLI wrapper now waits in bounded 100 ms intervals,
returning to Python to handle signals while work is active. The worker, gate,
cancellation policy, ciphers, protocol and dependencies are unchanged.

Run in the supported Windows Python 3.12.4+ virtual environment with the native
dependencies and PyInstaller installed:

```powershell
.venv/Scripts/python tools/verify_windows_console.py --report acceptance-results/windows-console.json
```

The existing Windows recovery workflow runs the tool after the uninstrumented
recovery-EXE round-trip checks. Only JSON metrics are uploaded. Synthetic keys,
packages, plaintext, logs and executables live in a private TemporaryDirectory
and are removed when its processes have exited. Full failure text is propagated
to the runner and JSON report. `--skip-exe` is an explicitly partial source-only
run, useful in a supplementary environment; it is not the full acceptance gate.

## What is exercised

Five entry points each run three deterministic orderings, for 15 cases:

| Entry | Cancel wins | Publish wins | Late cancel with output conflict |
|---|---|---|---|
| Primary CLI | 130 | 0, warning | 1 |
| Enhanced encrypt | 130 | 0, warning | 1 |
| Enhanced batch, one file | 130 | 0, warning | 1 |
| Generated recovery Python | 130 | 0, warning | 1 |
| Instrumented recovery EXE | 130 | 0, warning | 1 |

Every target receives its own hidden `CREATE_NEW_CONSOLE`. An external helper
detaches its own initial console, attaches to that owned target's console,
ignores Ctrl+C only for itself and sends
`GenerateConsoleCtrlEvent(CTRL_C_EVENT, 0)`. It does not send a POSIX signal,
call a Python handler directly, use Ctrl+Break, or target the runner's console.
This follows the documented broadcast semantics: Ctrl+C cannot be restricted to
a nonzero process-group ID. See Microsoft's
[GenerateConsoleCtrlEvent](https://learn.microsoft.com/en-us/windows/console/generateconsolectrlevent)
and [SetConsoleCtrlHandler](https://learn.microsoft.com/en-us/windows/console/setconsolectrlhandler).

A test-only probe wraps the real gate to pause immediately before or after its
real `enter_publishing` transition. The parent waits for an atomically published
ready marker, sends an event, and waits for a marker produced only after the
real installed Python handler returns. A second event must also be observed
before the gate is released; only one cancellation request may reach the token.
The target must still be alive and no new output published during the hold.
Polling sleeps wait for explicit markers and bounded deadlines; no race outcome
is inferred from elapsed time.

After release, cancellation must return 130, retain and report the owned private
stage and publish no final output. A late request must preserve successful
plaintext/package recovery and the Windows durability warning, returning 0.
With an existing destination, the same late request must return 1 and preserve
the destination bytes. Recovery cases additionally prove their cancellation
module was imported from the generated `runtime.zip`, outside the source tree.

## Instrumentation and limits

Python only added interruptible Windows lock acquisition in 3.14; see the
[Python threading reference](https://docs.python.org/3/library/threading.html#threading.Lock.acquire).
The supplementary 3.14 run therefore did not establish that the supported 3.12
wait was responsive. The original 3.12 failure is retained as evidence; its
assertions were not relaxed. Timed `concurrent.futures.wait` allows the original
signal handler to execute, rather than injecting a wakeup from the probe. Task
exceptions still propagate from `future.result()` after completion.

`windows_console_probe.py` is solely an acceptance tool. It observes the existing
token and signal handler and holds the existing gate; it replaces no cipher,
state transition or cancellation handler. Source tests run their real entry
scripts through this wrapper. The EXE test uses the real KeyInjector build path
with one additional test-only PyInstaller runtime hook. Production KeyInjector
does not include this hook or recognize its environment variables. The EXE
artifact here is instrumented and must never be distributed.

This demonstrates native console event delivery and the compiled bootloader /
embedded Python path with controlled test instrumentation. It is not a physical
keypress in Windows Terminal, ConPTY, SSH, VS Code or every terminal host, and
does not prove an uninstrumented shipping executable was interrupted at a chosen
instant. The ordinary uninstrumented EXE round trips remain separate evidence.
It also does not add Ctrl+Break, window-close/logoff cancellation, immediate
native-call interruption, real-display Qt interaction, GPU hardware, GUI packaging,
signing/installer, clean-machine or power-loss coverage.

On harness failure, the held worker is first released normally. Only if that
private synthetic target then exceeds its shutdown deadline may the harness
terminate that specific process tree. This test cleanup is not application
cancellation behavior. No user process or shared runner process is terminated.
