# Preserve the development recovery menu

Normal boot-deploy regeneration overwrites manually added extlinux entries.
For the current filesystem boot, the supported flag in `deviceinfo.fragment`
retains a managed menu while normal kernel/DTB/initramfs updates continue.

First back up `/etc/deviceinfo`, the complete boot filesystem, modules, exact old
kernel APK and raw boot/GPT fingerprints on both host filesystems. Construct and
verify the menu before disabling generation. The current default uses stable
`/vmlinuz`, `/initramfs` and `/qcom-msm8926-lg-madai.dtb` paths. The explicit
native16 rescue entry uses preserved files in its own subdirectory and a retained
distinct module release. Keep actual UUIDs and full command lines private.

Append the fragment to `/etc/deviceinfo` only after the menu exists. Source review
and the actual kernel update confirm DTB copying is independent of the generation
flag. Two supervised normal mkinitfs runs preserve menu bytes; a subsequent r3
kernel upgrade also preserves the menu and copies the different, expected DTB.
Verify native kernel/DTB/initramfs, load-slot fit, fallback files/modules and raw
boot/GPT readbacks after each update. Select and physically rehearse the fallback
before declaring recovery qualified.

Root UUID, command-line or file-path changes require an explicit menu update.
This policy is for the current development filesystem boot; final partition
consolidation and the offset-aware raw boot updater remain separate acceptance
work. No repartition is implied by this fixture.

The first physical rehearsal is recorded in
[recovery evidence](../../evidence/2026-10-29-native-recovery-rehearsal.json).
Native16 reaches systemd but does not reach SSH and returns to lk2nd. Treat that
entry as **unqualified**, despite intact files/modules. A RAM image assembled
from the exact r3 kernel/DTB/initramfs reaches SSH, permits restoring the original
menu bytes, and is followed by another installed-r3 boot. That rescue still uses
the existing matching root/module tree; independent rescue and factory-stock
restoration remain open.

A subsequent [standalone rescue](../standalone-rescue/README.md) removes that
root/module dependency. Its frozen r3 entry passes a normal filesystem boot
after the r4 module update, plus a bounded boot-only menu repair with no root
mount. See [the measured result](../../evidence/2026-10-30-standalone-rescue.json).
Package/root rollback and factory-stock restoration remain separate tests.
