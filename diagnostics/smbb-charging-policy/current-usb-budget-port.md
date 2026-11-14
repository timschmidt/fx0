# USB budgets on the current power kernel source

The [manifest](../../manifests/usb-budget-current-kernel.json) pins the isolated
source and recipe. The three reviewed actuator, binding and gadget-budget patches
apply in order after managed foundation `83564de797cc`. Two additional USB schema
corrections fix the existing PHY tuple nesting and type the role-switch presence
flag. Those corrections leave runtime C, headers and board DTB bytes unchanged.
The [five-message series](../../patches/linux-integration/usb-budget-6.18.63-series.patch)
replays onto that foundation and reproduces all seven changed files.

The code requests a conservative 100 mA input budget before configuration and
caps accepted requests at 500 mA. A configuration request is held until successful
EP0 IN completion. Reset, disconnect and pullup loss return to the conservative
state; USB suspend requests zero. The managed charger keeps input available at
100 mA when a battery-absent suspend cannot be honored. Limits and suspend are
verified through register readback, with errors reported. These source behaviors
do not establish actual input current, USB timing compliance or physical safety.

## Qualified host checks

| Check | Result |
| --- | --- |
| ChipIdea callbacks | 59 cases pass for supplier acquisition/release, configuration completion/failure, reset/disconnect, work coalescing and suspend/resume. |
| SMBB input callbacks | 59 managed cases and 48 original-actuator compatibility cases pass. |
| Charging regression | 2,604 policy and 6,242 legacy cases pass; the 27 child-probe/PM/lifetime model cases and three rejected mutations also pass. |
| Runtime-source export | All five check programs pass from a 16-file export without ignored local programs. The two subsequent schema-only corrections preserve all exercised runtime sources. |
| ARM objects | Managed and legacy community profiles build ChipIdea core/UDC and SMBB objects. A separate minimal ARM profile builds ChipIdea with power-supply support actually disabled. Objects use Alpine Clang 22.1.3 and W=1 without driver warnings. |
| Feature guards | The budget-worker symbol appears in both power-supply-enabled objects and is absent from the disabled-profile object. Actual Kconfig output, not a command-line substitute, controls each build. |
| Current board and firmware | The DTB compiles and the retained firmware hooks generate its runtime profile and gate marker using simulated pack/PMIC inputs. |
| Binding contracts | Fourteen real processed-schema cases cover the PHY tuple, boolean role-switch flag, managed host/role-switch rejection and conflicting manual limit. The suite also passes from a three-file schema/DTB/program export. |
| Selected schemas | Corrected binding documents, reference closure and selected USB/charger/policy/battery nodes of the static and simulated runtime trees pass. Host-mode and manual-limit mutations produce the expected diagnostics. |

The two original attempts to disable power-supply support in the community seed
were rejected by configuration guards: HID drivers selected the subsystem again.
The successful feature-absence check uses a preserved, hash-verified minimal ARM
seed. The main candidate retains its HID options. No result from the two rejected
profiles counts as disabled-subsystem coverage.

The board DTB retains three W=1 warnings at unchanged eFuse/display definitions
in `qcom-msm8226.dtsi`; it is not described as warning-free. The selected schema
checks cover the power/USB paths, rather than every board binding. The callback
and lifetime fixtures use modeled hardware, work queues and device resources;
they do not execute real Linux driver-core removal, actual USB traffic or suspend.

The PHY correction describes the existing single TCSR phandle and its two fixed
arguments. The MSM parser and nine board descriptions agree on that ABI. The USB
role-switch correction describes the existing boolean flag. Malformed property
shapes and forbidden managed-budget combinations are tested directly against
the processed schemas. A false-schema diagnostic can omit the property name;
acceptance checks its actual error/value/schema and the independent contract suite.

## Normal package qualification

The new recipe is revision 6 with release
`6.18.63-fx0-power-policy-alpine`. Its only configuration changes from the
reproducible input are the unique release and built-in managed-policy option.
All 91,271 archived Git bodies, link targets and executable modes verify.
The checksum pins a local Git archive with deterministic gzip; a published
GitHub archive representation has not been verified for these unpublished heads.

Two normal offline abuild/Kbuild runs completed in separate empty workspaces.
Retained keys were read in place by the normal signers. The launcher and audits
did not inspect, hash or copy private-key bodies. All eleven host audit stages
passed, checking 91,271 source paths in each build and byte equality across 564
outputs, including 464 modules and all 63 DTBs. The signed APKs and repository
indexes are also byte-identical.

The audit verifies full compressed DWARF5, nonpermissive CFI, the embedded public
trust certificate, all module CMS signatures, 25,309 imported-symbol CRCs and
module dependency closure. Ordinary board checks and the 14-case USB/power
binding contract pass. The other 62 DTBs match the reproducible base; the Fx0
DTB matches the independently checked power/USB board fixture. Independent APK
and index RSA verification and valid-format metadata/payload corruption controls
pass, as does offline ARMv7 package resolution without installation or hooks.

The actual community configuration check passes with four inherited preferred
option notices. Normal builds have no compiler warning or error lines and retain
two abuild notices about `/lib` packaging and architecture detection. The native
OpenSSL root audit verifies 6,236 noncredential paths and 554 symlinks, retaining
the three known setup differences in abuild/account configuration. It excludes
credentials and does not query the phone's current trust store.

`CONFIG_MODULE_SIG_FORCE` remains disabled as in the retained input. A future
boot must supply `module.sig_enforce=1` and verify runtime enforcement. Signing
and host trust-list checks do not establish that runtime result.

This qualification uses the deterministic local archive pinned by recipe
`5b863dcb43f9eac6965b7b7f6160266d252b3712`. A public-download recipe still
requires publishing the reviewed source, independently fetching and verifying
the actual server archive against Git, repinning its representation and
requalifying the resulting recipe. The local checksum must not be presented as
a verified GitHub archive checksum.

[Full package evidence](../../evidence/2026-11-14-power-policy-standard-package.json)
records exact artifact hashes, build identity, module manifest digest and scope.
The [module file manifest](../../evidence/2026-11-14-power-policy-module-files.json)
contains all 478 packaged module and metadata file hashes.

No source or recipe is published by this work, and the phone is untouched.
The failed r2 physical-base gate remains open. The exact paired firmware gate,
real USB budget timing/current, battery measurements and BMS discrepancy,
charging completion, thermal protection, source loss, actual suspend, package
installation/recovery and full hardware/reliability acceptance remain required.

[Sanitized evidence](../../evidence/2026-11-14-usb-budget-current-kernel.json)
