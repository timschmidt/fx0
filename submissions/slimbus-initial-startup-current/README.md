# Initial startup for an already running DSP

If the DSP starts before NGD probes, no new SSR/PDR UP notification may arrive.
The original Fx0 fix schedules an initial bring-up. This port initializes a
startup request before discovery and notifier callbacks can run, and uses the
existing parent/child readiness publication to schedule it after initialization.
Any explicit DOWN can revoke the request. Late child binding or a QMI service
can replay a pending request, including after an initial wait timeout. No extra
state flag or separate startup path is introduced.

The source patch carries Timothy Schmidt's original author identity and author
timestamp and Claude Opus 5.5's coauthor credit from commit
fe063af17b097af73c8ca55609ca9ee3648ac1dc. Codex adapted the admission logic and
generated the logical qualification. The coauthor tag's case is normalized;
checkpatch still reports its one inherited nonstandard-signature warning. The
unfiltered log is retained, and filtering that known warning yields no other
diagnostics. No Signed-off-by is invented. Human review and DCO remain pending.

The model uses 23 exact NGD/core callback bodies and logical QMI, PM, wait,
workqueue, DMA and child services with selected pthread interleavings. It passes
81 cases and 1,263 checks; the pre-port source fails 35 checks. All 29 earlier
and four new regression controls are rejected by their named cases without
sanitizer diagnostics. The obsolete test requiring initial startup to remain
absent is replaced with its positive requirement; the other 70 cases remain and
ten cases are added. Services and callback extraction are unchanged. Normal
LSan and fail-fast ASan/UBSan are enabled. Nine other regression programs,
including software DMA admission and QMI allocation errors, are byte-identical.

Eight ARM/ARM64 objects build with LLVM21 W=1 and strict callback diagnostics
without compiler diagnostics. The combined runtime kernel and 459 modules build;
CMS, ELF, release and module dependencies pass. Prior module paths and 20 DTB
hashes are preserved. This incremental build does not establish clean public
source package reproducibility, installed recovery or physical acceptance.

Run `python3 -B replay.py /tmp/new-initial-startup-replay` with clang-21 and
patch installed, outside ptrace for normal LSan. Replay checks the pinned input
hashes, applies source and runtime patches without offset or fuzz, reruns the
before/after lifecycle model and 33 controls, and compares both generated
programs. It needs no Git, Internet, kernel services or device.

The pinned pre-port snapshots contain earlier local SLIMbus work. This packet
qualifies the startup delta; its dependencies remain in the preceding review
history, including `../slimbus-dma-admission-current` and
`../slimbus-qmi-transaction-current` at review parent
dad693fe162f9c8537ff70dd55ce8e92cf20ba1e. The latter archive SHA256 is
2cff3debe2d96362cc096b36a7dcce959b71ec8a758e9b52105f64f73defe326.

The extended primary-source audit traces vendor SPS disconnect to interrupt
masking and pipe disable, without a reset write or NGD idle acknowledgment.
It does not establish the modern BAM reset precondition. Registered-client
endpoint replacement also retains its old connected QMI client and still needs
recovery work. Hardware stop, suspend rollback, endpoint/failed-start recovery,
late wire TID reuse, maintained-LTS recovery and physical acceptance remain open.
The runtime work is based on 7.4-rc1, not final maintained-LTS acceptance.

All heads remain local and unpublished; the draft is unsent. No real QMI,
firmware, DMA, audio, phone, WiFi scan or network configuration executes.
