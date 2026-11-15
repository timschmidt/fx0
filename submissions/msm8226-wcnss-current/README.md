# MSM8226 WCNSS: unsigned current maintainer drafts

These drafts restore the complete existing WCNSS description and its RF
dependencies on the recorded current maintainer bases. The regulator fix is
kept separate from new platform support.

| Route | Base | Local head | Patches |
| --- | --- | --- | --- |
| Remoteproc RF support | rproc-next `3035b6708f61259c93a368238e206dcec313e584` | `ac7727e0a7ee1da9ef085045f1e9eeddb8b38baf` | 2 |
| Remoteproc regulator fix | rproc-fixes `9db31edf92dde1f3c98008bd5f88e859d14324cc` | `962a507202bac5ecd7c7e37a77e0de32a122f598` | 1 |
| Wireless RF classification | wireless-next `5dbf2415ca9821a611d09308e3b29d2c37e7cd77` | `2dc038c6fa74e00ddb265b274103c46894c2541a` | 1 |
| Qualcomm ARM32 WCNSS DTS | preceding [display/GPU draft](../msm8226-display-gpu-dts-current/README.md) `6155789433f4c828677b67b9d47c22b2a8547aba`, on Qualcomm `ae2005cea2e4f84692268e54199bb03f5c6f4558` | `c3bd956de3414d28aa8273e2a4c746134a4811d3` | 1 |

The complete source IDs, trees, original authors and original commits are in
[qualification.json](qualification.json). Patch files and maintainer discovery
results are grouped by route. No maintainer has been contacted.

## Source changes and dependencies

The two RF patches retain Matti Lehtimäki's original binding and remoteproc
changes, `9587367f58f6` and `5519845f0bd8`. WCN3660A uses the existing WCN3680
power/XO data but keeps its own compatible. The wireless patch preserves
Matti's `3cc8fd9f5851`: WCN3660A belongs with WCN3660/B for RF classification.
It must not acquire WCN3680's unsupported VHT capability. Each runtime change
adds one match condition; current allocation and error handling are retained.

The regulator fix preserves Timothy Schmidt's original `61c60256c94a` and
Claude Opus 5.5 assistance. The existing count comparison selects only PD
regulators on Pronto v1/v2, omitting MX/PX or PX depending on attached domains.
Selecting by `num_pd_vregs` preserves the actual table split. The original
mainline introduction, `3dbc90b9c22ea96e37bf55f6011e63b5123ec668`, is verified
against its actual parent in the included [diff](Fixes-introduction.patch).
This is a regular regulator-selection bug. Its Fixes tag is not applied to
the separate new RF or platform descriptions.

The DTS patch retains Bartosz Dudziak's `c8d156a3bee3`, Matti Lehtimäki's
co-development and Timothy Schmidt/Claude's later `b2512c53f035` level-high DXE
interrupt correction. It adds the original reserved memory, SMP2P edge and
Pronto/SMD/control/Bluetooth/Wi-Fi nodes. Pronto and its control device remain
disabled until a board supplies its rails and configuration. The milletwifi
and memul deletion/recreation adapters preserve their existing smaller ranges.
The current `RPMPD_VDDCX` name replaces the older alias; other platform data
is retained.

Runtime use requires both RF match changes and the regulator fix. Validation
head `2a681d3c53cb7ae592d0b808d2a72bfdb655982e` imports only the exact separately
qualified IOMMU, CAMSS and WCN3660A schemas. The pristine WCNSS binding is
identical on the remoteproc and Qualcomm bases before that import. These
schema imports do not combine or qualify the runtime drivers.

## Qualification

All six native ARM/ARM64 component qualifications pass with LLVM 21, `W=1`,
incompatible-function-pointer warnings treated as errors and `COMPILE_TEST=n`:
three composite remoteproc objects per configuration and eight wireless
objects per configuration, 28 verified objects in total. The regulator final
metadata amendment has the identical compiled tree. Exact configurations are
in [configs](configs); no signing key bodies or generated certificates are
included. Reproduce a component with its matching config, `olddefconfig`,
`modules_prepare`, then `drivers/remoteproc/qcom_wcnss_pil.o` or
`drivers/net/wireless/ath/wcn36xx/wcn36xx.o`.

