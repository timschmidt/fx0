# Calibration-reference conversion experiment

This diagnostic patch is **not an integration fix**. It applies to Linux
`31061619c6a1ec6579b07ecbd3303614899d116b` and removes the fresh gain/offset
conversions from each BMS sample. Initial and periodic provider calibration
still refresh references. The unmodified driver's relative-counter and live
current interfaces otherwise remain in place. Do not install this variant as
a solution to the current discrepancy: calibration invalidation/cache semantics
and absolute accuracy remain unqualified.

The exact ARM module builds with W=1. A RAM test uses the same signed r4
kernel/initramfs and temperature-enabled DTB for all arms. USB stays connected;
no synthetic CPU load runs. The initial/read-time thermistor stop bound is
630 mV. Each arm starts with 100 mA USB input, then switches to 500 mA. Driver
reloads intentionally start new counter epochs. The final control reloads the
unchanged base driver while input remains at 500 mA. Cleanup restores 100 mA.
No charger voltage/current/thermal thresholds or installed package change.

| Arm | Background readings after switching to 500 mA |
| --- | --- |
| Base A1 | -6.2 to -7.3 mA |
| Cached-reference variant B | -2.6 to -4.1 mA |
| Base A2 | -3.6 to -4.1 mA |
| Base reload at unchanged 500 mA | -0.5 to -1.6 mA |

Live/manual readings are zero in these windows. The large frozen-current
symptom does not recur after the first reprobe, including with the unchanged
base. Differences between these arms therefore do not establish cache causality
or electrical ground truth. Capture the first-probe transition before another
reinitialization and examine initial sense/calibration/counter sequencing.

The [sanitized evidence](../../evidence/2026-10-30-bms-reference-cache.json)
includes source/module/patch hashes, timing and per-arm measurements. The patch
passes `git apply --check` against the clean base. Apply only to an isolated
experimental worktree. Raw calibration/logs and RAM images remain private.
