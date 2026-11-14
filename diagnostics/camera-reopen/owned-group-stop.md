# Full-thread acknowledgement for the camera-client pause

The first pause experiment timed its window from the primary task's stopped
state. That source and its observations remain preserved in their pinned commit;
it did not independently prove completed group stop across every live thread.
This follow-up strengthens the acknowledgement and repeats the matched cases
on the same accepted installed r1 boot.

The helper pins its owned child with a pidfd, waits for the kernel's
`CLD_STOPPED`/`SIGSTOP` notification through `waitid` on the pidfd with
`WSTOPPED | WNOWAIT | WNOHANG`,
then checks every live task under `/proc/PID/task`. Timing begins only when all
live task states are stopped. After `SIGCONT`, it checks that every live task has
left the stopped state before recording resume acknowledgement. Exited tasks
are excluded; a child that exits before resume acknowledgement is recorded as
exited rather than successfully resumed.

## Native observations

Six full-resolution rear RAW10 sessions alternate unpaused controls and 250 ms
client stops after at least eight delivered buffers. Every session delivers its
24 requested buffers. In each paused case the kernel confirms group stop and
both live `cam` threads are observed in state `T`. Both are subsequently observed
in state `S` after resume. No pixel data is written to frame files or transferred.

| Case | Full-group stop timed (ms) | Largest completion interval (ms) | First new completion after resume request (ms) |
| --- | ---: | ---: | ---: |
| 0, control | — | 33.483 | — |
| 1, paused | 250.460 | 199.637 | 58.410 |
| 2, control | — | 33.480 | — |
| 3, paused | 250.507 | 199.542 | 60.383 |
| 4, control | — | 33.408 | — |
| 5, paused | 250.511 | 199.639 | 66.272 |

Buffers 8–11 complete during each confirmed group stop. The next new completion
is buffer 12. Its timestamp follows resume acknowledgement by 51.6, 53.6 and
59.4 ms respectively. Those figures differ from resume-request latency because
the stronger acknowledgement checks all live tasks. They do not demonstrate
improved device recovery over the earlier leader-only probe. Already-completed
buffers are available when the application resumes; these are new kernel buffer
completion timestamps, not first application-dequeue times or sensor frame IDs.

Every paused case has one interval above 1.5 times its approximately 33.3 ms
median; the controls have none. All 144 buffers arrive, all clients exit 0, and
the full independent preflight/launch/capture/cleanup kernel window has no messages.
The original `Missing ready buf 1 4!` diagnostic and the approximately one-second
frame-file writing gaps still do not recur. Their causes remain unresolved.

## Verification

The ownership helper now passes 11 tests against real disposable Linux child
processes, including an eight-thread process, rejection of an inconsistent
thread-stop observation and a child killed while stopped. The earlier tests
continue to verify unrelated-session isolation, private-group interrupt/kill,
reaping, bad identity/session rejection and cleanup after exceptions. Seven
pause-correlation, ten discovery and fourteen timing checks also pass: 42 checks
in total, repeated from a five-file export without ignored local helpers.

```sh
python3 diagnostics/camera-reopen/check-owned-client.py
python3 diagnostics/camera-reopen/check-pause-evidence.py
python3 diagnostics/camera-reopen/check-current-discovery.py \
  --worker diagnostics/camera-reopen/pause-queue-test.py
python3 diagnostics/camera-reopen/check-timed-evidence.py \
  --worker diagnostics/camera-reopen/pause-queue-test.py
```

The exact updated worker runs in a new owned service with the same 90-second
runtime, 15-second stop and 512 MiB memory limits. It exits 0 and is stopped;
the cgroup is empty and no temporary case directory remains. Both sensors
runtime-suspend after each case and both pattern controls return to zero.
Independent postflight retains the accepted boot-file/package/world/repository
hashes, taint zero, healthy services and unchanged Sway/gesture processes.
USB is configured at high speed in every case sample; the battery reports
discharging and Good health. There is no module, package, tracing, firmware,
boot or reboot change.

The read-only trace inventory still supplies the next useful path: an owned
tracefs instance using existing vb2 queued/driver-owned buffer counters. Its
lifetime and restoration must be verified before capture. Then match the
original front/rear binned/full switching workload and preserve private raw
traces, complete kernel windows and lost-event counts. No kernel patch or benign
classification follows from these pause tests.
[Sanitized full-thread measurements](../../evidence/2026-11-14-camera-owned-group-stop.json)
