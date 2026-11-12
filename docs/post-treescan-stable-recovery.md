# Stable userspace recovery after treescan r1

The installed kernel remains Linux 6.18.63-r1, with treescan 0.1-r1, Sxmo r7 and UPower r5 on the accepted boot. This checkpoint rehearses the next 30 stable package updates in a private filesystem on the actual ARM phone. It does not install those updates on the live OS.

A fresh capture replaces stale kernel and treescan state in earlier recovery plans. Both real APK lock types remain held throughout capture. The lock file is hashed through the held descriptor, preserving the POSIX lock. The capture contains 7,002 paths and 701 directory memberships, including nanosecond timestamps, 254 hardlink aliases and 1,480 SELinux labels. Five private recovery files have verified copies on both host and phone. Runtime private keys are excluded.

All four current repository indexes and 30 candidate archives pass independent signature checks using the phone's existing public trust keys. Altered control and payload streams are rejected. Native APK 3.0.8 verifies every candidate archive and selects exactly the same 30 upgrades as the isolated host solver. The kernel, treescan, local checksum holds and Sxmo packages remain protected.

The native rehearsal runs normal APK hooks in a private network and device namespace, with the live filesystem read-only. It covers a successful upgrade and one OpenSSH post-upgrade execution failure injected before the hook body. Both cases commit the 30 candidate package identities, preserve the other 745 identities and then recover the original 775 identities, world file, all captured metadata and the independently checked 545-entry unit inventory. The upgraded APK 3.0.9 and restored APK 3.0.8 both run natively. Recovery begins only after the owned package process and descendants have exited.

A retained executor inserted by the harness is explicitly labelled synthetic. Only a known signed script body may be removed; the rehearsal does not claim that APK itself retained that file. It also does not qualify a running hook failure, abrupt power loss or the stop-signal matrix.

The retained signed old-version APKs cover 21 of the 30 packages. They match the current installed identities and pass fresh signature, payload and tamper checks. Complete recovery therefore depends on the captured files; availability of all 30 old APKs is not claimed.

A read-only draft maps 2,824 old or candidate package-owned paths and all 18 candidate configuration sidecars under `/etc`. Native protected-path rules, shared directory metadata, configuration handling and a separate constrained live transaction controller still need qualification. The generic file restoration helper continues to refuse the live root. The private fixture is retained for that next qualification, with no owned process left running.

Independent postflight checks verify the installed kernel payloads, boot bytes, signature enforcement, services, gesture daemon and installed treescan timestamps. The display and touch confirmation already supplied for this unchanged boot remains applicable. No reboot, live package update or audio test occurs in this checkpoint. Full hardware bringup remains open.
