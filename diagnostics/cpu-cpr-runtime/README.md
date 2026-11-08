# Fx0 CPR runtime trials

`register.sh` is pinned to the separately built `6.18.59-fx0-cpr-observe`
RAM kernel. The initramfs contains only its two signed CPU modules, a
registration-only marker and their exact SHA256 manifest. Start the kernel
with `cpufreq.default_governor=userspace module.sig_enforce=1`.

The script requires signature enforcement and the requested default before
loading anything. It verifies the 300 MHz bootstrap, unapplied performance
state, disabled feedback and the retained 1.15 V APC target. It loads
`cpufreq_userspace.ko` successfully before `cpufreq-dt.ko`; the source otherwise
falls back to built-in schedutil. After registration it requires userspace,
300 MHz, the seven expected eligible rates and unchanged bootstrap state.
It makes no explicit frequency or voltage request.

The actual CPUFreq/userspace functions are executed by
`tests/test_cpufreq_controlled_start.py`, including missing-governor, wrong
boot default and changed driver-flag controls. The real shell script runs
against instrumented files/module loads in `tests/test_cpr_ram_registration.py`.
These host checks do not qualify hardware registration or performance changes.

A separate first performance trial must retain a userspace policy, limit it
to 300–384 MHz, verify each observed rate/APC target, and return through the
existing 180-second RAM timer to installed r50. Both rates map to the first
fixed-voltage corner: the stock 1.075 V floor/ceiling is rounded to 1.08 V on
this provider's 10 mV grid. Consequently LOOP_EN must remain clear at these
rates even after a positive performance state becomes applied. Feedback
at later corners, higher eligible rates, analogue rails, thermal/load/suspend,
and installed-package qualification remain separate gates.

Keep the new module certificate/build family separate from installed r50 and
from the unbooted Alpine r54 package. RAM trial artifacts and signing keys
remain in ignored private workspace storage. Audio and host built-in Wi-Fi
changes remain excluded.

## Transport encoding and observed scope

The original packed observation kernel stalls during data-only USB download at
3,588,096 confirmed bytes, before any BOOT and before the initramfs. The known
content-dependent lk2nd transport defect therefore also affects a compressed
kernel. `xz-preset3.py` is the exact wrapper used to re-encode the XZ payload,
retaining CRC32, architecture filter and dictionary options. It only adds the
LZMA2 preset. The original packed outputs are archived first. Rebuilding
`zImage` with `XZ=/absolute/path/to/xz-preset3.py` and the original build
identity requires invalidating the packing dependency (touching `Image` was
used here). Verify that both piggy streams, excluding their appended four-byte
size word, decompress to the identical `Image`, and that ELF, certificate and
Module.symvers hashes remain unchanged. Exact staging/readback is still required.
This is a lossless encoding workaround, not a transport fix.

The re-encoded kernel passes signed-module registration with taint zero and
then a separate `first-step.sh` RAM trial reaches 384 MHz through a 768 MHz PLL
and returns to the 300 MHz auxiliary path. Both points have applied 1.08 V APC
targets and LOOP_EN clear. The active MX vote requests a 1.0875 V floor; this
is not a claim that all other clients release their higher votes or that an
analogue rail was measured. The timed warm return restores the original r50
boot hash and native PMIC S2 range/VSET 1/115 (1.15 V target). That trial's
physical display/touch check is recorded separately in
`evidence/2026-11-08-cpr-first-fixed-corner.json`. Quiet two-second holds and
one warm return do not qualify sustained load, thermal/suspend or later-corner
feedback.

## First 600 MHz feedback trial

`feedback-600.sh` adds a `300-600` permit and calls the same guarded
registration script. It caps userspace at 300–600 MHz and explicitly requests
600 MHz, then 300 MHz. The second corner's stock floor/ceiling of
1.075–1.175 V become 1.08–1.18 V on the provider's 10 mV grid. At 600 MHz,
each check requires the uncached CPU clock, applied corner, allowed and enabled
feedback, matching APC/cache targets within those bounds, four online CPUs,
zero taint, unchanged policy and reported temperatures below 60°C.

Fifty samples, separated by 0.2-second sleeps, log voltage/control/result and
the four-CPU CPR interrupt total. A feedback pass requires interrupt progress
and either a cache/plan voltage difference or an IRQ-handler floor/ceiling
response flag. LOOP_EN or an interrupt alone is inconclusive. After sampling,
the script requires 300 MHz, the fixed 1.08 V target and LOOP_EN clear before
reporting success or inconclusive feedback. Invalid state stops further
requests; the unchanged 180-second timer remains responsible for native return.

`tests/test_cpr_feedback.py` executes the real shell control with FIFO frequency
requests and simulated observations. Its 22 modes cover voltage adjustment,
both clamps, inconclusive feedback, bad preconditions, voltage/grid/cache/clock
errors, interrupt storm, temperature cutoff and failed return. Host models do
not establish hardware behavior. Quiet feedback observation does not qualify
sustained load, analogue rails, thermal/suspend or higher eligible rates.

The first hardware run passes all fifty samples at the unit's 1.08 V initial
floor, with one interrupt and CTL `0x20000469` (enabled loop and auto-NACK-DOWN).
This is the handled floor branch, with no observed voltage adjustment. Return
to 300 MHz verifies CTL `0x20000428`. The timed native return restores r50's
original boot hash and PMIC 1.15 V target. The exact run and newest physical
UI/startup status are in `evidence/2026-11-08-cpr-feedback-600.json`.
The owner confirms display and touch on that newest return. Native startup
still has only the existing time-sync jobs pending at the latest check.

