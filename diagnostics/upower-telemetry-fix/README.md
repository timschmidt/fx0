# Validate battery telemetry before reporting it

The [review patches](../../submissions/upower/README.md) correct the numeric
validity and recovery gaps reproduced in the separate
[unchanged-production baseline](../upower-telemetry-validity/README.md). The
baseline probes and their deliberately failing results remain frozen.

The parser reads the uncached attribute text and preserves success separately
from the number. NULL, empty text, trailing junk, overflow, NaN and infinity
cannot become a successful zero. Capacity must also be in the range 0–100.
Remaining energy/charge needs usable full or design metadata; a lifetime charge
counter cannot establish remaining charge. A genuine zero remains eligible.

Coldplug validates the charge information consumed by the battery backend. A
later unusable sample keeps the last good properties and update time. A change
event can register a previously ignored supply once usable data appears; the
existing removal path clears its sibling links before registration is retried.
Removal/presence updates still work when charge data is invalid.

Valid capacity takes priority. Without it, real remaining charge with known
full/design data takes priority over an approximate capacity level. Recognized
levels remain a fallback, with the legacy Unknown approximation retained for
peripherals. Unknown alone cannot invent system state of charge. MacBook system
capacity handling preserves peripheral percentages. A zero energy sample is
not replaced with an older nonzero energy average. The 1.91.0 core also gains
the current version's positive-denominator guard for percentage inference.

## Reproduce

Apply the appropriate source patch at its exact pinned base as described in the
review directory. Use the usual Linux integration dependencies and an isolated
environment with its own process filesystem, writable temporary directories and
private D-Bus services. The test suite mocks devices, logind and polkit.

```sh
meson setup output -Didevice=disabled -Dgtk-doc=false -Dman=false \
  -Dsystemdsystemunitdir=/usr/lib/systemd/system
meson compile -C output
meson test -C output --no-rebuild --num-processes 2 --print-errorlogs
python3 /path/to/fx0/diagnostics/upower-telemetry-fix/verify.py \
  --family current --log output/meson-logs/testlog.json \
  --report /absolute/path/to/new-summary.json
```

Use `--family backport` for the 1.91.0 tree. This exact configuration has 131
current-tree tests and 122 backport tests, including 28 telemetry validity cases
per tree. The verifier requires normal success for every case, rejects skips,
failures, duplicate names, missing controls and incomplete runs, and records the
input hash. Other dependency configurations may change the configured count.
The test-only libudev NULL-read shim is built and supplied by Meson, with no
manual preload setting needed outside the two fault-model tests.

The current tree's existing NaN-only test now requires an absent display battery
and no warning, replacing its former expectation of a fabricated zero. Existing
overfull tests retain their 100%/energy expectations. Its Wacom test loads the
same fixture records with main-loop intervals between them, retaining all final
assertions: the unpaced fixture's UMockdev event sender also fails against
unchanged pinned production code, while pacing passes against both versions of
the production code. This test harness change is recorded separately from the
telemetry behavior in the evidence.

The existing charge/discharge state-inference fixture in both trees now bases
its simulated 1 W energy changes on elapsed monotonic time. Under heavy host
scheduling, its former fixed energy change per loop could represent less than
the inference threshold instead of 1 W. The final charging/discharging assertions
remain unchanged. Earlier timing failures and the separate Wacom event failures
are retained rather than counted as successful full runs.

## Limits

These are x86_64 UMockdev/private D-Bus results. The read-error shim models NULL
from libudev with ENODATA; it does not inject a kernel error. No native power
action, radio or audio operation is exercised. Keeping the last good sample does
not qualify a complete stale-data policy. ARM packaging, native deployment,
physical current/SOC accuracy and final battery/charging acceptance remain open.
Installed r50 and UPower r4 are unchanged by this source correction.

See [reviewed evidence](../../evidence/2026-11-09-battery-telemetry-fix.json).

## ARM r5 candidate

The [r5 recipe](https://github.com/timschmidt/fx0-pmaports/tree/integration/fx0-upower-r5/extra-repos/systemd/upower)
at `4c5db910dd68205cc26303325186ccb39cb17521` adds the tested backport to r4.
All eight patches apply; the unchanged Nura timing patch retains its seven-line
offsets. Actual retained ARM build source matches all 159 expected files,
including that timing change. Two builds in the same QEMU target/toolchain with
a warm cache produce byte-identical sets of six original APKs. This is not
independent-environment reproducibility.

The current build key differs from the phone's existing trust store. Candidate
APKs use the already trusted build key inside a network-disabled signing
container, with original control and data gzip streams preserved byte for byte.
No private key bytes are host-read/exported and no phone trust key is added.
All six signatures pass against the captured native public keys; modified signed
recipe metadata fails verification. Offline simulation against the actual r50
package database upgrades only upower, upower-lang and upower-systemd.

The existing ARM dummy-backend/core test runs under QEMU: five bodies exercise
backend/device/list/history/native logic; polkit and daemon bodies return early
without a system bus. This does not run the Linux telemetry integration suite
on ARM. The recipe's inherited `!check` policy remains; the full 122-test Linux
backport suite was validated separately on x86_64.

The exact candidate CLI/shared library and daemon run from a temporary phone
directory with eager symbol resolution. CLI version/enumeration/dump/battery and
daemon help pass as an unprivileged user; installed files/database, boot hash and
the running r4 daemon PID stay unchanged. Probe files are removed. The CLI and
shared library match the original r4 APK byte for byte; the updated daemon's
help path establishes loading, not native execution of the new battery logic.

See [candidate manifest](../../manifests/upower-telemetry-r5.json) and
[package evidence](../../evidence/2026-11-09-upower-r5-arm-candidate.json).
Rollback/config/database/boot backup, package deployment and native daemon/
telemetry acceptance remain pending. No reboot or physical power/radio/audio
operation is performed.
