# Maintained LTS audio device-tree and dependency equivalence

The four original APR/core, SLIMbus/BAM, QDSP6 service and ASM front-end
descriptions are already present in maintained LTS. Ten common subtrees
match the frozen reviewed source byte for byte. Protocol/service constants
and zero-based ASM IDs 0, 1 and 2 match both headers and the driver's eight-
entry template. Common APR, BAM and NGD nodes remain disabled; the three
Madai board variants already enable them. No source or status is changed.
Original author Timothy Schmidt, Claude Opus 5.5 attribution, source notices
and Codex refresh disclosures remain in the archived original patches.

Nineteen compiled family DTBs preserve the register windows, interrupts,
remote BAM execution environment, channel counts, RX pipe 3/TX pipe 4,
APR domain/channel, service IDs and DAI/routing cells. Focused recursive
binding validation passes on seven relevant nodes per board. Six semantic
corruptions and six invalid binding inputs are rejected. The earlier full
nineteen-board schema proof is reused: all DTS, binding and constant-header
inputs remain unchanged since that build. No new full-schema run is claimed.
The original four patches also pass strict checks with no ignored types;
there is no new kernel patch in this audit.

Ninety native objects cover APR, QDSP6, ASoC machine/common glue, SMD/RPMSG,
remoteproc/PIL/MDT, QMI/PDR, SLIMbus and BAM across ARM, ARM64 and ARM64 RT.
Principal drivers have the requested built-in/module modes, W=1 has no
diagnostics, CFI stays nonpermissive, and ELF checksums bind C source bytes.
The initial mixed-mode attempt was rejected because the Qualcomm ASoC parent
menu remained at module mode; the accepted profiles select it explicitly.
No object is loaded, signed or installed. ARM32 RT remains unsupported.

Run `python3 -B replay.py --output /absolute/new/private/output` with the
dtschema environment recorded in evidence/schema-tooling.json. The manifest
is checked before execution. The source-block, compiled topology, focused
binding checks and twelve controls reproduce the exact accepted receipt.
The public processed schema and nineteen public-source DTBs are included.
Native objects and the prior complete schema build are archived evidence,
not rebuilt by this replay. Source property/compatible checks and compilation
do not establish driver behavior, DMA/IRQ lifetime, firmware, physical memory
address validity or functioning audio. No probe or audio operation executes.

The original inventory is now 72 ports (47 exact, 25 reconciled), 54 scoped
existing equivalents, three newer API-only changes inapplicable and eighteen
SLIMbus/BAM runtime audits pending. Four local IOMMU repairs, seven upstream
runtime changes, two upstream prerequisites and the cfg80211 test commit stay
separate. Current complete linking, trusted normal APK/update/recovery, raw
timestamp/IRQ constraints, original r2 fault and all seven bringup requirements
remain open. Human DCO and owner/security review are pending. Source and
review remain local/unpublished. No phone/SSH, firmware/audio/LED/NFC/radio
execution, Wi-Fi scan, Replimat3 interaction, network change, maintainer contact,
private boot/signing/device data or new public download is included.
