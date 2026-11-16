# MSM8226 SPM owner and RPM reply correlation

This local review exports four commits on the official Qualcomm
`drivers-for-7.5` base pinned in `source-topics.json`: the L2 ownership
binding, the complete SPM owner, its separate raw-regmap lock fix and
per-request RPM reply correlation. The original Timothy Schmidt feature
authorship and dates are retained. The separate raw-lock fix is attributed
to Codex. Ports, integration, changelogs and qualification used OpenAI Codex
assistance. Human DCO review remains pending. No maintainer contact or
publication has occurred.

The maintainer base contains two upstream SPM fixes missing from the earlier
runtime. Both are retained in the port and exported separately against that
runtime: the SDM660 silver AVS correction and the conditional sequence write.
Dmitry Baryshkov's original authorship, dates, messages and existing human
review/sign-off trailers are preserved. Codex added no sign-off. The complete
SPM file now matches between the runtime and maintainer topics. Every other
runtime source path, board and binding remains unchanged. These two stacks
use separate bases; they are not a concatenated six-patch kernel series.

Four native Qualcomm profiles compile 32 objects on ARM/ARM64 with ordinary
and PREEMPT_RT configurations, LLVM 21, W=1 and COMPILE_TEST=n. All compiler
commands return zero. The original strict diagnostic gates remain recorded
as failed: each profile reports two occurrences of the same pre-existing
`qcom_smd_channel.cb` documentation warning in unchanged `qcom_smd.c`.
The SPM/RPM changes introduce no diagnostics. The successful selected binding
lint, meta-schema and examples are recorded separately. Full kernel/module
build evidence is incremental and does not establish clean package
reproducibility. The inherited full-kernel warnings are not declared fixed.

With Python 3, `patch`, `clang-21` and its normal sanitizer runtimes installed:

```sh
python3 -B replay.py /tmp/fx0-spm-rpm-review-output
```

The output directory must not exist. Replay checks every file hash, applies
both stacks with zero fuzz, compares candidate bytes and runs two existing
actual-function models. The SPM model checks publication, partial retries,
register access and I/O errors. The RPM model retains its 111,537 bounded
synthetic packet cases. A focused well-formed-reply model adds 18 checks for
delayed, duplicate, retired and premature completions: original code fails
ten checks; the candidate fails none. Both deliberate RPM regressions fail.
The initial twelve-check comparison referenced by the RPM commit message
predates the added wait-service assertions; its five failures are retained
in the qualification evidence.

The actual regmap selection/callback model uses current core code with the
separately qualified regulator and PMIC parent sources pinned in
`support-provenance.json`. It reproduces nine failures before the SPM raw fix,
then passes 20 cases/149 checks and rejects both deliberate lock regressions.
The independent PMIC parent raw-lock fix remains a prerequisite for the full
APC chain. No hardware, IPI, scheduler, transport or RT concurrency is implied
by synthetic services. Standalone models use ASAN, UBSAN and normal leak
detection. Native, schema and complete kernel builds are recorded evidence;
portable replay does not repeat them.

No Git, network, phone, firmware, initramfs, signing key, credential or unit
calibration data is needed. Physical CPU calibration, higher OPPs, thermal,
charging, suspend/wake and RT/lockdep acceptance remain open. Deep-PM RPM
sleep-vote handoff is still unimplemented. The original r2 display/IOMMU fault,
maintained-LTS public-source package reproducibility and normal installation,
updates and recovery remain open; development-kernel tests do not complete
bringup.

The portable RPM fixture passes a valid scratch buffer for zero-length requests
to satisfy the host C library copy annotations. Replay enables fail-fast UBSAN;
this harness correction does not change the production driver.

All 45 existing CPU methods were also rechecked with fail-fast sanitizer
settings after correcting a zero-length host fixture payload. The source and
fixture hash maps identify all inputs in this commit and the preceding CPU
review packet. The portable replay here reruns the two SPM/RPM methods and
four regression controls; it does not repeat the full 45-method host suite.
