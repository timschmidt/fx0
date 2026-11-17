# Maintained LTS panel and touch sequencing

The existing tree already has the Madai compatible, safe system-suspend return
and reset GPIO support. Four attributed reconciliations carry the missing I2C
panel-reference constraints/example and the touch/runtime and panel-cleanup
fixes. LTS APIs, the compatible enum, board data and exact DSI command/wait bytes
are preserved. Original authors, dates, source notices and credits are retained.

Before/after actual-source host models reproduce 16/0 broken touch interleavings
out of 34 and 8/0 broken panel cleanup cases out of 16. Two touch callback and two
panel cleanup regressions fail their intended runtime contracts. Eighteen DSI
trace/error cases per variant match the production tables for baseline and
candidate; three command/wait/order regressions are detected. Normal LSan and
fail-fast ASan/UBSan run throughout. Selected real DRM/regulator functions are
extracted, with low-level I/O and schedules mocked; the full driver core is not
executed. Current RMI does not enable runtime PM; these schedules are synthetic.
Touch regulator-disable failure recovery, coupled/late regulator failures and
physical panel/touch/timing acceptance remain open.

Eleven native objects pass without diagnostics with nonpermissive CFI in ARM
built-in, ARM64 modular, ARM64 RT modular and ARM DRM-disabled configurations.
ELF source checksums match all current source bodies. DRM-disabled objects lack
the panel callbacks. All 19 previous maintained-family/control DTBs remain
byte-identical and pass the full new processed schema. Three ordinary binding
gates and 25 positive/negative binding cases pass. Four metadata/source patches
pass strict checkpatch with no ignored types; human DCO/review remain pending.

Run `python3 -B replay.py --output /absolute/new/private/output` with clang-21.
The manifest is checked before source re-extraction, and all nine generated
fixtures must match the qualified bytes. Only selected host models run; no Git,
network, phone, radio, USB device or actual display/touch hardware is accessed.
Native ELF receipts and binding logs are archived evidence, not replayed builds.

This packet is local and unpublished. Complete maintained linking, normal trusted
public-source APK/update/recovery, all seven bringup requirements, final-image
boot/suspend matrices and hardware acceptance remain open. The original r2
display/IOMMU failure has not been proven fixed physically. No Wi-Fi scan,
Replimat3 interaction, network change, phone action or maintainer contact occurred.
