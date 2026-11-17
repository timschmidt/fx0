<!-- SPDX-License-Identifier: GPL-2.0-only -->
# Experimental MSM8226 system suspend: private review draft

The candidate coordinates CPR voltage and clock state, RPM receive IRQs,
MPM wake routing, secondary CPU collapse and CPU0/L2 collapse for the Fx0.
The normal board targets remain unchanged. The new suspend target is
experimental and has not been booted or physically qualified.

The pinned integration source is `fc5120c4e0f2ab4790cb62f1f4c40aea74697a18`,
tree `db872556b9b09289d09138209e0bb7674326300a`, based on runtime36
`192b0d581ac98b3d245df8ee8183dcdd4d7fb39c` and RPM admission prerequisite
`a96c6085b9cb90ff5f48489bf66867135dd360d7`. The three fixes and ten feature
patches retain their original author and AI attribution. A human must
review the changes and provide any Developer Certificate of Origin;
there is no AI Signed-off-by. Nothing in this packet has been sent.

## What has been checked

The committed-source replay passed 5,009 synthetic host cases and 85
behavioral controls with AddressSanitizer, UndefinedBehaviorSanitizer and
normal leak detection. Four retained clock programs also passed. Some
cases run real host threads, but this is not a kernel concurrency proof.
SCM, firmware, regulator responses, driver traversal and register banks
remain synthetic services. A compile failure, timeout or sanitizer fault
does not count as a successful behavioral control.

There are 48 valid native objects across ARM, ARM RT, ARM64 and ARM64 RT,
20 actual kernel Kconfig cases, 21 compiled DTBs and 12 negative binding
controls. All 20 prior DTBs are byte identical. Full unfiltered schema
validation is silent. The extra experimental DTB adds two occurrences
of the existing TSENS duplicate-address warning; no new unique DTC
diagnostic was introduced. The ARM64 RT profile initially omitted
EXPERT and did not actually enable RT. That result was invalidated;
the corrected profile verifies both EXPERT and PREEMPT_RT in `.config`.

The cached full build and a clean Git-free committed-source build both
produce the kernel and 459 modules. Both normal module installations
pass CMS signature, ELF32 ARM, release and dependency checks. They use
the same existing private development signing key through normal build
tools. The audit never reads, hashes or copies that key. This is not
an independently reproducible public signing recipe.

The first binary comparison differed because an unset build version
left a temporary `#` version string, versus fixed `#30`, as well as
different debug paths. After fixing the cached build's version, its
System.map and Module.symvers match the clean build exactly. Remaining
allocated differences are the kernel and embedded vDSO GNU build IDs;
debug information also differs. This is not byte-for-byte reproduction.
Two fresh builds with fixed version metadata and normalized debug paths
now match byte for byte: vmlinux, zImage, System.map, Module.symvers and
all 459 module files, including debug information and build IDs. Their
source and output directories differ; both use Git-free source exports
and deny Git during compilation. The existing development signing input
is held constant. This demonstrates controlled host-build reproduction,
not an independent public signing recipe or package/update acceptance.
Both normal installations also produce byte-identical signed module
files and all 14 dependency metadata files, with CMS, ELF32 ARM, release
and dependency checks passing for each. Build-directory symlinks are
excluded from the metadata comparison.

Checkpatch reports zero errors. Its retained advisories include new-file
MAINTAINERS reminders, long description lines and the existing
`mx_max_uV` field name. The new binding has a MAINTAINERS entry; other
paths fall under existing entries. The two RPMsg kernel-doc warnings
are inherited, with a saved before/after comparison.

## Offline replay

Use a pristine, Git-free export of the pinned source and a new output
directory. Python 3, clang-21, ASAN/UBSAN runtimes and POSIX threads are
required. LeakSanitizer must be permitted by the execution environment.
The runner verifies the pinned source and fixture hashes, constructs
its private workspace and disables Git on PATH:

```sh
python3 -B replay.py /path/to/exported-linux /path/to/new-results
```

This executes only synthetic host programs. It does not install
packages, contact a phone, run a codec, request Wi-Fi scans or request
network access. An externally enforced network sandbox may be added;
the runner itself is not a network security boundary. The Linux source
archive is intentionally excluded from this small review packet.

## Limits and remaining acceptance

The firmware/APC wake-voltage chain, physical CPU collapse, wake routes,
display and touch after collapse, motion-wake reliability, standby
current, false wakes, soak testing and final-image boot cycles remain
unqualified. The sleep-only APC vote retains the covering 1,337,500 uV
level. No lower sleep voltage or changed DATA0/VCTL protocol is claimed.

The candidate is based on experimental 7.4-rc1, not the maintained-LTS
acceptance target. Normal public-source packages, installed updates,
recovery and the final board target still require qualification. All
seven original bringup requirements remain in scope. The
independent SLIMbus hardware-stop, runtime-PM rollback, QMI endpoint
replacement and late transaction-ID recovery gaps remain open.

The MPM probe-unwind fix removes a stale genpd provider on error.
That stale provider can retain freed devres; no exploit has been
demonstrated. Human security classification is pending before deciding
how to report it. The other two fixes address an OF-node reference leak
and retryability after failed SMD channel registration. Retryability
means a later state-work pass may retry; no automatic retry timer was
added. Feature patches are not presented as stable fixes.

The owner has prohibited Replimat3 interaction and Wi-Fi scanning.
Public source downloads over the existing connection are permitted.
This review and qualification phase stays on the workstation and does
not access the phone, firmware, radios or audio hardware.

## Review dependencies

`dependencies.json` lists provider/API and earlier bringup dependencies for
each feature patch. The ten feature commits form an ordered integration
series. They are not ten independently buildable maintainer topic heads.
In particular, the RPM receive gate needs the new SMD IRQ API, CPR needs
the retained clock and sleep-voter prerequisites, and the coordinator
needs every provider plus the ARM hooks. Independent rebases and builds
remain pending. `routing/` contains unsent maintainer lookup output.

## Fixes on current maintainer bases

The public RPMsg `rpmsg-next` tip `55f8464acbac850d44493073cb516ae91173f495`
and IRQ `irq/core` tip `1aed0e209f0c3bb1f28d4d69c2fc23528d30981e`
were downloaded read-only. Their SMD/MPM files match the integration
pre-fix source byte for byte. The private fix branches contain only
the original two SMD changes and the MPM unwind change, respectively.
Original attribution and human DCO requirements remain explicit.

Focused models on those exact public bases run 34 release cases,
396 state-worker cases and 43 probe cases. They reproduce 17, 11 and
21 failed assertions before the fixes, respectively, and zero after.
They use synthetic reference acquisition, channel/device services and
registration fault injection; they do not demonstrate kernel races
or an exploit. These 473 cases are separate from the 5,009 integration
cases and are not added to the 85 behavioral-control count.

Both fixed drivers also compile as eight fresh native objects on their
own full maintainer source exports, across ARM/ARM64 normal/RT. Actual
EXPERT and PREEMPT_RT values are checked. These are object builds, not
full maintainer-base kernel links. Pinned public before/after files,
private branch metadata, patches, fixtures and evidence are under
`maintainer-fixes/`; the portable runner includes their focused replay.

The saved `evidence/executed-host-build-script.py` records the executed
host procedure and refers to private workspace build inputs. It is an
audit artifact, not a standalone public package recipe. The generic
experimental kernel config is included; signing keys are excluded.
