# Gen1 source fix qualification checkpoint

This is the earlier source/component checkpoint. The later
[normal r7 package qualification](package-qualification.md) and
[current media-base draft](../../submissions/camss-gen1-coalesced-completion/README.md)
record the subsequent host work; physical acceptance remains open.

The final kernel candidate is `250e7412a5a15068b2a2fe32b57b66c300c91b5f` on
`development/fx0-vfe-coalesced-completion-02`. It consumes old saved WM status
when a gen1 register-update resets a STOPPING output, before that status can
consume a fresh ping/pong buffer. The 4.1, 4.7 and 4.8 handlers also consume the
corresponding PIX composite status. Other output completions and diagnostic
paths remain active. The 17x callback returns zero for the extended ISR API.

The host harness compiles extracted production types, queue operations,
state transitions and IRQ dispatch. All 28 scenarios pass for each of three
dispatchers (84 executions) under ASan/UBSan. Fifteen controls fail for the
expected reasons in the baseline and three unsafe alternatives. In particular,
a fresh pending buffer is touched by the old WM snapshot in the baseline;
blanket IRQ reordering returns a buffer before its required later idle ack.
The tests also exercise queueing after unlock, WM reassignment, missing
last-buffer pointers, multiple drains and unrelated outputs. These are fake
hardware/locking endpoints, not physical or SMP qualification.

The first harness attempt stopped at an expectation label: the baseline had
already returned a fresh buffer when the total-return assertion ran, before
the more specific fresh-buffer assertion. Its generated sources and runner
remain preserved. A later ordinary run passes 72 executions and 15 controls;
the final sanitizer run adds the boundary cases above and passes all 84.
The production fix was unchanged between those attempts.

A fresh ARM build prepares the configuration and compiles/links the complete
CAMSS relocatable object with KCFI and integer normalization enabled. All
three build stages exit zero without compiler warnings/errors. Both gen1 and
17x provider type words are `0xe8f4cf55`, and all four IRQ dispatchers contain
the matching check constant; the old void-return providers use `0xf0f6e568`.
This is static consistency, not a runtime CFI or module-load test. Linker
capability fields change from LLD18 to LLD21 during olddefconfig; the delta is
recorded, and no byte-identical full-package configuration is claimed.
No signing key is generated or used for this component target.

The component is built from `d2caf06a30e67781175fb90ad953f5440d3dfcb5`;
the host test input hashes match its production source tree.
A signed-patch style check then catches one spelling preference in that
commit's message. A separate clone corrects only the message, preserving the
compiled source/commit and the failed style artifacts. The final candidate
has the identical full Git tree `9a3bec66b22c9cf60d78634487904b0139e9087f`; its signed
patch passes checkpatch with no findings and retains the DCO trailer.
A complete package must still be built and qualified from the final pin.

No phone access, module replacement, package install, boot trial, publication
or maintainer message occurs in this phase. The accepted native r1 reference
and every pending physical/publication gate remain unchanged. A normal package
pair, ABI/signature checks and a separately gated camera/return trial are
still required; the full bringup goal remains open.

[Sanitized evidence](../../evidence/2026-11-15-camera-vfe-drain-source-fix.json)
