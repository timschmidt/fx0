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

The original native buffers and callbacks remain in
[the callback witness](../camera-reopen/vfe-callback-order.md). Host regression
and a CFI-enabled ARM CAMSS component build do not qualify a full kernel,
signed package, module load, camera DMA or physical recovery. A fresh complete
package build and a separately gated phone trial are still required.

[Current mainline source applicability](mainline-applicability.md) passes the
source-only sanitizer regression at a verified mainline pin.
[Fresh r7 package preparation](../../evidence/2026-11-15-camera-vfe-r7-package-preparation.json)
pins the final source with an unchanged input configuration and two separate
normal signed builds. Builds and the twelve independent audit stages must
finish successfully before package qualification can be claimed. The
unchanged-r2 repeat/return and distinct candidate operator gates remain open.
