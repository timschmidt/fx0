# Generic passive RAM-trial flow

[The public module](passive_trial.py) orders callbacks for one RAM trial.
[Its tests](../../tests/test_passive_trial_flow.py) use synthetic callbacks;
they require no ignored local tree, USB, SSH, device identity or boot image.

The object is single-use, including after a failed preflight. This is an
in-memory guard. The device adapter must additionally enforce durable attempt
ownership across processes and restarts. Constructing another object supplies
no authorization, new operator window or safe-retry proof.

## Adapter contract

| Callback | Required behavior |
| --- | --- |
| `preflight()` | Check the actual current operator receipt, exact device/image/baseline and durable single-attempt ownership before any device action. |
| `enter()` | Enter the explicitly prepared bootloader state using the adapter's bounded, identity-checked procedure. |
| `stage()` | Own and reap the actual transfer process. Return a boolean `terminal`, integer `returncode` and optional boolean `timeout`; a state file alone cannot prove a process stopped. |
| `readback_matches()` | Check complete device readback against the pinned image before BOOT. |
| `start_observers()` / `observers_live()` | Start the prepared observation processes and verify their actual current liveness before the intent barrier. These callbacks must not issue BOOT/reset/reboot commands. |
| `stop_observers()` | Establish that owned observers stopped before a pre-BOOT recovery. A failure prevents speculative recovery. |
| `return_native(reset=...)` | Perform the adapter's reviewed pre-BOOT return procedure after transfer ownership is released. A reset is permitted only for a nonzero, known terminal timeout. |
| `mark_boot_attempt()` | Durably record the attempt before `boot()` is called. A partial write or exception is a failed run requiring conservative observation. |
| `boot()` | Make at most one BOOT request; never retry internally after a missing reply. |
| `uncertain_boot(error)` | Record uncertainty without retry, reset or reboot. Reporting failure must not prevent the subsequent observation/verification attempts. |
| `finish_observers()` | Observe the independent device return path. The RAM image must already contain its own qualified return mechanism. |
| `native()` | Verify the installed system and perform only the adapter's scoped host cleanup. This callback must not issue BOOT/reset/reboot commands or manufacture recovery when observation is missing. |

Uncertain transfer ownership or invalid exit-status metadata permits neither
BOOT nor recovery commands. A successful transfer with a readback mismatch
does not authorize a reset. Once the BOOT-intent callback begins, the module
uses observation and native verification only. Its `boot_attempted` flag marks
that conservative barrier; it is not proof that the device received BOOT.
An intent-write failure can therefore require operator recovery if the native
verification cannot succeed.

After the intent barrier, native verification is attempted even when the BOOT
call, uncertainty report or observer callback fails or is interrupted. Errors
propagate. A callback being attempted does not imply that it passed; SIGKILL,
host failure and repeated interrupts cannot be made reliable by Python cleanup.
The independent device timer remains essential.

The returned success text describes BOOT/return ordering only. A successful
native return does not prove that the candidate worker passed. The adapter must
separately assess the identity-bound serial worker result and actual native
postflight, then obtain any required fresh display/touch confirmation.

## Prepared r1 snapshot

This new public module adds explicit single-use and transfer-result checks,
limits pre-BOOT reset eligibility, and strengthens post-intent cleanup. It has
not replaced the frozen prepared r1 controller's original `flow.py`. That
controller retains its separate outer guards and original qualification record.
A future adapter revision must snapshot the exact chosen public module and
qualify its bindings before using it for a physical trial. Existing private
device/image inputs and pending operator receipts remain separate.

Run the public callback tests from a source checkout with:

```sh
python3 -B -m unittest discover -s tests -p test_passive_trial_flow.py -v
```

These tests prove bounded software ordering properties. They establish no
physical RFSA mapping, USB-console behavior, firmware ownership, automatic
return or modem/GNSS function.
