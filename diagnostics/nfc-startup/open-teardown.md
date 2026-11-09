# Open NCI teardown source correction

The r58 I2C remove path releases the IRQ before `nci_unregister_device()`.
For an open controller, unregister calls `nci_close_device()`, which sends
CORE_RESET and waits for a response. Without the IRQ, that request times out.
The close function discards the request result and returns zero, so successful
unregistration alone cannot prove that the reset completed.

The new source adds an optional `stop_rx` transport callback. Core removal
unregisters with receive available, invokes the callback outside `info_lock`,
then performs final cold-mode cleanup and frees NCI state. The I2C callback
drains/releases the IRQ only when its registration succeeded. This also keeps
the probe IRQ-error unwind from releasing an IRQ it does not own.

The [17-patch source profile](../../manifests/kernel-nfc-open-teardown.json)
replays to Linux commit `7bbe33bd97b6f57a05de33ce8dcceba6942352a3`.
The input configuration changes only LOCALVERSION from the frozen r58 input,
reserving `6.18.59-fx0-nfc-open-teardown-alpine` for an independent build.
At that source checkpoint, no kernel, signed module, APK or RAM image existed
for this family. A complete r59 kernel/module/APK build is now verified in the
[measured build manifest](../../manifests/kernel-nfc-open-teardown-build.json).
A matching moduleless RAM image is now
[prepared separately](r59-startup.md), with physical qualification still open.
The private `nxp_nci_phy_ops` layout changed: build all matching modules and
verify their ABI and signatures before any hardware use.

## Host verification

Run from the coordination repository with the source checkout at
`worktrees/linux-fx0-nfc-open-teardown`, or set
`FX0_NFC_OPEN_TEARDOWN_SOURCE` to its absolute path:

```sh
TMPDIR="$PWD/local/kernel-reconstruction/tmp" \
PYTHONDONTWRITEBYTECODE=1 CC=clang \
FX0_NFC_TEST_CFLAGS='-g -fsanitize=address,undefined -fno-omit-frame-pointer' \
python3 -m unittest discover -s tests -p test_nxp_nci_open_teardown.py -v
```

The test extracts sixteen actual Linux functions, five driver type declarations
and the actual transport callback table. It runs NXP open/close/send,
I2C probe/write/read/IRQ/remove, core remove and transport stop, plus NCI reset,
close, unregister, receive and reset-response parsing. Kernel services, bus
responses, queues, scheduling and completion waits are modeled. The successful
reset response follows the NCI 1.x parser branch; real elapsed timeout and NCI
2.x notification timing are not exercised.

Five tests cover ten cases: four open variants, cold removal with and without
a pending IRQ, serialized firmware-state completion, IRQ registration failure,
an optional callback and a deliberately missing reset response. The pending
thread runs during IRQ release while NCI state still exists; after close it
must see cold mode and avoid destroyed NCI queues. Address and undefined
behavior sanitizers pass.

The frozen r58 source passes the cold pending-IRQ case but fails the new open
case with one reset sent, zero acknowledged and one modeled timeout. Five
isolated defects are also detected: draining before reset, draining after
free, holding the mode mutex during drain, omitting callback wiring and
claiming an IRQ whose registration failed. The frozen r58 tests remain intact;
their simpler open test does not execute the NCI reset path.

Fresh ARM objects for core, I2C and firmware compile with Alpine Clang 22.1.3,
`W=1`, CFI and full compressed DWARF retained. These forensic objects use the
r58 normalized configuration in an isolated output directory and are not
loadable artifacts for the newly named profile. Strict checkpatch and both
incremental and complete profile replay pass. The first tool-environment
attempt failed because `/dev/null` was read-only; its logs/output are retained,
and the corrected isolated build passes without warnings.

## Physical qualification still required

Open removal, pending IRQ timing, concurrent firmware download and RF/PM
behavior remain unqualified on hardware. The existing r58 controller image
explicitly performs DEV_DOWN and verifies its reset response and cold state
before ordinary unload; it does not attempt open unregister. Its bytes and
the qualified cold lifecycle evidence remain frozen.

The current native-boot display/touch check remains pending separately from
the already-passed moduleless return. No phone boot or installation is part
of this source checkpoint. See the
[reviewed evidence](../../evidence/2026-11-08-nfc-open-teardown-source.json).

## Matching r59 package verified

The separate build produces `6.18.59-fx0-nfc-open-teardown-alpine` with a new
certificate and the exact published source bytes for all 22 changed files.
The actual normalized configuration passes the community checker and differs
from r58 only in LOCALVERSION. CFI, signing, schedutil and full compressed
DWARF remain enabled. All 468 modules pass explicit-certificate CMS checks
and 25,562 imported CRC comparisons. Dependency metadata has 391 direct and
577 transitive edges; all 468 binary-index loader dry-runs pass.

The only exported CRC change is `nxp_nci_probe`, from `0x487c4a66` to
`0xb0b785be`. The new I2C module rejects the r58 export map; altered imports
and wrong certificates are also rejected. APK signature and signed-metadata
tamper controls pass. An isolated r58-to-r59 usermode replacement, with hooks
disabled, verifies all 549 final payload files and removes the old module
family. This does not qualify phone installation, boot or update/recovery.

Two initial attempts stop before compilation on builder setup: missing cached
upstream metadata, then unavailable public indexes with networking disabled.
Their separate homes/controllers/logs remain intact. The third attempt uses a
fresh home, full pinned checkout and normal public dependency retrieval and
completes successfully. No new physical trial starts. See
[package evidence](../../evidence/2026-11-08-nfc-open-teardown-package.json).
