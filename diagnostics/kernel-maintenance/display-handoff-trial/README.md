# R5 display-handoff RAM trial preparation

These sources prepare a distinct diagnostic for the qualified
`6.18.63-fx0-handoff-trace-alpine` package. Its kernel source is
`de5568bfc81f221984b8e82519af9a15b00b5b6f`, recipe
`5126c3ea32047109b87bafbfa5e9588b7710902b`, signed APK SHA256
`20ccaf9bfc19132384d68b9b7770e0dff6e3d9ea2b1852fcda7e46644f660209`.
The 15 trace messages add no MDP/IOMMU register operations and preserve the
existing statement order. Logging can change timing. Neither a prepared image
nor a passing host package audit proves the earlier r2 reset cause or a fix.

The unchanged r2 repeat remains the first physical diagnostic step. R5 has
not been staged or booted. Any later R5 run needs its own reviewed controller,
specific current operator availability, fresh native baseline/staged-input
checks and independent return observation. The private preparation plan does
not authorize execution. Do not reuse the earlier r2 availability response,
the passive-r1 response, or a public repository approval.

The helper is the qualified public passive-r1 return implementation with only
release, token and deadline constants changed. It requires exactly
`fx0.native_trial=display-handoff-r5-01` and the R5 release. It arms an absolute
420-second BOOTTIME deadline before ordinary init. The harness rejects the
older r1 passive and r2 tokens, tests deadline/error/order behavior and checks
atomic marker creation. ARM/QEMU runs the harness and invalid-argument entry;
it never invokes an actual reboot. Two static Clang helper builds match and
use the same seven verified static link inputs from the authenticated public
userspace bootstrap roots.

The init prefix verifies the marker's PID, deadline and R5 token. The cleanup
hook checks all 478 candidate module files, copies the release tree into tmpfs,
checks it again and moves only the RAM mount over the native module search
path. The future stage is
`/var/lib/fx0-diagnostics/kernel-display-handoff-r5-01/candidate`.
Nothing has created that path on the phone. The timer/service live under
`/run/systemd/system` and request normal return at 360 seconds. Native installed
kernel/module files are not an overlay output.

The existing owner-approved initramfs remains private. Because R5 has a new
release name, its early archive requires 60 module-path changes, replacement
of all 19 early modules and all 14 corresponding metadata files. The
[newc transformation](../relabel_initramfs_modules.py) preserves every unrelated
record verbatim, and every changed record's metadata except name length and
body size. It rejects destination collisions, nonregular module entries,
hardlinked replacement files, incomplete/extra replacement rosters and
concatenated input archives. The original 243-entry archive plus the seven
record overlay yields 249 effective entries, retaining ordinary init.

Two private image assemblies match at 17,272,832 bytes, SHA256
`0669a11a5c9ad05dfccf6335993ffdbeead8cac3fa9edc3d681553be992ca19c`.
An independent parser checks all headers, records and load bounds; GNU cpio
compares all 33 changed regular files and seven added records. Four controls
run from the actual ARM image payload, and the systemd units pass verification.
Private image, initramfs, command line and raw audit files remain ignored local
artifacts. None is included in this source review.

Host fixtures test corruption/identity failure before an installed-tree mount
can be hidden. They substitute mounts, native device responses and reboot;
physical display, touch, automatic return and the complete bringup remain open.
