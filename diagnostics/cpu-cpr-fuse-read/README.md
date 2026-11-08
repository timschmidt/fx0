# Native conditional-fuse read pilot

This diagnostic performs one read of the compiled Madai CPR conditional rule
through `qcom_scm_legacy_fuse_read()`. It requires the candidate kernel exporting
that API and refuses other board compatibles. It exposes only read status and
whether bits 42–47 of row54 match seven; raw fuse bytes are neither logged nor
exported. It changes no regulator, CPU frequency, audio or network setting.

The two module parameters are readable only by root. Initialization overwrites
their input values, so a failed firmware request remains an error. A successful
module load alone does not prove the read passed: require `read_status=0` and
`condition_matches` equal to zero or one. A mismatch selects the manufacturer's
conditional minimum-floor rule; the diagnostic does not apply that floor.

Build as an external module against the completed candidate's exact output
and symbol versions, strip debug information and sign with the same existing
module key before loading. Do not build it against a live/incomplete kernel
build. The source intentionally does not claim an in-tree module marker.
Consequently Linux records the expected out-of-tree taint while it is loaded;
unloading cannot clear historical taint. Record that fact and reboot to the
unmodified candidate afterward before any zero-taint qualification.

The pilot must be loaded manually after boot and unloaded after collecting
its root-only parameters. It has no auto-load alias or writable hardware
controls. The r50 native pilot returned `read_status=0` and `condition_matches=1`;
see [native evidence](../../evidence/2026-11-06-cpu-calibration-r50-native.json).
This confirms this unit’s selector comparison, without applying CPU voltage
control or qualifying higher frequencies.
