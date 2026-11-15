# Current Fx0 board identity and touch integration

This review carries the existing LG Fx0 identity entry onto Qualcomm's current
`for-next` binding and combines it with the qualified RMI panel/reset/suspend
changes and the current power/USB/IIO stack. The full Fx0 board remains intact.

The standalone one-line binding proposal is
`51d9fd646b0a71a795c31c9903aec8e6e1d0610f`, based on Qualcomm `for-next`
`6a876df4686788cd39128b62d7fcbff62f39278f`. It preserves Timothy Schmidt's
original author/date from local proposal `933d3593e3abf43752e0d7f858a0d9b98cb06744`.
Ordinary Kbuild binding validation, 19 complete board positives, two inherited
parent-schema controls and eight malformed string identity controls pass.
A non-string compatible does not select the filtered board schema reliably;
its root type rejection is checked separately with the unfiltered validator.
The other unfiltered diagnostics from that malformed fixture are not counted.

The integration head is `2223cefc134cca099f3c9fb5470ed58b6057ca38`, on
`38b038c9742e288153e1dea553c0317233a80206`. Its five new patches are the identity
entry and the four-patch Input proposal at `75f0dd5b051c1b1cda53eb84726b3cb13e6a8552`.
Their originals and applied IDs are pinned in validation/source-assembly.json.
The Input patches and attribution are in the parent RMI review directory.
Only the RMI transport, its Kconfig and binding, and the QCOM root binding
change. The integration base's existing devm_kzalloc probe call is retained;
Input next uses devm_kzalloc_obj. All other transport bytes match that proposal.

ARM with built-in DRM produces 30 component objects, ARM64 with modular DRM
produces 28, and an additional DRM-disabled RMI build produces 11. These are
native Qualcomm configurations, LLVM 21, W=1 and COMPILE_TEST disabled. Their
69 object hashes and exact configurations are included. No full kernel link,
package build or physical boot of this source was performed.

All 19 ordinary platform DTBs match the prior APR/power results byte for byte,
including the unchanged complete Fx0 board. The 58 inherited DTC warnings
are unchanged. Selected binding examples and board/RMI malformed controls
pass. Full unfiltered validation still reports unmatched bindings for the
panel, both cameras and raw QFPROM, listed in validation/full-Fx0-unfiltered.txt.
No hardware or audio descriptions were removed to obtain these results.

The RMI callback extractor passes all 34 synthetic panel/PM sequencing cases
with ASan/UBSan. Its executable fixture bytes equal the previously qualified
adaptation after that export's explanatory attribution header. The fixture
uses mocked IRQ, regulator and function I/O and successful rail disable. It
does not execute the real driver core, DRM, devres or PM core. Runtime PM is
not enabled by the current driver. Real concurrent/disable-failure behavior
and physical touch/panel sequencing remain unqualified.

The exported check-board-binding.py takes a processed schema, its original
parent YAML, a directory of the 19 prebuilt DTBs, the included DTB-results.json
manifest, and a fresh output path. It accesses no Git repository, phone or
network. Rebuild the standalone schema with the identity patch on its recorded
Qualcomm base and ordinary `make dt_binding_check DT_SCHEMA_FILES=arm/qcom.yaml`.
The root schema snapshots here preserve those exact before/after bytes.
The full combined DTBs come from the recorded integration checkout, the exact
ARM configuration and ordinary Kbuild. The parent APR review describes the
complete board/schema imports; the parent power review covers both connected
software chains. These are host qualifications with distinct scopes.

Original RMI reset authorship and Roman Vivchar's existing human sign-off are
preserved, along with prior Claude and Codex assistance disclosures. Codex:GPT-6
assisted this integration and review. No agent Signed-off-by was added. Human
kernel DCO remains pending. Kernel-source licenses and attribution apply to
the extracted fixture; see NOTICE and LICENSE.GPL-2.0 and the parent RMI review.

Nothing here publishes source or contacts maintainers. This work preserves
the remaining original physical, camera integrity, power/current/SOC/thermal,
suspend, reliability, update/recovery and public-download reproducibility
requirements. The separate unchanged-r2 RAM repeat used a different kernel image;
it does not qualify this mainline source or prove the original r2 fault fixed.

For a Git-free callback replay with Clang and working ASan/UBSan runtimes:

```sh
clang-21 -std=c11 -O1 -g -Wall -Wextra -Werror -fsanitize=address,undefined fixtures/RMI-panel-combined.c -o /tmp/fx0-RMI-panel-check
/tmp/fx0-RMI-panel-check
```

The expected result is `cases=34 broken=0`. For the board replay, use Python
from a dtschema environment with `dt-validate` beside that interpreter and
supply the exact prebuilt board-subsystem schema and 19 DTBs:

```sh
python3 -B check-board-binding.py --schema /path/to/processed-schema.json --before-schema source/before-qcom.yaml --dtb-directory /path/to/arch/arm/boot/dts --manifest validation/DTB-results.json --output /tmp/fx0-board-identity-check
```

Use fresh output paths. The 19 unchanged complete DTBs, eight malformed string
lists and separately checked unfiltered type control must produce the recorded
results. `files.json` pins every export file except that manifest itself.
