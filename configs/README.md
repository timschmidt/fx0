# Diagnostic kernel configurations

These generated configurations derive from the Nura shared MSM8226 kernel
configuration and the Linux 6.18.59 Kconfig tree. They retain the upstream
Linux configuration licensing (GPL-2.0-only); the coordination repository's
MIT license does not relicense upstream kernel material.

The first configuration records the completed initial kernel/module build.
The `simplefb` configuration additionally enables built-in simpledrm for
an inherited framebuffer console. Hardware support still depends on the
exact device tree, kernel source revision, firmware and physical validation.
