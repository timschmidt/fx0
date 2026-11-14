# Unchanged-r2 native repeat adapter

The [native adapter](native_trial_adapter.py) uses the qualified
[durable runtime](../modem-control/passive-runtime.md),
[single-BOOT flow](../modem-control/passive-trial-flow.md) and concrete
[transport callbacks](../modem-control/passive_adapter.py). It specializes
staged-module checks, native observation and candidate health for the existing
r2 image. The original failed trial and prepared controller02 remain unchanged.

This profile accepts only the original 17,272,832-byte image, SHA256
`49c23a63402b645c49c55ffbd44f140c64ad0bba722170472891fa3b1a45f0d1`.
The expected r2 kernel notes are
`1e9be71c9bb7ed42d12826a039097bd853bb6f9781325b47008ed46c679353e0`.
The image's early helper has a 420-second absolute BOOTTIME return; normal
systemd return is at 360 seconds. This controller neither modifies that image
nor authorizes installing a kernel, creating another native stage or starting
modem firmware. R5 remains a separate later diagnostic.

## Private plan and entry

Use the exact plan schema in the [private-plan contract](../modem-control/passive-adapter.md),
with these native-profile differences:

- The source root must identify the executing `native_trial_adapter.py`.
  The mandatory source roster is exactly its ten `SOURCES` paths.
- `workspace_inputs_SHA256` has exactly `before.json`, `preparation.json`,
  `stage-record.json` and `owner-display-touch-before.json`.
- `preparation.json` identifies the unchanged r2 image. Its independent audit
  must verify the original init/CPIO/module replacements and 420/360-second
  return deadlines.
- `stage-record.json` is the retained stage provenance. It must bind the
  exact r2 module manifest and the accepted installed module-tree digest.
  The same-boot UI record supplies previously accepted display/touch evidence.
- The fresh operator receipt's exact answer is `Available for another run`,
  bound to this image and the plan's accepted baseline boot, aged `[0,600)`
  seconds. A motion-test answer, earlier completed r2 availability, passive-r1
  availability, publication approval or goal continuation cannot supply it.

The workspace is private mode 0700; the reviewed plan is mode 0600 and its
SHA256 is supplied separately. Private client/device-record bodies are excluded
from every input hash role. Their normal client import is deferred until all
immutable-input and current operator gates pass. Errors expose phase/type only,
without private exception text or tracebacks. Preserve every consumed or
superseded attempt and source snapshot; use a fresh reviewed workspace after
source or input changes.

```sh
python3 -B diagnostics/kernel-maintenance/native_trial_adapter.py \
    --plan /absolute/private/workspace/plan.json \
    --plan-sha256 REVIEWED_PLAN_SHA256 --check-inputs
```

This mode verifies noncredential inputs only. It neither imports the private
client nor reads its device record, claims a workspace, locks a USB port or
contacts a phone. Actual execution omits `--check-inputs` only after the specific
current operator response and concrete plan review. Do not invoke another
image profile through this entry point. Optimized Python is forbidden in the
adapter, observer and remote probes.

## Runtime and evidence

Before bootloader entry, the adapter repeats the accepted r1 byte/service
audit and [read-only staged guard](native_trial_stage_probe.py): all 478 staged
files, the exact module digest, root ownership, writable-mode and symlink/type
checks, and free space. It reuses the shared selected-port lock, durable attempt
claim and journal. Transfer, observer and pre-BOOT normal-return owned-child
waits are bounded at 180, 1100 and 45 seconds, plus bounded termination/kill
grace. A parent deadline cannot authorize USB reset. An observer deadline is
failure even when its actual terminal status is 0.

The [observer](native_trial_observer.py) has an exclusive persistent marker,
rejects stale observation artifacts and writes mode-0600 file/directory-fsynced
receipts. Its read-only loop has a 1000-second observation window and bounded
SSH/health calls. Candidate health checks exact notes/token, module tmpfs and
all 478 module/metadata files, original package/world/raw boot bytes, the exact
live early helper, active normal return timer, running systemd/Sway/lisgd, the
touch descriptor, four CPUs/governor/cap and serious kernel-log patterns.
It records client exception types without copying credential-bearing text.

Candidate health, owned observer completion, installed r1 return verification
and fresh physical display/touch confirmations are separate gates. Native
return alone cannot qualify an unseen or unhealthy candidate. Parent acceptance
also requires an actually reaped observer without deadline expiry and matching
candidate/return boot identities. Once BOOT intent begins, failures observe the
independent return and attempt full installed-r1 verification without another
BOOT/reset/reboot command.

The public fixtures use synthetic image/baseline profiles and block device
providers by default. They run actual disposable host children, including a
child that exits 0 on termination after deadline. Observer/native responses and
health remain fixtures. A real static plan check covers the retained image
without a client load or phone action. No host test supplies operator presence
or proves physical r2 startup, display/touch, automatic return, installation or
complete bringup.
