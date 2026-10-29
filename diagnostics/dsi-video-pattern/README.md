# Fx0 DSI video pattern isolation diagnostic

This temporary GPL-2.0-only module prepares a display-link test that generates
pixels in the DSI controller, without reading a framebuffer through the MDP
IOMMU. It follows the fixed-color video pattern sequence in the pinned
[stock driver](https://github.com/peremen/android-kernel-lg-madai/blob/03aba4427a7666d57b5ae06d375e259ea337f351/drivers/video/msm/mdss/mdss_dsi_host.c).
It is a development diagnostic, not an upstream display-driver fix.

**Current validation:** exact kernel 39 W=1 build/checkpatch, disabled-host guard
and active preflight pass. The corrected published helper ran a 120-second
fixed-color test and restored generator control/color to 0 afterward; DCS power
and pixel-format reads still return 1c/77. Hardware register snapshots confirm
clock-pre extension remains 0. No owner visual response has arrived, so no
physical pattern/display pass is claimed. DSI error-worker flags 5/4 became more
frequent during generation. Active unload before timeout remains untested.

The module requires `lg,madai`, a registered Fx0 DSI panel, the expected host
resource at 0xfd922800 and host version 0x10000002. It refuses to wake an inactive
host, requires the controller and video-mode enable bits, and refuses an
already enabled pattern generator. It pins the host's module and holds its
runtime-PM reference. The default `apply=0` only reads registers after those
guards. With `apply=1`, it enables a solid-color video pattern; delayed work
checks the timeout/video state every 20 ms. Video mode needs no command trigger;
the physical color mapping remains to be qualified.

The physical offsets include the host's four-byte shift: generator control
0x15c and initial color 0x164. The old stock test routine also writes 0x180,
but the maintained host map identifies that offset as clock-pre extension.
That write was removed before the first active test. These are not addresses to copy to
other SoCs or host generations. The default color is 0xff0000, and the default
interval is 60 seconds; accepted intervals are 1–120 seconds. Delayed work stops
and restores the saved generator control/color registers at the deadline or
when video is disabled. Unload synchronizes with that work and also restores.
Do not unbind drivers, change modes or cycle panel power during a test.

Before using it, preserve any existing touch observation with its completion
status. The earlier pre-DRM test was saved as incomplete, without confirmed
gestures, before the camera-DT RAM boot. Bring
up native video using the documented diagnostic power holds, explicitly unblank
fb0, preserve kernel logs and confirm the active mode and panel replies. Keep
that boot stable and use one pattern operation at a time. This module does not
prepare the panel, set brightness, change PHY/PLL timings, change DCS commands,
or repair native runtime-PM sequencing.

Build against the exact running kernel output with its matching toolchain:

```sh
make -C /private/exact-kernel-output ARCH=arm LLVM=1 \
  M="$PWD/diagnostics/dsi-video-pattern" W=1 modules
```

Sign using a key trusted by the running kernel, transfer to RAM, and verify
device identity, kernel release and artifact hashes. On the verified RAM
system, first run preflight and unload before the active test:

```sh
insmod /tmp/fx0_dsi_tpg.ko
rmmod fx0_dsi_tpg
insmod /tmp/fx0_dsi_tpg.ko apply=1 color=0xff0000 seconds=60
# Record the owner's observation and logs; verify timeout restoration.
rmmod fx0_dsi_tpg
```

Compare the generator against a known newly allocated opaque RGB framebuffer.
Visible generator output with invisible framebuffer output would direct the
next investigation toward the MDP/DMA path. Failure of both would still need
panel, link and clock diagnosis; it would not alone identify a defective part.
Retest ordinary scanout and touch after restoration. Keep the prior reset on
native CRTC shutdown unresolved until isolated evidence explains it.
