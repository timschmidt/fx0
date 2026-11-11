# Stable CPR RAM trial controller

[`stable_ram.py`](stable_ram.py) owns one registration-only RAM trial of the
exact `6.18.63-r3` image. It is prepared and tested on the host; this image has
not been staged or booted. The installed phone remains r50/Sxmo r7.
See the [manifest](../../manifests/stable-cpr-ram-controller.json) and
[evidence](../../evidence/2026-11-11-stable-cpr-ram-controller.json).

The controller reserves a new private trial directory once, retains its actual
transfer and observer `Popen` objects, waits for transfer completion, verifies
the exact readback bytes and checks the observer is alive before one BOOT.
It never derives liveness from a saved PID or a `/proc` entry. The two helpers
do not fork children. The test fixture deliberately supplies a stale PID file
and makes any `os.kill` use fail; the owned-process path still succeeds.

The observer uses only the selected diagnostic USB serial device. It waits
for a matching per-trial challenge and the pinned image digest before sending
one registration command. It captures the kernel release, a new boot UUID,
guarded module-registration result, zero taint, unchanged persistent boot hash
and live `/dev/kmsg`. A pass requires the existing init's exact return-timer
message with a kernel timestamp of at least 180 seconds, with no captured
panic, Oops, CFI failure or CPU warning. Registration success followed by a
kernel fault does not pass. No temporary network connection is created.

Before entry, the controller requires a confirmed display/touch result for
the exact expected native boot. This check precedes private USB identity reads,
backend construction, process launches, USB opens and trial-directory creation.
It then pins the image, public runtime certificate, kernel, DTB, two-module
selection, timer and helper source hashes. Guards remain active under Python
optimization.

The real native preflight checks boot UUID/release, the raw boot partition,
five boot/package/world files, zero taint, running systemd without failed units
or jobs, Sway and gesture counts, sensor proxy, both thermal sensors and the
original four-rate schedutil policy. Two exact nine-byte PMIC reads require
range/VSET 1/115, the restored 1.15 V programmed target. This is register
readback, not an analogue rail measurement. The same checks apply after a
different native boot UUID returns.

Lost reboot or BOOT acknowledgements never trigger another request. A failed
transfer, altered readback or exited observer forbids BOOT. Before-BOOT failure
can request one normal native recovery only after both owned children are
terminal and the same bootloader answers an identity query. After a BOOT
attempt, the controller waits for the independent RAM timer and native return;
it sends no recovery command or repeat BOOT. Uncertain outcomes require
inspection of the original controller and device state.

The actual read-only probe passes on r50 boot
`747e87fe-198f-49f8-997a-8e198315968d`: original boot/file hashes, zero taint,
running services, one Sway and gesture daemon, and the restored APC target.
Fourteen host tests cover real child-process lifecycles, two pseudo-terminal
observer cases, stale/missing owner data, altered inputs, wrong build families,
readback/observer failures, lost acknowledgements, early return, kernel faults
and replay refusal. These models do not qualify real USB entry or recovery.

The actual `--run` entrypoint is also executed with the current UI answer
missing. An audit hook forbids process launches, socket connections, private
identity reads and USB opens. It rejects at that exact owner check, performs
none of those operations and creates no trial directory.

For an offline check of the prepared current-r50 plan:

```sh
python3 -E -B diagnostics/cpu-cpr-runtime/stable_ram.py \
  --plan local/stable-cpr-ram-controller-01/plan-r50-pending.json --check
```

It currently rejects the unanswered UI check. `--run` owns the full trial;
there is no separate PID-file-driven BOOT command. Keep its live tool/process
handle for observation. If that handle is lost, inspect the original process
and device state rather than launching a new controller.

The approved r1 native installation remains the next phone action after the
current return's UI answer. Once that update and persistent boot qualify,
capture a fresh native baseline and owner receipt in a new plan and trial
directory before this RAM trial. The old r50 plan cannot pass against a
changed boot, kernel, boot image, package database or world. Do not overwrite
published plans or reuse an earlier boot's physical answer.

Real r3 startup, registration, timed return and physical display/touch recovery
remain unqualified. Later OPPs, sustained load, thermal/physical rail behavior,
suspend, NFC operations and the broader bringup remain open. Audio is excluded.