## Repeated transitions and bounded 600 MHz load

`load-600.sh` requires a separate `600-repeat-load` permit and the same guarded
registration. It caps userspace at 600 MHz, checks five 300→600→300 MHz round
trips, then runs one `sha256-worker.c` process on each CPU at 600 MHz. Each
process verifies its affinity, repeatedly hashes the known one-MiB repeating
0–255 byte pattern, checks every digest and exits after 30 monotonic seconds.
A compiler memory barrier requires a fresh buffer read each iteration.
The helper reports its own CPU and elapsed time and rechecks affinity.

The shell verifies the helper binary's digest and known-pattern result before
any performance request. Throughout transitions and load it checks the actual
clock, applied/cache/APC state, policy, four CPUs, zero taint, two reported
temperatures below 60°C, monotonic IRQ counts and the same voltage bounds.
It stops and joins workers on a guard failure or handled termination. All four
workers must exit successfully, report the correct affinity, at least 25 CPU
seconds each and 30–35 elapsed seconds before any 300 MHz return. The final
fixed-corner return gets ten more checks separated by 0.5-second sleeps.
The independent 180-second RAM return timer remains unchanged.

Build the helper with the tested ARM Alpine musl development sysroot and
Clang/LLD; no libraries are needed in the RAM image:

```sh
fx0_arm_sysroot=/path/to/alpine-armv7-rootfs
clang --target=armv7-alpine-linux-musleabihf --sysroot="$fx0_arm_sysroot" \
  -march=armv7-a -mfpu=neon-vfpv4 -mfloat-abi=hard -std=gnu11 -O2 \
  -Wall -Wextra -Werror -nostdlib -static --ld-path=/usr/bin/ld.lld-18 \
  "$fx0_arm_sysroot/usr/lib/crt1.o" "$fx0_arm_sysroot/usr/lib/crti.o" \
  diagnostics/cpu-cpr-runtime/sha256-worker.c \
  "$fx0_arm_sysroot/usr/lib/libc.a" \
  "$fx0_arm_sysroot/usr/lib/gcc/armv7-alpine-linux-musleabihf/15.2.0/libgcc.a" \
  "$fx0_arm_sysroot/usr/lib/crtn.o" -Wl,--build-id=none -o cpr-sha256
```

Keep the production 30-second default. `--digest SIZE` checks the repeating
byte pattern at lengths up to one MiB; `--worker CPU` performs the bounded
load. Four host tests use Clang's undefined-behavior sanitizer, including a
one-second variant for lifecycle/accounting, independent hashlib padding
vectors, checksum corruption and termination. Six shell tests cover 17 modes
with instrumented I/O and real child cleanup. The exact production ARM binary
also passes fifteen checksum cases and a 30-second emulated worker run.

The first hardware run passes all 90 state checks, including 37 load samples.
Four workers verify 1,463 one-MiB hashes with 113.737 total process CPU seconds;
reported temperatures span 38–44°C. APC stays at the 1.08 V floor with one
handled floor interrupt; voltage adjustment is not observed. Both observers
exit zero after the timer at 181.714515 seconds. See
`evidence/2026-11-08-cpr-load-600.json` for native recovery and the newest UI
check. This short workload does not qualify whole-RAM correctness, long stress,
thermal throttling, analogue rails, battery power, suspend or higher rates.
Native startup subsequently reaches running with NTP synchronized and no
failed units/jobs, without configuration changes. The newest UI check remains
boot-specific in the evidence; earlier DNS/startup delays remain unqualified.

## Prepared 787.2 MHz trial

`load-787.sh` is a separate, unbooted extension requiring the
`787-repeat-load` permit. It caps userspace at 787.2 MHz and checks three
787.2→600→787.2→300 MHz cycles, with ten quiet checks after the first PLL
entry. It then uses the same verified four 30-second workers at 787.2 MHz
and returns through 600 MHz to the fixed 300 MHz corner. Its 15 requests
never exceed 787.2 MHz; the kernel, signed modules, DTB, worker, boot arguments
and independent return timer are unchanged.

The qualified C mapper puts both 600 and 787.2 MHz in virtual corner 4/fuse
corner 2, so both retain the 1.08–1.18 V provider bounds and 1.1875 V MX floor.
The new path requires the uncached CPU PLL to read 787.2 MHz with enable count
one at 787.2 MHz, and enable count zero at 600/300 MHz. CPU mux, PLL, voltage,
loop, policy, IRQ and both temperature observations are logged. Only responses
observed at 787.2 MHz contribute to its feedback-response condition.

Six real-shell tests cover 22 simulated modes, including wrong PLL rate,
disabled PLL at 787.2 MHz, active PLL on an auxiliary return, false CPU rate,
worker failures and cleanup. `tests/test_cpu_rate_selection.py` executes the
actual qualified PLL/mux selection functions with the board PLL OPP table:
42 canonical decisions and two non-exact-rate rejection controls pass.
Parent callbacks/programming are modeled there; this is not a hardware test.
Four actual C corner-mapper tests also pass against the pinned vendor plans.

The prepared RAM image has not been staged or booted. Physical entry requires
the matching display/touch pass for the preceding r50 boot; the stage entry
has been checked to stop before any phone command while that result is
pending. See `evidence/2026-11-08-cpr-787-preparation.json`. No 787.2 MHz CPR
hardware, load, thermal or recovery result follows from this preparation.
