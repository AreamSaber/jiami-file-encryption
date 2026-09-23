# Documentation for authenticated v1

Start with the [project README](../README.md) and [user guide](user_guide.md).

- [User guide](user_guide.md): supported setup, CLI, Qt recovery, batch processing, recovery secrets.
- [Developer guide](developer_guide.md): test commands, ownership and review boundaries.
- [Architecture](architecture.md): the actual producer, reader and publication paths.
- [Security design](security-redesign.md): format, trust model and failure semantics.
- [Remote development](remote-development.md): Linux workspace, CI and manual Claude handoff.
- [Windows acceptance](windows-acceptance.md): real recovery-EXE results and remaining desktop checks.
- [Resource admission](resource-admission.md): Phase 1 implementation, configurable soft reservations and precise limits.
- [Resource-control design](resource-control-design.md): approved phase split; cancellation remains a future implementation.
- [Memory measurements](memory-profile.md): bounded experiments and their limits.
- [Review history](reviews/2026-09-23-v1-manual-review.md): historical, commit-specific findings.

Other historical documents and root-level experiments are not promises of v1 functionality. In particular, no legacy pickle reader, password-based recovery protection, recipient-public-key delivery, transparent GPU acceleration, or streaming large-file pipeline is provided by this release. Profile labels do not measure security strength.
