# Manual Claude review — v1 Linux CPU

This is Codex's summary of the review pasted by the user on 2026-09-23. The pasted terminal transcript contains duplicated and truncated lines; this file is not a verbatim reconstruction.

## Reviewed revision and verdict

Claude reported a clean checkout at `/home/claude-dev/projects/jiami-protocol-v1`, HEAD `00833fb2925b41ad163da842244e6f06796cc0c5`, tree `00f5de5e28eba82cd34eb46f2fb9558b55829515`, compared against `7443b929e51ea846efde5ed78b7791042983cce7`.

Verdict: approve the Linux CPU v1 implementation at that commit, with no blocking findings and two non-blocking cleanup items. Claude inspected code and independently checked algorithm arithmetic; it did not rerun application tests. The supplied test counts remain Codex's execution evidence.

This approval does not cover subsequent commits, Windows profile coverage, GUI window interaction, GPU hardware parity, physical power-loss behavior, or executable packaging. No merge is authorized by this record.

## Follow-up 1: unused dependency and historical registry paths

The normal v1 Salsa20 profile is `Salsa20_PyNaCl`, handled by real PyNaCl SecretBox. The bare `Salsa20` pycryptodome branch cannot be reached through the closed v1 schemas.

The follow-up change removes that branch and its bare/CPU aliases, removes pycryptodome from requirements and the CPU lock, and removes the generated recovery program's dependency claim and PyInstaller Crypto collection. The CLI dependency display is updated too.

Historical GPU-only branches remain for trusted in-process engine experiments, as permitted by the review's alternative of documenting this boundary. They are not v1 file algorithms, nor are they the backend selected by GPUDecryptor. The one remaining Salsa20 experiment is named `Salsa20-GPU-ONLY` explicitly.

Regression coverage resolves every schema algorithm through the registry and compares handler coverage, with one explicit historical Salsa20 exception. Comparing canonical registry names directly with wire names would be incorrect: for example, the `ChaCha20` handler is reached by the `ChaCha20-CPU` wire alias. Unsupported aliases are checked against schema rejection; adding another unaccounted handler fails the coverage assertion.

## Follow-up 2: exact pre-read bound

A data frame has 50 bytes of fixed overhead; a recovery frame has 82. `read_frame` now uses the corresponding bound, closing the previous 32-byte excess allowance for data frames. Wire encoding and accepted valid v1 files are unchanged.

The regression test uses a real frame exactly at a reduced test limit, verifies successful reading and decoding, then adds one byte and ensures fstat rejects it before any content read. It covers both frame types.

## Verification procedure

Run the full Linux CPU suite after synchronizing the reduced lock and proving `Crypto` is absent from the dedicated venv. This includes all eleven profile roundtrips and all eleven standalone programs outside the checkout. Run the selected Windows framing/publication/boundary and registry tests with pycryptodome removed there too.

Results and the follow-up commit range are recorded in [PR #3](https://github.com/AreamSaber/jiami-file-encryption/pull/3) and the manual handoff evidence. Do not expand the original approval to untested platforms or to the new revision automatically.
