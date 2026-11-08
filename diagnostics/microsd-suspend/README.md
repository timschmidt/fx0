# Fx0 microSD suspend trial

`check.py OUTPUT_DIRECTORY` is a bounded, root-only hardware trial for the
installed Fx0. It requires an unmounted FAT card at `/dev/mmcblk1p1`, verifies
that the parent reports SD, and refuses a failed read-only filesystem check.
It never formats or repairs the filesystem.

The trial creates a uniquely named directory, writes and fsyncs 64 MiB of
random data, and checks SHA256 after discarding that file's cached pages.
Three RTC suspend cycles use the installed hotspot coordinator and existing
phone-user doas permissions. Kernel trace proves real s2idle; each resume
must retain the payload hash, boot ID and zero taint. An unmount, read-only
FAT check, remount and fresh hash verify persistence. The owned file/directory
are removed, the card is unmounted, and a final read-only FAT check runs.

Run with USB SSH keepalives longer than the 12-second sleep and an idle/sleep
inhibitor to prevent unrelated automatic suspension. Explicit rtcwake bypasses
that inhibitor. The helper temporarily disables USB wake and selects s2idle,
then restores those settings and any still-future preexisting RTC alarm.
Audio and other suspend blockers are not exercised. Failure while the card
is unmounted leaves its test directory for diagnosis; inspect the result
before manually removing that directory. An unhandled kill or power failure
cannot run Python cleanup, so do not interrupt a live trial casually.

The helper targets this known device layout, not arbitrary removable media.
Original card contents are never selected for deletion or overwritten.

## Isolating card-detect activity

`phase_probe.py OUTPUT_DIRECTORY` uses a fresh owned 4 MiB file and samples
the known SD controller/CD interrupt counters every 50 ms around idle, mount,
buffered write, fsync, sync, cache-discarded read, deletion and unmount. It
requires an unmounted SD/FAT device, runs read-only filesystem checks, and
removes only its own directory. It neither changes pin/IRQ configuration nor
suspends the system. Current r49 evidence shows a GPIO37 CD interrupt burst
during fsync; reads and idle controls show no CD IRQ increments. This is a
diagnostic result, not a suspend fix. Source/IRQ numbering is device-specific.
