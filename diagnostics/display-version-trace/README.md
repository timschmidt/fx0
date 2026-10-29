# DSI version-read diagnostic

Apply `trace.patch` to the exact source in `source-hashes.json`. It replaces
three existing inlined reads with distinct noinline wrappers, preserving
register offsets and read order. Persistent function tracing can then identify
the last entered read wrapper after a reset. An entry alone does not prove that
the read returned or that its instruction caused the reset.

This is a diagnostic, not a production fix. It builds with W=1 against the
separate pmdebug1 kernel and its matching modules/certificate. One failed start
captures entry into the first unshifted version read followed by `do_DataAbort`.
Console-detached and ramoops-only-console boots still fail intermittently,
without retaining complete status/address/PC. The separate
[abort-value diagnostic](../abort-value-trace/README.md) attempts to preserve
those values as function names. No functional fix is claimed. Do not load these
modules into another kernel build or force signatures.

Use the configuration and retained-RAM layout described in
[building](../../docs/building.md). Capture the loaded module `.text` address
privately before probing and decode against this exact module. Keep the full
raw 512KiB dump before any later boot. A filtered persistent trace must include
the module functions; the earlier deferred module filter did not record those
functions reliably. Unfiltered tracing is expensive. Excluding persistent
buffer helpers reduces self-generated trace volume. Keep raw addresses/logs,
unit identifiers, and module signing keys private.
