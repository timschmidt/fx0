# Native display shutdown trace

This diagnostic adds log messages around DSI host/PHY teardown. It is not a
power-management fix and is not part of the upstream submission series.
`trace.patch` applies to the kernel commit and original file hashes recorded in
`source-hashes.json`. It changes logging only.

Build with the exact running kernel configuration, generated headers and
Module.symvers. For an external build, copy drivers/gpu/drm/msm into a private
build directory, apply the patch with paths adjusted to that copy, and add the
canonical drivers/gpu/drm/msm and disp/dpu1 directories as fallback include paths
for relative DRM internal headers. Run `make W=1 modules` with ARCH=arm LLVM=1.
Sign with a key already trusted by the test kernel. Do not force module versions,
ignore signatures, or overwrite the installed modules.

Boot the diagnostic kernel from RAM, keep the installed filesystem read-only,
and load this module instead of the original msm module. Load all its dependencies
first; with kmod use `modprobe -a` when passing multiple module names. Start a working native framebuffer and retain its original DRM owner and
buffer. Stream /dev/kmsg to the host before attempting a single controlled CRTC
power cycle. Preserve partial ioctl output even if the device resets. Retrieve
the retained console, complete raw ramoops and staged bootloader log before
starting another kernel; download each staged payload immediately after its
corresponding OEM command.

A final trace line identifies the last observed boundary, not necessarily the
faulting operation. A reproducible reset still requires finer instrumentation or
an independently justified change before assigning a cause.
