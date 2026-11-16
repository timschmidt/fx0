# Qualcomm NGD parent startup readiness

The parent now publishes readiness after its final initialization step and
replays a remembered UP only when both parent and child are ready. QMI,
PDR/SSR, child-probe replay and the worker enforce these independent lifetimes.
Parent cancellation closes its own admission before releasing providers or
disabling the IRQ, so a concurrent child binding cannot reopen startup. DOWN
after parent closure records state and leaves cleanup to child removal.

The maintainer series contains eleven patches on official base
6628e7d4c6b25c8d18f1345e3a20d21829aae7e4, including earlier ownership,
DMA, power-error and QMI fixes. The runtime patch applies this followup to
integration 22. All other runtime source paths are unchanged. Full source
identities and snapshot paths are pinned in source-topics.json.

## Qualification

The QMI/parent model executes 23 byte-exact driver/core callbacks. Its 71 cases
and 1,079 checks fail 51 checks on the immediate prior source and pass all on
the candidate. All 29 controls are rejected. Cases cover partial parent probe,
remembered UP/DOWN, errors, late QMI, child binding during cancellation,
queued and waiting workers, post-wait closure, endpoint serialization and
discovery rebind.

Power remains 626 cases per PM profile: 13,284 current-PM checks and 12,708
cached 6.18.63 PM checks. DMA setup remains 85/1,150; ownership 10/114;
bookkeeping 21/152. Their 37 controls are rejected, for 66 total. The redundant
historical interrupted-wait control is documented separately.

Eight native ARM/ARM64 objects build with LLVM21, W=1, strict callback
diagnostics and COMPILE_TEST disabled, without diagnostics. The incremental
runtime ARM kernel and 459 signed modules build, stage and pass ELF, CMS,
release and dependency checks. Module paths and twenty previously qualified
DTB hashes are preserved. No arch or binding source changed. The original
full build had inherited warnings; this does not establish a warning-free
kernel or a clean reproducible package build.

## Offline replay

Run `python3 -B replay.py /tmp/fx0-ngd-parent-replay-UNUSED` with clang-21,
Python, patch and sanitizer runtimes installed. Choose a nonexistent output
path outside this packet. Replay checks every manifest hash, applies twelve
patches without fuzz or offsets, compares candidate snapshots and prerequisite
baselines, then runs all models and 66 controls. Generated maintainer/runtime
models must be byte-identical. Git and Internet access are unnecessary.
Native kernel, full module, DTB and schema builds are not repeated by replay;
their separate receipts are included.

## Limits and remaining work

Wait queues, PM coordination, device/devres lifetime, QMI, IRQ/DMA and
workqueues are synthetic services. Callback bodies are extracted without
rewriting their logic; the controller layout and providers are modeled.
The concurrent binding hook executes the actual child probe at a forced
cancellation point; Linux device-core locks and that physical schedule are
not executed. Cancellation under the worker mutex is reported without
intentionally deadlocking. Logical allocation audits precede physical fixture
release. Normal LeakSanitizer and fail-fast ASan/UBSan remain enabled.

Master work and external transfer admission/quiescence, RX callback lifetime,
registered-client endpoint-generation recovery, complete failed-start and LTS
hard-error recovery, and initial DSP bootstrap remain unqualified. No physical
hardware, firmware, audio, network or phone acceptance is established. No
package installation, phone change or maintainer submission is performed.

Codex generated the followups, models and evidence. Genuine upstream metadata
and prior history remain intact. Human review and DCO remain pending; no agent
Signed-off-by is added. Source/model licenses are retained in LICENSES.
Private keys, boot images, firmware blobs, credentials and per-device data
are excluded.
