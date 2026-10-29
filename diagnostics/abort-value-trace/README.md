# Retained ARM abort values

This Fx0-only, RAM diagnostic records the first kernel-mode `do_bad` call's
address, FSR, original PC and CPSR as function names in the existing persistent
function trace. Each field marker is followed by eight hexadecimal digit
functions, most significant first, then an end marker. It adds no reserved RAM
and does not access display registers or write storage. It is not a production
fix. Loading it marks the kernel out of tree.

Build with the exact target kernel output, configuration and release. Sign with
that output's already trusted key; never force versions or signatures. The
module refuses another board or release. The tested targets are source
`476e36e72527b4115b656117634fb17a4b6e77dc`, full44 and its distinct pmdebug1
configuration. `do_bad` has the three-argument ARM fault-handler ABI in that
source. A probe on `do_DataAbort` was rejected by the kernel; this module uses
the normally permitted `do_bad` site instead.

Before loading MSM, enable persistent function recording with the pmdebug1
layout in [building](../../docs/building.md). Include the digit and marker
functions in the trace filter; an empty global filter records all functions.
Exclude the persistent buffer's own helper functions to reduce trace volume.
Load with `selftest=1`, check the read-only `selftest_pass` parameter, and save
`/sys/module/abort_value_trace/sections/.text` privately while the phone is alive.

The self-test checks a known RAM read, safe rejection of an invalid address,
and a synthetic fault frame. It does **not** deliberately cause a hardware fault
or prove the real exception path. On full44, the invalid address is rejected
with `-ERANGE`. The observed synthetic function stream decodes exactly to
`fabcdef0`, `12345678`, `c0010100`, `600001d3`, followed by both end markers.
Probe registration and clean unloading also pass. These constants are invented
test data. The first actual startup failure with this module retained no value
markers and stopped at the initial DSI read; real argument capture remains open.

After a reset, retrieve the complete raw 512 KiB region before another boot.
Decode privately using LLVM readelf and the exact module:

```sh
python3 diagnostics/abort-value-trace/decode.py private-raw.bin exact-module.ko PRIVATE_TEXT_BASE >private-values.json
```

The decoder reads all four complete rings and resolves only symbols inside the
module's actual `.text` section and symbol bounds. A missing capture is not
proof that no abort occurred: a stalled MMIO transaction may never reach the
handler, the probe may not run, or records may be overwritten. An incomplete
stream is reported as incomplete. Keep raw dumps, addresses, identifiers,
full logs and signing keys private. Do not enable this module in a shipped
Nura kernel or infer a functional fix from timing changes under instrumentation.
