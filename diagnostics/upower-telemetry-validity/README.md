# Unusable battery telemetry probes

These probes extend the existing incomplete-battery guard in two pinned source
trees: UPower 1.91.5 with the review draft at
`d8e650c3180db30b4c7df59caadefae9c2ff2866`, and the installed 1.91.0 backport
source at `1ddb4275a13932db1a64d8549182947066c57fb0`. They modify only the
integration test, leaving production C unchanged. This is a reproduction,
with no production fix, package update or phone fault injection.

The native r50 inventory has a charger-labelled battery without remaining
charge/capacity measurements. The installed guard correctly ignores that
interface. A future gauge must also handle present but unusable attributes,
temporary read failure and later availability. Relative counters and design
capacity do not establish remaining charge.

## Matched contract probes

Twelve additional cases exercise empty, malformed, NaN, infinite and negative
capacity; malformed energy, average energy and charge; an unavailable coldplug
read; malformed/unavailable reads after a valid 50% sample; and an ignored
supply gaining valid capacity on a change event. Finite full/design energy
metadata is supplied where a case does not already define a full value, so
the comparison isolates the remaining-value failure.

The test-only preload library interposes `udev_device_get_sysattr_value()` for
the named mock battery and attribute. It returns NULL with errno ENODATA and
records each injection. This reaches both GUdev presence checks and numeric
getters; interposing only GUdev's string getter misses its numeric path.
It models the library-visible failure, without injecting a real kernel errno.

Five controls must pass: an unavailable coldplug read, the existing charger-only,
design-only and measurement-only guards, and the existing real-zero-charge test.
The latter must retain the normal critical warning. The other eleven contract
probes deliberately fail against the unchanged guard. On 1.91.5, nine cases
expose a false 0% critical/action warning. On the 1.91.0 backport, eight do;
NaN capacity instead causes a fatal GObject percentage diagnostic and abort.
Both report infinity as 100% and leave an ignored supply invisible after data
becomes valid.

Daemon and logind tests run under UMockdev and private D-Bus services. No native
power action, charging setting, audio operation or radio is exercised.

## Reproduce

Use a new pristine isolated clone of either pinned tree, with normal UPower
Linux integration-test dependencies. `prepare.py` refuses a dirty checkout or
another base and records the production C fingerprints before adding probes.

```sh
python3 diagnostics/upower-telemetry-validity/prepare.py \
  --source /absolute/path/to/isolated-upower \
  --report /absolute/path/to/new-preparation-report.json
```

For the 1.91.0 backport, add
`--base 1ddb4275a13932db1a64d8549182947066c57fb0`.

```sh
meson setup output -Didevice=disabled -Dgtk-doc=false -Dman=false \
  -Dsystemdsystemunitdir=/usr/lib/systemd/system
meson compile -C output
cc -std=gnu11 -O2 -Wall -Wextra -Werror -shared -fPIC \
  /path/to/fx0/diagnostics/upower-telemetry-validity/gudev-read-error.c \
  -o /absolute/path/to/gudev-read-error.so -ldl -pthread
```

Set `FX0_GUDEV_READ_ERROR_LIBRARY` to that absolute library path. Meson's test
environment supplies the built daemon/library/typelib paths; run the twelve
`Tests.test_validity_*` cases plus the four existing controls named in
`summarize.py`. Run in a container or other isolated environment with its own
process filesystem, writable temporary directories and no host D-Bus access.
The suite starts its own bus and mocks logind/polkit.

`summarize.py` verifies recorded baseline results and their log hashes; it
rejects skips, harness errors and unexpected outcomes. The exact backport NaN
abort is identified separately from assertion failures. It does not declare the
eleven failing contracts fixed. Once corrected, the actual integration tests
must pass with normal zero exit status, including valid-data recovery and the
real-empty-battery control.

## Retained earlier observations

The first attempt lacked a chroot process filesystem and fixture voltage,
causing setup failures. It was stopped and excluded. The next shim missed
numeric reads, so its refresh read-error case is excluded. Both are retained.
Initial backport fixtures without full-capacity metadata also produce a
non-finite percentage and a fatal diagnostic abort; those logs remain separate
from the matched comparison. No failing probe is promoted to a physical result.

See [reviewed evidence](../../evidence/2026-11-09-battery-telemetry-validity.json).
