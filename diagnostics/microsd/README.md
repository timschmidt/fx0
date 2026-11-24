# Fx0 SDHC2 card-detect observation and bias candidate

The r49 writeback probe recorded 22,675 GPIO37 interrupts during a 4 MiB
file fsync. An earlier suspend trace captured a card-detect wake event
before the freezer aborted. The controller column in the old writeback
summary stayed zero during both fsync and read, so it cannot establish how
many SDHCI completions occurred. The original observations remain recorded.
[Writeback evidence](../../evidence/2026-11-06-microsd-writeback-cd-irqs.json)

The new observer identifies the controller, power and card-detect lines
through the SDHC2 device-tree alias, hardware IRQ number, action and trigger.
It uses the Linux IRQ numbers from each boot and sums counters across CPUs.
Missing or ambiguous rows, identity changes and decreasing counters are
errors. On r50 the observed lines were IRQ58/GIC157 for the controller,
IRQ59/GIC253 for power and IRQ63/TLMM37 for card detect.

A read-only 4 MiB direct read of the unmounted SD disk accounted for 8,192
read sectors, 18 controller interrupts, zero power or card-detect interrupts
and zero written sectors. Two three-second idle windows were quiet. GPIO37
stayed low with an internal pull-up. The read payload was discarded on the
phone. The result verifies counter attribution and quiet read behavior on
this boot. Writeback, removal and suspend behavior remain open.

## GPIO37 bias comparison

The vendor Madai gpiomux uses a 2 mA GPIO input with internal bias disabled
in its active configuration and the `MACH_LGE` suspend configuration. The
Madai defconfig selects the board that enables `MACH_LGE`, and the vendor
board code installs that pin configuration. Both trees use GPIO37 active
low. The stock code does not establish the external pull or the reason for
the observed IRQ burst.

The [DT patch](fx0-sdhc2-stock-cd-bias.patch) changes `bias-pull-up` to
`bias-disable` for the GPIO37 pin group. The DTB comparison finds just that
property replacement. IRQ routing, GPIO polarity, pin function, drive
strength, supplies and SDHC2 configuration match the baseline. The patch
replays with zero fuzz. Both DTBs compile with the same three inherited
warnings, and the relevant pinctrl schema produces no diagnostics. The
verifier rejects the unchanged pull-up DTB and a changed CD polarity.

The two RAM images use the same exact retained native r50 kernel, compressed
initramfs and 180-second timer. Their DTBs differ only in the bias property.
Both images reparse and reproduce byte for byte. They are prepared for a
comparison after the current display/touch baseline and coordinated powered-off
card reseat. The card must report a stable low level when inserted and a
stable high level when absent before a writeback comparison. Repeat the same
owned-file fsync/read/idle phases on the same media and power setup, with
controller and GPIO37 counts recorded separately. Suspend entry, RTC wake,
removal and filesystem integrity each need physical evidence.
[Image manifest](../../manifests/microsd-cd-bias-ram.json)

Run the observer on the phone with its current boot ID. The optional
`--direct-read` performs the 4 MiB control after checking for mounts in the
current namespace and active block holders. It opens only the verified
removable block device read-only and outputs counters.

```sh
python3 observe-sdhc2.py --boot-id CURRENT_BOOT_ID --direct-read
```

Five host regression methods cover role attribution, IRQ renumbering, CPU
counter changes, ambiguous rows and disk replacement. The current kernel
and card have a live read result. The paired RAM images and writeback/suspend
comparison remain untested on hardware.
[Evidence](../../evidence/2026-11-10-microsd-cd-bias.json)
