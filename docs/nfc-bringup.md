# Fx0 PN547 NFC preparation

The native r50 kernel has NFC disabled. A read-only baseline on November 8
finds QUP3 disabled with no children, GPIO10/11/20/21/22 unclaimed and an
`AF_NFC` socket rejected with `EAFNOSUPPORT`. The module list is unchanged by
that capability check. This does not establish that the physical controller
is absent or faulty.

The pinned production source at
`03aba4427a7666d57b5ae06d375e259ea337f351` enables PN547 C2 and its PMIC clock
path. Its board description and selected driver/pinmux give:

| Resource | Production mapping and preparation |
| --- | --- |
| Bus/address | QUP3 `0xf9925000`, SDA10/SCL11, 100 kHz, address `0x28`; production bus drive strength 8 mA |
| Enable | GPIO20, active high; 2 mA, no pull, cold output low |
| Firmware mode | GPIO22, active high; 8 mA, no pull; vendor probe drives it low, as the new cold state does |
| Interrupt | GPIO21, 8 mA, pull-down/input; vendor driver requests rising edge despite the older DT's falling-edge flag |
| Reference clock | Vendor `cxo_d1_pin`, XO buffer ID 2; maintained RPMCC exposes the same pin-control vote as `RPM_SMD_CXO_D1_PIN` (54), fixed 19.2 MHz |

These are source constraints and requested settings, not new electrical
measurements or a controller identity/communication pass. Existing stock
properties name the NXP vendor and running `nfcd`; the proprietary firmware
and libraries remain private and are neither copied into this work nor run.

## Source changes and checks