The [regulator fixture](check-regulators.py) extracts the production helper,
all four production data tables and the production regulator structure. Host
allocation/regulator interfaces are emulated; expected names and voltages are
independent. Under ASan/UBSan, the fixture shows six incorrect selections in
eight valid baseline cases; the fix passes all eight. Each run also passes 16 allocation/get-error
controls. The source-only export repeats the fixed qualification successfully.

Ordinary kernel RF binding/examples pass on the remoteproc base. On the
schema-only Qualcomm validation checkout, WCNSS PIL, control, SMD edge, SMP2P,
reserved-memory and previous camera/IOMMU/GPU binding/examples pass. All 18
actual affected board DTBs build. Their retained display/GPU baseline hashes
are reverified without rebuilding it. The same 56 existing DTC warnings remain,
with none added; targeted direct validation emits no diagnostics.

The [portable checker](check-WCNSS-DTBs.py) compares schema-typed phandle
references, including argument cells and null slots. Every existing node and
property is preserved. All five pre-existing WCNSS ranges remain exact; the
other 13 boards gain the original 10 MiB region. Actual reserved-memory
overlap sets are unchanged, and no WCNSS region overlaps another active
reservation. The earlier hypothetical default-envelope inventory was not a
reproduced overlap bug.

Independent platform checks verify the SMEM pair 451/431, endpoint IDs,
doorbells 18/17, register blocks, interrupt tuples, power domain, stop signal,
RF identity and Wi-Fi state bits. Five malformed actual-Falcon DTBs produce
the expected property/schema diagnostics. Six further decoded controls reject
wrong Wi-Fi triggers, SMEM order, doorbell, remote PID, RF identity and an
overlapping reservation. WCN3660A also passes in the complete enabled ordinary
upstream RF binding example. This schema example does not enable a physical
board. Clean-review and three-file source-only checker replays both pass.

For a DTB replay, run the checker with `--inventory affected-boards.json`,
`--baseline-build` and `--candidate-build` pointing at the recorded output
trees, their `--baseline-log`/`--candidate-log`, the ordinary `--binding-log`,
`--source` pointing at source head `c3bd956d`, and a fresh `--output` directory.
Use the same dtschema environment as the kernel checks. For the sanitizer
fixture, run `python3 check-regulators.py --source KERNEL --output NEW_DIR
--expect fixed`; the expected compiler is `clang-21`.

## Remaining work and disclosure

The unchanged complete Fx0 board now has eight unresolved prerequisite labels,
down from nine. Its current-include compile still fails on the five immediate
PON/flash/APR/SLIMbus labels. The [dependency inventory](remaining-board-dependencies.json)
preserves those requirements and the original board hash. Audio testing is
excluded, while the existing board's audio descriptions remain intact. No
complete current-base Fx0 DTB, combined runtime kernel/package or hardware
acceptance is claimed.

All five patches pass strict dependency-aware checkpatch with `--no-signoff`:
zero errors, warnings or checks. DTS checkpatch without its RF binding reports
the expected undocumented-compatible warning. Full checks require only human
Signed-off-by. Kernel guidance forbids agent-added DCO certification. The older
regulator-fixes base additionally requires `Assisted-by: LLM`, present in its
final metadata. This refresh and qualification used OpenAI Codex; original
authorship and assistance credits are preserved. Human review/DCO and exact
publication approval remain pending.

Earlier failed harness/config attempts and their corrections are recorded in
qualification evidence; their results were preserved. No new native rebuild
was used to replace the already successful wireless compile when correcting
its eight-object verification. No phone access occurred for these WCNSS
checks. The separate physical r2 startup investigation remains open.
