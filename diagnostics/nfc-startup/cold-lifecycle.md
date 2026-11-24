# NFC cold module lifecycle

The corrected r58 family passes a physical RAM-only signature/registration and
cold module lifecycle trial. See [evidence](../../evidence/2026-11-08-nfc-cold-lifecycle.json)
and [the tested image manifest](../../manifests/nfc-cold-lifecycle-ram.json).
This qualifies cold ownership and cleanup; controller startup, tag/RF and power
management remain separate requirements.

`cold-lifecycle.sh` first invokes the qualified startup guard, checks its own
permit and all module hashes, and requires the exact release/linked notes,
signature enforcement, no preloaded modules, four CPUs, zero taint, two bounded
temperatures, RAM/pseudo-filesystems only and no CPUfreq policy or CPR provider.
Its independent init return timer is unchanged. The kernel, DTB, command line
and all fourteen previous CPIO entries match the qualified r58 startup image.

Five signed APK modules are included in dependency order: `rfkill`, `nfc`,
`nci`, `nxp-nci`, `nxp-nci_i2c`. All signatures and 325 imported symbol CRCs are
verified against the exact r58 kernel family. Two controls use the same rfkill
ELF: one omits its signature trailer, the other changes one CMS signature byte
while retaining a parsable CMS structure. Both retain the valid module's release
and ABI. The real kernel rejects both with key errors and status 129 before any
valid load; rejected controls leave no modules and zero taint. Then all five
signed modules load without force options.

The transport probe leaves NCI cold. VEN20 and FIRM22 are output-low, IRQ21 is
an input with the board's pull-down/drive configuration, and `cxo_d1_pin` has
zero enable/prepare/protect counts. Pinmux ownership, the correct I2C driver,
NFC class parent, rfkill child and IRQ handler are checked together; GPIO debug
output alone is not used as ownership proof. Three explicit unbind/rebind
rounds recreate the class/rfkill state and release/reacquire ownership. Reverse
ordinary module unload performs the fourth cold removal. The final state has
no modules, NFC/rfkill child, IRQ handler, pin owners or clock consumer.

Each operation runs in a child whose completion/status is observed before the
next mutation. Twenty completion checks bound an individual operation, with a
90-second overall monotonic deadline and a separate 180-second init timer. On
uncertain completion or any failed guard the checker stops further module/bind
operations, sends no kill or forced cleanup, and leaves return to the init timer.
The observer invokes it once and then only reads notes, boot hash and kernel
logs. No NCI up/reset/poll, direct GPIO request, RF or firmware command occurs.

Three host tests exercise 43 modes using simulated module callbacks and actual
FIFO writes for bind/unbind. They cover acceptance of invalid signatures,
wrong rejection reasons, stalled operations, thermal/policy/taint changes,
missing or excessive IRQs, wrong ownership/parents and cleanup failures. Tests
detect isolated removal of clock-vote, IRQ-release and deadline guards. A fake
clock update race found during a control run is corrected by atomic replacement;
the final suite and all three controls pass. The exact ARM BusyBox parses all
four image scripts and executes background-wait and pinmux-awk controls.
These host tests model the kernel callbacks; the physical result is recorded
separately in the evidence.

The physical run captures 18 completed operations, 12 snapshots and 48 temperature
samples at 38–39°C. All four probe/removal cycles remain cold; all captured NFC
IRQ counters are zero. This does not stress a pending IRQ thread, an open NCI
device or concurrent firmware download. The timer returns to native r50, with
its original boot hash, programmed 1.15 V APC target, zero taint, UI services
and unchanged host networking. Latest owner display/touch status is recorded
in the evidence. No candidate is installed, and the content-dependent USB
transport defect and wider reliability work remain open.
