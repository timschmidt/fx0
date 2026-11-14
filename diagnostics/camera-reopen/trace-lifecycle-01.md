# First native trace lifecycle probe

This revision is preserved as tested. Its 16 host model/parser cases passed,
but the empty native trace lifecycle probe failed before enabling events with
`ValueError: trace buffer size mismatch`. The helper incorrectly required an
exact 256 KiB readback after requesting that size. The actual readback value
was not retained in this revision. No camera capture occurred.

The owned instance was removed. The service exited with status 1 and its
stop-post recovery verified that both expected instances were absent and
global and other-instance settings matched the pre-probe snapshot. Raw
observations and journals remain private. Native trace qualification remains
open; host model success does not establish real tracefs behavior.

The pinned kernel rounds requested bytes up by payload-page capacity in
`ring_buffer_resize`, reports capacity through `ring_buffer_size`, and
truncates that capacity to KiB in `tracing_entries_read`. A fresh revision
will retain sizing readbacks and validate the rounding contract before
retrying in new instance and service namespaces.
