# Native trace lifecycle qualification

The revised helper accepts the pinned kernel's bounded payload-page rounding,
records sizing before validating it, requires the default 4 KiB subbuffer,
and verifies equal capacities for all CPU buffers. An exported copy passed
25 model/parser cases, including invalid sizes and unequal CPU readbacks.

The first host launch preparation was rejected before staging because the
previous probe's owned failed unit left systemd degraded. Its failure and
cleanup receipts were preserved; only that terminal owned unit's failed flag
was reset after checking it was the sole failed unit. A fresh host attempt
then passed the native empty trace test and injected setup failure test on
the same installed r1 boot. No camera capture occurred.

The requested 256 KiB produced 259 KiB on each of four CPUs with a 4 KiB
subbuffer. The normal trace contained one monotonic marker, no buffer events,
and no trace loss. Both instances were removed; global and other-instance
settings matched before and after. The completed service was stopped and
its stop-post guarded recovery verified absence of both namespaces.

This qualifies the trace lifecycle only. It does not resolve the prior
`Missing ready buf` camera warning or establish complete camera correctness.
Private raw traces, journals, claims and observations are excluded.