The [NFC source branch](https://github.com/timschmidt/fx0-linux/tree/integration/fx0-nfc)
is published at `94010ddccf9aaa212870ecd0ea0058e33de482c9`. Its conservative
base `789d5197844d5268197a17a94605316eedae9fdb` matches all 18 changed source
files of the reconstructed r50 profile. The NFC changes do not depend on the
later CPU/CPR candidate.

Four separate commits:

1. Unregister an already registered NCI device if threaded IRQ setup fails.
2. Describe one optional reference clock named `ref`, requiring the clock and
   its name together while retaining existing no-clock boards.
3. Acquire that optional clock, enable it before raising VEN and release it
   after entering cold mode. Failed clock acquisition/enable does not change
   GPIO state, and failed open leaves the core cold so it can retry. Repeated
   mode changes do not duplicate votes.
4. Describe the PN547, rising IRQ, cold GPIO states and reference clock on
   QUP3. TLMM uses `output-disable` for the IRQ input; its binding deliberately
   rejects `input-enable`. No unqualified wake capability or LP5521 device is
   added.

The [manifest](../manifests/kernel-nfc-preparation.json) pins the base, commits,
raw patches and config fragment. All four raw patches replay to the exact
published tree and pass strict checkpatch with sign-off checking disabled.
Contributor certification, current receiving-tree bases and upstream routing
remain separate requirements; no mail or PR is sent.

Twenty ARM ELF objects/composites from the NFC/NCI stack and driver compile
with `W=1` and no compiler warnings; KCFI remains enabled. Twelve host checks
pass without skips: actual C mode/open/close/probe functions execute nine
controlled cases, and real schema checks cover the compiled NFC/QUP/TLMM/RPM
nodes, five rejected clock-property shapes and two legacy configurations.
Three failure tests reject the unmodified driver. The compiled board keeps
r50's four active CPU OPPs and original clock/domain semantics. Its three DTC
warnings are identical to the separately compiled r50 baseline, which matches
the original r50 DTB hash exactly.

The isolated sparse build initially missed host headers and a syscall-table
reference; these fixture files were restored before final checks. Checkpatch's
vendor-prefix reference was also restored before its final pass. No source or
validation guard was weakened. The qualified r50 source index, all 18 changed
files and recorded kernel/config/DTB/symbol/certificate artifacts stay unchanged.

## Build and next hardware gates

Use the exact published source with the r50 config, normalize it for the host
toolchain, merge [the NFC fragment](../configs/msm8926-nfc.fragment), then run
`olddefconfig`. The distinct release is `6.18.59-fx0-nfc-prep`; only NFC options
and `LOCALVERSION` differ from the normalized r50 config. Targeted checks are
`make ARCH=arm LLVM=1 LD=ld.lld-18 W=1 prepare net/nfc/
drivers/nfc/nxp-nci/ qcom/qcom-msm8926-lg-madai.dtb` with a separate output
directory. This targeted preparation did not produce a full linked kernel,
MODPOST-checked signed modules, source APK or boot image.

## Complete host kernel and module verification

The same source now builds a complete `6.18.59-fx0-nfc-prep` ARM kernel,
all 468 modules and the Fx0 DTB. The successful build takes 355.87 seconds.
KCFI remains enabled in compilation and the linked ELF, with permissive mode
disabled. Its only undefined symbols are the same five BPF/weak-EFI entries
as the reconstructed-r50 baseline. The DTB is byte-identical to the earlier
schema-checked NFC DTB, and kernel/BSS placement fits below the forced RAM
ramdisk address. No RAM image has been built or booted from this Fedora artifact family.

The first attempt terminates on the per-user `/tmp` quota despite filesystem
free space. The workspace retry adds only
[lossless DWARF compression](../configs/nfc-debug-storage.fragment) to the
normalized NFC configuration. Actual `.debug_info`, `.debug_line` and
`.debug_str` ELF streams decompress completely and retain DWARF5; CFI,
signing, CPU and other runtime choices stay unchanged. No debug information
is stripped from the linked kernel.

To provide linking headroom, seven regenerable top-link `vmlinux.o`
intermediates from earlier workspace builds are losslessly archived. Every
archive is independently decompressed and checked before removing that
original intermediate, freeing 1,129,364,904 bytes. All 46 recorded existing
final kernel/config/DTB/symbol/certificate hashes remain unchanged. The private
receipt records original/archive paths, sizes and SHA256 values; restore a
matching intermediate before incrementally relinking one of those old build
directories. The protected root index and conservative source/index remain
unchanged, and the recovery disk is never written.

All 468 stripped, signed, compressed staged modules verify against the exact
1,324-byte certificate embedded in the new kernel. All have the correct ARM
architecture, release and in-tree marker. All 25,562 imported symbol CRCs
match this full build's `Module.symvers`. Modified payload/signature, wrong
certificate and wrong-ABI controls reject. The NFC I2C dependency order is
`rfkill`, `nfc`, `nci`, `nxp-nci`, `nxp-nci_i2c`; all five must come from this
same new certificate/build family. The private signing key remains mode 0600.
Future RAM registration must enforce signatures; the host checks do not prove
runtime signature enforcement. No module is loaded during these checks.

The [full-build manifest](../manifests/kernel-nfc-full-build.json) and
[evidence](../evidence/2026-11-08-nfc-full-build.json) pin these artifacts and
the complete configuration delta. The independent Alpine source build is described below. RAM startup/NFC
operation and installed update/recovery remain unqualified.

## Independent Alpine distribution build

The separate r56 source package now builds from the exact ten conservative
r50 patches plus the four NFC patches. Its complete exported series matches
the published NFC tree, with a distinct `6.18.59-fx0-nfc-alpine` release and
certificate. The actual Alpine configuration has only the 19 known compiler
capability differences, passes the official community checker and retains
nonpermissive CFI, module signing and compressed DWARF. All 468 packaged
modules pass CMS and import-CRC checks against this kernel, with tampered and
wrong-family controls rejecting. APK signatures and normal offline ARMv7
resolution pass. The package initially exposes empty BusyBox dependency lists for compressed
modules. Explicit kmod plus a packaging-only rerun fixes all 391 direct/577
transitive edges without changing the compiled kernel/configuration/key;
the new all-module dependency audit rejects the preserved original bad APK.
The prior uninstalled r55 Alpine package shares this metadata defect;
[r57 now corrects it](../evidence/2026-11-08-cpr-package-dependencies.json) while
retaining its exact kernel and signed modules. Neither NFC family has booted.

See the [package manifest](../manifests/kernel-nfc-package.json),
[build procedure](building.md#independent-alpine-pn547-nfc-package) and
[measured package evidence](../evidence/2026-11-08-nfc-alpine-package.json).
Source composition, artifact identity and distribution build checks do not
transfer native r50 hardware qualification or establish installed update hooks.

## Prepared first Alpine NFC RAM startup

The first bounded startup image is prepared from the verified Alpine r56 APK:
6,207,488 bytes with SHA256
`e4b04713cfcf8deda30872b69fdaf1cd429af525d4053c6412fc0953f16eb1b7`.
Its original kernel/DTB encoding is retained, with no modules, firmware or CPU
registration payloads. All ten base initramfs entries, including BusyBox,
init/USB/HTTP and the 180-second warm-return timer, are unchanged from the
qualified RAM family. Only the command-line governor changes from `userspace`
to `schedutil`, matching this conservative source profile; signature enforcement
remains requested. No CPUfreq policy or NFC binding is expected without modules.

The [read-only checker](../diagnostics/nfc-startup/check-startup.sh) pins the
exact kernel notes and release, then validates signatures/topology/taint/module,
mount/temperature state and one unbound PN547 client on enabled QUP3. Its actual
shell implementation passes 28 fixture modes without changing any fixture or
calling module/GPIO/I2C tools. Independent header/checksum/CPIO parsing proves
all 14 archive entries and the absence of modules/firmware. ARM BusyBox syntax
and compatible-byte conversion pass under emulation. None of these tests boots
the new kernel or proves runtime signature enforcement, GPIO levels, bus/RF
operation or timer recovery.

The actual staging process rejects the pending native UI result before phone
access; instrumented pending and wrong-boot cases likewise reach no phone
client or subprocess. No staging/BOOT/controller state exists. The latest
native r50 boot/hash/policy/services remain unchanged. See the
[image manifest](../manifests/nfc-startup-ram.json),
[trial procedure](../diagnostics/nfc-startup/README.md) and
[preparation evidence](../evidence/2026-11-08-nfc-startup-preparation.json).

## Teardown fixes and independent r58 family

Preparation of a cold module load/unload trial exposes two defects in the
pinned driver: the I2C remove callback frees the NCI device before releasing
its threaded IRQ, although that handler reads the device and driver data;
the core holds `info_lock` across `nci_unregister_device()`, which can call
close/flush callbacks requiring that mutex. The isolated source branch now
releases/drains the IRQ first, runs unregister outside the mutex, then finalizes
cold mode under the mutex and unlocks before freeing NCI state. Existing
firmware-work handling is unchanged; concurrent firmware download is unqualified.

Two raw patches replay to the exact published source at
`3be72fe7a5fb16f74494023b134ce1f2654bff40`. Nine host tests execute actual C in
16 modes, including instrumented pending IRQ and unregister close/flush
callbacks. Restoring either old defect alone makes its regression fail. Both
patches pass strict style checks. These are instrumented callbacks, separate
from real IRQ concurrency or live NCI teardown qualification.

The complete 16-patch r58 source build uses the distinct
`6.18.59-fx0-nfc-teardown-alpine` release and a new certificate. The input changes
only LOCALVERSION from the prior NFC configuration; normalization has the same
19 compiler/capability differences. CFI, exact trust list, full compressed DWARF,
all 468 signatures and 25,562 imported CRCs verify. Both changed ARM objects
also compile with W=1 without warnings and match the full-build object bytes;
original command/object bytes and timestamps are restored afterward. All
577 dependency edges and 468 binary-index loader dry-runs pass. Its DTB and
`Module.symvers` match the prior NFC family, but release/certificate/module
identity remains separate and hardware acceptance does not transfer.

APK signatures, tamper rejection, offline ARMv7 resolution and isolated usermode
r56-to-r58 replacement pass. All 549 final payload files match the signed APK,
and old module-family payloads are removed. Scripts/hooks are disabled during
workspace extraction; actual phone update, autoload, boot and recovery are open.
The build uses a separate mounted home, preserving prior source builds, packages,
keys and the original unbooted moduleless startup image.

Do not use the old r56 NFC modules for the planned teardown trial. The preserved
startup image has no modules, so it cannot execute these driver remove paths;
it still provides no hardware result. Before exercising corrected modules,
prepare/qualify a matching r58 moduleless startup and native return, then a
separate bounded signed-module cold-registration/cleanup trial. See the
[source profile](../manifests/kernel-nfc-teardown.json),
[measured build manifest](../manifests/kernel-nfc-teardown-build.json) and
[fix/build evidence](../evidence/2026-11-08-nfc-teardown-source-package.json).

## Remaining hardware and distribution gates

The phone still runs the same original r50 boot/hash and conservative policy,
with zero taint, running startup, Sway and sensor proxy. QUP3 remains disabled
and no NFC modules are loaded. The prior exact-boot physical UI result remains
pending; no NFC RAM entry, GPIO/clock change, bus transaction, RF operation,
firmware download or nonvolatile programming occurred.

After the exact native-return UI gate, qualify moduleless startup and native
recovery for the corrected family. Use separate bounded signed-module trials
for cold ownership, balanced clock/GPIO cleanup and NCI reset/init responses.
Then test
tag reading, RF/protocol behavior, userspace integration, restart/error unwind,
suspend/wake and final distribution packaging. The maintained kernel NCI path
does not provide the vendor `/dev/pn547` userspace ABI. No native NFC hardware
function is accepted yet. See [preparation evidence](../evidence/2026-11-08-nfc-source-preparation.json).

## Corrected-family startup prepared

The owner confirms working display and touch on native r50 boot
`28db1c68-3b08-4a53-8e5a-3397b8315813`; its original boot hash, zero taint,
running systemd, Sway and sensor proxy are rechecked. The corrected r58
NFC family now has a separate moduleless RAM image and checker, passing 30
fixture cases including rejection of the older r56 release and marker.
Kernel/DTB bytes match the signed r58 APK; qualified init/USB/HTTP/BusyBox
and the independent 180-second return timer remain unchanged. The image
is unstaged and unbooted at this checkpoint. See [r58 startup details](../diagnostics/nfc-startup/teardown-startup.md)
and [preparation evidence](../evidence/2026-11-08-nfc-teardown-startup-preparation.json).

Fresh byte comparisons also correct an earlier audit count: each r56/r58
build has 21 changed source files matching its published commit. The old
field reported ELF symbol-string-table bytes. Original reports and all
linked artifact hashes are preserved; [the erratum](../evidence/2026-11-08-nfc-source-comparison-correction.json)
adds no runtime or hardware qualification.

## Corrected r58 moduleless startup and recovery pass

The corrected r58 family passes one moduleless RAM startup and timed return to
installed r50. Its original packed image first times out before BOOT; after
terminal transfer recovery and an owner-confirmed native boot, isolated XZ
preset-3 encoding preserves the exact runtime Image/ELF/notes/certificate/ABI.
The new image reads back exactly, the actual startup checker passes, and its
84-byte notes match the linked r58 build. Four CPUs, no modules and one unbound
PN547 client at QUP3 `1-0028` are observed. The timer returns at 181.610626 s,
with serial and 22 complete HTTP pairs. Original r50 hash, zero taint, 1.15 V
PMIC target, policy and UI services are restored; owner confirms display/touch
on boot `98ab64c6-01c6-4c1e-91a2-433fc3afc4cf`. See
[startup evidence](../evidence/2026-11-08-nfc-moduleless-startup.json).

The preceding intermediate native reboot also verifies the retained 512 MiB
eMMC pattern with direct reads, full pattern and hash checks, and no ext4
errors. Its exact synthetic files are archived/removed after the later RAM
return. This is warm-reboot persistence, with power-loss/endurance qualification
still open. See [storage evidence](../evidence/2026-11-08-emmc-cross-boot-persistence.json).

Signed module runtime checks, NFC GPIO/clock ownership/teardown, controller/RF/PM
and wider bringup remain open. Original build/package/image artifacts and the
protected root index are unchanged. The USB transport fault remains unresolved;
native systemd currently waits on time synchronization with no failed units.
