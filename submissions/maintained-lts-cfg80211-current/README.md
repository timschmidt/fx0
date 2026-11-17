# Maintained LTS cfg80211 MBSSID and completion audit

Two exact source-delta ports release the caller reference when a rejected
nontransmitted BSS is unlinked and keep merged profile length as size_t.
Preserve Zhao Li's and Wahid Khan's authorship, dates, genuine upstream
trailers, notices and assistance disclosures. A separate Codex-authored
test commit exercises the actual kernel inform-BSS/cache/reference paths.

Nineteen new real-kernel KUnit case instances pass on an unregistered dummy
wiphy: eighteen profile lengths from 20 through 1536 bytes, plus a rejected-
reference test with sixteen reports. The index and final marker at the end
of long profiles must survive generation, and rejected children must leave
only the cache and caller references on their parent. Fourteen baseline cases
fail. A reference-only control fails thirteen profile cases; a length-only
control fails the reference test. The failing control cleans up the observed
lost reference afterward. The original 253-byte fixture accidentally made
an invalid one-byte continuation; the corrected fixture retains that boundary
with a valid minimum two-byte continuation. Exact failed inputs and receipts
are retained. This is no scan request or physical network observation.

The deferred completion repair is already in LTS. Four actual request-release,
completion and worker functions match the reviewed source byte for byte.
Thirty synthetic lifecycle cases pass, with two failing fault controls.
Workqueue scheduling, messages, ownership and driver timing are modeled;
full split-scan success, WEXT behavior and concurrency are not modeled.
Twelve native ARM, ARM64 and ARM64 RT objects pass W=1 and nonpermissive CFI,
including built-in/module and WEXT-on/off compilation; ELF checksums bind C.
All three kernel patches pass strict checkpatch with zero findings and no
ignored types. Human DCO and owner/security review remain pending.

Run `python3 -B replay.py --output /absolute/new/private/output` with clang-21
for three pinned actual-source lifecycle fixtures, with normal LSan and
fail-fast ASan/UBSan. The manifest is checked before execution. Real MBSSID
kernel results are archived separately. To rebuild those nineteen cases,
run `python3 -B replay-kunit.py --kernel-repository /path/to/kernel/git`
`--output /absolute/new/private/output`. It archives the exact committed
tracked source into an isolated tree before building, excluding ignored
private files and signing keys. LLVM 21 and the standard UML build dependencies
are required; no download is made by either replay. The kernel repository
must contain the source head in manifest.json.

UML has no host networking devices or host filesystem driver; modules and
private signing are disabled. Default public regulatory-certificate verification
is retained. An early post-check incorrectly rejected this public keyring and
is preserved as an unqualified attempt. A missing regulatory.db message stays
inside the isolated kernel; no host firmware data is read. Inherited UML
null-pointer-arithmetic and RWX linker warnings are retained; the native
production-architecture component builds have no diagnostics. These runs do
not qualify physical wireless, real driver concurrency or the complete stack.

No DTS/schema bytes change; retain the previous full nineteen-board schema
proof without a new run. The original inventory is now 72 ports (47 exact,
25 reconciled), 50 scoped existing equivalents, three newer API-only changes
inapplicable and 22 audits pending. The separate changes remain four local
IOMMU repairs, seven upstream runtime changes, two upstream prerequisites and
one qualification-test commit. The isolated failing baseline is a control,
never a production candidate. Complete current linking, paired reader/kernel
packaging, trusted normal APK/update/recovery, raw timing/IRQ constraints,
original r2 fault, final hardware matrices and all seven original requirements
remain open. Everything stays local/unpublished. No phone/SSH, Wi-Fi scan,
Replimat3 interaction, network change, private boot/signing/device data,
maintainer contact or new source download is included.
