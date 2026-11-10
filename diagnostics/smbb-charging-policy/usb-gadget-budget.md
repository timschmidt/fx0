# Fx0 USB gadget input budget

The candidate routes ChipIdea USB gadget current requests to the verified
PM8226 USB input actuator. Apply the actuator, bindings and budget patches
in that order to Linux commit `2457eebe0bb67bcb5eccee7916650629cc4e9bf0`.
[Actuator](usb-input-control.patch) · [Bindings](usb-gadget-budget-bindings.patch) ·
[Budget](usb-gadget-budget.patch)

The Madai USB controller references the same SMBB charger node that provides
its VBUS extcon. The consumer selects the USB power supply on that node and
keeps a managed link to its parent through teardown and system sleep. The
legacy PHY callback still serves configurations that use a legacy PHY.
The new binding covers a controller configured for peripheral mode.

The charger verifies a 100 mA limit before registering its USB supply. The
controller returns to that budget on reset, cable loss, pullup loss or
configuration zero. For a nonzero configuration, it holds the requested
budget until the controller reports a successful EP0 IN status completion.
It caps the request at 500 mA. Cancelled, failed or superseded configuration
transactions leave the conservative limit. USB bus suspend requests zero.
Resume restores the last accepted budget. A sleepable worker applies the
latest request and reports write errors. It drains before system suspend
and replays the current state on resume.

On the opted-in board, both USB limit attributes are read-only in sysfs so
manual writes cannot override the gadget budget. The older property still
reports the programmed selector and the standard property reads the
effective hardware state. When the battery is absent, the charger keeps
USB input available at the verified 100 mA limit and reports the unsuccessful
suspend request. A failed hardware transaction can prevent either limit
or suspend from taking effect.

The ARM `W=1` build covers ChipIdea core, UDC and SMBB with the policy
enabled, plus the Madai DTB. A minimal ARM configuration also builds
ChipIdea with power-supply support disabled. The compiled DTB matches the
standalone replay, with just the charger opt-in and the USB phandle added.
The targeted schemas accept the baseline and candidate DTBs, and reject
host mode and the conflicting manual limit in separate fixtures. The
binding document check retains the original `phy-select` diagnostics.
The compiler's existing SoC DT warnings are identical in both builds.

The extracted ChipIdea suite passes 59 checks under ASan, LeakSanitizer
and UBSan. It covers supplier selection and release, successful and failed
EP0 completion, coalesced disconnect, reset, USB suspend/resume, system
sleep and write errors. The SMBB suite passes 59 checks on the managed
candidate and 48 on the original actuator. All 8,846 policy and legacy
checks pass against the replayed source.

```sh
python3 diagnostics/smbb-charging-policy/check-usb-gadget-budget.py \
  --driver /path/to/linux/drivers/usb/chipidea/udc.c --output /tmp/fx0-usb-budget-check
python3 diagnostics/smbb-charging-policy/check-usb-input.py \
  --driver /path/to/linux/drivers/power/supply/qcom_smbb.c --output /tmp/fx0-usb-input-check
python3 diagnostics/smbb-charging-policy/check-control.py /path/to/linux
```

Physical qualification needs USB current measurement across attach, status
completion, reset, suspend, resume and disconnect. In particular, verify
that PM8226 USB suspend preserves the VBUS-valid extcon event and that a
rapid replug drops the previous selector in time. Charger-only startup,
wall-charger detection and powered-off charging remain open. The patch is
unbooted and the compiled artifacts are kernel objects and a DTB.
[Manifest](../../manifests/smbb-usb-gadget-budget.json) ·
[Evidence](../../evidence/2026-11-10-smbb-usb-gadget-budget.json)
