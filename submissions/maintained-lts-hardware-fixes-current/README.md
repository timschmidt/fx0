# Maintained-LTS hardware source fixes

Local, unpublished host qualification against the Fx0 6.18.63 integration.
The base is `2677746cc1d6b6ab4aa60dbb5c8ad926fb327568`; the qualified head is
`136e614f365c855c3897e4a96ac3b2bdede9feda`.

Three exact backports add the MDP5 right-pipe ownership checks, correct the
PMI632 vibrator upper-byte shift, and guard the optional IOMMU global address.
Original authors, dates and credits are preserved. The original unsigned
message revisions remain in an archive ref. The Assisted-by spelling now uses
the format requested by this LTS checkpatch. Human review and DCO remain pending.

The LTS already carries the cached-pipe ownership and encoder-flush fixes,
plus the preceding three vibrator range/clamp/masked-write fixes. The helper
comparisons and actual-source models establish their focused equivalence;
syntactic patch checks alone were not treated as proof. No duplicate source
changes were applied for these five existing fixes.

The new batch passes 13,806 positive cases: 1,258 ownership, 12,303 vibrator,
four optional-IOMMU, and 241 preserved encoder cases. Baseline display and
vibrator code fail 9,212 assertions. Eleven deliberately faulty variants fail
without sanitizer diagnostics. The two IOMMU original-helper reproducers
trigger the expected UBSan null-offset reports and are byte-equal to the
saved baseline helpers; they are not clean behavioral controls. Normal leak
sanitizer checks remain enabled. Production function bodies are extracted
unchanged. Only synthetic DRM/core declarations adapt the newer transaction
type name, and the existing LTS single-flush helper is included unchanged.

Six selected source objects compile in each of ARM normal, ARM64 normal and
ARM64 RT (18 objects), with W=1, no diagnostics and nonpermissive CFI verified
from actual resulting configs. ARM32 RT is unsupported and is not counted.
These are selected object builds, not a full MSM component link or kernel APK.
The build controller ran before the local source commits and its source hashes
match the committed bytes. The first encoder fixture omitted the LTS-only
single-flush helper; its failed compile is preserved in the local workspace.
The initial commit-message check failures are included as historical evidence;
the final three source patches pass strict checkpatch without exclusions beyond
the documented absence of human sign-off (`--no-signoff`).

Run the source models with a normal LeakSanitizer-capable environment:

```sh
python3 replay.py --source /path/to/qualified/linux --output /new/private/output
```

Requires Python 3 and clang-21. The output path must not exist. The source file
hashes are checked against the receipt before execution. The replay includes
all positive, baseline and negative model checks and records terminal cleanup.
`build-native.py` is the exact workspace controller used for the native checks;
its existing seed paths and LLVM toolchain are required for that separate step.

MMIO, DRM locks, PM, SMP, regmap and work services are modeled. Paired CTL paths,
concurrent DRM ioctls, physical scanout/resume and the original r2 fault remain
unqualified. The PMI632 upper-field fix does not exercise the Fx0 PM8226 legacy
one-register path. There was no phone, firmware, radio or audio access, Wi-Fi
scan, Replimat3 interaction, network configuration, publication or maintainer
contact. Source-only files and receipts are included; no compiled programs,
private keys, boot images or firmware are included.

Across both LTS batches, six backports and five existing equivalent changes
have focused qualification. Another 136 current-source commits still require
audit. Full maintained integration, normal public-source APK/update/recovery,
physical hardware and final reliability acceptance remain open. All seven
original bringup requirements remain in scope.

Source patches and verification code retain GPL-2.0-only notices and original
kernel attribution. Receipts describe test evidence and its limits.

The two published UB-reproducer log copies replace the workspace path and
remove trailing whitespace. Their original and transformed hashes and exact
transformations are recorded in `sanitized-log-provenance.json`; the raw local
logs remain preserved.
