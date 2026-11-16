# Deferred wireless scan completion

Interface shutdown can leave a completion message blocking subsequent scan
requests when the driver still owns the cancelled request. Its eventual stale
completion only frees the request. This port queues the existing completion
worker when message delivery is deferred, preserving the current request
ownership and direct delivery paths.

`source-topics.json` pins two independent bases and endpoints. The one-patch
maintainer topic uses the freshly checked official wireless main branch. The
three-patch runtime topic also retains two existing upstream corrections in
the same file: rejected-BSS reference release and merged-profile length.
Runtime and maintainer scan source files match byte for byte. Every other
runtime path, board, binding and earlier feature remains unchanged.

Timothy Schmidt's original implementation, author timestamp and historical
Claude co-author credit are preserved in the evidence. This port, changelog
and qualification used OpenAI Codex assistance. The two upstream corrections
retain their original authors, author timestamps, messages and existing human
trailers. Codex added no sign-off. Human review/DCO remain pending; this local
draft has not been published or sent to maintainers.

The model executes four actual functions: request release, internal scan
completion, the work callback and driver completion. Thirty lifecycle cases
cover deferred/direct delivery, driver-owned/released and split requests,
both worker/late-callback orders, message allocation failure, empty state and
twenty repeated interface cycles. The original source fails 52 of 146 checks;
the candidate passes all 146, delivers 28 completion messages and releases
all 43 synthetic requests. Two deliberately broken controls fail 52 and 26
checks. Work scheduling, driver timing and messages are synthetic.

Native Qualcomm ARM and ARM64 builds compile eight core objects in total
with LLVM 21, W=1, strict callback diagnostics and COMPILE_TEST=n, with no
diagnostics. The integrated ARM kernel and 455 modules pass incremental
build and normal private module staging, including signatures, architecture,
release and dependency metadata. These are recorded build results, not a
clean reproducible package build or physical wireless acceptance.

Strict checkpatch uses only the UNKNOWN_COMMIT_ID exception: shallow local
history lacks the original Fixes object, whose exact ID and behavior were
verified through the official public commit API. No code/style warnings are
ignored. The preceding whole-kernel inherited warnings remain open.

Run the portable replay with Python 3, `patch`, `clang-21`, and its normal
sanitizer runtimes installed:

```sh
python3 -B replay.py /tmp/fx0-scan-completion-replay
```

The output directory must not exist. Replay verifies every artifact hash,
applies four patches with zero fuzz/offsets and compares complete file bytes,
then runs the lifecycle model and both controls with fail-fast ASAN/UBSAN and
normal leak detection. Native/kernel/module builds are not repeated. No Git,
network, phone, real wireless device, RF traffic, credentials or unit data
is required or accessed.

Physical wireless reliability, reconnect, suspend and repeated-boot acceptance
remain open. SLIMbus startup/lifecycle reconciliation, NFC source/RF work,
deep-PM RPM sleep-vote handoff and maintained-LTS public-source package,
installation/update/recovery qualification also remain open. The original r2
display/IOMMU fault is unresolved; this host draft does not complete bringup.
