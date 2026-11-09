# UPower review drafts

Apply these two patches in order to UPower master pinned on October 30, 2026 at
[`91ec33a7214362e65d1dc5bbae347f3c61153200`](https://gitlab.freedesktop.org/upower/upower/-/commit/91ec33a7214362e65d1dc5bbae347f3c61153200)
(version 1.91.5). The first adds CLI error-path coverage; the second ports the
existing Nura incomplete-battery guard with additional regression fixtures.
No upstream issue, merge request or message has been sent for these drafts.

## CLI error handling

The documented [`up_client_get_devices2()`](https://upower.freedesktop.org/docs/UpClient.html#up-client-get-devices2)
contract allows NULL on error. Upstream already fixes the affected callers in
Kate Hsuan's [`78466b1690be12f11666abbd500cc49d85c15fa9`](https://gitlab.freedesktop.org/upower/upower/-/commit/78466b1690be12f11666abbd500cc49d85c15fa9).
The first draft is a regression test for that accepted fix, with no new CLI C
change on current master.

A mock UPower service returns a real D-Bus error from `EnumerateDevices`. All
five modes (`--enumerate`, `--monitor`, `--monitor-detail`, `--dump`, `--battery`)
must exit with status 1. The expected library warning is allowed, while critical
diagnostics remain fatal. This tests the caller's NULL handling rather than
aborting on the warning first. Unpatched 1.91.0 crashes with SIGSEGV in the first
three modes; dump and battery already handle the error. The upstream backport
passes all five.

## Incomplete battery interfaces

Three fixtures expose Battery/present/Discharging with charger-only information,
design capacity/voltage only, or design plus live voltage/current/temperature and
a lifetime charge counter. None supplies remaining charge. Unmodified current
master registers each as a system battery and enters a false critical-action
warning. The guard rejects them before either battery backend is constructed.
Design capacity and a relative counter are not substituted for remaining charge.

The fourth battery fixture contains a genuine zero `charge_now` with a known
`charge_full`. It remains a present battery with zero percentage and the normal
low-battery warning. Existing critical-action tests continue to run. This guard
uses attribute presence; malformed values, ENODATA and every possible partially
populated battery interface are not solved by it. It does not implement a gauge.

## Validation and Nura backport

All 103 configured tests pass on the patched current-master build. The 1.91.0
backport passes all 94 configured tests. Both include the injected enumeration
failure and genuine empty-battery control. Tests use UMockdev and isolated D-Bus
services on x86_64; no physical power action or ARM hardware error injection is
claimed. The current-master build has iDevice disabled. Black 24.10.0 passes;
final formatting preserves the tested Python AST.

With the usual UPower Linux build/test dependencies, apply the drafts with
`git am`, then run:

```sh
meson setup output -Didevice=disabled -Dgtk-doc=false -Dman=false \
  -Dsystemdsystemunitdir=/usr/lib/systemd/system
meson compile -C output
meson test -C output --print-errorlogs
```

Dependencies include a C compiler, Meson/Ninja, GLib/GIO, GObject Introspection,
libgudev, libudev, polkit, D-Bus, python-dbusmock, PyGObject and UMockdev. The unit
directory is explicit so configuration does not require a systemd pkg-config
file merely to locate it. This does not disable mocked logind policy tests.

The [Nura r4 recipe](https://github.com/timschmidt/fx0-pmaports/tree/integration/fx0-upower-r4/extra-repos/systemd/upower)
keeps the channel's 1.91.0 base, carries the accepted CLI fix and its three
lifetime-cleanup prerequisites with original authorship, and expands the existing
guard tests. All six new patches apply without fuzz or offsets. The unchanged
Nura history-timing patch retains its seven-line offset. Applied CLI, guard and
test files match the validated backport source byte for byte.

The signed ARM candidate uses a checked recipe identity passed to abuild before
building/signing. This corrects the extra-repo `-dirty` metadata problem; the
earlier candidate is retained separately. No kernel or bootloader change is part
of this UPower update. See the [manifest](../../manifests/upower-telemetry-r4.json)
and [evidence](../../evidence/2026-10-30-upower-telemetry-r4.json) for exact revisions,
package hashes and native smoke-test scope. Review metadata and any required
author certification still need review before submission; no trailers have been
invented.

## November 9: validity gaps reproduced, correction pending

The [unusable-telemetry probes](../../diagnostics/upower-telemetry-validity/README.md)
extend the two pinned review/backport sources without modifying production C.
Each has eleven failing contracts and five passing controls. Unusable numeric
data and failed refreshes can become false critical warnings; infinity becomes
100%, and ignored supplies do not recover on change. The backport also aborts
on NaN under fatal diagnostics. A NULL read at coldplug is already rejected,
and the genuine zero-charge control passes. This distinguishes availability
from numeric validity and recovery. These diagnostic fixtures and libudev
read-failure model are not yet an additional production patch or submission.
Native r50 and UPower r4 remain unchanged; [evidence](../../evidence/2026-11-09-battery-telemetry-validity.json)
records the precise x86_64/mock scope and earlier excluded setup attempts.

## November 9: numeric validity and recovery correction

Apply [0003](0003-linux-validate-battery-telemetry-and-retry-ignored-supplies.patch)
after the two current-tree drafts above, at base
`d8e650c3180db30b4c7df59caadefae9c2ff2866`. It corrects the
[reproduced validity gaps](../../diagnostics/upower-telemetry-validity/README.md)
and adds 28 validity/lifecycle cases. The separate
[1.91.0 backport patch](backport-1.91.0-validate-battery-telemetry.patch) applies to
`1ddb4275a13932db1a64d8549182947066c57fb0`, the source base used for installed r4.
Do not apply the two version-specific corrections together.

Final complete Linux suites pass 131 tests on the current tree and 122 on the
backport. Parsing failure stays distinct from zero, failed refreshes hold prior
properties/update time, and ignored supplies can recover on change without
losing sibling lifetime. Real remaining charge outranks approximate levels;
peripheral Unknown and MacBook handling remain covered. The backport also gains
the current core's positive-denominator inference guard. Genuine-empty,
overfull and existing critical-action controls pass. The current NaN-only test
now requires no battery or warning instead of fabricated zero charge.

The current Wacom fixture paces identical records after its burst event-send
failure is reproduced against unchanged pinned production C. Both trees'
simulated 1 W state fixture tracks elapsed time so host scheduling cannot lower
the intended power. All original final assertions remain. Earlier fixture and
partial-selection runs are retained and excluded from complete-pass claims.

See [build/reproduction instructions](../../diagnostics/upower-telemetry-fix/README.md)
and [evidence](../../evidence/2026-11-09-battery-telemetry-fix.json) for exact source
trees, patch/test hashes and replay. These are x86_64 mock results, with no ARM
package or native deployment yet. Installed r50/UPower r4 remain unchanged.
These additional review drafts have no fabricated author certification; no
upstream issue, merge request or message has been sent.

## ARM r5 packaging checkpoint

The [r5 recipe](https://github.com/timschmidt/fx0-pmaports/tree/integration/fx0-upower-r5/extra-repos/systemd/upower)
is published at `4c5db910dd68205cc26303325186ccb39cb17521`. All 159 retained
ARM source files match the validated recipe, including its inherited Nura timing
patch. Two same-target/toolchain builds produce identical original APKs. The six
candidates are signed inside the container using the key already trusted by the
phone, preserving the built control/data bytes and adding no trust-store key.
Native-key verification, a signed-metadata tamper rejection and an offline plan
against the actual r50 database pass; only the three installed UPower packages
would upgrade.

Five ARM core bodies pass under QEMU; two system-bus-dependent bodies are not
exercised. The full Linux integration suite remains x86_64 coverage. Temporary
native CLI/read-only and updated-daemon help checks pass with eager loading,
while installed r4 and its daemon PID remain unchanged. CLI/shared-library bytes
match the original r4 APK; the new daemon's service/telemetry behavior is not
native-qualified by a help check. Probe files are removed. See
[manifest](../../manifests/upower-telemetry-r5.json),
[procedure and limits](../../diagnostics/upower-telemetry-fix/README.md#arm-r5-candidate)
and [evidence](../../evidence/2026-11-09-upower-r5-arm-candidate.json).
The candidate is not installed; rollback/deployment and native daemon acceptance
remain open. No upstream message or author certification is added.
