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
directory. This work does not produce a full linked kernel, MODPOST-checked
signed modules, source APK or boot image.

The phone still runs the same original r50 boot/hash and conservative policy,
with zero taint, running startup, Sway and sensor proxy. QUP3 remains disabled
and no NFC modules are loaded. The prior exact-boot physical UI result remains
pending; no NFC RAM entry, GPIO/clock change, bus transaction, RF operation,
firmware download or nonvolatile programming occurred.

Next build and verify a complete distinct kernel/module family, prepare a
bounded RAM trial after the native-return UI gate, and first qualify cold
ownership, balanced clock/GPIO cleanup and NCI reset/init responses. Then test
tag reading, RF/protocol behavior, userspace integration, restart/error unwind,
suspend/wake and final distribution packaging. The maintained kernel NCI path
does not provide the vendor `/dev/pn547` userspace ABI. No native NFC hardware
function is accepted yet. See [preparation evidence](../evidence/2026-11-08-nfc-source-preparation.json).
