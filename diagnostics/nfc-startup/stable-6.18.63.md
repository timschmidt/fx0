# NFC integration on Linux 6.18.63

The separate `6.18.63-r2` package combines the stable r50 baseline, the qualified
vibrator fixes, and the final r59 NFC source. It has passed the normal Alpine
source build and host audits. This exact kernel has not booted on the phone.
See the [manifest](../../manifests/kernel-nfc-6.18.63-alpine.json) and
[evidence](../../evidence/2026-11-11-nfc-stable-6.18.63.json).

The source branch is
[`integration/fx0-6.18.63-nfc`](https://github.com/timschmidt/fx0-linux/tree/integration/fx0-6.18.63-nfc),
commit `1ffffb2b0f3b323c1c619d01ae69655a28b5858d`. Six cherry-picks preserve
the original authors and record their original commits. The failed-probe IRQ
cleanup is already in stable as `9c5a037acdec408a7db4a85fbc78217109ee72e7`
(mainline `56345cea6a30dc7a1b036d5fb7900434b4a4c5e8`, Griffin Kroah-Hartman);
its patch is byte-identical to the earlier local fix and is not reapplied.
The final NFC/NCI files match r59, and the vibrator driver remains unchanged.
CPU/CPR experimental activation is still excluded.

The normal package recipe is
[`integration/fx0-nfc-6.18.63-package`](https://github.com/timschmidt/fx0-pmaports/tree/integration/fx0-nfc-6.18.63-package),
commit `7f382d74a0d3d002d7781701b05c320ba6a19cdb`. Its full build uses Alpine
Clang/LLD 22.1.3, a fresh build home and a new runtime module certificate.
All 91,269 compiled source paths match the published Git tree. CFI remains
nonpermissive, and full DWARF5 sections retain valid zlib compression.
All 468 signed modules match the embedded runtime certificate, their imported
symbol CRCs match the new kernel, and dependency metadata passes verification.
The signed APK passes offline ARMv7 resolution and rejects altered signed
recipe metadata. That resolution does not execute native update hooks.

The compiled DTB reproduces r59 exactly. Five binding tests cover the NXP NCI,
QUP I2C, TLMM and RPM clock schemas, production GPIO/clock wiring, negative
clock-pair/name/count cases, and unchanged conservative CPU OPP/domain wiring.
Twelve actual-C host tests cover 19 modeled clock and close/remove cases with
AddressSanitizer and UndefinedBehaviorSanitizer. The shared clock fixture also
passes seven tests against the earlier clock-only source. Six integration
commits pass strict checkpatch. The unchanged r59 negative-control fixture is
identified by its exact hash; its already-passed controls are not repeated.

Keep this kernel, DTB and complete module set together. The new
`nxp_nci_probe` CRC is `0x4752f140`, distinct from r58 `0x487c4a66` and r59
`0xb0b785be`. Their modules cannot be mixed. The I2C IRQ and firmware-work
callbacks retain ARM KCFI type words; weak cross-object type symbols need not
appear in every object. An initial supplementary audit assumed otherwise;
its corrected check examines the emitted type words without rebuilding or
altering compiled artifacts.

The installed phone remains r50/Sxmo r7. The owner's latest reply confirms the
earlier Linux 6.18.63-r1 RAM boot, whose confirmation is already recorded. It
does not confirm the current r50 return. The prepared r1 native installer
therefore remains pending that exact-boot physical UI result.

This is an integration checkpoint. Cold module lifecycle, physical NCI
open/close, RF operation, firmware concurrency, suspend and reliability remain
unqualified for this stable NFC package. The older moduleless r59 startup
result is not promoted to these claims. Current maintainer submission bases
and a final submission series remain separate work. No audio testing occurs.
