# Gen1 coalesced completion regression

The native callback trace observes register-update returning the final buffer
before the saved WM completion is dispatched in the same IRQ. The empty
output reports `Missing ready buf`; with pending buffers, the same ordering can
consume a newly installed buffer instead. The candidate returns a mask of old
WM indices while holding the output lock, then consumes only those saved
completions in the 4.1, 4.7 and 4.8 dispatchers. PIX composite completion is
also consumed when that PIX output was reset. The 17x register-update callback
returns zero, preserving its existing acknowledgement behavior.

`check_gen1.py` extracts production C functions, the real output/ISR types,
IRQ constants and the selected IRQ dispatcher from supplied kernel trees.
It compiles them with the local `shim.h` and `cases.c`. State transitions,
queue-list operations and IRQ dispatch come from the kernel; MMIO, locks,
clock and completion endpoints are host fakes. This checks source bookkeeping
and explicit interleavings, not actual DMA, SMP memory ordering or hardware.

Run with a candidate and a pristine pre-fix baseline:

```sh
python3 -B diagnostics/camera-vfe-regression/check_gen1.py \
  --kernel-tree /path/to/candidate-linux \
  --baseline-tree /path/to/pre-fix-linux \
  --output-dir /new/private/output-directory \
  --cc clang-21 --sanitize
```

The output directory must be new. Generated source, source hashes, compiler
commands, logs and results remain there for replay. Sanitizer execution needs
an environment where LeakSanitizer is permitted to run; do not disable it to
hide a ptrace failure.

The 28 scenarios run against all three gen1 dispatchers (84 executions).
They cover both ping/pong phases; zero, one and two pending buffers; PIX
composite and individual-WM status; delayed final-buffer return; queueing after
register-update unlock; WM reassignment; multiple drains; unrelated active
outputs; missing deferred-buffer pointers; and the unchanged wait/17x paths.
Fresh frames must still complete on later IRQs. Unexplained active, IDLE,
unmapped and later-IRQ missing-buffer diagnostics remain visible.

Fifteen negative controls require specific runtime failures after successful
compilation. They reproduce empty-output and fresh-buffer failures in the
baseline, reject an IDLE-only guard, catch premature return under blanket IRQ
reordering, and catch valid completion loss under blanket WM suppression.
Thus a quiet log alone cannot satisfy the regression.

For the separate `STOPPING` completion fix at `2150f900adaf`, add
`--stopping-baseline-tree /path/to/pre-stopping-fix-linux` with the source at
`c595fe52cc30`. Keep the original coalesced-IRQ baseline at `f71b29239d14`.
The extra cases check the final buffer at lock release, then exercise both
ping/pong phases on RDI and PIX when a separate completion arrives before the
register update. They check that the stray completion leaves the final buffer,
pending queue and sequence available for the matching acknowledgement and the
first fresh frame. All 99 dispatcher executions and 30 negative controls
passed with Clang 21.1.8, ASan, UBSan and LeakSanitizer. The complete ARM CAMSS
component also compiled with `W=1`. Hardware capture with this change is
pending.

The original native buffers and callbacks remain in
[the callback witness](../camera-reopen/vfe-callback-order.md). Host regression
and a CFI-enabled ARM CAMSS component build do not qualify a full kernel,
signed package, module load, camera DMA or physical recovery. The separate
[normal package qualification](package-qualification.md) covers the r7 host
artifact. A separately gated phone trial is still required.

[Current mainline source applicability](mainline-applicability.md) passes the
source-only sanitizer regression at a verified mainline pin.
[Fresh r7 package preparation](../../evidence/2026-11-15-camera-vfe-r7-package-preparation.json)
records the inputs before launch. The later
[package qualification](package-qualification.md) records both completed
normal signed builds, eleven ordinary stages and the corrected CAMSS stage,
including its initial failure and the retained fakeroot notice. The
[unsigned media-fixes draft](../../submissions/camss-gen1-coalesced-completion/README.md)
has source-model and ARM/ARM64 component checks, with human DCO and physical
acceptance still open. The unchanged-r2 repeat/return and distinct candidate
operator gates remain required.
