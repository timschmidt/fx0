# Fx0 Wi-Fi and Bluetooth

The plan's [phase 4](bringup-plan.md#phase-4-establish-wireless-connectivity)
requires scanning, association, DHCP/DNS, sustained traffic, reconnect, resume,
a correctly derived MAC, Bluetooth pairing/HID/audio and coexistence. Signed
Nura package **6.18.59-r6** now carries WCNSS support and three fixes on the
installed system. Wi-Fi association, DHCP/DNS, traffic, reconnect and radio
toggling pass on an owner-designated WPA2 network. Bluetooth pairing, suspend/
resume, hotspot, coexistence, soak and the factory-MAC policy remain open.

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

## Installed packages

Signed r5 (`4eebb215c` recipe, source `b2512c53f`) installs the board and the
two WCNSS fixes through the same pre-install rollback checkpoint, trusted dry
run, supervised `apk add`, readback and installed-boot checks as r4. The
packaged DTB is byte-identical to the RAM-tested one. It is signed with the key
the phone already trusts. On r5, WCNSS runs with the fixed MX/PX consumers,
taint is 0, and the display and UI checks pass.

The build container needs `python3` added to the documented package list; the
r4 launch command had not been recorded. Two of the first r5 boot-script checks
were wrong: `apk info -v` prints descriptions, and the phone has no `zstd`.
They were replaced by `apk list -I` and comparison of installed `.ko.zst`
hashes with the APK. r6 adds the cfg80211 fix below and boots as build 7 with
taint 0. Its loaded `qcom_wcnss_pil` and `cfg80211` match the APK, and a
disassembly check confirms the fix is in the packaged module.

## Scan blocked after reconnect

On r5 the first connection works. After NetworkManager cycles the interface
during a scan, every scan returns `-EBUSY`, and wpa_supplicant cannot find the
network again. The cycle can come from applying Nura's default
`wifi.cloned-mac-address=stable` on activation, or from deleting or
reactivating a profile. Tracing shows the requests never reach the driver.
cfg80211 rejects them because the interface-down path parked a scan-done
message that mainline `dab68a74e90b` no longer flushes. The
[scan diagnostic](../diagnostics/wcnss-scan-busy/README.md) records the
localisation, controls and fix. Over 10 identical cycles, the unfixed module
stops scanning from the first disconnect. The fixed module and the installed r6
both pass all 10, with no wpa_supplicant scan failures.

## Wi-Fi qualification on installed r6

Results on the signed r6 kernel, taint 0, without module swaps:

| Check | Result |
| --- | --- |
| Association | WPA2, 5 GHz channel 36, 270 Mbit/s link, signal 69, 5.6 s |
| Addressing | DHCPv4 and IPv6 configured |
| DNS | Query sent from `wlan0` to the Wi-Fi resolver answered |
| Gateway | 20/20 pings, about 10.8 ms average |
| Download | Three 25 MB transfers at 62, 54 and 48 Mbit/s |
| Upload | 30 MB at 57 Mbit/s |
| Sustained (r5 with fixed module) | 10 × 25 MB in 36 s, mean 55.6 Mbit/s, all complete |
| Reconnect | 5/5 in 4.0–5.6 s, each with 3/3 gateway replies |
| Radio off/on | Reconnects |
| Kernel log | No wcn36xx, SMD or WARNING errors |

NetworkManager chose 5 GHz. A forced 2.4 GHz association on channel 11 (signal
73) gets DHCP and downloads 25 MB at 40.6 Mbit/s. Its first 20 gateway pings,
taken right after association, lost 3 and averaged 332 ms. Repeats of 30 pings
returned all of them, at 12.3 ms average with default power save and 1.8 ms with
power save disabled. The cause of the early loss is unexplained. The profile is
restored to automatic band and default power save. The
network name and credentials are kept only in ignored local files and in the
phone's root-only NetworkManager profile.

## Bluetooth with the host adapter

With owner approval, the phone was paired with the development host's adapter
and the pairing was then removed from both sides. Results on installed r6:

| Check | Result |
| --- | --- |
| Phone → host ACL (`l2ping`), unpaired | 10/10 in every run |
| Host inquiry finds the phone | Intermittent: missed in 12 s and 40 s scans, found in a 25 s scan |
| Host-initiated pairing | Fails: the host cannot page the phone (`ConnectionAttemptFailed`) |
| Phone-initiated pairing | Passes: SSP numeric comparison shows the same passkey on both sides; phone bonded, host paired |
| After bonding | `l2ping` gets 4 replies, then the link resets; a 4 MiB RFCOMM transfer resets on the host and stalls on the phone |
| Phone kernel log | No Bluetooth, SMD or WCNSS errors |

HCI traces captured with `btmon` correct parts of the first readings. The owner
approved installing `bluez-btmon` and `bluez-deprecated` on the phone. In one run
the phone accepted the host's page. That run also completed phone-initiated
pairing with a 16-byte encryption key, then an RFCOMM transfer hit supervision
timeout after about 20 KB.

