# Managed charging foundation on Linux 6.18.63

The isolated kernel branch in the [manifest](../../manifests/managed-charging-6.18.63.json)
ports seven preserved charger/control/policy commits onto the voltage prerequisite
`e0e89468dcfc`. The driver and policy header match the authenticated prototype
source. Applying patches preserves the newer board's unrelated changes. The
paired firmware is exactly `2ce757408f36`; its pack selector, early inhibition
and bounded SPMI source match the preserved checkpoint. Neither is installed
by this work.

The [seven-message source series](../../patches/linux-integration/managed-charging-6.18.63-series.patch)
replays onto the voltage prerequisite and reproduces the tested files. All source
and review commits remain local. The reproducible kernel foundation `e7c72f8c`
still lacks physical acceptance after its failed r2 trial; this port does not
replace that unchanged-repeat gate or qualify a newer boot candidate.

## Host qualification

| Check | Result |
| --- | --- |
| LG model comparison | All 83 stock thermistor points and 21,496 conversion/transition cases pass. |
| Charger/control callbacks | 2,604 policy worker, actuator, fault, stale-data, PM and handoff cases plus 6,242 legacy cases pass, including the existing concurrent-request cases. |
| Child probe and lifetime model | 27 new cases execute the actual child-probe, suspend/resume, shutdown and managed-stop callbacks against modeled IIO/devres APIs. |
| Lifecycle negative controls | Missing cleanup registration, lost resume restrictions and unknown-profile acceptance each fail their contract assertion. |
| Firmware profile and gate | 41 identity/FDT rollback cases and 307 gate/FDT/SPMI rollback cases pass. |
| Firmware SPMI | 1,024 transfer/delay/error cases for each core variant pass. |
| Firmware battery data | 128 selector/FDT/atomic-failure cases and all 155 vendor OCV entries, five temperatures and 31 percentages match. |
| Source-only reproduction | All seven fixture programs pass from a 30-file export containing no ignored local program tree. The first export omitted two SPMI headers and is retained as a failed preparation attempt. |
| Actual Kconfig and ARM | Fresh managed and legacy Kconfig output trees build the complete charger object with W=1 and no warnings. The policy-probe symbol appears only in the managed object. |
| Current board DTB and firmware hooks | The DTB compiles. Actual firmware hooks generate the profile, monitored-battery reference and inhibition marker in either hook order, using simulated pack/PMIC inputs. Critical charger properties match between orders. |
| Selected schemas | Both experimental binding documents and the charger/policy/battery nodes of the static and generated runtime DTBs pass DT-schema 2026.9. Unknown-profile and wrong-channel-name DTBs produce the expected diagnostics. This does not validate every board binding. |

The ARM build uses the retained previously audited Alpine Clang 22.1.3 toolchain
and read-only source/tool mounts. Fresh Kconfig resolution enables the built-in
policy with its real dependencies; no command-line substitute defines the policy
configuration. No module or APK signing occurs. The first build stops because
the compiler's temporary directory is read-only. Its corrected fresh attempt
sets a writable directory and passes; original inputs remain unchanged.

The board's W=1 DT compiler emits three warnings at unchanged eFuse and display
definitions in `qcom-msm8226.dtsi`. Those source bytes match the base. These
warnings remain recorded; the complete DTB is not described as warning-free.

## What the lifetime fixture proves

The fixture rejects missing/unknown profile data, incompatible battery metadata,
unavailable or mismatched suppliers, failed link creation, channel-type errors
and cleanup-registration failure. It checks that queued work is stopped before
modeled IIO resource release; resume keeps restrictions until a fresh sample;
failed sampling and suspend errors retain inhibition; and the pack-loss vote
survives a successful child probe/sample. Debugfs absence does not prevent the
policy from operating. Three modeled bind/cleanup cycles preserve resource order.

It compiles actual callback bodies, reusing only the existing control fixture's
source-generation prefix and mock hardware plumbing. It does not execute Linux
driver-core/devres internals, real supplier removal, concurrent kernel work,
actual system suspend or PMIC hardware. Automatic supplier reprobe is not claimed.
Run it with the existing checks from the [main README](README.md):

```sh
python3 diagnostics/smbb-charging-policy/check-lifetime.py "$FX0_LINUX" --negative-controls
```

Use Clang with ASan/UBSan and real libfdt development files for the paired firmware
checks, outside a tracing wrapper. The manifest pins the schema dependencies.

## Remaining deployment and physical work

The source retains runtime pack selection, verified inhibition and conservative
temperature-comparator requirements. The profile identifies a boot-time stock
pack selection; it does not authenticate pack silicon. No unconditional removable-
pack model or wider comparator window is added. Persistent bus failures and a
stalled CPU can still prevent software verification or timely inhibition; this
host qualification does not replace hardware protection tests.

The USB input actuator/gadget-budget patches still need an ordered port onto this
foundation. The BMS/live-versus-background current discrepancy, calibration,
counter/SOC behavior and telemetry lifetime remain separate unfinished work.
Complete normal signed combined packaging, firmware integration, physical RAM
boot/return, installation/recovery, sensor accuracy, charge-current/completion,
thermal boundaries, source loss, USB budgets, actual suspend and reliability
qualification before considering deployment. All existing operator and
publication gates remain separate. This pass makes no phone access, image
assembly, package update, charging/clock write or maintainer contact.

[Sanitized host evidence](../../evidence/2026-11-14-managed-charging-current-kernel.json)
