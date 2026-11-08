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
