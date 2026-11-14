# Passive-trial workspace and child ownership

[The Linux host runtime](passive_runtime.py) supports the
[single-use callback flow](passive-trial-flow.md). It provides no USB, SSH,
fastboot or device access. Device adapters supply those operations and must
retain their current operator, image, identity and native-state checks.

`AttemptJournal(directory)` requires an existing directory owned by the caller
with mode 0700. It reserves `attempt.claim` with exclusive creation and no
symlink following, then fsyncs the claim and directory. Existing state or a
claim prevents another attempt. Closing the journal preserves the claim.
Inspect and archive consumed workspaces; the runtime never deletes a claim or
turns an old attempt into an authorized restart.

Each state update writes a new exclusive mode-0600 temporary file, flushes and
fsyncs it, atomically replaces `controller.json`, then fsyncs the directory.
Errors propagate. A visible state file alone does not prove successful durable
commit. The earlier durable claim still prevents automatic reuse after a later
write, rename or directory-sync failure. These software tests do not prove
survival of a real storage power loss.

`wait_owned(child, timeout, terminate_grace=2, kill_grace=2)` operates on the
actual owning `Popen` object. It waits with a deadline, requests termination on
expiry, then kill if needed, with bounded waits after each. A returned result
requires an integer exit status and matching `poll()` after `wait()`. A child
that remains unreaped raises `UnreapedChild`; a state file, default status or
unrelated PID check cannot substitute for ownership evidence.

The result distinguishes `process_deadline_expired` from a transfer helper's
USB I/O timeout. A process deadline does not authorize a USB reset. A reviewed
adapter may return normally before BOOT after a known terminal failure, with
reset eligibility separately established. After the BOOT-intent barrier,
observe the independent device return and verify native state without a BOOT,
reset or reboot retry. An observer's nonzero exit cannot qualify the candidate
from an earlier partial result.

The new private r1 adapter revision snapshots these helpers. It adds parent
wait limits, rejects optimized Python before device-helper imports and rejects
nonzero observer completion while preserving native verification attempts.
It has passed offline callback and fault tests using real disposable host
children and forbidden-by-default transport substitutes. It remains unbooted
and requires the same distinct current operator window and fresh device
preflight. The original prepared revision remains unchanged.

Run the public runtime tests on Linux, with `TMPDIR` pointing to available
temporary storage if necessary:

```sh
python3 -B -m unittest discover -s tests -p test_passive_runtime.py -v
```

These checks cover workspace exclusion, crash/restart refusal, file/directory
sync failures, real child termination/kill and uncertain ownership. They do not
qualify physical USB recovery, RFSA mapping, firmware, independent RAM return,
display/touch or modem/GNSS operation.
