# Self-contained Fx0 development rescue

This replaces only the second-stage script in a frozen native r3 initramfs.
The original first-stage wrapper establishes the temporary initial display
power holds. All 22 embedded modules remain byte-identical and signed for the
frozen r3 kernel; this environment never discovers, resizes or mounts the
installed root and never switches to it. Root UUID arguments are removed from
the rescue image/menu entry. The normal installation is not changed by a RAM
boot of this image.

Prepare the replacement as a newc archive containing executable
`init_2nd.sh`, append its deterministic gzip member to the verified r3 initramfs,
and assemble the image with the exact r3 kernel and Fx0 DTB. Validate all archive
members, module hashes, image headers and the measured lk2nd load-slot limit.
Keep complete images, actual command lines and UUIDs private. For a filesystem
entry, preserve the frozen kernel, DTB and initramfs together under a distinct
boot subdirectory and retain a managed extlinux menu. Never let a normal update
replace those frozen rescue files.

The script starts the embedded module/udev environment, sets internal eMMC
block devices read-only, and provides development root shells over USB serial
and USB-only telnet at the initramfs network address. There is no automatic
normal-OS continuation. Use `reboot -f` to return to lk2nd. The initial display
holds remain in force in this short-lived recovery environment. This fixture is
not a normal OS service or final charging/power-management policy.

The RAM test verifies zero disk filesystems mounted, all 42 exposed internal
eMMC block nodes read-only, taint 0 and matching raw boot/GPT readbacks. Host modem
probing corrupts the serial capture; the verified evidence uses independently
framed commands over the network console. Serial enumeration alone is not a
successful serial-shell qualification.

After the actual r4 package replaces persistent modules with a new signing key,
the saved filesystem entry boots this r3 rescue with taint 0 and no root mount.
A bounded repair first attaches userdata read-only, mounts only its boot
filesystem read-only and verifies the expected menu hash. It then lifts RO on
the enclosing eMMC/userdata block devices only, uses a fresh writable loop and
boot-only mount, restores the saved normal menu through a checked temporary file
and rename, syncs, unmounts, detaches and restores RO. All 42 nodes return to RO;
raw boot and both GPT fingerprints remain unchanged. This tests a real repair
without depending on the installed module tree. The installed root is not mounted.

The root/module package rollback and factory-stock restoration procedures are
still separate acceptance work. Final partition consolidation and raw-boot
updater qualification remain open; do not infer permission to skip their gates
from this successful development rescue.
