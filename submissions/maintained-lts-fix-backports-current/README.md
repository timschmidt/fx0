# Maintained 6.18.63: three focused backports

This private review draft adds the SMD node-reference release, failed-channel
registration retryability and MPM probe-unwind fixes to the maintained Fx0
integration. The kernel.org release feed and official stable tag confirm
6.18.63 as the current non-EOL 6.18 release at the recorded check time.
Final acceptance still requires a fresh currency and live-device check.

The base is `250e7412a5a15068b2a2fe32b57b66c300c91b5f`; the current local
head is `2677746cc1d6b6ab4aa60dbb5c8ad926fb327568` on
`integration/fx0-lts-current-01`. The commits preserve the original author,
date, licenses, AI attribution and full source-commit references. Message
formatting revisions preserve every source tree. Earlier local revisions
remain available in archive refs. Nothing has been published or submitted.

The actual maintained source reproduces 49 failed assertions before the
fixes and zero after, across 34 release, 396 state-worker and 43 probe cases.
These models use synthetic reference acquisition, channel/device services
and registration failures. They do not prove kernel concurrency, hardware
behavior or an exploit. Retryability allows a later state-worker pass;
no automatic retry timer is added.

The combined series compiles as six native objects across ARM, ARM64 and
ARM64 RT, with nonpermissive CFI verified in each actual config. ARM32 RT is
unsupported by this maintained kernel's Kconfig and is not counted as an
RT native build. The first seed attempt produced six warnings because three
newer tristates are bools in 6.18. That evidence is preserved. Corrected fresh
profiles request the actual bool types and produce no diagnostics. Strict
checkpatch reports zero errors, warnings and checks; original provenance
objects are made visible read-only for its commit-reference validation.

Focused replay uses Python 3, clang-21, ASAN/UBSAN runtimes and normal leak
detection. Use a new output directory for each invocation:

```sh
python3 -B harness/check.py edge source-before /path/to/new-edge-before --expect-failure
python3 -B harness/check.py edge source-after /path/to/new-edge-after
python3 -B harness/check.py state source-before /path/to/new-state-before --expect-failure
python3 -B harness/check.py state source-after /path/to/new-state-after
python3 -B harness/check.py mpm source-before /path/to/new-mpm-before --expect-failure
python3 -B harness/check.py mpm source-after /path/to/new-mpm-after
```

The native objects were built before the source commits; exact source hashes
bind them to the final tree. A complete link with the final release identity,
normal package build, installation, updates, recovery and physical acceptance
remain pending. This is the start of the maintained integration, not the
completed current-source port. The ledger retains all 147 experimental
commits: three exact changes are backported and 144 applicability/equivalence
audits remain. An unaudited entry is not a claim that the older fork lacks
all of its behavior.

All seven original requirements remain in scope. The independent SLIMbus
hardware-stop, PM rollback and QMI endpoint/transaction recovery gaps remain
open. No phone, firmware, radio or audio execution occurred. Kernel source
notices and the included GPL/MIT licenses are preserved. Codex prepared the
backports and verification; human review and DCO remain pending. The MPM stale
provider issue also awaits human security classification before a reporting
or publication decision.
