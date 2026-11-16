NGD descriptor and device ownership
===================================

The NGD descriptor belongs to the controller parent. A child driver unbind must
retain that descriptor for rebind and later parent removal. The parent now
manages descriptor allocation and holds a managed extra platform-device
reference. Normal platform-device unregister drops the initial reference, while
the managed reference keeps the device available through controller queue drain.
Parent IRQ shutdown happens before descriptor lifetime can end. Error paths
release the initial and extra references exactly once, including managed-action
registration failure. A child that never bound no longer owns parent cleanup.

Six patches are included on the advertised SLIMbus maintainer snapshot
6628e7d4c6b25c8d18f1345e3a20d21829aae7e4: earlier bookkeeping and parent
startup-work prerequisites, then these two ownership fixes. The runtime topic
adds only the two ownership patches to runtime17. Final driver bytes match.
Other platform descriptions and previously qualified hardware source are unchanged.

Qualification
-------------

* Ten ownership cases execute 114 checks using exact driver functions, the
  platform-device put/unregister wrappers, and the devres action-or-reset inline.
  The baseline fails 34 checks, IRQ shutdown leaves 31 separate ownership
  failures, and the final candidate has none. Cases cover bound/unbound/failed
  child probe, child-only unbind/rebind, an external device reference and
  descriptor/device/action/override/add allocation failures.
* Six independently broken variants are rejected, with 5, 18, 14, 15, 12 and 3
  failed checks: IRQ left enabled, unmanaged descriptor, child freeing parent
  data, leaked initial device reference, missing extra reference, and leaked
  initial reference on action-registration failure.
* Device refs, devres LIFO release, allocations, IRQ, PM, QMI, DMA and framework
  binding are synthetic services. Logical lifetime is audited while fixture
  allocations stay live, preventing execution of NULL/dangling accesses in the
  unchanged baseline. Fixture cleanup recovers simulated leaks only after the
  ownership audit. Normal LeakSanitizer and fail-fast ASan/UBSan check the host
  fixture; this does not execute the real kernel device/devres/IRQ machinery.
* The earlier parent-work pthread suite still passes 12 cases and 72 checks;
  the bookkeeping suite still passes 21 cases and 152 checks. Four and seven
  independent regression controls remain effective. The parent fixture only
  adds a modeled IRQ field and IRQ/platform-unregister leaf services; all
  extracted callback bodies remain intact.
* Eight native ARM/ARM64 NGD/core/messaging/stream objects build with LLVM 21,
  W=1 and strict callback diagnostics, with no warnings or errors. ARCH_QCOM is
  enabled, COMPILE_TEST disabled and native module dependencies retained.
* The integrated development ARM kernel and all 459 modules build. Normal private
  modules_install staging verifies every CMS signature, ELF32 ARM architecture,
  release and dependency entry. NFC and all prior source features remain. This
  incremental build does not prove clean reproducibility or final maintained-LTS
  package install, update, recovery or physical acceptance.
* Both new patches pass strict checkpatch without signoff checking. Shallow
  UNKNOWN_COMMIT_ID lookup is excluded; cached primary upstream commit metadata
  and original functions establish the Fixes target. Current MAINTAINERS routing
  is captured with historical Fixes lookup disabled. Nothing was sent.

Replay
------

Run `python3 -B replay.py /absolute/path/to/new-output` with Python 3, clang-21,
patch and pthread development support, outside a ptrace sandbox for normal leak
checking. All manifest hashes and eight patch applications are checked without
Git, fuzz or offsets. The IRQ-only prefix, three baseline/candidate suites and
all seventeen controls execute. Runtime and maintainer generated models must
match byte for byte. Native and full kernel/module/schema builds are not
repeated; their source-bound receipts and public configurations are included.

Remaining work and attribution
------------------------------

Resource identity across rebind is established at the modeled framework level.
Full child-only unbind/rebind operation still needs notification admission,
master-work and DMA transfer quiescence, late QMI arrival, completion handling,
repeated DOWN and power-up failure qualification. The original startup fallback
is not integrated. Physical bus, firmware concurrency and whole-device acceptance
remain open. No audio, firmware, phone or radio execution occurred.

OpenAI Codex implemented these fixes, changelogs, models, integration and packet.
Existing upstream authors and human trailers remain in source and Fixes evidence.
Human review and DCO certification are pending; no agent Signed-off-by was added.
This packet is unpublished and no maintainer contact occurred. Private keys,
credentials, boot images and per-device data are excluded.
