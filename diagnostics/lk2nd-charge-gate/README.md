# Fx0 early firmware charge gate

The experimental [firmware branch](https://github.com/timschmidt/fx0-lk2nd/tree/integration/fx0-charge-gate)
inhibits battery charging before Linux can defer native charger probe on missing
profile or sensor suppliers. It uses checked SPMI calls, preserves forced-battery
mode and other charger-control bits, then selects and verifies the conservative
BTC window while charging is off. It does not enable charging.

This protocol is a development proposal. The Linux thermal worker and firmware
handoff validation are not connected yet; the existing driver can re-enable
charging when its normal setup completes. Do not enable this flag with an older
driver and treat the boot-time marker as a complete software charging policy.
The physical test deliberately disables the native charger driver.

| Property on the sole `qcom,pm8226-charger` node | Meaning |
| --- | --- |
| `qcom,software-charge-control` | Empty boolean requesting the early gate. New/proposed property, not an accepted upstream binding. |
| `qcom,boot-charge-inhibited` | Empty boolean added only after successful hardware verification. Firmware rejects an incoming copy. |

The hook applies only to native `lg,madai`, at the verified PM8226 SID0/address
0x1000. Downstream/nested firmware and trees without the opt-in receive no gate
I/O. Unknown battery selection does not bypass an explicitly requested gate.
Runtime PMIC type/subtype must match before writes. Conflicting nodes, malformed
properties, existing markers and wrong addresses fail rather than selecting a
fallback target.

The callback clones the tree in aligned memory and completes its fallible FDT
work before PMIC access. It clears CHG_CTRL bit7, verifies the full byte, then
updates BTC mask0x83 to value0x81 and verifies the byte. All unrelated bits and
the thermistor reference are preserved. A control/BTC error attempts a separate
verified inhibition and returns the original error even if recovery succeeds.
The marker is published only after complete success. Permanent bus failure can
prevent inhibition. An error aborts boot; current aboot treats a failed DT update
as an assertion, so recovery may require a physical reset.

The shared SPMI implementation now bounds status polling to 1,000 one-microsecond
delays per transfer. Checked read/write APIs propagate failure; older byte/void
helpers still discard errors and are not retrofitted by this change. Host tests
do not measure physical bus timing.

```sh
python3 diagnostics/lk2nd-charge-gate/check-spmi.py /path/to/lk2nd
python3 diagnostics/lk2nd-charge-gate/check-gate.py /path/to/lk2nd
```

The first suite executes the complete SPMI implementation against fake MMIO:
2,048 transfer cases across both compiled core layouts, runtime channel lookup,
1–8 byte payloads, delayed completion, error status and timeout. The second
executes the actual gate with real libfdt: 307 ASan/UBSan cases cover both control
bytes, bit preservation, gate ordering, invalid/legacy paths, every bus boundary,
errors before/after writes, dropped writes, bad readback and transactional FDT
failure. The existing 128 battery-profile cases remain independent regressions.
These tests do not establish physical timing or the final Linux policy.

For hardware isolation, the DTB preparation option adds the opt-in and sets the
charger's status to disabled, without forging a marker. `build.py` packages the
known kernel, static ARM BusyBox and read-only observer with the supplied DTB.
The init mounts only virtual filesystems, makes available eMMC block devices
read-only, records the actual firmware marker/control/BTC state and reboots.
Its independent 90-second timer starts after init begins; it cannot recover an
earlier kernel hang. No SSH or USB gadget is expected in this diagnostic.

Capture original boot files/prefix/GPT and both exact RAM images on two host
filesystems before booting the candidate firmware, then the observer image.
Retrieve retained logs through original lk2nd and return to installed r4 with
taint zero and normal services. This is an intentionally disabled-driver test,
not a completed test of real fw_devlink supplier deferral or runtime removal.

The first physical run verifies CHG_CTRL=0 before native probe but observes
inherited BTC=0x82, failing its narrower-window assertion. This is evidence of
the boot-path state; the precise writer/reset source was not traced. The revised
gate explicitly narrows BTC while charging is off. Keep failed-run captures and
their exact firmware separate from the subsequent run.

The repeated run uses the same observer image and passes with charge control
0x00, BTC0x81 and reference0xc0. Both runs return to installed r4 with taint zero,
active normal services and matching bootloader/GPT readbacks. The exact tested
commit is pinned separately from a later comment-only clarification in
[the manifest](../../manifests/firmware-charge-gate.json). See
[hardware evidence](../../evidence/2026-10-30-firmware-charge-gate.json).
