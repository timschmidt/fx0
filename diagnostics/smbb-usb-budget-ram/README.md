# Fx0 USB budget RAM comparison

The control and managed images use the same moduleless kernel, initramfs
and boot command line. The managed DTB adds the PM8226 charger opt-in and
the controller's reference to that charger. Both DTBs keep the software
charge-inhibit flag and omit the charge-policy child, so the comparison
isolates USB input from battery charging. The initramfs also checks the
inhibit state and the raw charge-control register before binding a gadget.
[USB budget patches](../smbb-charging-policy/usb-gadget-budget.md)

The first phase samples the PM8226 with the USB gadget unbound. The initramfs
then binds an NCM gadget with a 500 mA descriptor for 55 seconds, unbinds it
for eight seconds, and rebinds with a 300 mA descriptor for 55 seconds. An
independent 180-second timer returns to installed lk2nd. Only virtual
filesystems are mounted. Available MMC block devices are set read-only.
The image contains no kernel modules.

The sample includes USB state, gadget binding, effective current limit,
configured selector, USB suspend, OTG state, battery presence and charger
enable. The ARM helper opens the charger map read-only and verifies the USB
peripheral identity before reading six more fixed rows. The host can read
`/status.txt` and `/trace.txt` over NCM at `172.16.42.1`. The same changes go
to the kernel console for retrieval from ramoops after disconnect or suspend.

Verify the prepared images and interpret their traces with the corresponding
mode. An optional `--require-suspend` on the managed trace also requires
a suspended UDC, a verified zero input limit with VBUS-valid still asserted,
and a subsequent return to 500 mA in the same 500 mA phase.

```sh
python3 diagnostics/smbb-usb-budget-ram/verify-images.py local/smbb-usb-budget-ram-01/images
python3 diagnostics/smbb-usb-budget-ram/check-trace.py /path/to/control-trace.txt --mode control
python3 diagnostics/smbb-usb-budget-ram/check-trace.py /path/to/managed-trace.txt --mode managed --require-suspend
```

For physical comparison, keep the same battery, host port, cable and
measurement setup across both runs. Record the host USB events and measured
VBUS current on the same timeline as the diagnostic trace. Let the host
suspend and resume the diagnostic USB device during the 500 mA phase.
Programmed limits establish the control state. Current measurement is
needed for compliance, especially before enumeration and during suspend.
Rapid physical replug, wall chargers, charger-only startup and system sleep
require separate observations.

The images are prepared for RAM boot. The published evidence covers the
kernel build, image layout, exact decompression and synthetic fixtures.
[Image manifest](../../manifests/smbb-usb-budget-ram.json) ·
[Evidence](../../evidence/2026-11-10-smbb-usb-budget-ram.json)
