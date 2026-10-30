# Runtime Fx0 battery-profile handoff

The experimental [firmware branch](https://github.com/timschmidt/fx0-lk2nd/tree/integration/fx0-battery-handoff)
selects the observed stock pack from the original bootloader's exact
`lge.battid=ISL6296_L` argument. Unknown, truncated and duplicate values select
no profile. This is a boot-time type selection, not live battery authentication.

The firmware creates a standard `simple-battery` node and `monitored-battery`
references for the charger and optional experimental BMS. Upstream Linux board
DTS files keep replaceable-pack characteristics out of their static hardware
description. The handoff contains:

- The advertised 2,370 mAh rated capacity, distinct from the vendor's 2,440 mAh
  nominal parameter and temperature-dependent measured full-charge values.
- The existing 4.35 V charging and 3.40 V cutoff source references.
- All 155 vendor OCV points at −20, 0, 25, 40 and 60°C, with percentages and
  millivolt-to-microvolt conversion preserved exactly.

The OCV data come from vendor revision
`03aba4427a7666d57b5ae06d375e259ea337f351`, file
`arch/arm/mach-msm/lge/bms-batterydata-LGE_BL_59UH_2440mAh_TOCAD_MADAI_Final.c`.
The GPL-only adaptation remains in lk2nd's GPL module. See the source references
and qualifications in [battery bringup](../../docs/battery-bringup.md).

No current state of charge, learned capacity, fabricated sensor value or charging
temperature range is supplied. Charger-current ratings and battery operating
temperature limits are not inferred from unrelated board limits. The code makes
no PMIC writes and does not enable the extended BTC window. Removing a pack must
eventually invalidate native policy until its identity is established again;
runtime removal/replacement remains unqualified.

The DT update uses a separate, eight-byte-aligned workspace and publishes all
references together. Conflicting profiles, exhausted space/phandles and allocation
or write failures return errors without modifying the original DT. Downstream
kernels, nested lk2nd images and other machines are untouched. The GPL build
reserves 8 KiB of checked DT padding for the generated tables and other hooks.

## Host and firmware checks

The host test needs clang, ASan/UBSan and libfdt headers/library. It executes the
actual selector and update hook against real libfdt:

```sh
python3 diagnostics/lk2nd-battery-handoff/check.py /path/to/lk2nd --vendor /path/to/vendor-linux
```

The suite has 128 cases, including unknown/duplicate identities, both consumer
layouts, conflicts, malformed input, insufficient space, allocation/write errors
and byte-identical originals on failure. It models an ARM32 malloc allocation
aligned to four bytes; the firmware workspace must request stronger alignment.
Every vendor OCV value, temperature and percentage is checked independently.

The original commit `47a77fa` used ordinary malloc. Reproduce its defect with a
checkout of that revision:

```sh
python3 diagnostics/lk2nd-battery-handoff/check.py /path/to/original-lk2nd --expect-unaligned-failure
```

It returns `FDT_ERR_ALIGNMENT` for an otherwise valid tree. The corrected commit
uses `memalign(8, size)`. A host allocator's usual stronger alignment is not
evidence that the original ARM32 code was correct.

Build a RAM diagnostic with an ARM bare-metal GNU toolchain:

```sh
make lk2nd-msm8226 BOOTLOADER_OUT=/path/to/build LK2ND_FORCE_FASTBOOT=1
```

GCC 15.2 builds the full firmware with no new-source diagnostics. The linker
reports an RWX LOAD segment; this is not a zero-warning whole-firmware result.
Source/style checking uses LK's fixed-width types rather than Linux type aliases.

An existing DTB can be transformed by the same C hook without booting:

```sh
python3 diagnostics/lk2nd-battery-handoff/check.py /path/to/lk2nd --dtb-in input.dtb --dtb-out new-output.dtb
```

The output path must be new. Keep runtime DTBs private because they may contain
unit identifiers or command-line values. Targeted schema processing needs the
charger, BMS, common power-supply, battery, ADC-thermal, thermal-sensor and
regulator schemas. Omitting the regulator dependency produces misleading
`otg-vbus` diagnostics. Baseline schemas reject the new references; the candidate
bindings and both generated R4/BMS DTBs pass without diagnostics.

## Device procedure

Preserve the current installed bootloader prefix and both GPT regions on two
independent host filesystems. Freeze the exact candidate, source revision,
configuration and hashes there too. Use only identity-checked `fastboot boot`
for the firmware; verify its new version and selected battery type before
continuing the installed filesystem boot. Do not flash the candidate during
qualification.

Check the new firmware version in `/chosen`, the generated profile and references,
all five OCV-table hashes and the power-supply design attributes. Verify that
`capacity` remains absent and charger limits are unchanged. Initially mask the
ordinary UPower unit, then sample the real daemon through a bounded transient
service. Its lifetime must remain below the installed daemon's 20-second critical
action delay. Check actual D-Bus name ownership, rather than the list of
activatable names. Retain core results before starting that separate probe.

Always restore the original firmware and R4, remove the test-owned service mask,
restore normal UPower/Sxmo and the configured development USB budget, and compare
the bootloader/GPT captures. Normal OS filesystem writes are expected; this does
not claim a bit-identical whole eMMC or a factory-stock restoration rehearsal.
Successful handoff alone does not qualify charging policy, gauge accuracy,
capacity estimation, pack replacement or suspend protection.
