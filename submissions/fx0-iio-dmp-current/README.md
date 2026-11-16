# Current IADC, IIO precision and MPU6515 DMP review

Eight unsigned local commits restore the IADC signed microamp conversion,
MPU calibration register stride and runtime-PM prerequisites, exact tiny
binary scales, guarded quaternion streaming, and one-shot significant
motion with suspend retention. The final commit documents the proposed
ABI and leaves timestamp placement to the current core. No firmware
bytes are included. These drafts require human review and DCO attestation
before submission; nothing has been sent to maintainers.

The verified IIO `togreg` base is
`1390ca4953a7400ca932cb49635f02c727f885a6` (7.4-rc1). Exact source,
integration and original attributed commits are in `qualification.json`
and `evidence/source-commits.json`. The first seven commits preserve
Timothy Schmidt's original authorship and dates. The last commit and
current qualification used OpenAI Codex assistance. The MPU prerequisite
messages contain no per-unit calibration data.

| Actual-source qualification | Cases or tests | Candidate result |
| --- | ---: | --- |
| IADC, both channels and synthetic calibration/resistors | 18,618 cases | 74,462 checks pass |
| MPU offset access and calibration PM/error ownership | 106 cases | 21,485 checks pass |
| Driver scan descriptors plus real IIO layout/push helpers | 14 cases | 99 checks pass |
| Real UML `iio-format` KUnit | 8 tests | 8 pass |

The original IADC code fails 25,296 checks. Three independent controls
catch unsigned differences, lost microamp conversion and missing range
checks. Offset and PM baselines fail 54 and 66 checks; independent
controls catch a wrong gyro stride and a leaked PM reference. Calibration
values are synthetic. These tests do not establish physical current
direction, resistor accuracy, factory calibration validity or charging
accuracy.

Six DMP sanitizer variants execute the actual transport, configuration,
decoder, FIFO lifecycle, pending-restoration recovery, one-shot SMD and
private pinned-image loader. They pass 1,695,946 fixture assertions,
including bus-service assertions during operation-by-operation fault
injection. Five independent controls reject cursor loss, the wrong
packet error, prematurely cleared restoration state, the pedometer
status bit and bus access while suspend state is retained. Bus, PM, IRQ,
mutex and integer-square-root services are modeled. The stream tests use
the actual IIO descriptor, scan-layout and timestamp-push code instead
of the old push shim. This does not qualify kernel lockdep, real interrupt
concurrency, firmware motion accuracy, standby consumption or false wakes.

The current core places a quaternion scan's timestamp at byte 16 with
tail padding to a 32-byte scan. The saved 6.18 core writes it at byte 24.
Both actual-helper probes use the current driver descriptors and pass, and a reader using the old offset fails
against the current core. `read-quaternion-current.py` is explicitly for
the pinned current layout and passes nine synthetic scans with nonzero
tail padding. The existing legacy device reader is unchanged. Do not
choose the layout by guessing from zero or nonzero timestamps.

The real kernel KUnit baseline passes seven tests and fails the added
tiny-fraction test; the candidate passes all eight. Its inherited UML
build diagnostics include generic IO null-pointer arithmetic, an unused
Clang target argument, fortify self-checks and an ignored documentation
file. The incremental candidate adds no unique diagnostic; this is not
a warning-free UML build. A separate sanitized host test compares tiny
scales with an independent Decimal oracle across shifts 30 through 63,
signed numerator limits, ordinary formatting and a nonzero buffer offset.
Its arithmetic and sysfs services are modeled; it complements real KUnit.

Four native Qualcomm profiles compile 72 selected driver and core
objects with LLVM 21, `W=1` and `COMPILE_TEST=n`, without diagnostics.
They cover ARM and ARM64 on both the maintainer source and the combined
runtime. The complete MPU I2C/SPI components, IADC, IIO core/buffer/event/
trigger helpers, timestamp helper and formatter tests compile. Configs,
commands and object hashes are in `configs/` and
`evidence/native-components.json`. The recorded dirty source bytes are
bound to the resulting committed source and integration heads. These
are component builds, not full kernel links, modpost or package builds.

The aggregate source passes strict checkpatch with only the generic
`FILE_PATH_CHANGES` reminder excluded after verifying the existing driver
wildcard and adding its ABI document to MAINTAINERS. The original seven
ports carry formatting that the eighth commit tidies; judge checkpatch
against the complete series. `evidence/get-maintainer.log` is a read-only
maintainer lookup, not a record of messages sent. The copied upstream
Linux syscall license note retains its exact bytes, including a blank
line at EOF. Only that byte-verified file is excluded from packet
whitespace checking; authored files and patches are checked normally.

Run the portable replay with Python 3, Clang 21 and standard `patch`:

```sh
python3 -B /absolute/path/to/fx0-iio-dmp-current/replay.py /tmp/iio-replay-new
```

Choose a fresh output directory outside the packet. The replay verifies
the file manifest, applies all eight patches with zero fuzz, checks final
source bytes and runs 23 model variants, three Decimal test methods and
nine reader scans. No Git, network, device, private logs or credentials
are needed. Sanitizers run with their normal leak checks enabled. When a
restricted runtime blocks LeakSanitizer, use a normal host environment.
The complete successful loader model additionally needs an owner-supplied
image with SHA256
`eabe2b79d93565358cca83864fece47d7dca5d5826bfbdab2d79ed75996076aa`;
an optional `--firmware /private/path` repeats it without copying that
image into the packet. The default replay does not repeat that private
loader test, native builds or real KUnit. `firmware-contract.json` records
the AOSP HAL and manufacturer-kernel provenance. `extract-reference.py`
accepts owner-supplied pinned source and accompanying license files via
`--source` and `--license`, verifies both input hashes and the output image,
and creates a new private directory via `--output`. It performs no network
or device access. Redistribution rights have not been established; the
image and agreement remain private.

For native reproduction, use the complete pinned source tree for the
desired profile, copy its supplied configuration into a fresh absolute
output directory as `.config`, then run `olddefconfig`, `modules_prepare`
and the object targets in `evidence/native-components.json`. Set
`O=/absolute/output`, `ARCH=arm` or `ARCH=arm64`, `LLVM=-21`, `W=1`,
`KCFLAGS=-Werror=incompatible-function-pointer-types`,
`--jobserver-style=pipe` and `-j4`. For real KUnit on the patched complete
IIO tree, run:

```sh
python3 -B tools/testing/kunit/kunit.py run \
  --kunitconfig=/absolute/packet/format.kunitconfig \
  --build_dir=/absolute/fresh-uml-output \
  --make_options=LLVM=-21 --make_options=W=1 \
  --make_options=--jobserver-style=pipe --jobs=4 --timeout=90 iio-format
```

The combined runtime changes ten IIO paths plus the ABI document and its
MAINTAINERS entry. All previous board, binding, display, camera, power,
touch, vibrator and USB source paths remain unchanged. Historical DMP
phone evidence is not physical acceptance of this current source. The
maintained-LTS endpoint, original r2 display fault, complete build/package/
update/recovery route and all remaining nonaudio hardware interactions
remain open, including final-image motion wakes, battery standby and soak.
