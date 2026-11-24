# Private native-trial console capture

The [host entry](native_console.py) collects bounded console records through the
existing private pinned-SSH client. The [remote probe](native_console_probe.py)
opens only `console-ramoops-0` through `console-ramoops-3` under `/sys/fs/pstore`
and `/var/lib/systemd/pstore`. It does not clear, unlink or write phone files,
start services, reboot, stage an image or change packages. This entry uses the
unchanged-r2 trial plan; it does not dispatch that trial or authorize R5.

The remote probe requires the independently accepted native boot ID and kernel
notes before and after its read. Every console path component and final file is
opened without following symlinks. Files must be root-owned regular files without
group/other writes. Nonblocking opens reject FIFOs without waiting for a writer.
Each file is limited to 1 MiB and the complete raw capture to 4 MiB. Two reads
and metadata comparison detect changing records. Missing files, rejected paths,
limits and unstable reads are distinct states. A failed/incomplete capture is
retained for inspection and cannot reuse its output directory automatically.

## Inputs and gates

Use the [reviewed native plan](native-trial.md) and its separately reviewed
SHA256. Its runtime sources, unchanged image and four workspace inputs are
verified before any client load. The additional
[capture source lock](../../manifests/native-console-capture.json) pins the host
entry, remote probe, analysis source and exact R5 trace catalog. Supply that
lock's separately reviewed SHA256; do not accept a modified lock merely because
it can be hashed.

A `before` capture requires the actual fresh specific r2 operator receipt and
an undispatched attempt. An `after` capture requires the durable attempt claim
and a full verified `native-return.json`: a new boot, original kernel/notes,
package/boot/module hashes, ext4 module tree, no trial token, zero taint and
running native UI services. It does not require renewing operator availability
for this read-only postflight. Fresh physical display/touch confirmations remain
separate requirements. Both phases use the actual shared port lock, and existing
capture output prevents another client load. Private exception text is never
included in CLI errors.

First check local noncredential inputs only:

```sh
python3 -B diagnostics/kernel-maintenance/native_console.py \
    --plan /absolute/private/workspace/plan.json \
    --plan-sha256 REVIEWED_PLAN_SHA256 \
    --source-lock-sha256 REVIEWED_CAPTURE_SOURCE_LOCK_SHA256 \
    --phase before --check-inputs
```

After the specific operator response, the same command without `--check-inputs`
performs the bounded read-only `before` capture. Inspect its actual exit status
and completion report. It does not claim the RAM trial workspace or execute the
trial. Run the separately reviewed unchanged-r2 controller only after its own
gates pass. After verified native return, invoke this entry with `--phase after`.
There is no automatic retry, recovery action or combined boot command here.
Optimized Python is rejected before private-client/device execution.

Outputs are new `console-before/` and `console-after/` directories inside the
private attempt workspace, mode 0700. `capture.private.json` contains base64 raw
console bytes and is mode 0600; it is private boot data, including any logged
command line. The host validates exact paths, limits, identities, hashes and
completion metadata before saving. Source/plan provenance is recorded separately.
File and directory fsync precede the completion report. Do not publish raw files,
print the remote packet in a chat/tool result, or copy them into source review.

## Comparison and limits

When a valid before capture exists, the after phase writes `comparison.json`.
It distinguishes changed, unchanged, new, disappeared, missing and inconclusive
records using complete stable record hashes. A changed record is not proof of a
fresh candidate boot. File modification times and the phone's native boot change
cannot supply that proof either. Missing or unchanged records may be uninformative.

The [analysis](native_console_analysis.py) emits only known release labels, time,
fault/panic/helper counts and the 15 known R5 trace IDs. It does not reproduce
arbitrary log lines, device prefixes, command lines, PIDs, addresses or unknown
trace values. Sensitive-looking lines are excluded from signal analysis. The
event list is bounded at 512 while counts remain exact. Missing trace markers
are always inconclusive. No summary asserts a reset cause or exact image identity
from a release banner.

The [trace catalog](../../manifests/display-handoff-trace-sites.json) is extracted
from all four SHA256-verified R5 source files at
`de5568bfc81f221984b8e82519af9a15b00b5b6f`. All 15 formats were already verified
in the qualified objects and linked outputs. Their C escapes decode to normal
newlines. Cataloging does not boot R5 or imply a fix; tracing can change timing.

The retained first-r2 input contains a sanitized banner and 12 tail lines, not
the complete console or a before/after pair. Offline replay recognizes its fault
message at 6.164901 seconds and keeps fresh-boot attribution/reset cause unproven.
No new phone observation is claimed by that replay or by the synthetic tests.
