# Public passive-r1 adapter and private input plan

[The adapter](passive_adapter.py), [observer](passive_observer.py) and
[read-only native probe](passive_native_probe.py) provide the runtime source.
No controller program has to be copied from an ignored local directory.
The adapter uses the [generic flow](passive-trial-flow.md) and
[durable runtime](passive-runtime.md).

This profile is specifically the qualified passive-r1 image, SHA256
`428779913614a376bd40844bf80b10d004de0571d721b1bb29b85b68f31d4f53`,
6,785,024 bytes, with its independent 180-second return. It leaves the modem
disabled and uses the RAM-shadow RMTFS worker. This is preparation for RFSA/local
publication qualification; neither these host tests nor a native return alone
qualifies modem/GNSS, r2/r4/r5 kernels or the complete bringup.

## Private inputs

Use an existing, owned mode-0700 attempt workspace and a mode-0600 `plan.json`
inside it. Source and input files must be owned regular files without writes
permitted to another account. Preserve every consumed attempt workspace.
The private plan is identified by a separately reviewed SHA256 supplied on the
command line. Changing a source, baseline, preparation file or plan requires a
new reviewed plan; do not repair an already dispatched attempt in place.

| Plan field | Meaning |
| --- | --- |
| `format` | Integer `1`. Unknown fields reject. |
| `repository_root`, `workspace` | Absolute public-source root and private attempt directory. The root must identify the executing adapter. |
| `image_path`, `image_SHA256`, `image_bytes` | Absolute path and exact identity of the prepared passive-r1 image. |
| `image_audit_path`, `image_audit_SHA256` | Absolute private independent image-audit JSON and its reviewed digest. |
| `baseline_boot_id` | The accepted boot to which the current operator receipt and before-state belong. |
| `workspace_inputs_SHA256` | Exactly `before.json` and `preparation.json`, keyed by workspace-relative basename. |
| `source_files_SHA256` | Exactly the eight public source paths exported by `passive_adapter.SOURCES`, keyed relative to `repository_root`. |
| `credential_client` | Absolute path to the existing private pinned-SSH client module. Its body is neither hashed nor copied by the adapter. |
| `device_record` | Absolute private JSON device-record path containing `serial`; it is excluded from the hash roster. |
| `usb_port` | Selected Linux USB topology name, such as `1-7`. |
| `host_index_path`, `host_index_SHA256` | Absolute protected repository index path and accepted digest; source execution and host guard paths may be separate. |
| `port_lock_path` | Shared absolute `fx0-ram-port-PORT.lock` path used by every adapter selecting that physical port. |

`before.json` is the accepted native probe result, augmented with the host's
`native_USB_generation` for the selected port. It must represent the accepted r1
kernel and full byte/service baseline, not a guessed inventory or a new state
accepted merely because it is observed. `preparation.json` supplies
`image_path`, `image_SHA256` and `image_bytes` matching the plan. The independent
image audit must confirm its exact image hash, initial shell/interpreters and
GNU cpio extraction agreement. Private plan/input bodies and raw logs stay
outside public commits.

The client API supplies `run(command, root=..., timeout=...) -> bytes` and
`OPTS` for the existing pinned read-only SSH readiness probe. It must implement
the already authorized device access. Do not put credentials in the plan or
command line. The adapter loads this client only after its immutable-input and
specific current operator gates pass. Client exceptions are reported by phase
and type without a credential-bearing message or traceback.

## Entry modes

First verify local noncredential inputs:

```sh
python3 -B diagnostics/modem-control/passive_adapter.py \
    --plan /absolute/private/workspace/plan.json \
    --plan-sha256 REVIEWED_PLAN_SHA256 --check-inputs
```

This mode does not load the client, read the private device record, acquire a
trial claim or perform a device action. It is not an availability receipt or
authorization to boot. Its successful output explicitly states
`credential_client_loaded: false` and `device_actions: false`.

A real trial additionally requires `owner-availability.json` from the actual
current operator response, with fields `answer`, `boot_id`, `image_SHA256` and
`recorded_UTC`. The exact answer is `Available; display and touch work`, bound
to the plan's accepted boot and image, with age in `[0, 600)` seconds. Another
trial's availability, publication approval or goal continuation cannot supply
this response. Keep the receipt absent until that response arrives.

After that gate and a review of the concrete plan, the same entry without
`--check-inputs` performs the prepared trial. It repeats local/operator/native
preflight, acquires the common port lock and consumes one durable workspace.
The normal output and process exit status must both be inspected; state files
alone cannot prove successful child completion. BOOT/readback/observer/native
checks remain separate from the fresh physical display/touch confirmation.
Optimized Python is rejected, since the concrete device assertions must run.

The parent waits are bounded at 180 seconds for transfer, 400 for the observer
and 45 for normal pre-BOOT return, plus bounded termination/kill grace. These
are failure limits, not a promised trial duration. A parent deadline is not a
USB I/O timeout and cannot authorize USB reset. Once intent is reached, the
adapter observes the independent return and verifies native state without a
BOOT, reset or reboot retry. A failed observer cannot qualify an earlier partial
worker result.

## Host qualification and limits

The public tests use synthetic profiles/metadata and forbidden-by-default
transport providers. They run disposable host children; no test contacts USB,
SSH or a phone. The actual prepared image and retained baseline also passed a
separate local `--check-inputs` run without an operator receipt or client load.
The retained-image callback fixtures exercise the concrete public factory;
their device responses remain fixtures, not current native evidence.

```sh
python3 -B -m unittest discover -s tests -p 'test_passive_*.py' -v
```

The original private revisions remain frozen. No public-source export, passing
host suite or static input check stages the image, supplies operator presence,
starts firmware or closes physical RFSA/USB/return/modem/GNSS requirements.
