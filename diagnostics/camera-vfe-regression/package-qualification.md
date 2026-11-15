# Normal r7 package qualification

Kernel `250e7412a5a15068b2a2fe32b57b66c300c91b5f` and recipe
`42b48f561ae26ed4bb95a4a5dd27ad6da50ffb16` produce
`linux-postmarketos-qcom-msm8226-6.18.63-r7.apk`. Two ordinary signed abuild
runs start from separate empty HOME/tmp directories with compile caching
disabled. Tools and retained normal signers are mounted read-only; preparation
and audits do not open, hash or copy private key bodies. The input config is
unchanged from r6. Its kernel release remains
`6.18.63-fx0-power-policy-alpine`; the package revision/build version changes.

Both builds finish with status zero. All 91,271 tracked source paths match
the pinned Git tree in each build. The 564 compared outputs, complete signed
APKs and signed repository indexes are byte-identical. The APK SHA256 is
`5b53d7b7b21605f248b33d9ae457b0cf31424563cf2d85ffd1b1c050f805dd28`.

The eleven ordinary audit stages pass: artifact and embedded-certificate
inspection; normalized configuration and full compressed DWARF5; all 464
module CMS signatures, 25,309 imported CRC checks and dependency closure;
linked-kernel/CFI checks; the power/USB source and DTB cohort; board schemas
and rejection controls; community configuration; independent APK/index RSA,
valid-format corruption controls and offline ARMv7 solver simulation. All
63 DTBs retain their expected inventory and the Fx0 board matches the
independently checked power/USB fixture.

The added CAMSS stage initially fails because its first checker assumes the
MOVW/MOVT constant sequence emitted by the earlier LLVM21 component build.
The normal Alpine LLVM22 build emits an A32 XOR-immediate chain. The original
failed attempt and eleven successful stages remain intact. A corrected,
separately pinned stage decodes the complete type-word load, XOR chain,
EQ branch, trap and same-target indirect call. All four dispatchers check
the new provider type `0xe8f4cf55`; both providers and all four guards survive
the complete packaged module. Allocated sections match the unstripped
module. Twenty controls reject changed immediates, branches, traps, call
targets and real old void-return callers. This is static consistency.

Kbuild emits no compiler warnings/errors. Build one emits one
`libfakeroot internal error: payload not recognized!` message during package
preparation, then completes. Build two has no such message. An additional
audit validates all 725 archive entries, numeric root ownership, exact
recipe modes, known PAX fields, timestamps and all 545 data-file checksums.
Membership, ownership, modes and PAX structure match both builds and the
retained r6 fixture. The message is retained; its original cause remains
unproven and build-tool follow-up remains open. A silent build is not claimed.

The source archive is a locally deterministic Git export with every body,
link target and executable mode verified. The final GitHub server archive
representation remains unpublished/unverified. A verified public-download
recipe needs approved source publication, an independent server fetch/tree
check, repinning and package requalification.

No new RAM image is assembled or staged, and no phone package, module or
boot changes. Module signatures and nonpermissive CFI match the input policy;
`CONFIG_MODULE_SIG_FORCE=n` still requires `module.sig_enforce=1` and a fresh
enforcement check on a future gated boot. The unchanged-r2 repeat/verified
return, distinct candidate operator gate, fresh boot identity and diagnostic
callsite inventory remain required. Camera DMA, SMP behavior, recovery and
the full bringup are unqualified by these host checks.

[Full sanitized artifact evidence](../../evidence/2026-11-15-camera-vfe-standard-package.json),
[archive metadata evidence](../../evidence/2026-11-15-camera-vfe-package-metadata.json),
[replayable CFI check](check_arm_cfi.py),
[CFI guard evidence](../../evidence/2026-11-15-camera-vfe-arm-cfi-encoding.json),
[maintainer-base draft](../../submissions/camss-gen1-coalesced-completion/README.md).

The public CFI entry accepts repeated `--object` and `--baseline-object`
arguments plus a new `--output` JSON path. Its default type words match this
candidate and baseline. Use `--guards-per-object 4` for the complete CAMSS
module payload. It intentionally recognizes the LLVM22 A32 guard encoding;
unsupported encodings fail, and a successful check does not prove runtime
CFI enforcement.
