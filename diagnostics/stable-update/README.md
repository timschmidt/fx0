# Supported stable userspace update preparation

This host-only plan uses the current r50/Sxmo r7 phone database and world,
with 775 installed packages. Four freshly downloaded supported v26.06/Alpine
v3.24 indexes have independently verified RSA signatures against the current
native public trust keys. An altered signed index stream is rejected. Local
APK catalog availability or a zero index-load status is not signature proof.

The [plan](plan.json) selects 30 upgrades, with no removals, installations or
downgrades. All ten exact signed-control holds and all eight Sxmo r7 packages
remain untouched. The [host solver](solver-context.json) is apk3.0.9; the phone
still runs apk3.0.8. Database and world stay byte-identical in the host simulation.
This does not execute the native solver or native installation hooks.

All [30 downloaded candidate APKs](verified-packages.json), totaling 15,903,143
bytes, match the authenticated index control checksums. Independent RSA checks,
current native public keys, signed compressed-data SHA256 and ordinary APK verify
pass. Valid-gzip altered control and valid-tar altered payload cases reject.
No package payload is installed or executed on the phone.

## Rollback preparation remains incomplete

[Twenty-one original APKs](verified-rollback-packages.json) match the exact
current installed control identities and pass signature/data checks, including
both corruption controls. Fourteen came from the phone cache, four from existing
host caches and three from supported repository URLs. The nine missing original
versions are listed in the plan; they include eight OpenSSH packages and
alpine-release. Do not treat the available subset as a complete rollback.

The [file plan](backup-scope.json) inventories 2,678 old owned files and 2,688
replacement files. A complete targeted file/config/database/script/trigger
backup and a fault-tested restoration are still required. File-backed recovery
for unavailable original APKs remains a possible approach, not a verified one.

Only openssh-server and libheif supply package control hooks in this set. Their
historical less-than version branches are false for the installed versions in
[host comparison checks](hook-condition-review.json). Fifteen installed trigger
rows were captured privately; their real execution remains unqualified. No
claim of unchanged services during a future transaction follows from this review.

The [fresh native postflight](native-postflight.json) retains r50 boot747e87fe,
original database/world/repositories, systemd running and taint0. No native
repository, index, key, package or boot is changed. The approved kernel r1 update
and a refreshed native baseline precede userspace activation. Phone updates and
GitHub publication already have standing approval; no further permission is
being requested. The current native-return physical UI check remains pending.
Audio testing is excluded, and full Fx0 bringup remains active.
