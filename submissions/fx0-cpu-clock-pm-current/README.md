# MSM8226 clock and MSM8926 CPU domain review

This local draft ports the complete qualified CPU clock, CPR domain and CPUfreq
changes to the respective freshly checked clock, PM and ARM CPUfreq maintainer
bases. Eleven attributed commits are exported as four independent topics.
`source-topics.json` pins every base, endpoint, author, date and changed path.
The runtime topic carries only five allocator API conversions from Kees Cook's
upstream commit `4dd10fbbeb9c33709edc89916e19c03c780a0751`; the entire existing
board, binding and feature trees remain unchanged. Timothy Schmidt's original
authorship and dates are retained for the feature ports. Codex performed the
ports, integration and qualification. Human DCO review and sign-off remain
pending. Nothing in this packet has been submitted to maintainers or published.

The clock topic retains the current typed allocation APIs. Its native ARM build
includes GCC_MSM8974; ARM64 does not enable that ARM-only driver. The PM topic
includes the legacy SCM fuse API prerequisite, ownership, bindings, calibration
and rail helpers, the domain implementation and coupled CPUfreq support. The
flexible `fuse_corners[]` member remains last and uses the current kernel flexible
allocator. All seven PM commits were rewrapped after initial qualification;
`PM-message-only-rewrite.json` proves the source trees are identical.

The separate ARM CPUfreq topic retains its base's older allocation expression.
Its first patch stages the shared CPR query header; its native build uses the
disabled-MSM8926-feature inline stub. The enabled query is compiled in the PM topic.
It requires the PM implementation and configuration to enable that provider.
Its four actual-function model methods also run with the explicitly declared
PM supplier implementation. The two topic stacks are alternatives for review,
not a concatenated eleven-patch kernel series.

Eight native Qualcomm profiles compile 83 objects with LLVM 21, W=1,
COMPILE_TEST=n and strict callback diagnostics. All selected builds have zero
diagnostics. Recorded precommit heads are bound to the final candidates by
their exact source hashes; PM's message-only rewrite changes no source bytes.
Enabled and disabled optional-interface symbol gates pass, as does the ARM
clock division dependency check. Three selected bindings pass lint, meta-schema
and examples. The integrated ARM kernel and 455 modules build incrementally;
normal private module staging verifies signatures, ELF architecture, release
and dependency metadata. Earlier full-build inherited warnings remain recorded
in the preceding complete-CPU packet. This is not a clean reproducible package
build, a whole PREEMPT_RT build, or phone acceptance.

Run the portable replay with Python 3, `patch`, `clang-21`, and its normal
address/undefined/leak sanitizer runtimes installed:

```sh
python3 -B replay.py /tmp/fx0-clock-pm-review-output
```

The output directory must not already exist. Replay verifies every packet hash,
applies all four topics with zero fuzz or offsets and compares candidate bytes.
It then assembles 43 public-source dependencies from `model-composition.json`,
runs 45 existing model methods plus four ARM-topic methods, and runs the
independent calibration model (4,068 cases and 178,907 checks) with three
deliberately failing controls. All inputs are public source or synthetic data.
This composition is for selected-function tests, not a complete kernel tree.

Standalone C models use ASAN, UBSAN and normal leak detection. The numeric
ctypes shared-library oracles are explicitly unsanitized. Allocation adapters
preserve modeled allocation failures and bounded fixture sizes; native objects
use the real kernel APIs. These adapters do not test allocator overflow or
type-safety semantics. Transport, locks, hardware and scheduling services in
models remain synthetic. Native builds and binding tools are recorded evidence
and are not rerun by the portable replay. No Git, network, phone, firmware,
initramfs, private keys, unit calibration values or credentials are required.

SPM/RPM standalone source review and deep-PM RPM sleep-vote handoff remain open.
Physical CPU calibration, higher OPPs, thermal/charging interactions, standby,
suspend/wake, repeated boot and recovery acceptance remain open. The original
r2 display/IOMMU failure is unresolved. Maintained-LTS public-source package
reproducibility and normal installation/update/recovery still require their
own qualification; development-kernel component tests do not complete bringup.
