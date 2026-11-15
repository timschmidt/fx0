# PM8226 PON and torch: unsigned current maintainer drafts

These drafts carry the existing Fx0 torch driver and PMIC descriptions onto
the recorded LED, MFD and Qualcomm maintainer bases. They also correct a
reproduced shutdown error in the carried driver. The existing integration's
[basic hardware evidence](../../evidence/2026-10-31-kernel-r9-r10-and-torch.json)
remains historical; these current-base drafts have host qualification.

| Route | Base | Local head | Patches |
| --- | --- | --- | --- |
| LED binding and driver | `for-leds-next` `4e88404a72e5e26720539e5555c383069cefb486` | `11be4e3efab2332b352187cfa13d67f1340d81da` | 2 |
| MFD parent binding | `for-mfd-next` `c92739a23a80f5f0a7c6f3c10aa792102d252ac4` | `64dde42de6c14287c91522602ab4737020db93d3` | 1 |
| Qualcomm PMIC DTS | qualified [WCNSS draft](../msm8226-wcnss-current/README.md) `c3bd956de3414d28aa8273e2a4c746134a4811d3` | `3c4dccb16e558b2100fdfb79cea0933cc8d223c7` | 2 |

The Qualcomm chain retains official ARM32 base
`ae2005cea2e4f84692268e54199bb03f5c6f4558`. Full source IDs, trees, original
commits, configurations and results are in [qualification.json](qualification.json).
Patch files and maintainer discovery are grouped by route. No maintainer
contact or publication occurred.

## Driver and binding dependencies

The driver preserves Timothy Schmidt's `cbfe7bb0e361` and Claude Opus 5.5
assistance. It supports the distinct type-0x18, subtype-1/2 register layout,
programs both current registers in 16 torch steps, and retains the optional
`vin` supply. Basic PM8226 torch operation was already demonstrated in the
older integration. Current-base physical operation, boost, flash strobe,
safety limits and charging interactions remain unqualified.

The source-extracted fixture reproduces five carried shutdown errors: early
register errors prevent remaining off operations, and regulator-disable
failure is ignored while the software reference is cleared. The refreshed
driver attempts the remaining off operations and clears the supply reference
only after successful disable. Healthy register sequencing is preserved.
This correction accompanies a new driver on the LED maintainer base; it is
not presented as a mainline regression with an invented Fixes tag.

The new first-generation LED binding preserves the existing compatible pair
and LED child layout. Its current limit is 12,500–200,000 microamps. A limit
need not be a multiple of a hardware step; the existing driver rounds the
programmed maximum down. The proposed narrow MAINTAINERS entry, including the
human submitter's name, remains subject to human review.

The PMIC parent previously sent every `led-controller` child to the later
flash binding. Direct validation of all 17 PM8226 boards reproduced that
missing dependency even with the new LED schema present. The separate MFD
patch selects exactly one of the two complete LED bindings. It preserves the
later binding's requirements; no diagnostic filter or generic permissive
child schema replaces them. The pristine parent schema, later LED binding
and common LED binding are byte-identical across the three inspected bases.
The LED schema must accompany the MFD change when it is merged.

The two DTS patches preserve Timothy/Claude's original PON label
`7e5f8f6b2250` and disabled flash controller from `cbfe7bb0e361`. The label
changes no PON properties. The original complete flash node, compatible pair,
address 0xd300 and disabled status are preserved; it follows the vibrator in
the current file's address order. Boards retain their own enablement and LED
descriptions.

## Qualification

Both native ARM and ARM64 complete torch component objects compile with LLVM
21, `W=1`, incompatible-function-pointer warnings treated as errors and
`COMPILE_TEST=n`. The compiled source roster is reverified against the final
commits. Only MAINTAINERS metadata changed after those builds. Exact configs
are in [configs](configs); signing key bodies and certificates are excluded.

The [host fixture](check-torch-errors.py) extracts the actual production
structure, constants and four register/brightness functions. Regmap, optional
regulator and sleep interfaces are emulated; concurrent callbacks use real
pthread mutexes. Under ASan/UBSan, the baseline fails all five off-error cases
and the combined on/cleanup-fault case. The correction passes those cases,
eight on-error controls, 32 healthy level/supply combinations and 400 concurrent
callback transactions. It checks reference preservation and a subsequent off
retry after regulator-disable failure. These checks exercise host interfaces,
not real PMIC fault injection.

Ordinary LED binding/examples pass on the LED base. The parent extension and
both complete LED binding/examples pass on the MFD base with the exact new
LED schema supplied as a temporary validation-only dependency. That borrowed
file is removed afterward; it is excluded from the MFD source commit.

The include graph finds 17 affected PM8226 boards. All 18 preceding Qualcomm
targets are built: the remaining Samsung S3ve3g board provides an unaffected
control. Their retained WCNSS baseline hashes are verified without rebuilding
that baseline. The same 56 existing DTC warnings remain, with none added.
Schema-typed phandle comparison preserves every existing node/property,
including PON and reserved memory. Only the 17 disabled torch nodes are added.
The unaffected board's DTB is byte-identical.

The original parent-schema rejection and its logs are retained. After adding
the exact MFD dependency, validation head
`fd6cf007ad8277756da9f5af3d9c21c93a6e8dfe` refreshes only schemas/examples.
All 18 actual-board DTB hashes and the config remain unchanged. Direct
validation then emits no targeted diagnostics. Ordinary checks include PON,
SPMI PMIC, both flash bindings and the previous WCNSS/camera/IOMMU dependencies.

Seven malformed copies of the complete ordinary enabled LED example produce
the expected diagnostics: wrong fallback, low/high current limits, missing
limit, missing LED, extra LED and extra register. PM8941-only, minimum-current
and non-multiple-limit positive cases pass. The [portable checker](check-PMIC-DTBs.py)
and [inventories](affected-PM8226-boards.json) are replayed from an independent
review checkout and a four-file source-only export. The exported sanitizer
fixture also passes against the final source.

Reproduce a native object with its matching config, `olddefconfig`,
`modules_prepare`, then `drivers/leds/flash/leds-qcom-flash-v1.o`, using the
recorded LLVM/W settings. Run the host fixture with `python3 check-torch-errors.py
--source KERNEL --output NEW_DIR --expect fixed`; it uses `clang-21`.
For DTB replay, pass the checker both inventories, baseline/candidate output
trees and logs, the final ordinary binding log, canonical DTS source head
`3c4dccb1`, and a fresh output directory. Use the kernel's dtschema environment.

## Remaining work and disclosure

The unchanged complete Fx0 board now has six unresolved labels, down from
eight. Its current-include compiler still fails on APR and the two immediate
SLIMbus labels; dependent QDSP6 references also remain. The
[dependency inventory](remaining-board-dependencies.json) preserves these
requirements and the original board hash. Existing audio descriptions remain
intact despite excluded audio testing. A complete current-base Fx0 DTB,
combined current kernel/package and physical acceptance remain open.

All five patches pass strict dependency-aware checkpatch with `--no-signoff`:
zero errors, warnings or checks. Full checks require only human Signed-off-by.
Kernel guidance forbids agents supplying that DCO certification. Earlier
metadata drafts, harness/config assumptions and the initial failed MFD
checkout are retained locally. This refresh and qualification used OpenAI
Codex, with original authorship and assistance credits preserved. Exact
publication approval and human review/DCO remain pending. No phone changes
or physical PMIC tests occurred for this qualification.
