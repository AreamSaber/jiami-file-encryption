# Windows recovery executable acceptance

The [Windows recovery EXE acceptance run](https://github.com/AreamSaber/jiami-file-encryption/actions/runs/35814821914) passed at implementation commit `5a19f477572681a95071319a6f2d2e3b598ade6b`. It ran on Windows Server 2022 with Python 3.12.10 and PyInstaller 6.22.3. Native Twofish was compiled from source and checked against its known-answer vector before building.

`tools/verify_windows_recovery.py` builds real private recovery executables through KeyInjector, then runs them outside the checkout with PYTHONPATH/PYTHONHOME removed. It uses private synthetic inputs, checks recovered bytes/hashes, and deletes temporary recovery secrets and executables. The CI artifact contains JSON results only.

| Case | Round trip | Existing output preserved | Tampering/legacy rejected | Durability warning |
|---|---|---|---|---|
| multi_algorithm file | passed | passed | passed | present |
| paranoid file | passed | passed | passed | present |
| standard folder, including an empty directory | passed | passed | passed | present |

The multi_algorithm recovery EXE also rejected paranoid ciphertext carrying a different embedded-key association without producing output. These three cases exercise the current native Twofish/PyNaCl/cryptography recovery dependencies and custom transformations in real compiled launchers. This is not an assertion that every profile/size/Windows version was tested as an EXE.

To reproduce in a supported Windows virtual environment with the C build toolchain:

```powershell
.venv/Scripts/python -m pip install --no-binary=twofish -r requirements.txt 'pyinstaller>=6,<7'
.venv/Scripts/python tools/verify_windows_recovery.py --report acceptance-results/windows-recovery.json
```

Keep generated recovery programs private: they contain keys. Do not use a real user's encrypted data for build logs or CI artifacts. The historical manual_packager tool is not this acceptance path.

## Native desktop status

The local main Qt window was launched and its Windows accessibility tree inspected in the existing Python 3.14.7 environment. That environment remains supplementary and outside the supported installation matrix. The computer-use helper could not capture the window (`SetIsBorderRequired`, 0x80004002), and coordinate input was unavailable after activation. Reading the control tree is not proof that the native file dialogs, real clicks, font rendering, DPI scaling or accessibility interaction work correctly. Desktop acceptance remains incomplete.

Remaining separate work includes native desktop interaction, a distributable main GUI application EXE, signing/installer behavior, a clean machine without Python installed, GPU hardware and physical power-loss testing. The passing recovery-EXE checks do not imply any of those have been verified.

Packaging configuration references: [PyInstaller spec files](https://pyinstaller.org/en/stable/spec-files.html), [runtime resource paths](https://pyinstaller.org/en/stable/runtime-information.html).
