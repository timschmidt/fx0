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
