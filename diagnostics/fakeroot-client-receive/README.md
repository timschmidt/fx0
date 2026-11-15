# Native fakeroot interrupted receive diagnostic

The retained r7 build emits one `libfakeroot internal error: payload not
recognized!` message, completes, and produces the same signed artifacts as
its independent build. Their complete archive metadata is checked separately.
This fixture tests one possible nonfatal mechanism using the actual native
fakeroot client and daemon. It does not establish the original build's cause.

A traced control and a single-client interrupted receive both complete with
status zero. The injected `msgrcv` returns `EINTR`, the client prints the exact
message, and its next receive succeeds on the same queue. Fake ownership,
permissions and a three-entry tar archive match the control byte for byte.
The daemon is neither traced nor interrupted. Real file ownership remains
with the unprivileged build account. All owned processes are reaped and the
traced targets disappear.

An earlier broad experiment interrupted both sides of the exchange and failed
after the daemon's queues disappeared. That attempt remains preserved and is
excluded from successful evidence. The passing client test does not justify
ignoring every fakeroot message or qualifying daemon interruptions. Actual
signal delivery and the original package run were not replayed.

The wrapper creates its own stopped client, verifies that it belongs to the
owned bwrap process tree, checks its inner PID and tracer identity, and resumes
only that target. It accepts no external PID. Tools and source inputs are
pinned; the native root is mounted read-only, networking is disabled, and no
signers or phone interface are mounted.

Replay requires an independently verified native Alpine root containing Python,
fakeroot, GNU tar and build user `pmos` at UID 12345; an existing rootless Podman
vfs runtime; bwrap; and a host strace with syscall error injection and ptrace
permission. Take the native database digest from the trusted tool manifest.
Use new private output paths and the runtime's absolute configured paths:

```sh
python3 -B diagnostics/fakeroot-client-receive/prepare.py \
  --native-root /verified/native-root \
  --runtime-root /verified/podman-runtime \
  --expected-native-db-sha256 SHA256_FROM_VERIFIED_MANIFEST \
  --output /new/private/fakeroot-fixture

python3 -B /new/private/fakeroot-fixture/run.py control
python3 -B /new/private/fakeroot-fixture/run.py eintr

podman --root /verified/podman-runtime/podman-storage \
  --runroot /verified/podman-runtime/podman-run \
  --storage-driver vfs --cgroup-manager cgroupfs unshare \
  python3 -B /new/private/fakeroot-fixture/verify.py
```

The verifier uses the existing user namespace to read the deliberately 0640
fixture file without changing its permissions. Every case is one-shot; retain
failures and use a fresh prepared workspace for a changed experiment. This
diagnostic does not install packages, modify the native tools or sign anything.

[Sanitized native evidence](../../evidence/2026-11-15-fakeroot-client-interrupted-receive.json)
