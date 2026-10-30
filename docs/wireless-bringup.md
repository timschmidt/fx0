# Fx0 Wi-Fi and Bluetooth

The plan's [phase 4](bringup-plan.md#phase-4-establish-wireless-connectivity)
requires scanning, association, DHCP/DNS, sustained traffic, reconnect, resume,
a correctly derived MAC, Bluetooth pairing/HID/audio and coexistence. This
record covers the first native WCNSS start and the supply fix it exposed. It
does not qualify association, traffic, Bluetooth pairing or suspend.

## Board description

The [Linux branch](https://github.com/timschmidt/fx0-linux/tree/integration/fx0-wireless-r4)
applies the recovered MSM8226 WCNSS series to the exact r4 source
`5c3efd4c7fa8`. It keeps the original authors and adds an Fx0 board commit. The
stock vendor tree supplies every board value:

| Supply | Rail | Stock limits | Resolved on Fx0 |
| --- | --- | --- | --- |
| Pronto MX | L3 | 0.75–1.3375 V | Pronto v2 vote 1.2875 V |
| Pronto PX | L6 | 1.8 V | 1.8 V, already always-on for eMMC |
| Iris XO | L10 | 1.8 V | 1.8 V, shared with USB PHY |
| Iris PA | L16 | 3.0–3.35 V | 3.0 V |
| Iris RFA and digital | L24, shared | 1.30–1.35 V | 1.3 V |

Stock's Iris profile requests PA 2.9–3.0 V and digital 1.225–1.8 V. Within
L16/L24 limits these give exactly 3.0 V and 1.3 V. The mainline `qcom,wcn3660`
profile gives the same result. The recovered `qcom,wcn3660a` compatible maps to
the WCN3680 profile, which would raise PA to 3.3 V, so the Fx0 does not use it.
Both compatibles select the same wcn36xx RF ID and 48 MHz XO.

The Iris driver ignores voltage-request failures. Its digital request
(1.2–1.225 V) cannot be met on the shared rail, so the kernel logs
`l24: unsupportable voltage range: 1300000-1225000uV` and the RFA request sets
the rail. The Motorola Titan board has the same arrangement. Removing this
expected warning, for example with a stock-matching digital range, is a
submission cleanup item.

TLMM40–44 use the stock active 5-wire configuration: function 1 (wlan), 6 mA,
pull-down. Stock suspend uses GPIO function, 2 mA and pull-up. That sleep state
is not yet described and must be handled during suspend work.

## Firmware and calibration

Nura's installed `msm-firmware-loader` mounts the original `modem` and `persist`
partitions read-only and links `wcnss.mdt`/`.bNN` and
`wlan/prima/WCNSS_qcom_wlan_nv.bin` into the kernel firmware path. No firmware
is packaged or published, and the device's own calibration NV is used. The
loader logs a tmpfs mount failure because its mount point does not exist yet,
and a `dirname` error when no DT `firmware-name` exists. Neither prevented
loading here, but both are worth reporting to that project.

## First native start

A RAM boot used the installed r4 kernel, initramfs and command line unchanged,
with only the new DTB. Results:

- Pronto is `running`. The control channel reports WCNSS 1.5 1.2, and wcn36xx
  reports `WCN v2.0 RadioPhy vIris_TSMC_3.0 with 48MHz XO`, CRM
  `CNSS-PR-1-4-1-c3-00062`, API 1.5.1.2. This matches the retained stock log.
- `phy0`/`wlan0` and Bluetooth `hci0` (btqcomsmd) register. Neither rfkill is
  blocked. NetworkManager manages `wlan0`. Kernel taint stays 0.
- The scan reports 20 BSSes on 2.4 GHz channels 1, 3, 6 and 11 and on 5 GHz
  channels 36 and 44.
- The Bluetooth controller is Qualcomm (manufacturer 0x001d), HCI version 6,
  with central and peripheral roles. A 12-second scan discovers two devices.

## Supply defect found

The started system shows only a dummy `vddcx` regulator supplier for Pronto. The
RPM L3 and L6 regulators have no WCNSS consumer. The 6.18.59 stable backport
of `3dbc90b9c22e` treats Pronto v1/v2 tables as Pronto v3, so MX/PX are never
requested on any board with one or two power domains attached. The
[regulator check](../diagnostics/wcnss-regulators/README.md) reproduces this from
the real source. The fix on the branch selects the v3 path only when the table
has no PD regulators. It passes all ten table/domain cases; unfixed 6.18.59 fails
six. No upstream fix for v1/v2 was found.

The rebuilt module was built from an exported tree, so its release is plain
`6.18.59`. Its vermagic and all 73 import CRCs match the installed r4 module.
Loaded in place of that module, it makes Pronto consume RPM L3 as `vddmx` (vote
1.2875 V, within the stock limit) and L6 as `vddpx`; the dummy supply is gone. The
unsigned diagnostic module sets taint E (8192) only for that boot.

## Restart and DXE interrupts

Stopping and restarting WCNSS on the first RAM DTB brings the firmware back. The
wifi child then fails with `irq: type mismatch, failed to map hwirq-177` and
`IRQ tx not found`. wcn36xx requests both DXE interrupts with
`IRQF_TRIGGER_HIGH`, and the MSM8916/8939/8953 descriptions declare level-high.
The recovered MSM8226 node, copied from MSM8974, declares rising edge. Stock
leaves the type unspecified. The first probe silently reprograms the mapping, so
any later re-probe fails, including remoteproc recovery.

A separate SoC commit declares level-high. On the second RAM DTB, a restart with
the regulator-fixed module re-registers Wi-Fi and Bluetooth. A rescan again finds
2.4 GHz channels 1/3/6/11 and 5 GHz channels 36/44. MSM8974 carries the same
specifier upstream, but that is untested here.

While the radio is active, the PMIC readback shows L16 at 3.3 V, although Linux
votes 3.0 V. The Pronto firmware makes its own RPM vote during operation,
within the stock 3.0–3.35 V limit. The Linux Iris profile governs only the boot
handover.

## MAC addresses

`wlan0` and `hci0` currently use `02:00:…` addresses. lk2nd derives these
locally administered values from the serial number and injects them as DT
`local-mac-address`. They are stable, but they are not factory addresses. The
preserved NV slot 0 holds an LG Electronics OUI address. Slots 1–3 are
consecutive generic placeholders. Stock receives its MAC through a userspace NV
path rather than from the chip. Using NV slot 0 is therefore likely correct, but
a stock runtime reading must confirm it. `.bt_nv.bin` holds one tag-1, six-byte
BD_ADDR record whose vendor is not evident. Full addresses stay private.

## Next steps

1. Associate with an owner-designated test network. Then qualify DHCP/DNS,
   sustained traffic, reconnect and both bands.
2. Decide the MAC source after a stock runtime reading, then implement it without
   publishing the per-unit values.
3. Pair a Bluetooth device. Then test transfer, HID and audio profiles, and
   coexistence under Wi-Fi traffic.
4. Describe the TLMM sleep state, then test WCNSS across real system suspend.
   Check hotspot capability.
5. Package the kernel change into a signed Nura build and boot it from eMMC.
6. The regulator fix is prepared for the remoteproc tree with its checks and is
   awaiting owner review and sign-off; see the
   [remoteproc draft](../submissions/remoteproc/README.md). Fold the DXE
   trigger fix into the MSM8226 WCNSS node series once that series is prepared. Add the matching MSM8974 trigger
   change only with a test there or as an explicitly untested suggestion.
   Replace the expected L24 warning with a clean profile.

Evidence: [first start, fixes and return](../evidence/2026-10-30-wcnss-first-start.json).