Later runs varied the WLAN state: radio off, 2.4 GHz, 5 GHz, and radio on but
disconnected. At first these seemed to show Bluetooth depending on WLAN, but the
interpretation was confounded and is withdrawn. The only fully successful run
was the only one in which the host contacted the phone first. A clean-boot
2.4 GHz baseline, a host-first 5 GHz run and a WLAN-idle run all fail the same
way. Inquiry works, but connections time out in both directions (phone side:
Connection Accept Timeout 0x10). A plain unpaired phone-to-host `l2ping`, which
passed 10/10 in five early runs, now fails even after a clean phone reboot.

That points at host-side state, such as the host stack or adapter after repeated
pair/remove cycles or the host's own combo radio. Phone-side causes are not
excluded. An independent Bluetooth peer is needed to separate them. Two
observations remain open questions:

- The Iris PA (L16) and RFA/digital (L24) rails switch off when the WLAN radio
  is off. Whether that affects Bluetooth is unproven.
- Prima sends a block of BTC CFG items at start that wcn36xx's WCN3660 table
  omits. Its separate `WDA_BTC_SET_CFG` handler is a no-op. One test with those
  items was confounded and is inconclusive.

See [Bluetooth evidence](../evidence/2026-10-30-bluetooth-host-pairing.json).

### Independent peer

The owner provided a Plugable Bluetooth 4.0 USB adapter (Broadcom BCM20702A0)
as an independent peer. Unpaired phone-to-peer `l2ping` passes 10/10 at about
7 ms once the peer is discoverable. Before that, BlueZ on the peer refuses the
unknown device, which explains the earlier PC-adapter failures.

With the harness confirming on both sides, phone-initiated pairing bonds on the
first attempt. Three separate bonded RFCOMM connections each deliver 4 MiB with
matching SHA-256, at about 1.2 Mbit/s, while WLAN is associated on 5 GHz.
Bonded `l2ping` gets 4 replies before the peer closes the idle, profile-less
link. The phone's Bluetooth controller, pairing, encryption, reconnection with
the stored key and data transfer therefore work. The pairing was removed on
both sides; the owner's existing peer pairings were untouched.

With the WLAN radio off, when the PMIC showed the Iris rails off, pairing still
bonds and two of three 4 MiB RFCOMM transfers complete with matching SHA-256.
The third connection was reset by the peer, so the rail state does not disable
Bluetooth, but this case needs repetition in soak testing. See
[peer evidence](../evidence/2026-10-30-bluetooth-independent-peer.json).

## Hotspot

wcn36xx offers AP mode. A NetworkManager hotspot with default settings fails:
wpa_supplicant logs `key setting validation failed` and cannot initialise the
AP interface. The driver advertises only WEP40, WEP104, TKIP and CCMP-128, with
no BIP/CMAC cipher, so management-frame protection cannot work. Yet the default
PMF setting makes wpa_supplicant attempt a key that cfg80211 rejects.

With `wifi-sec.pmf disable`, a WPA2-CCMP hotspot starts on 2.4 GHz channel 6,
and the development host sees its beacon (signal 89). A client association,
forwarding and power test needs a second Wi-Fi client. Nura's hotspot defaults
need PMF disabled on wcn36xx, or wpa_supplicant should skip PMF when BIP is
missing. See [hotspot evidence](../evidence/2026-10-30-wifi-hotspot.json).

## MAC addresses

When connected, NetworkManager applies Nura's default stable cloned MAC per
connection. The underlying `wlan0` and `hci0` hardware addresses are `02:00:…`. lk2nd derives these
locally administered values from the serial number and injects them as DT
`local-mac-address`. They are stable, but they are not factory addresses. The
preserved NV slot 0 holds an LG Electronics OUI address. Slots 1–3 are
consecutive generic placeholders. Stock receives its MAC through a userspace NV
path rather than from the chip. Using NV slot 0 is therefore likely correct, but
a stock runtime reading must confirm it. `.bt_nv.bin` holds one tag-1, six-byte
BD_ADDR record whose vendor is not evident. Full addresses stay private.

## Next steps

1. Run an overnight soak, explain the transient early 2.4 GHz loss, and test
   suspend/resume once system suspend is qualified.
2. Decide the MAC source after a stock runtime reading, then implement it without
   publishing the per-unit values.
3. Test HID and audio profiles with a peripheral in pairing mode, repeat the
   WLAN-off RFCOMM case, and decide the Bluetooth address source.
4. Describe the TLMM sleep state, then test WCNSS across real system suspend.
   Check hotspot capability.
5. Upstream submission is gated on owner approval. The regulator fix is
   prepared for remoteproc ([draft](../submissions/remoteproc/README.md)) and
   the cfg80211 fix for wireless ([draft](../submissions/wireless/README.md)).
   Both lack Signed-off-by and have not been sent. Fold the DXE
   trigger fix into the MSM8226 WCNSS node series once that series is prepared. Add the matching MSM8974 trigger
   change only with a test there or as an explicitly untested suggestion.
   Replace the expected L24 warning with a clean profile.

Evidence: [first start, fixes and return](../evidence/2026-10-30-wcnss-first-start.json)
and [installed r5/r6 and Wi-Fi qualification](../evidence/2026-10-30-wifi-r6-qualification.json).
